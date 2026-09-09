import { describe, expect, it } from "vitest";
import {
    EMPTY_STAGING,
    buildView,
    cellState,
    countsByKind,
    countsFor,
    countsSpec,
    delaySpec,
    stage,
    timesSpec,
    toRawSpec,
    toggleRemove,
    toggleSpec,
    trackingSpec,
    unstage,
    unstageKind,
} from "./staging";
import type { Staging } from "./staging";
import type { Activity, Spec, TrackAttribute } from "./types";

const PAY: Activity = { name: "Pay Fine", display: "Pay_Fine", events: 10, cases: 8 };
const CLOSE: Activity = { name: "Close", display: "Close", events: 8, cases: 8 };
const AMOUNT: TrackAttribute = {
    attribute: "amount", numeric: true, events: 10,
    methods: ["latest", "sum"], columnPrefix: "Pay_Fine.amount::",
};

describe("column naming", () => {
    // Mirrors `column_name` in specs.py: Python re-derives the name from the
    // spec it receives, so a mismatch would show one column and produce another.
    it("names a count after the activity's converted display name", () => {
        expect(countsSpec(PAY).column).toBe("Pay_Fine::count");
    });

    it("names a first/last occurrence after the end it marks", () => {
        expect(timesSpec(PAY, "start").column).toBe("Pay_Fine::start");
        expect(timesSpec(PAY, "end").column).toBe("Pay_Fine::end");
    });

    it("names a delay after both ends", () => {
        expect(delaySpec(PAY, CLOSE).column).toBe("Pay_Fine:Close::delay");
    });

    it("takes a tracking column's prefix from the catalog rather than rebuilding it", () => {
        expect(trackingSpec("Pay Fine", AMOUNT, "sum").column).toBe("Pay_Fine.amount::sum");
    });

    it("keeps the raw activity name on the spec, not the display name", () => {
        // Python matches events on the raw value; the display name is for columns.
        expect(countsSpec(PAY).activity).toBe("Pay Fine");
        expect(delaySpec(PAY, CLOSE).activityTo).toBe("Close");
    });
});

describe("toRawSpec", () => {
    it("sends the snake_case shape from_dict expects", () => {
        expect(toRawSpec(delaySpec(PAY, CLOSE))).toEqual({
            kind: "delays", method: "delay", activity: "Pay Fine",
            activity_to: "Close", attribute: null, column: "Pay_Fine:Close::delay",
        });
    });
});

describe("cellState", () => {
    const applied = [countsSpec(PAY)];

    it("reads all four states", () => {
        const staging: Staging = { add: [timesSpec(PAY, "end")], remove: ["Pay_Fine::count"] };
        const view = buildView(applied, staging);
        expect(cellState("Pay_Fine::count", view)).toBe("removing");
        expect(cellState("Pay_Fine::end", view)).toBe("staged");
        expect(cellState("nothing", view)).toBe("off");
        expect(cellState("Pay_Fine::count", buildView(applied, EMPTY_STAGING))).toBe("applied");
    });
});

describe("toggleSpec", () => {
    it("stages an unapplied column and unstages it again", () => {
        const spec = timesSpec(PAY, "end");
        const staged = toggleSpec(EMPTY_STAGING, spec, buildView([], EMPTY_STAGING));
        expect(staged.add.map((s) => s.column)).toEqual(["Pay_Fine::end"]);

        const back = toggleSpec(staged, spec, buildView([], staged));
        expect(back.add).toEqual([]);
    });

    it("marks an applied column for removal and back again", () => {
        const spec = countsSpec(PAY);
        const applied = [spec];
        const removing = toggleSpec(EMPTY_STAGING, spec, buildView(applied, EMPTY_STAGING));
        expect(removing.remove).toEqual(["Pay_Fine::count"]);

        const kept = toggleSpec(removing, spec, buildView(applied, removing));
        expect(kept.remove).toEqual([]);
    });

    it("is reversible in every state, which is what makes staging explorable", () => {
        const spec = countsSpec(PAY);
        for (const applied of [[], [spec]]) {
            const view = buildView(applied, EMPTY_STAGING);
            const once = toggleSpec(EMPTY_STAGING, spec, view);
            const twice = toggleSpec(once, spec, buildView(applied, once));
            expect(twice).toEqual(EMPTY_STAGING);
        }
    });
});

describe("stage", () => {
    it("stages several at once, skipping the ones already there", () => {
        const first = stage(EMPTY_STAGING, [countsSpec(PAY)]);
        const both = stage(first, [countsSpec(PAY), timesSpec(PAY, "end")]);
        expect(both.add.map((s) => s.column)).toEqual(["Pay_Fine::count", "Pay_Fine::end"]);
    });

    it("skips a column the case log already has", () => {
        const view = buildView([countsSpec(PAY)], EMPTY_STAGING);
        expect(stage(EMPTY_STAGING, [countsSpec(PAY)], view)).toBe(EMPTY_STAGING);
    });

    it("dedupes within a single call", () => {
        expect(stage(EMPTY_STAGING, [countsSpec(PAY), countsSpec(PAY)]).add).toHaveLength(1);
    });

    it("returns the same object when nothing was fresh, so React can skip", () => {
        const staging = stage(EMPTY_STAGING, [countsSpec(PAY)]);
        expect(stage(staging, [countsSpec(PAY)])).toBe(staging);
    });
});

describe("unstage and unstageKind", () => {
    const staging = stage(EMPTY_STAGING, [
        countsSpec(PAY), timesSpec(PAY, "end"), delaySpec(PAY, CLOSE),
    ]);

    it("drops the named columns", () => {
        expect(unstage(staging, ["Pay_Fine::count"]).add.map((s) => s.column))
            .toEqual(["Pay_Fine::end", "Pay_Fine:Close::delay"]);
    });

    it("drops every staged column of one kind", () => {
        expect(unstageKind(staging, "times").add.map((s) => s.kind)).toEqual(["counts", "delays"]);
    });

    it("returns the same object when there is nothing to drop", () => {
        expect(unstage(staging, ["ghost"])).toBe(staging);
        expect(unstageKind(staging, "tracking")).toBe(staging);
    });
});

describe("toggleRemove", () => {
    it("adds and removes the column from the removal list", () => {
        const on = toggleRemove(EMPTY_STAGING, "a");
        expect(on.remove).toEqual(["a"]);
        expect(toggleRemove(on, "a").remove).toEqual([]);
    });
});

describe("countsFor", () => {
    const base = ["start_time", "end_time"];

    it("counts what the case log would look like after applying", () => {
        const applied: Spec[] = [countsSpec(PAY), timesSpec(PAY, "end")];
        const staging: Staging = { add: [delaySpec(PAY, CLOSE)], remove: ["Pay_Fine::count"] };
        expect(countsFor(base, applied, staging)).toEqual({
            applied: 2, staged: 1, removing: 1, live: 2 + 2 + 1 - 1, dirty: true,
        });
    });

    it("does not let a stale removal make the apply button look busy", () => {
        const counts = countsFor(base, [], { add: [], remove: ["never applied"] });
        expect(counts.removing).toBe(0);
        expect(counts.dirty).toBe(false);
    });
});

describe("countsByKind", () => {
    it("splits applied from staged from removing, per kind", () => {
        const applied = [countsSpec(PAY), timesSpec(PAY, "end")];
        const staging: Staging = {
            add: [delaySpec(PAY, CLOSE)], remove: ["Pay_Fine::count"],
        };
        expect(countsByKind(applied, staging)).toEqual({
            counts: { applied: 0, staged: 0, removing: 1 },
            times: { applied: 1, staged: 0, removing: 0 },
            delays: { applied: 0, staged: 1, removing: 0 },
        });
    });

    it("mentions no kind that has nothing", () => {
        expect(countsByKind([], EMPTY_STAGING)).toEqual({});
    });
});
