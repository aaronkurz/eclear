import type { NumericProfile } from "./types";

/** Bin edges and per-bin counts, derived from the quantile sketch.
 *
 *  The pane re-derives both on every keystroke, so neither may cost a round trip
 *  to Python. Everything here is therefore an *estimate* off a fixed-size
 *  sketch: exact for quantile and equal-width edges, accurate to about a percent
 *  for the counts. The preview and the applied column are computed in Python and
 *  are exact — which is what the pane's counts are labelled against.
 */

export function equalEdges(profile: NumericProfile, bins: number): number[] {
    const out: number[] = [];
    for (let index = 1; index < bins; index += 1) {
        out.push(profile.min + ((profile.max - profile.min) * index) / bins);
    }
    return refine(out, profile);
}

export function quantileEdges(profile: NumericProfile, bins: number): number[] {
    const out: number[] = [];
    for (let index = 1; index < bins; index += 1) {
        out.push(quantile(profile, index / bins));
    }
    return refine(out, profile);
}

/** Round a derived method's edges, then drop the ones that would not cut.
 *
 *  Two things collapse edges that arrived distinct. A column with a repeated
 *  value has repeated *quantiles* — half the road-traffic log's numeric columns
 *  are 0 more than half the time, so four quantile bins ask for edges at
 *  `[0, 0, 0]` — and `round1` collapses any two edges that round together, which
 *  a narrow-range column does whatever its distribution.
 *
 *  Both are dropped here rather than surfaced as bins, because a repeated edge
 *  is not a bin: `(0, 0]` holds nothing, Python rejects the spec outright
 *  (`bin edges must be distinct`), and rendering one puts a row in the table
 *  that no value can ever land in.
 *
 *  An edge outside `[min, max)` goes for the same reason. The outer edges are
 *  unbounded, so an edge at or above the maximum leaves an empty bin above it,
 *  and one below the minimum an empty bin below. A column whose values are all
 *  equal therefore yields no edges at all — there is genuinely nothing to cut,
 *  which the pane says rather than offering a cut that does nothing.
 *
 *  Custom edges do not come through here: those are the user's own, and an edge
 *  deliberately placed past the data is a choice the counts already show.
 */
function refine(edges: number[], profile: NumericProfile): number[] {
    return distinct(edges.map(round1)).filter(
        (edge) => edge >= profile.min && edge < profile.max,
    );
}

/** The values of `edges`, in order, without repeats. */
export function distinct(edges: number[]): number[] {
    return edges.filter((edge, index) => edges.indexOf(edge) === index);
}

/** The value at fraction `q` of the sketch, linearly interpolated between the
 *  two nearest sketch points. */
export function quantile(profile: NumericProfile, q: number): number {
    const points = profile.quantiles;
    if (!points.length) return profile.min;
    const position = Math.min(Math.max(q, 0), 1) * (points.length - 1);
    const low = Math.floor(position);
    const high = Math.min(low + 1, points.length - 1);
    const weight = position - low;
    return points[low] * (1 - weight) + points[high] * weight;
}

/** The fraction of values at or below `value`: the inverse of `quantile`.
 *
 *  The bound is `< points[0]`, not `<= points[0]`. A column whose minimum
 *  *repeats* — half this log's numeric columns are 0 most of the time — has a
 *  run of equal points at the bottom of its sketch, and an edge sitting on that
 *  minimum is at or above every one of them. Short-circuiting on equality
 *  reported none of those events as below the edge, which showed up as a first
 *  bin holding 0 of 1,505 events. The search below walks the run to its end and
 *  gets it right.
 */
export function fractionBelow(profile: NumericProfile, value: number): number {
    const points = profile.quantiles;
    if (!points.length) return 0;
    if (value < points[0]) return 0;
    if (value >= points[points.length - 1]) return 1;
    let low = 0;
    let high = points.length - 1;
    while (high - low > 1) {
        const middle = (low + high) >> 1;
        if (points[middle] <= value) low = middle;
        else high = middle;
    }
    const span = points[high] - points[low];
    const within = span === 0 ? 0 : (value - points[low]) / span;
    return (low + within) / (points.length - 1);
}

/** Estimated event count per interval, outer edges unbounded. */
export function binCounts(profile: NumericProfile, edges: number[]): number[] {
    const bounds = [0, ...edges.map((edge) => fractionBelow(profile, edge)), 1];
    const counts: number[] = [];
    for (let index = 0; index < bounds.length - 1; index += 1) {
        counts.push(Math.round(profile.count * Math.max(bounds[index + 1] - bounds[index], 0)));
    }
    return counts;
}

/** `(−∞, 4]`, `(4, 10]`, `(10, +∞)` — the intervals the edges describe. */
export function intervalLabels(edges: number[]): string[] {
    const out: string[] = [];
    for (let index = 0; index <= edges.length; index += 1) {
        const low = index === 0 ? "−∞" : String(edges[index - 1]);
        const high = index === edges.length ? "+∞" : String(edges[index]);
        out.push(`(${low}, ${high}${index === edges.length ? ")" : "]"}`);
    }
    return out;
}

/** Insert an edge, keeping edges sorted and labels aligned to their interval. */
export function addEdge(
    edges: number[],
    labels: string[],
    value: number,
): { edges: number[]; labels: string[] } {
    if (Number.isNaN(value) || edges.includes(value)) return { edges, labels };
    const next = [...edges, value].sort((a, b) => a - b);
    const at = next.indexOf(value);
    const nextLabels = [...labels];
    nextLabels.splice(at + 1, 0, "");
    return { edges: next, labels: nextLabels };
}

export function removeEdge(
    edges: number[],
    labels: string[],
    at: number,
): { edges: number[]; labels: string[] } {
    return {
        edges: edges.filter((_, index) => index !== at),
        labels: labels.filter((_, index) => index !== at + 1),
    };
}

/** Fill in `bin_n` for any interval the user has not named. */
export function resolveLabels(labels: string[], edgeCount: number): string[] {
    const out: string[] = [];
    for (let index = 0; index <= edgeCount; index += 1) {
        out.push(labels[index] && labels[index].trim() ? labels[index] : `bin_${index + 1}`);
    }
    return out;
}

function round1(value: number): number {
    return Math.round(value * 10) / 10;
}
