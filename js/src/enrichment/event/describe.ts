import { OP_LABELS, TIME_PART_LABELS } from "./copy";
import { normalizeOp } from "./naming";
import type { EventKind, EventSpec, TimePart } from "./types";

const AGG_LABELS: Record<string, string> = {
    cumsum: "cumulative sum",
    count: "count",
    runmax: "running max",
    runmin: "running min",
    ffill: "last value seen",
};

const AGG_CALLS: Record<string, string> = {
    cumsum: "cumsum",
    count: "count",
    runmax: "cummax",
    runmin: "cummin",
    ffill: "ffill",
};

function partLabel(part: unknown): string {
    return TIME_PART_LABELS[String(part) as TimePart] ?? String(part ?? "");
}

/** One line saying what a column holds, for the column list and the schema.
 *
 *  Read off the spec rather than the column name: the name is the user's, and a
 *  user-chosen name is exactly the thing that cannot be parsed back. */
export function summaryOf(spec: EventSpec): string {
    const params = spec.params as Record<string, string | number | null | string[]>;
    if (spec.kind === "arithmetic") {
        const right = params.right ?? String(params.constant ?? "");
        return `${params.left} ${OP_LABELS[normalizeOp(String(params.op))] ?? params.op} ${right}`;
    }
    if (spec.kind === "delta") {
        const neighbour =
            params.neighbour === "any"
                ? "any event"
                : params.neighbour === "same"
                  ? "same type"
                  : String(params.neighbour_type ?? "");
        return `${params.direction === "prev" ? "since previous" : "until next"} ${neighbour}`;
    }
    if (spec.kind === "running_agg") {
        const aggregate = AGG_LABELS[String(params.aggregate)] ?? String(params.aggregate);
        return `${aggregate} of ${params.source} per case`;
    }
    if (params.mode === "time") return `${params.source} → ${partLabel(params.part)}`;
    const labels = (params.labels as string[]) ?? [];
    return `${params.source} → ${labels.length} bins`;
}

/** The pandas dtype the column will land as. */
export function dtypeOf(kind: EventKind, params: Record<string, unknown>): string {
    if (kind === "binning") return "category";
    if (kind === "delta" && params.unit === "timedelta") return "timedelta64";
    return "float64";
}

/** The `input → output` line under the builder. */
export function formulaTextOf(kind: EventKind, params: Record<string, unknown>): string {
    const value = (key: string) => String(params[key] ?? "");
    if (kind === "arithmetic") {
        const right = params.right ?? value("constant");
        return `${value("left")} ${OP_LABELS[normalizeOp(value("op"))] ?? value("op")} ${right} → `;
    }
    if (kind === "delta") {
        const neighbour =
            params.neighbour === "any"
                ? "event"
                : params.neighbour === "same"
                  ? "same type"
                  : value("neighbour_type");
        return params.direction === "prev"
            ? `timestamp − previous ${neighbour}.timestamp → `
            : `next ${neighbour}.timestamp − timestamp → `;
    }
    if (kind === "running_agg") {
        const name = AGG_CALLS[value("aggregate")] ?? value("aggregate");
        return `${name}(${value("source")}) per case → `;
    }
    if (params.mode === "time") return `${value("source")}.${value("part")} → `;
    return `${value("source")} cut at [${((params.edges as number[]) ?? []).join(", ")}] → `;
}

/** A caveat worth stating before the column exists, or `null`.
 *
 *  Warnings, never errors: each names something the column will genuinely do,
 *  and in every case the column is still worth having. */
export function warningOf(
    kind: EventKind,
    params: Record<string, unknown>,
): { title: string; text: string } | null {
    if (kind === "arithmetic" && params.op === "/") {
        const divisor = params.right ?? "the constant";
        return {
            title: "Division by zero",
            text: `Events where ${divisor} is 0 get NaN on this column; every other row is unaffected.`,
        };
    }
    if (kind === "delta" && params.missing === "zero") {
        return {
            title: "Zero instead of NaT",
            text: `Events with no ${params.direction === "prev" ? "earlier" : "later"} neighbour get 0, which is indistinguishable from a genuine zero gap.`,
        };
    }
    if (kind === "running_agg" && (params.aggregate === "runmin" || params.aggregate === "ffill")) {
        return {
            title: "Missing before the first value",
            text:
                `Events before the case's first ${params.source} value get NaN rather than 0 — ` +
                `${params.aggregate === "runmin" ? "the smallest value so far" : "the last value seen"} has no answer yet, and 0 would invent one.`,
        };
    }
    return null;
}
