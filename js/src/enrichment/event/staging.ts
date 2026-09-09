import { distinct, equalEdges, quantileEdges, resolveLabels } from "./bins";
import type { EventCatalog, EventKind, EventSpec, EventType, TimePart } from "./types";

/** Columns staged to be added (as full specs) and applied columns staged to go.
 *  Same shape and same four states as the case tab's `Staging`, keyed by column
 *  name, so a colour means the same thing on both tabs. */
export interface EventStaging {
    add: EventSpec[];
    remove: string[];
}

export const EMPTY_EVENT_STAGING: EventStaging = { add: [], remove: [] };

export type EventColState = "applied" | "removing" | "staged" | "off";

export function eventCellState(
    column: string,
    applied: EventSpec[],
    staging: EventStaging,
): EventColState {
    if (applied.some((spec) => spec.column === column)) {
        return staging.remove.includes(column) ? "removing" : "applied";
    }
    return staging.add.some((spec) => spec.column === column) ? "staged" : "off";
}

export function stageEvent(staging: EventStaging, spec: EventSpec): EventStaging {
    if (staging.add.some((entry) => entry.column === spec.column)) return staging;
    return { ...staging, add: [...staging.add, spec] };
}

export function unstageEvent(staging: EventStaging, column: string): EventStaging {
    const add = staging.add.filter((spec) => spec.column !== column);
    return add.length === staging.add.length ? staging : { ...staging, add };
}

export function toggleEventRemove(staging: EventStaging, column: string): EventStaging {
    const remove = staging.remove.includes(column)
        ? staging.remove.filter((name) => name !== column)
        : [...staging.remove, column];
    return { ...staging, remove };
}

export interface EventCounts {
    applied: number;
    staged: number;
    removing: number;
    live: number;
    dirty: boolean;
}

export function eventCountsFor(
    baseColumnCount: number,
    applied: EventSpec[],
    staging: EventStaging,
): EventCounts {
    const appliedColumns = new Set(applied.map((spec) => spec.column));
    const removing = staging.remove.filter((column) => appliedColumns.has(column)).length;
    return {
        applied: applied.length,
        staged: staging.add.length,
        removing,
        live: baseColumnCount + applied.length + staging.add.length - removing,
        dirty: staging.add.length + removing > 0,
    };
}

export function eventCountsByKind(
    applied: EventSpec[],
    staging: EventStaging,
): Record<string, { applied: number; staged: number; removing: number }> {
    const tally: Record<string, { applied: number; staged: number; removing: number }> = {};
    const bucket = (kind: string) => {
        if (!tally[kind]) tally[kind] = { applied: 0, staged: 0, removing: 0 };
        return tally[kind];
    };
    const removing = new Set(staging.remove);
    for (const spec of applied) {
        const entry = bucket(spec.kind);
        if (removing.has(spec.column)) entry.removing += 1;
        else entry.applied += 1;
    }
    for (const spec of staging.add) bucket(spec.kind).staged += 1;
    return tally;
}

// ---------- the builder's draft configuration ----------

export interface ArithmeticDraft {
    type: string;
    left: string;
    op: string;
    /** `null` means the right operand is the constant below. */
    right: string | null;
    constant: string;
}

export interface DeltaDraft {
    type: string;
    direction: "prev" | "next";
    neighbour: "any" | "same" | "type";
    neighbourType: string;
    unit: string;
    missing: "NaT" | "zero";
}

export interface RunningAggDraft {
    source: string;
    aggregate: string;
    carry: string;
}

/** Both binning modes in one draft, so flipping the switch and coming back does
 *  not lose the edges the user typed. Only the active mode's fields are sent. */
export interface BinningDraft {
    mode: "numeric" | "time";
    type: string;
    source: string;
    method: "equal" | "quantile" | "custom";
    bins: string;
    edges: number[];
    labels: string[];
    draft: string;
    timeSource: string;
    part: TimePart;
}

export interface Drafts {
    binning: BinningDraft;
    arithmetic: ArithmeticDraft;
    delta: DeltaDraft;
    running_agg: RunningAggDraft;
    /** Per category: the name the user typed, or `""` while the suggestion stands. */
    names: Record<EventKind, string>;
}

const EMPTY_NAMES: Record<EventKind, string> = {
    binning: "",
    arithmetic: "",
    delta: "",
    running_agg: "",
};

/** Aggregates for which "0 between occurrences" says nothing: forward fill *is*
 *  carrying, and a 0 written between minima would read as a new low. */
export const CARRYLESS_AGGREGATES = new Set(["runmin", "ffill"]);

/** Numeric attributes an event type carries, including the columns already
 *  applied or staged on it. A binning column is categorical and never offered. */
export function numericAttrsOf(
    type: string,
    catalog: EventCatalog,
    columns: EventSpec[],
): string[] {
    const entry = catalog.eventTypes.find((candidate) => candidate.name === type);
    const base = (entry?.attributes ?? [])
        .filter((attr) => attr.kind === "num")
        .map((attr) => attr.name);
    const derived = columns
        .filter(
            (spec) =>
                spec.kind !== "binning" &&
                (spec.eventType === type || spec.eventType === null),
        )
        .map((spec) => spec.column);
    return dedupe([...base, ...derived]);
}

/** Every numeric column in the log — what a running aggregation may run on,
 *  since it is written on every event rather than one type's. */
export function logNumericColumns(catalog: EventCatalog, columns: EventSpec[]): string[] {
    const names: string[] = [];
    for (const type of catalog.eventTypes) {
        for (const attr of type.attributes) if (attr.kind === "num") names.push(attr.name);
    }
    for (const spec of columns) if (spec.kind !== "binning") names.push(spec.column);
    return dedupe(names);
}

/** Timestamp columns an event type carries. The log's own timestamp comes first
 *  and is present on every type, so this is never empty. */
export function timeColumnsOf(catalog: EventCatalog, type: string): string[] {
    return catalog.timeColumns[type] ?? [];
}

export function profileOf(
    catalog: EventCatalog,
    type: string | null,
    column: string,
) {
    const key = type ?? catalog.allEvents;
    return catalog.numericProfiles[key]?.[column] ?? catalog.numericProfiles[catalog.allEvents]?.[column];
}

export function initialDrafts(catalog: EventCatalog): Drafts {
    const first: EventType | undefined = catalog.eventTypes[0];
    const type = first?.name ?? "";
    const numeric = numericAttrsOf(type, catalog, []);
    const logNumeric = logNumericColumns(catalog, []);
    const binType =
        catalog.eventTypes.find((entry) => numericAttrsOf(entry.name, catalog, []).length)?.name ??
        type;

    return {
        binning: {
            // Numeric unless the log offers nothing to cut: a log of pure
            // categoricals still has timestamps, and opening on a mode with an
            // empty picker looks like a broken pane.
            mode: numericAttrsOf(binType, catalog, []).length ? "numeric" : "time",
            type: binType,
            source: numericAttrsOf(binType, catalog, [])[0] ?? "",
            method: "quantile",
            bins: "4",
            edges: [],
            labels: [],
            draft: "",
            timeSource: timeColumnsOf(catalog, binType)[0] ?? "",
            part: "hour",
        },
        arithmetic: {
            type,
            left: numeric[0] ?? "",
            op: "/",
            right: numeric[1] ?? null,
            constant: "1",
        },
        delta: {
            type,
            direction: "prev",
            neighbour: "any",
            neighbourType: catalog.eventTypes[0]?.name ?? "",
            unit: "hours",
            missing: "NaT",
        },
        running_agg: { source: logNumeric[0] ?? "", aggregate: "cumsum", carry: "carry" },
        names: { ...EMPTY_NAMES },
    };
}

/** The params a category's draft sends to Python.
 *
 *  Keys are snake_case because Python reads `spec.params` as given — this object
 *  is the wire format, not a view model. */
export function draftParams(kind: EventKind, drafts: Drafts, edges: number[]): Record<string, unknown> {
    if (kind === "arithmetic") {
        const draft = drafts.arithmetic;
        return {
            left: draft.left,
            op: draft.op,
            right: draft.right,
            constant: draft.right === null ? Number(draft.constant) : null,
        };
    }
    if (kind === "delta") {
        const draft = drafts.delta;
        return {
            direction: draft.direction,
            neighbour: draft.neighbour,
            neighbour_type: draft.neighbour === "type" ? draft.neighbourType : null,
            unit: draft.unit,
            missing: draft.missing,
        };
    }
    if (kind === "running_agg") {
        const draft = drafts.running_agg;
        const carry = CARRYLESS_AGGREGATES.has(draft.aggregate) ? "carry" : draft.carry;
        return { source: draft.source, aggregate: draft.aggregate, carry };
    }
    const draft = drafts.binning;
    if (draft.mode === "time") {
        return { mode: "time", source: draft.timeSource, part: draft.part };
    }
    return {
        mode: "numeric",
        source: draft.source,
        edges,
        labels: resolveLabels(draft.labels, edges.length),
        method: draft.method,
    };
}

export function draftEventType(kind: EventKind, drafts: Drafts, allEvents: string): string {
    if (kind === "running_agg") return allEvents;
    if (kind === "arithmetic") return drafts.arithmetic.type;
    if (kind === "delta") return drafts.delta.type;
    return drafts.binning.type;
}

export function buildEventSpec(
    kind: EventKind,
    drafts: Drafts,
    edges: number[],
    column: string,
    allEvents: string,
): EventSpec {
    const eventType = draftEventType(kind, drafts, allEvents);
    return {
        kind,
        column,
        eventType: eventType === allEvents ? null : eventType,
        params: draftParams(kind, drafts, edges),
    };
}

function dedupe(names: string[]): string[] {
    const seen = new Set<string>();
    const out: string[] = [];
    for (const name of names) {
        if (!name || seen.has(name)) continue;
        seen.add(name);
        out.push(name);
    }
    return out;
}

/** The bin count a derived method will use: what the user typed, clamped to the
 *  range the pane offers. Shared with the pane so the header can say how many
 *  bins were *asked* for when the column cannot support that many. */
export function requestedBins(bins: string): number {
    return Math.max(2, Math.min(10, parseInt(bins, 10) || 4));
}

/** The edges the bins draft currently describes: its own list in custom mode,
 *  otherwise the ones its method derives from the column's sketch.
 *
 *  A derived method may return fewer edges than the bin count asks for — see
 *  `refine` in `bins.ts`. The pane says so rather than the shortfall arriving
 *  as a silently coarser column. */
export function effectiveBinEdges(drafts: Drafts, catalog: EventCatalog): number[] {
    const draft = drafts.binning;
    if (draft.mode === "time") return [];
    if (draft.method === "custom") return [...draft.edges].sort((a, b) => a - b);
    const profile = profileOf(catalog, draft.type, draft.source);
    if (!profile) return [];
    const bins = requestedBins(draft.bins);
    return draft.method === "quantile" ? quantileEdges(profile, bins) : equalEdges(profile, bins);
}

/** Why this draft cannot be staged, or `""`.
 *
 *  Pure, and here rather than in the pane, so it can be checked against Python's
 *  `validate_event_spec` from a test without rendering anything — see
 *  `eclear/contracts/rejections.json`.
 *
 *  The same conditions Python's `validate_event_spec` checks, applied one step
 *  earlier so the button explains itself instead of the apply failing. Python
 *  stays the backstop — a disagreement between the two means the frontend and
 *  the log disagree about the log, which is worth an error rather than a column.
 */
export function stageBlocker(
    kind: EventKind,
    drafts: Drafts,
    edges: number[],
    name: string,
    taken: Set<string>,
): string {
    if (!name) return "the column needs a name";
    if (taken.has(name)) return `${name} already exists on the event log`;
    if (kind === "arithmetic") {
        const draft = drafts.arithmetic;
        if (!draft.left) return "no numeric attribute on this event type";
        if (draft.right === null && Number.isNaN(parseFloat(draft.constant))) {
            return "the constant is not a number";
        }
    }
    if (kind === "running_agg" && !drafts.running_agg.source) {
        return "no numeric column in this log";
    }
    if (kind === "binning") {
        const draft = drafts.binning;
        if (draft.mode === "time") {
            if (!draft.timeSource) return "no timestamp column on this event type";
        } else {
            if (!draft.source) return "no numeric attribute on this event type";
            if (!edges.length) return "bins need at least one edge";
            // Both mirror `_validate_binning`. Distinct edges are guaranteed for
            // the derived methods but not for custom ones, and the labels are
            // the user's to collide however they like.
            if (distinct(edges).length !== edges.length) return "bin edges must be distinct";
            const labels = resolveLabels(draft.labels, edges.length);
            if (new Set(labels).size !== labels.length) return "bin labels must be distinct";
        }
    }
    return "";
}
