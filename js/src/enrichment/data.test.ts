import { describe, expect, it } from "vitest";
import { formatCount, normalizeCatalog, normalizeSpecs, normalizeSummary } from "./data";

describe("normalizeCatalog", () => {
    it("falls back to the full rail when Python sends no kinds", () => {
        const catalog = normalizeCatalog({});
        expect(catalog.kinds.map((k) => k.key)).toEqual([
            "base", "counts", "times", "delays", "tracking",
        ]);
        expect(catalog.kinds.every((k) => k.label.length > 0)).toBe(true);
    });

    it("survives an entirely absent payload", () => {
        const catalog = normalizeCatalog(undefined);
        expect(catalog.activities).toEqual([]);
        expect(catalog.baseColumns).toEqual([]);
        expect(catalog.trackGroups).toEqual([]);
        expect(catalog.allEvents).toBe("*");
    });

    it("drops a kind it does not know", () => {
        const catalog = normalizeCatalog({
            kinds: [{ key: "counts", label: "Activity counts" }, { key: "sorcery", label: "S" }],
        });
        expect(catalog.kinds.map((k) => k.key)).toEqual(["counts"]);
    });

    it("labels a kind Python sent without one", () => {
        expect(normalizeCatalog({ kinds: [{ key: "delays" }] }).kinds)
            .toEqual([{ key: "delays", label: "Activity delays" }]);
    });

    it("defaults an activity's display to its name and its counts to zero", () => {
        expect(normalizeCatalog({ activities: [{ name: "Pay" }] }).activities)
            .toEqual([{ name: "Pay", display: "Pay", events: 0, cases: 0 }]);
    });

    it("keeps the converted display name Python computed", () => {
        // The frontend must never re-derive this: it builds column names from it.
        const [activity] = normalizeCatalog({
            activities: [{ name: "Pay Fine", display: "Pay_Fine", events: 3, cases: 2 }],
        }).activities;
        expect(activity.display).toBe("Pay_Fine");
    });

    it("defaults a tracking attribute's column prefix rather than leaving it blank", () => {
        const [group] = normalizeCatalog({
            track_groups: [{ event_type: "Pay", attributes: [{ attribute: "amount" }] }],
        }).trackGroups;
        expect(group.attributes[0]).toEqual({
            attribute: "amount", numeric: false, events: 0, methods: [],
            columnPrefix: "amount::",
        });
    });

    it("labels a track group after its event type when Python sends no label", () => {
        const [group] = normalizeCatalog({ track_groups: [{ event_type: "Pay" }] }).trackGroups;
        expect(group.display).toBe("Pay");
        expect(group.label).toBe("Pay");
    });
});

describe("normalizeSummary", () => {
    it("reads the header counts", () => {
        expect(normalizeSummary({
            cases: 3, events: 10, activities: 4, case_id_col: "case:concept:name",
        })).toEqual({ cases: 3, events: 10, activities: 4, caseIdCol: "case:concept:name" });
    });

    it("gives zeros and a placeholder id column for an absent payload", () => {
        expect(normalizeSummary(undefined))
            .toEqual({ cases: 0, events: 0, activities: 0, caseIdCol: "case" });
    });
});

describe("normalizeSpecs", () => {
    it("reads the applied list Python reports", () => {
        expect(normalizeSpecs([{
            kind: "delays", method: "delay", activity: "Pay", activity_to: "Close",
            attribute: null, column: "Pay:Close::delay",
        }])).toEqual([{
            kind: "delays", method: "delay", activity: "Pay", activityTo: "Close",
            attribute: null, column: "Pay:Close::delay",
        }]);
    });

    it("drops a spec with an unknown kind or no column", () => {
        expect(normalizeSpecs([
            { kind: "sorcery", column: "x" },
            { kind: "counts", column: "" },
            { kind: "counts", column: "Pay::count" },
        ])).toHaveLength(1);
    });

    it("reads absent optional fields as null, not undefined", () => {
        const [spec] = normalizeSpecs([{ kind: "counts", column: "Pay::count" }]);
        expect(spec.activity).toBeNull();
        expect(spec.activityTo).toBeNull();
        expect(spec.attribute).toBeNull();
        expect(spec.method).toBe("");
    });

    it("survives an absent list", () => {
        expect(normalizeSpecs(undefined)).toEqual([]);
    });
});

describe("formatCount", () => {
    it("groups thousands, which is how every count in the header reads", () => {
        expect(formatCount(1505)).toBe("1,505");
        expect(formatCount(150370)).toBe("150,370");
        expect(formatCount(0)).toBe("0");
    });
});
