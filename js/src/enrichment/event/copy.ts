import type { EventKind, TimePart } from "./types";

/** Short tag per category, so the rail reads at a glance. Matches the case tab's
 *  `KIND_TAG` in intent and in width.
 *
 *  Some are pictures, some are abbreviations, because some of these categories
 *  have a shape and some do not: bins are three blocks and a running value moves
 *  along the case, but there is no picture of "one attribute divided by another"
 *  that beats writing it down. */
export const EVENT_KIND_TAG: Record<EventKind, string> = {
    binning: "▮▮▮",
    arithmetic: "a+b",
    delta: "Δt",
    running_agg: "→",
};

/** Which tags are drawn as a glyph rather than a mono abbreviation. Glyph fonts
 *  are not monospaced and 9.5px turns an arrow into a smudge, so those tags take
 *  `.en-glyph` — same box height, larger and proportional type. */
const GLYPH_KINDS = new Set<EventKind>(["binning", "running_agg"]);

export function isGlyphEventKind(kind: EventKind): boolean {
    return GLYPH_KINDS.has(kind);
}

export function eventKindTagClass(kind: EventKind): string {
    return `en-kindtag en-ev-kind-${kind}${GLYPH_KINDS.has(kind) ? " en-glyph" : ""}`;
}

/** One clause under the rail's section heading: what the section has in common. */
export const EVENT_GROUP_HINTS: Record<string, string> = {
    local: "Computed from the event's own attributes.",
    contextual: "Computed from where the event sits in its case.",
};

/** One clause under the pane title: what this category gives you. */
export const EVENT_KIND_HINTS: Record<EventKind, string> = {
    binning: "Cut a number into intervals, or a timestamp into its parts.",
    arithmetic: "Arithmetic on two numeric attributes of one event.",
    delta: "Gap to a neighbouring event in the same case.",
    running_agg: "A value aggregated along each case as it goes.",
};

/** The info tip's "what it computes" section. */
export const EVENT_KIND_NOTES: Record<EventKind, string> = {
    binning:
        "Numeric cuts a column into labelled intervals with unbounded outer edges, so no value " +
        "falls outside a bin and a missing input stays missing. A single edge gives a two-way " +
        "column — the threshold flag, without a category of its own. Time cuts a timestamp into " +
        "one of its natural parts instead: the year, the month of the year, the day of the week " +
        "or the hour of the day.",
    arithmetic:
        "Arithmetic on two numeric attributes of the same event, or one attribute and a " +
        "constant. Only events of the chosen type get a value; every other row stays missing. " +
        "Dividing by zero yields NaN rather than an infinity.",
    delta:
        "The gap between an event and its neighbour in the same case, read in timestamp order. " +
        "Since previous and until next differ only in which neighbour is read, so direction is a " +
        "control here rather than two separate categories.",
    running_agg:
        "One numeric column aggregated along each case, written at every event position. " +
        "Cumulative sum, count and running max start a case at 0: how much has accumulated so " +
        "far answers none before the first value. Running min and forward fill stay missing " +
        "until the first value — the smallest value so far and the last value seen have no " +
        "answer before there is one, and 0 would invent both.",
};

/** The info tip's "how to use it" section. */
export const EVENT_KIND_USAGE: Record<EventKind, string> = {
    binning:
        "Numeric: equal width and quantile derive the edges from the column, custom edges are " +
        "added one number at a time, and event counts are estimated from a sketch — the preview " +
        "is exact. Time: pick a timestamp column and a part; there is nothing else to configure, " +
        "and every category exists whether or not this log contains it.",
    arithmetic:
        "Non-numeric attributes are not offered in either operand picker, so a type mismatch " +
        "cannot be configured. Pick constant… as the right operand to divide or scale by a number.",
    delta:
        "Choose which neighbour counts: any event, the next of the same type, or a type you pick. " +
        "NaT keeps events with no neighbour apart from a genuine zero gap; 0 does not.",
    running_agg:
        "Carry writes the running value onto every event of the case; 0 between writes it only on " +
        "events that hold a value, and is offered only where it says something — forward fill is " +
        "carrying, and a 0 between minima would read as a new low. The column is written on every " +
        "event type either way.",
};

/** What each timestamp part is called in the pane, and in a column name. */
export const TIME_PART_LABELS: Record<TimePart, string> = {
    year: "year",
    month: "month of year",
    weekday: "day of week",
    hour: "hour of day",
};

/** An example value, so the picker says what the column will hold. */
export const TIME_PART_EXAMPLES: Record<TimePart, string> = {
    year: "2016, 2017, …",
    month: "1 … 12",
    weekday: "Mon … Sun",
    hour: "0 … 23",
};

export const OP_LABELS: Record<string, string> = {
    "+": "+",
    "-": "−",
    "*": "×",
    "/": "÷",
};
