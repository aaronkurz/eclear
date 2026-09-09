import type { EventKind } from "./types";

/** A column-name-safe rendering of an attribute or value name.
 *
 *  Mirrors `slug` in `eclear/enrichment/event_specs.py`. Unlike the case-log
 *  side, a disagreement here is harmless: the name is a *suggestion* the user
 *  can overwrite, and Python stores whatever comes back rather than re-deriving
 *  it. Kept in step anyway, so a column built by clicking and one built in a
 *  notebook cell end up called the same thing.
 */
export function slug(text: string): string {
    // Unicode-aware, because Python's `str.isalnum()` is: a log with an
    // `Ünïcode` column has to get the same name from both sides. An ASCII-only
    // class here produced `n_code` where Python produced `Ünïcode`.
    return String(text)
        .replace(/[^\p{L}\p{N}]+/gu, "_")
        .replace(/^_+|_+$/g, "");
}

/** The ASCII spelling of an arithmetic operator. Mirrors `normalize_op` in
 *  `event_specs.py`, including its alias table — the widget renders `− × ÷`,
 *  and a spec hand-written in a notebook may well use them. */
export function normalizeOp(op: string): string {
    return OP_ALIASES[String(op)] ?? String(op);
}

const OP_ALIASES: Record<string, string> = {
    "\u2212": "-",
    "\u2013": "-",
    "\u00d7": "*",
    "\u00f7": "/",
};

const OP_WORDS: Record<string, string> = { "+": "plus", "-": "minus", "*": "x", "/": "per" };
const UNIT_SUFFIX: Record<string, string> = {
    min: "_min",
    hours: "_h",
    days: "_d",
    timedelta: "",
};
const AGG_SUFFIX: Record<string, string> = {
    cumsum: "_cum",
    count: "_count_so_far",
    runmax: "_running_max",
    runmin: "_running_min",
    ffill: "_last_seen",
};

export function suggestColumn(kind: EventKind, params: Record<string, unknown>): string {
    const text = (key: string, fallback = "") => String(params[key] ?? fallback);
    if (kind === "arithmetic") {
        const right = params.right as string | null | undefined;
        const tail = right ? slug(right) : slug(text("constant", "const"));
        const word = OP_WORDS[normalizeOp(text("op", "+"))] ?? "op";
        return `${slug(text("left"))}_${word}_${tail}`;
    }
    if (kind === "delta") {
        const head = params.direction === "prev" ? "since_prev" : "until_next";
        const neighbour = params.neighbour;
        const middle =
            neighbour === "same"
                ? "_same"
                : neighbour === "type"
                  ? `_${slug(text("neighbour_type"))}`
                  : "";
        return `${head}${middle}${UNIT_SUFFIX[text("unit")] ?? ""}`;
    }
    if (kind === "running_agg") {
        return `${slug(text("source")).toLowerCase()}${AGG_SUFFIX[text("aggregate")] ?? ""}`;
    }
    const source = slug(text("source"));
    if (params.mode === "time") return `${source}_${slug(text("part"))}`;
    return `${source}_level`;
}

/** The suggestion, made unique against the names already in play. */
export function uniqueName(base: string, taken: Set<string>): string {
    if (!base || !taken.has(base)) return base;
    let index = 2;
    while (taken.has(`${base}_${index}`)) index += 1;
    return `${base}_${index}`;
}
