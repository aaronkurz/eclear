import type { Kind } from "./types";

/** One short line under the pane title: what this enrichment gives you. Kept to
 *  a single clause — the full story is one hover away in the pane's info tip. */
export const KIND_HINTS: Record<Kind, string> = {
    base: "The columns every case log starts with.",
    counts: "How many times each activity occurs in a case.",
    times: "When an activity first and last occurs, relative to the case start.",
    delays: "Time between the first occurrences of two activities.",
    tracking: "Carry an event attribute forward through a case with an aggregation.",
};

/** The info tip's "what it computes" section. Written out because the difference
 *  between "first occurrence" and "earliest timestamp", or between a null and a
 *  zero, is what makes a column readable. */
export const KIND_NOTES: Record<Kind, string> = {
    base:
        "start_time and end_time are the earliest and latest event of the case; duration is " +
        "their difference and no_of_events the number of events. Relative event times " +
        "(rel_time, rel_log_time) are added to the event log in the same step.",
    counts:
        "Occurrences per case, one column per activity, named Activity::count. A case in which " +
        "the activity never occurs counts 0, not missing.",
    times:
        "::start takes the first occurrence per case, ::end the last. Both are measured on " +
        "rel_time, so 0 is the start of the case, and the value is NaT where the activity never " +
        "occurs. For an activity that happens once, the two are equal.",
    delays:
        "The first occurrence of the second activity minus the first occurrence of the first, so " +
        "a negative value means the second happened first, and NaT means one of them is missing " +
        "from the case.",
    tracking:
        "Each case's events are folded in timestamp order, skipping nulls: append keeps the whole " +
        "sequence, latest keeps the last non-null value, is_unique says whether the case ever " +
        "changed it. A case with no matching event counts 0, sums 0, appends [] and has no " +
        "latest, minimum, maximum or is_unique. An attribute carried by several activities is " +
        "offered under each of them and over the whole case, because those are different columns.",
};

/** The info tip's "how to use it" section: what clicking in this pane does. */
export const KIND_USAGE: Record<Kind, string> = {
    base: "Nothing to configure — these columns are always present and cannot be removed.",
    counts:
        "Click a row to stage or unstage it. Green rows are already applied; clicking one stages " +
        "a removal.",
    times:
        "Click a cell to stage that column. Both cells are relative to the case start, and ::end " +
        "equals ::start for an activity that occurs only once.",
    delays:
        "Pick two activities and add the pair — it stages right away. Click a chip to unstage it, " +
        "or to stage a removal if it is already applied.",
    tracking:
        "Click a method to stage it. Columns are named Event_type.attribute::method, and greyed " +
        "methods don’t apply to that attribute’s type.",
};

export const METHOD_HINTS: Record<string, string> = {
    latest: "last non-null value in the case",
    count: "how many events carried a value",
    append: "every value, in order",
    is_unique: "true when the case never changed it",
    sum: "sum of the values",
    min: "smallest value",
    max: "largest value",
};

export const STATE_LEGEND: { key: string; label: string }[] = [
    { key: "applied", label: "applied" },
    { key: "staged", label: "staged to add" },
    { key: "removing", label: "staged to remove" },
];
