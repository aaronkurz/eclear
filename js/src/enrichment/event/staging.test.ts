import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import {
    CARRYLESS_AGGREGATES,
    EMPTY_EVENT_STAGING,
    draftEventType,
    draftParams,
    effectiveBinEdges,
    eventCellState,
    eventCountsByKind,
    eventCountsFor,
    initialDrafts,
    logNumericColumns,
    numericAttrsOf,
    profileOf,
    requestedBins,
    stageBlocker,
    stageEvent,
    timeColumnsOf,
    toggleEventRemove,
    unstageEvent,
} from "./staging";
import type { Drafts, EventStaging } from "./staging";
import type { AttrKind, EventCatalog, EventKind, EventSpec, EventType, NumericProfile } from "./types";

// ---------- fixtures ----------

function profile(values: number[]): NumericProfile {
    const sorted = [...values].sort((a, b) => a - b);
    const quantiles: number[] = [];
    for (let i = 0; i < 101; i += 1) {
        const at = (i / 100) * (sorted.length - 1);
        const low = Math.floor(at);
        const high = Math.min(low + 1, sorted.length - 1);
        quantiles.push(sorted[low] + (sorted[high] - sorted[low]) * (at - low));
    }
    return { min: sorted[0], max: sorted[sorted.length - 1], count: sorted.length, quantiles };
}

function eventType(name: string, attrs: [string, AttrKind][], events = 10): EventType {
    return {
        name,
        display: name,
        events,
        attributes: attrs.map(([n, kind]) => ({ name: n, kind, events })),
        neighbours: { prev: 1, next: 1 },
    };
}

const DEFAULT_TYPES: EventType[] = [
    eventType("Treat", [["dose", "num"], ["reading", "num"], ["lifecycle:transition", "cat"]]),
    eventType("Check", [["dose", "num"], ["note", "cat"]]),
];

/** A two-type log: `Treat` carries two numerics and a categorical, `Check` one
 *  numeric. Small enough to state expected answers as literals. */
function catalogOf(types: EventType[] = DEFAULT_TYPES): EventCatalog {
    return {
        kinds: [
            { key: "binning", label: "Binning" },
            { key: "arithmetic", label: "Arithmetic" },
            { key: "delta", label: "Time delta" },
            { key: "running_agg", label: "Running aggregation" },
        ],
        kindGroups: [
            { key: "local", label: "Local", kinds: ["binning", "arithmetic"] },
            { key: "contextual", label: "Contextual", kinds: ["delta", "running_agg"] },
        ],
        eventTypes: types,
        timeColumns: { Treat: ["time:timestamp", "sampled_at"], Check: ["time:timestamp"] },
        numericProfiles: {
            "*": { dose: profile([0, 1, 2, 3, 4, 5, 6, 7, 8, 9]) },
            Treat: {
                dose: profile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]),
                reading: profile([0, 0, 0, 0, 0, 0, 0, 0, 1, 2]),
            },
        },
        allEvents: "*",
        columns: ["case:concept:name", "concept:name", "time:timestamp", "dose", "reading"],
    };
}

/** A full `Drafts` with one slice replaced — the shape the panes hand around.
 *  The casts are the price of driving it from a JSON table: the contract rows
 *  are untyped by construction, which is what lets Python read the same ones. */
function draftsWith(slice: Record<string, unknown>): Drafts {
    return { ...initialDrafts(catalogOf()), ...slice } as unknown as Drafts;
}

/** A full `Drafts` with one slice *merged* onto the defaults. */
function draftsMerging(kind: string, slice: Record<string, unknown>): Drafts {
    const base = initialDrafts(catalogOf()) as unknown as Record<string, Record<string, unknown>>;
    return { ...base, [kind]: { ...base[kind], ...slice } } as unknown as Drafts;
}

function spec(
    column: string,
    kind: EventKind = "binning",
    eventTypeName: string | null = "Treat",
): EventSpec {
    return { kind, column, eventType: eventTypeName, params: {} };
}

function contract<T>(name: string): T {
    return JSON.parse(
        readFileSync(new URL(`../../../../eclear/contracts/${name}.json`, import.meta.url), "utf8"),
    ) as T;
}

// ---------- the wire format, shared with Python ----------

const params = contract<{
    cases: {
        name: string;
        kind: string;
        draft: Record<string, unknown>;
        edges: number[];
        params: Record<string, unknown>;
    }[];
}>("params");

describe("draftParams sends exactly what Python reads", () => {
    for (const row of params.cases) {
        it(row.name, () => {
            const drafts = draftsWith({ [row.kind]: row.draft });
            expect(draftParams(row.kind as EventKind, drafts, row.edges)).toEqual(row.params);
        });
    }

    it("sends snake_case, because Python does not translate", () => {
        // `neighbourType` in the draft becomes `neighbour_type` on the wire.
        const drafts = draftsWith({
            delta: {
                type: "Treat", direction: "prev", neighbour: "type",
                neighbourType: "Check", unit: "hours", missing: "NaT",
            },
        });
        expect(Object.keys(draftParams("delta", drafts, []))).toEqual([
            "direction", "neighbour", "neighbour_type", "unit", "missing",
        ]);
    });
});

// ---------- what cannot be staged, shared with Python ----------

const rejections = contract<{
    cases: {
        name: string;
        kind: string;
        column: string;
        draft: Record<string, unknown>;
        edges: number[];
        taken: string[];
        ts: string | null;
    }[];
}>("rejections");

describe("stageBlocker matches Python's validate_event_spec", () => {
    for (const row of rejections.cases) {
        it(row.name, () => {
            const drafts = draftsMerging(row.kind, row.draft);
            const blocker = stageBlocker(
                row.kind as EventKind, drafts, row.edges, row.column, new Set(row.taken),
            );
            if (row.ts === null) expect(blocker).toBe("");
            else expect(blocker).toContain(row.ts);
        });
    }
});

// ---------- draft derivation ----------

describe("requestedBins", () => {
    it("clamps to the range the pane offers", () => {
        expect(requestedBins("1")).toBe(2);
        expect(requestedBins("99")).toBe(10);
        expect(requestedBins("4")).toBe(4);
    });

    it("falls back to 4 for anything that is not a number", () => {
        expect(requestedBins("")).toBe(4);
        expect(requestedBins("abc")).toBe(4);
    });
});

describe("effectiveBinEdges", () => {
    const catalog = catalogOf();

    it("sorts custom edges rather than trusting the order they were typed", () => {
        const drafts = draftsMerging("binning", { mode: "numeric", method: "custom", edges: [9, 2, 5] });
        expect(effectiveBinEdges(drafts, catalog)).toEqual([2, 5, 9]);
    });

    it("does not touch a custom edge that sits outside the data", () => {
        // Unlike a derived method: the user put it there, and the counts show it.
        const drafts = draftsMerging("binning", { mode: "numeric", method: "custom", edges: [-100, 500] });
        expect(effectiveBinEdges(drafts, catalog)).toEqual([-100, 500]);
    });

    it("derives from the sketch for quantile and equal width", () => {
        for (const method of ["quantile", "equal"]) {
            const drafts = draftsMerging("binning", {
                mode: "numeric", type: "Treat", source: "dose", method, bins: "2",
            });
            expect(effectiveBinEdges(drafts, catalog)).toHaveLength(1);
        }
    });

    it("is empty in time mode, whatever the numeric draft holds", () => {
        const drafts = draftsMerging("binning", { mode: "time", edges: [1, 2, 3], method: "custom" });
        expect(effectiveBinEdges(drafts, catalog)).toEqual([]);
    });

    it("is empty when the column has no sketch at all", () => {
        const drafts = draftsMerging("binning", {
            mode: "numeric", type: "Treat", source: "nope", method: "quantile",
        });
        expect(effectiveBinEdges(drafts, catalog)).toEqual([]);
    });
});

describe("initialDrafts", () => {
    it("opens on the first type that has something to cut", () => {
        const drafts = initialDrafts(catalogOf());
        expect(drafts.binning.mode).toBe("numeric");
        expect(drafts.binning.type).toBe("Treat");
        expect(drafts.binning.source).toBe("dose");
    });

    it("opens in time mode when the log offers no numeric column", () => {
        // A pane whose picker is empty looks broken; every log has timestamps.
        const categorical = catalogOf([eventType("Treat", [["note", "cat"]])]);
        expect(initialDrafts(categorical).binning.mode).toBe("time");
    });

    it("picks a timestamp column the chosen type actually carries", () => {
        const catalog = catalogOf();
        const drafts = initialDrafts(catalog);
        expect(timeColumnsOf(catalog, drafts.binning.type)).toContain(drafts.binning.timeSource);
    });

    it("survives a catalog with no event types at all", () => {
        const drafts = initialDrafts(catalogOf([]));
        expect(drafts.binning.type).toBe("");
        expect(drafts.arithmetic.left).toBe("");
        expect(drafts.running_agg.source).toBe("");
    });

    it("leaves every name blank, so the suggestion stands until overwritten", () => {
        expect(Object.values(initialDrafts(catalogOf()).names)).toEqual(["", "", "", ""]);
    });
});

describe("numericAttrsOf", () => {
    const catalog = catalogOf();

    it("offers the type's own numeric attributes, in catalog order", () => {
        expect(numericAttrsOf("Treat", catalog, [])).toEqual(["dose", "reading"]);
        expect(numericAttrsOf("Check", catalog, [])).toEqual(["dose"]);
    });

    it("adds columns earlier enrichments produced on this type or on every event", () => {
        const columns = [spec("gap", "delta", "Treat"), spec("total", "running_agg", null)];
        expect(numericAttrsOf("Treat", catalog, columns)).toEqual(["dose", "reading", "gap", "total"]);
    });

    it("never offers a binning column, which holds a label", () => {
        expect(numericAttrsOf("Treat", catalog, [spec("dose_level", "binning", "Treat")]))
            .toEqual(["dose", "reading"]);
    });

    it("does not offer a column scoped to another event type", () => {
        expect(numericAttrsOf("Check", catalog, [spec("gap", "delta", "Treat")])).toEqual(["dose"]);
    });

    it("returns nothing for a type the catalog does not know", () => {
        expect(numericAttrsOf("Nope", catalog, [])).toEqual([]);
    });
});

describe("logNumericColumns", () => {
    it("is every numeric column in the log, deduped across types", () => {
        expect(logNumericColumns(catalogOf(), [])).toEqual(["dose", "reading"]);
    });

    it("includes derived columns regardless of scope, but not binnings", () => {
        const columns = [spec("gap", "delta", "Treat"), spec("lvl", "binning", "Check")];
        expect(logNumericColumns(catalogOf(), columns)).toEqual(["dose", "reading", "gap"]);
    });
});

describe("profileOf", () => {
    const catalog = catalogOf();

    it("prefers the event type's own sketch", () => {
        expect(profileOf(catalog, "Treat", "dose")?.min).toBe(1);
    });

    it("falls back to the log-wide sketch when the type has none", () => {
        expect(profileOf(catalog, "Check", "dose")?.min).toBe(0);
    });

    it("reads the log-wide sketch for an unscoped enrichment", () => {
        expect(profileOf(catalog, null, "dose")?.min).toBe(0);
    });

    it("is undefined for a column nothing sketched", () => {
        expect(profileOf(catalog, "Treat", "note")).toBeUndefined();
    });
});

describe("draftEventType", () => {
    it("scopes a running aggregation to every event", () => {
        expect(draftEventType("running_agg", draftsWith({}), "*")).toBe("*");
    });

    it("takes the type each other category was configured with", () => {
        const drafts = draftsWith({});
        expect(draftEventType("arithmetic", drafts, "*")).toBe(drafts.arithmetic.type);
        expect(draftEventType("delta", drafts, "*")).toBe(drafts.delta.type);
        expect(draftEventType("binning", drafts, "*")).toBe(drafts.binning.type);
    });
});

describe("CARRYLESS_AGGREGATES", () => {
    it("names the aggregations for which a zero between values would lie", () => {
        expect([...CARRYLESS_AGGREGATES].sort()).toEqual(["ffill", "runmin"]);
    });
});

// ---------- the staging state machine ----------

describe("eventCellState", () => {
    const applied = [spec("dose_level")];

    it("reads applied, staged, removing and off", () => {
        const staging: EventStaging = { add: [spec("gap", "delta")], remove: ["dose_level"] };
        expect(eventCellState("dose_level", applied, staging)).toBe("removing");
        expect(eventCellState("gap", applied, staging)).toBe("staged");
        expect(eventCellState("dose_level", applied, EMPTY_EVENT_STAGING)).toBe("applied");
        expect(eventCellState("nothing", applied, EMPTY_EVENT_STAGING)).toBe("off");
    });
});

describe("stage / unstage / toggleRemove", () => {
    it("stages a column once, however many times it is asked", () => {
        const once = stageEvent(EMPTY_EVENT_STAGING, spec("gap"));
        const twice = stageEvent(once, spec("gap"));
        expect(twice.add).toHaveLength(1);
        expect(twice).toBe(once); // unchanged, so React can skip the re-render
    });

    it("unstages by column name", () => {
        const staging = stageEvent(stageEvent(EMPTY_EVENT_STAGING, spec("a")), spec("b"));
        expect(unstageEvent(staging, "a").add.map((s) => s.column)).toEqual(["b"]);
    });

    it("returns the same object when there is nothing to unstage", () => {
        const staging = stageEvent(EMPTY_EVENT_STAGING, spec("a"));
        expect(unstageEvent(staging, "zzz")).toBe(staging);
    });

    it("toggles a removal on and back off", () => {
        const on = toggleEventRemove(EMPTY_EVENT_STAGING, "dose_level");
        expect(on.remove).toEqual(["dose_level"]);
        expect(toggleEventRemove(on, "dose_level").remove).toEqual([]);
    });
});

describe("eventCountsFor", () => {
    it("counts the columns the log would have after applying", () => {
        const applied = [spec("a"), spec("b")];
        const staging: EventStaging = { add: [spec("c")], remove: ["a"] };
        expect(eventCountsFor(5, applied, staging)).toEqual({
            applied: 2, staged: 1, removing: 1, live: 7, dirty: true,
        });
    });

    it("ignores a removal aimed at a column that was never applied", () => {
        const counts = eventCountsFor(5, [], { add: [], remove: ["ghost"] });
        expect(counts.removing).toBe(0);
        expect(counts.dirty).toBe(false);
    });

    it("is clean with nothing staged", () => {
        expect(eventCountsFor(5, [spec("a")], EMPTY_EVENT_STAGING).dirty).toBe(false);
    });
});

describe("eventCountsByKind", () => {
    it("tallies each kind separately, and a removal is not an application", () => {
        const applied = [spec("lvl", "binning"), spec("gap", "delta")];
        const staging: EventStaging = { add: [spec("lvl2", "binning")], remove: ["gap"] };
        expect(eventCountsByKind(applied, staging)).toEqual({
            binning: { applied: 1, staged: 1, removing: 0 },
            delta: { applied: 0, staged: 0, removing: 1 },
        });
    });

    it("mentions no kind that has nothing", () => {
        expect(eventCountsByKind([], EMPTY_EVENT_STAGING)).toEqual({});
    });
});
