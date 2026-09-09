import { describe, expect, it } from "vitest";
import { dtypeOf, formulaTextOf, summaryOf, warningOf } from "./describe";
import type { EventSpec } from "./types";

function spec(kind: EventSpec["kind"], params: Record<string, unknown>): EventSpec {
    return { kind, column: "c", eventType: "Treat", params };
}

describe("summaryOf", () => {
    it("reads arithmetic off the spec, not the column name", () => {
        expect(summaryOf(spec("arithmetic", { left: "dose", op: "/", right: "reading" })))
            .toBe("dose ÷ reading");
    });

    it("shows the constant when there is no right operand", () => {
        expect(summaryOf(spec("arithmetic", { left: "dose", op: "*", right: null, constant: 2 })))
            .toBe("dose × 2");
    });

    it("renders a typographic operator the spec arrived with", () => {
        // A spec written by hand in a notebook may use `÷` directly.
        expect(summaryOf(spec("arithmetic", { left: "a", op: "÷", right: "b" })))
            .toBe("a ÷ b");
    });

    it("names the neighbour a delta measures against", () => {
        expect(summaryOf(spec("delta", { direction: "prev", neighbour: "any" })))
            .toBe("since previous any event");
        expect(summaryOf(spec("delta", { direction: "next", neighbour: "same" })))
            .toBe("until next same type");
        expect(summaryOf(spec("delta", { direction: "prev", neighbour: "type", neighbour_type: "Check" })))
            .toBe("since previous Check");
    });

    it("says what a running aggregation accumulates", () => {
        expect(summaryOf(spec("running_agg", { aggregate: "cumsum", source: "dose" })))
            .toBe("cumulative sum of dose per case");
        expect(summaryOf(spec("running_agg", { aggregate: "ffill", source: "dose" })))
            .toBe("last value seen of dose per case");
    });

    it("counts the bins a numeric binning produces", () => {
        expect(summaryOf(spec("binning", { source: "dose", labels: ["a", "b", "c"] })))
            .toBe("dose → 3 bins");
    });

    it("names the part a time binning cuts", () => {
        expect(summaryOf(spec("binning", { mode: "time", source: "time:timestamp", part: "weekday" })))
            .toContain("time:timestamp →");
    });
});

describe("dtypeOf", () => {
    it("calls a binning categorical, whichever mode it is", () => {
        expect(dtypeOf("binning", { mode: "numeric" })).toBe("category");
        expect(dtypeOf("binning", { mode: "time" })).toBe("category");
    });

    it("keeps the pandas dtype for a timedelta delta and floats otherwise", () => {
        expect(dtypeOf("delta", { unit: "timedelta" })).toBe("timedelta64");
        expect(dtypeOf("delta", { unit: "hours" })).toBe("float64");
        expect(dtypeOf("arithmetic", {})).toBe("float64");
        expect(dtypeOf("running_agg", {})).toBe("float64");
    });
});

describe("formulaTextOf", () => {
    it("writes the arithmetic out with the operator the widget renders", () => {
        expect(formulaTextOf("arithmetic", { left: "dose", op: "/", right: "reading" }))
            .toBe("dose ÷ reading → ");
    });

    it("normalizes a typographic operator rather than echoing it twice", () => {
        expect(formulaTextOf("arithmetic", { left: "a", op: "×", right: "b" }))
            .toBe("a × b → ");
    });

    it("puts the subtraction the right way round for each direction", () => {
        expect(formulaTextOf("delta", { direction: "prev", neighbour: "any" }))
            .toBe("timestamp − previous event.timestamp → ");
        expect(formulaTextOf("delta", { direction: "next", neighbour: "any" }))
            .toBe("next event.timestamp − timestamp → ");
    });

    it("names the pandas call a running aggregation maps to", () => {
        expect(formulaTextOf("running_agg", { aggregate: "runmax", source: "dose" }))
            .toBe("cummax(dose) per case → ");
    });

    it("lists the edges a numeric binning cuts at", () => {
        expect(formulaTextOf("binning", { source: "dose", edges: [2, 4] }))
            .toBe("dose cut at [2, 4] → ");
    });
});

describe("warningOf", () => {
    it("warns that dividing can produce NaN, naming the divisor", () => {
        const warning = warningOf("arithmetic", { op: "/", right: "reading" });
        expect(warning?.title).toBe("Division by zero");
        expect(warning?.text).toContain("reading");
    });

    it("names the constant when there is no right operand", () => {
        expect(warningOf("arithmetic", { op: "/", right: null })?.text).toContain("the constant");
    });

    it("says nothing about the other three operators", () => {
        for (const op of ["+", "-", "*"]) {
            expect(warningOf("arithmetic", { op })).toBeNull();
        }
    });

    it("warns that a zero gap is indistinguishable from a real one", () => {
        const warning = warningOf("delta", { missing: "zero", direction: "prev" });
        expect(warning?.title).toBe("Zero instead of NaT");
        expect(warning?.text).toContain("earlier");
        expect(warningOf("delta", { missing: "zero", direction: "next" })?.text)
            .toContain("later");
    });

    it("says nothing when a delta leaves the gap missing", () => {
        expect(warningOf("delta", { missing: "NaT" })).toBeNull();
    });

    it("warns that the carryless aggregations start missing rather than at zero", () => {
        for (const aggregate of ["runmin", "ffill"]) {
            const warning = warningOf("running_agg", { aggregate, source: "dose" });
            expect(warning?.title).toBe("Missing before the first value");
            expect(warning?.text).toContain("dose");
        }
    });

    it("says nothing for the aggregations that legitimately start at zero", () => {
        for (const aggregate of ["cumsum", "count", "runmax"]) {
            expect(warningOf("running_agg", { aggregate })).toBeNull();
        }
    });

    it("has nothing to say about a binning", () => {
        expect(warningOf("binning", { mode: "numeric" })).toBeNull();
    });
});
