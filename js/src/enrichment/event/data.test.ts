import { describe, expect, it } from "vitest";
import {
    EVENT_KIND_ORDER,
    isEventKind,
    normalizeEventCatalog,
    normalizeEventSpecs,
    toRawEventSpec,
} from "./data";

/** Everything here guards the same boundary: Python's payload arrives as
 *  untyped JSON over a traitlet, and these functions are the only thing between
 *  it and code that assumes a shape. A key Python stops sending has to surface
 *  as a sane default, not as `undefined` halfway down a render. */

describe("isEventKind", () => {
    it("accepts the four kinds and nothing else", () => {
        expect(EVENT_KIND_ORDER.every(isEventKind)).toBe(true);
        expect(isEventKind("sorcery")).toBe(false);
        expect(isEventKind("")).toBe(false);
    });
});

describe("normalizeEventCatalog", () => {
    it("falls back to the full rail when Python sends no kinds", () => {
        const catalog = normalizeEventCatalog({});
        expect(catalog.kinds.map((k) => k.key)).toEqual(EVENT_KIND_ORDER);
        expect(catalog.kinds.every((k) => k.label.length > 0)).toBe(true);
    });

    it("survives an entirely absent payload", () => {
        const catalog = normalizeEventCatalog(undefined);
        expect(catalog.eventTypes).toEqual([]);
        expect(catalog.columns).toEqual([]);
        expect(catalog.allEvents).toBe("*");
        expect(catalog.kindGroups.length).toBeGreaterThan(0);
    });

    it("drops a kind it does not know rather than rendering an empty pane", () => {
        const catalog = normalizeEventCatalog({
            kinds: [{ key: "binning", label: "Binning" }, { key: "sorcery", label: "Sorcery" }],
        });
        expect(catalog.kinds.map((k) => k.key)).toEqual(["binning"]);
    });

    it("labels a kind Python sent without one", () => {
        const catalog = normalizeEventCatalog({ kinds: [{ key: "delta" }] });
        expect(catalog.kinds).toEqual([{ key: "delta", label: "Time delta" }]);
    });

    it("keeps the kind groups Python sent, filtering unknown members", () => {
        const catalog = normalizeEventCatalog({
            kind_groups: [{ key: "local", label: "Local", kinds: ["binning", "sorcery"] }],
        });
        expect(catalog.kindGroups).toEqual([
            { key: "local", label: "Local", kinds: ["binning"] },
        ]);
    });

    it("falls back to the standard groups when every group is unusable", () => {
        const catalog = normalizeEventCatalog({ kind_groups: [{ key: "", kinds: [] }] });
        expect(catalog.kindGroups.map((g) => g.key)).toEqual(["local", "contextual"]);
    });

    it("defaults an event type's display to its name and its counts to zero", () => {
        const [type] = normalizeEventCatalog({ event_types: [{ name: "Treat" }] }).eventTypes;
        expect(type).toEqual({
            name: "Treat", display: "Treat", events: 0, attributes: [],
            neighbours: { prev: 0, next: 0 },
        });
    });

    it("carries neighbour coverage through, and defaults it to none", () => {
        const raw = {
            event_types: [
                { name: "Open", neighbours: { prev: 0, next: 1 } },
                { name: "Legacy" },
            ],
        };
        const [open, legacy] = normalizeEventCatalog(raw).eventTypes;
        expect(open.neighbours).toEqual({ prev: 0, next: 1 });
        // A payload from before coverage existed must not read as full coverage,
        // or the delta pane would go quiet exactly where it should warn.
        expect(legacy.neighbours).toEqual({ prev: 0, next: 0 });
    });

    it("reads an attribute kind it knows and calls anything else categorical", () => {
        const raw = {
            event_types: [{
                name: "Treat",
                attributes: [
                    { name: "dose", kind: "num", events: 3 },
                    { name: "when", kind: "time" },
                    { name: "odd", kind: "quaternion" },
                    { name: "unstated" },
                ],
            }],
        };
        const [type] = normalizeEventCatalog(raw).eventTypes;
        expect(type.attributes.map((a) => [a.name, a.kind])).toEqual([
            ["dose", "num"], ["when", "time"], ["odd", "cat"], ["unstated", "cat"],
        ]);
    });

    it("keeps time columns and numeric sketches keyed by event type", () => {
        const catalog = normalizeEventCatalog({
            time_columns: { Treat: ["time:timestamp"], Check: [] },
            numeric_profiles: {
                Treat: { dose: { min: 1, max: 9, count: 4, quantiles: [1, 5, 9] } },
            },
        });
        expect(catalog.timeColumns).toEqual({ Treat: ["time:timestamp"], Check: [] });
        expect(catalog.numericProfiles.Treat.dose).toEqual({
            min: 1, max: 9, count: 4, quantiles: [1, 5, 9],
        });
    });

    it("gives a half-sent sketch zeros rather than undefined", () => {
        const catalog = normalizeEventCatalog({ numeric_profiles: { Treat: { dose: {} } } });
        expect(catalog.numericProfiles.Treat.dose).toEqual({
            min: 0, max: 0, count: 0, quantiles: [],
        });
    });
});

describe("normalizeEventSpecs", () => {
    it("reads the applied list Python reports", () => {
        const specs = normalizeEventSpecs([
            { kind: "delta", column: "gap", event_type: "Treat", params: { unit: "hours" } },
        ]);
        expect(specs).toEqual([
            { kind: "delta", column: "gap", eventType: "Treat", params: { unit: "hours" } },
        ]);
    });

    it("reads a null event type as log-wide", () => {
        const [spec] = normalizeEventSpecs([{ kind: "running_agg", column: "total" }]);
        expect(spec.eventType).toBeNull();
    });

    it("drops a spec with an unknown kind or no column", () => {
        expect(normalizeEventSpecs([
            { kind: "sorcery", column: "x" },
            { kind: "delta", column: "" },
            { kind: "delta", column: "gap" },
        ])).toHaveLength(1);
    });

    it("copies params rather than aliasing Python's payload", () => {
        const params = { unit: "hours" };
        const [spec] = normalizeEventSpecs([{ kind: "delta", column: "gap", params }]);
        spec.params.unit = "days";
        expect(params.unit).toBe("hours");
    });

    it("survives an absent list", () => {
        expect(normalizeEventSpecs(undefined)).toEqual([]);
    });
});

describe("toRawEventSpec", () => {
    it("round-trips a spec back into the shape from_dict expects", () => {
        const spec = {
            kind: "binning" as const, column: "lvl", eventType: "Treat",
            params: { mode: "numeric", edges: [1, 2] },
        };
        expect(toRawEventSpec(spec)).toEqual({
            kind: "binning", column: "lvl", event_type: "Treat",
            params: { mode: "numeric", edges: [1, 2] },
        });
        expect(normalizeEventSpecs([toRawEventSpec(spec)])).toEqual([spec]);
    });
});
