import { describe, expect, it } from "vitest";
import {
    addEdge,
    binCounts,
    distinct,
    fractionBelow,
    equalEdges,
    intervalLabels,
    quantile,
    quantileEdges,
    removeEdge,
    resolveLabels,
} from "./bins";
import type { NumericProfile } from "./types";

/** A sketch of `values`, built the way `_profile` in `catalog.py` builds one:
 *  101 quantile points, linearly interpolated. Tests state the column, not the
 *  sketch, so a case reads as the data that produces it. */
function profileOf(values: number[]): NumericProfile {
    const sorted = [...values].sort((a, b) => a - b);
    const quantiles: number[] = [];
    for (let index = 0; index < 101; index += 1) {
        const position = (index / 100) * (sorted.length - 1);
        const low = Math.floor(position);
        const high = Math.min(low + 1, sorted.length - 1);
        quantiles.push(sorted[low] + (sorted[high] - sorted[low]) * (position - low));
    }
    return {
        min: sorted[0],
        max: sorted[sorted.length - 1],
        count: sorted.length,
        quantiles,
    };
}

function repeat(value: number, times: number): number[] {
    return Array.from({ length: times }, () => value);
}

/** `points` as the road-traffic log carries it: 0 on the overwhelming majority
 *  of events. Four quantile bins ask for edges at [0, 0, 0]. */
const REPEATED = profileOf([...repeat(0, 1400), ...repeat(1, 60), ...repeat(2, 45)]);

/** A column whose whole range rounds to one decimal place. */
const NARROW = profileOf(Array.from({ length: 500 }, (_, i) => 10 + (i / 499) * 0.05));

const CONSTANT = profileOf(repeat(0, 200));

const SPREAD = profileOf(Array.from({ length: 1000 }, (_, i) => i));

function strictlyIncreasing(edges: number[]): boolean {
    return edges.every((edge, index) => index === 0 || edge > edges[index - 1]);
}

describe("distinct", () => {
    it("keeps the first of each value, in order", () => {
        expect(distinct([3, 1, 3, 1, 2])).toEqual([3, 1, 2]);
        expect(distinct([])).toEqual([]);
    });
});

describe("derived edges are always usable", () => {
    // Every case below produced duplicate edges before `refine`, which Python
    // rejects outright ("bin edges must be distinct") and which renders as an
    // interval no value can land in.
    for (const [name, profile] of [
        ["a mostly-repeated column", REPEATED],
        ["a narrow-range column", NARROW],
        ["a well-spread column", SPREAD],
    ] as const) {
        for (const bins of [2, 3, 4, 5, 10]) {
            it(`${name}, ${bins} bins: quantile edges are strictly increasing`, () => {
                expect(strictlyIncreasing(quantileEdges(profile, bins))).toBe(true);
            });
            it(`${name}, ${bins} bins: equal-width edges are strictly increasing`, () => {
                expect(strictlyIncreasing(equalEdges(profile, bins))).toBe(true);
            });
        }
    }

    it("cuts a repeated column where the values actually separate", () => {
        // The regression: this asked for [0, 0, 0] and now asks for one usable
        // edge, which splits the 1400 zeros from the 105 non-zeros.
        expect(quantileEdges(REPEATED, 4)).toEqual([0]);
    });

    it("collapses edges that round together rather than repeating them", () => {
        expect(quantileEdges(NARROW, 4)).toEqual([10]);
        expect(equalEdges(NARROW, 4)).toEqual([10]);
    });

    it("offers no cut at all for a constant column", () => {
        expect(quantileEdges(CONSTANT, 4)).toEqual([]);
        expect(equalEdges(CONSTANT, 4)).toEqual([]);
    });

    it("never places an edge outside the observed range", () => {
        // An edge at or above the maximum leaves the bin above it empty, and one
        // below the minimum the bin below it.
        for (const profile of [REPEATED, NARROW, SPREAD, CONSTANT]) {
            for (const edges of [quantileEdges(profile, 7), equalEdges(profile, 7)]) {
                for (const edge of edges) {
                    expect(edge).toBeGreaterThanOrEqual(profile.min);
                    expect(edge).toBeLessThan(profile.max);
                }
            }
        }
    });

    it("gives at most the requested number of bins, and says so by giving fewer", () => {
        expect(quantileEdges(REPEATED, 10).length).toBeLessThanOrEqual(9);
        expect(quantileEdges(SPREAD, 4)).toHaveLength(3);
    });
});

describe("intervalLabels", () => {
    it("are unique whenever the edges are — what makes them safe to render", () => {
        for (const profile of [REPEATED, NARROW, SPREAD]) {
            for (const bins of [2, 4, 10]) {
                const labels = intervalLabels(quantileEdges(profile, bins));
                expect(new Set(labels).size).toBe(labels.length);
            }
        }
    });

    it("bounds the outer intervals and closes the others", () => {
        expect(intervalLabels([4, 10])).toEqual(["(−∞, 4]", "(4, 10]", "(10, +∞)"]);
    });

    it("describes one unbounded interval when there are no edges", () => {
        expect(intervalLabels([])).toEqual(["(−∞, +∞)"]);
    });
});

describe("fractionBelow", () => {
    it("counts a repeated minimum as being at or below itself", () => {
        // 1400 of 1505 values are 0. An edge at 0 has all of them at or below
        // it; reporting 0 here is what emptied the first bin in the pane.
        expect(fractionBelow(REPEATED, 0)).toBeGreaterThan(0.9);
    });

    it("is 0 strictly below the range and 1 at or above the top", () => {
        expect(fractionBelow(SPREAD, -1)).toBe(0);
        expect(fractionBelow(SPREAD, 999)).toBe(1);
        expect(fractionBelow(SPREAD, 10_000)).toBe(1);
    });

    it("tracks the quantile it inverts", () => {
        for (const q of [0.25, 0.5, 0.75]) {
            expect(fractionBelow(SPREAD, quantile(SPREAD, q))).toBeCloseTo(q, 2);
        }
    });
});

describe("binCounts", () => {
    it("accounts for every event in the profile", () => {
        const edges = quantileEdges(SPREAD, 4);
        const counts = binCounts(SPREAD, edges);
        expect(counts).toHaveLength(edges.length + 1);
        expect(counts.reduce((sum, count) => sum + count, 0)).toBe(SPREAD.count);
    });

    it("puts everything in the single bin when there are no edges", () => {
        expect(binCounts(SPREAD, [])).toEqual([SPREAD.count]);
    });

    it("separates a repeated value from the rest", () => {
        const [low, high] = binCounts(REPEATED, [0]);
        expect(low).toBe(1400);
        expect(high).toBe(105);
    });
});

describe("editing custom edges", () => {
    it("inserts in sorted position and keeps labels with their interval", () => {
        // (−∞, 10] "low" | (10, +∞) "high"  ->  adding 5 splits "low"
        const added = addEdge([10], ["low", "high"], 5);
        expect(added.edges).toEqual([5, 10]);
        expect(added.labels).toEqual(["low", "", "high"]);
    });

    it("appends beyond the last edge without disturbing earlier labels", () => {
        const added = addEdge([5], ["a", "b"], 12);
        expect(added.edges).toEqual([5, 12]);
        expect(added.labels).toEqual(["a", "b", ""]);
    });

    it("refuses a duplicate edge", () => {
        const before = { edges: [5, 10], labels: ["a", "b", "c"] };
        expect(addEdge(before.edges, before.labels, 10)).toEqual(before);
    });

    it("refuses a value that is not a number", () => {
        const before = { edges: [5], labels: ["a", "b"] };
        expect(addEdge(before.edges, before.labels, Number.NaN)).toEqual(before);
    });

    it("removes an edge and the interval label it opened", () => {
        const removed = removeEdge([5, 10], ["a", "b", "c"], 0);
        expect(removed.edges).toEqual([10]);
        expect(removed.labels).toEqual(["a", "c"]);
    });

    it("round-trips: adding then removing an edge restores the labels", () => {
        const edges = [10];
        const labels = ["low", "high"];
        const added = addEdge(edges, labels, 5);
        const back = removeEdge(added.edges, added.labels, added.edges.indexOf(5));
        expect(back.edges).toEqual(edges);
        expect(back.labels).toEqual(labels);
    });
});

describe("resolveLabels", () => {
    it("names every interval, filling only the blanks", () => {
        expect(resolveLabels(["low", "", "  "], 2)).toEqual(["low", "bin_2", "bin_3"]);
    });

    it("produces one label per interval, which is one more than the edges", () => {
        expect(resolveLabels([], 3)).toEqual(["bin_1", "bin_2", "bin_3", "bin_4"]);
        expect(resolveLabels([], 0)).toEqual(["bin_1"]);
    });

    it("defaults are distinct, so a spec is valid until the user collides them", () => {
        const labels = resolveLabels([], 9);
        expect(new Set(labels).size).toBe(labels.length);
    });
});
