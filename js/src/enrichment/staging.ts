import type { Activity, Kind, RawSpec, Spec, TrackAttribute } from "./types";

/** What a column is doing right now.
 *
 *  - `applied` — on the case log
 *  - `removing` — on the case log, staged to be dropped
 *  - `staged` — not on the case log yet, staged to be added
 *  - `off` — neither
 *
 *  Every picker in the widget renders these four and nothing else, so a single
 *  click always means "move to the next state", never "which of six things did
 *  I just do".
 */
export type ColState = "applied" | "removing" | "staged" | "off";

/** Columns staged to be added (as full specs) and applied columns staged to go. */
export interface Staging {
    add: Spec[];
    remove: string[];
}

export const EMPTY_STAGING: Staging = { add: [], remove: [] };

// ---------- column naming ----------
//
// These mirror `column_name` in `eclear/enrichment/specs.py`, which is the
// authority: Python re-derives the name from the spec it receives, so a
// mismatch here would show one column in the UI and produce another. The
// mangling of activity names (spaces to underscores) is deliberately *not*
// repeated — the catalog ships each activity's converted `display` and each
// tracked attribute's `columnPrefix` precisely so the frontend never has to.

export function countsSpec(activity: Activity): Spec {
    return {
        kind: "counts",
        method: "count",
        activity: activity.name,
        activityTo: null,
        attribute: null,
        column: `${activity.display}::count`,
    };
}

export function timesSpec(activity: Activity, which: "start" | "end"): Spec {
    return {
        kind: "times",
        method: which,
        activity: activity.name,
        activityTo: null,
        attribute: null,
        column: `${activity.display}::${which}`,
    };
}

export function delaySpec(from: Activity, to: Activity): Spec {
    return {
        kind: "delays",
        method: "delay",
        activity: from.name,
        activityTo: to.name,
        attribute: null,
        column: `${from.display}:${to.display}::delay`,
    };
}

export function trackingSpec(eventType: string, attr: TrackAttribute, method: string): Spec {
    return {
        kind: "tracking",
        method,
        activity: eventType,
        activityTo: null,
        attribute: attr.attribute,
        column: `${attr.columnPrefix}${method}`,
    };
}

/** Send a spec back to Python in the shape `EnrichmentSpec.from_dict` expects. */
export function toRawSpec(spec: Spec): RawSpec {
    return {
        kind: spec.kind,
        method: spec.method,
        activity: spec.activity,
        activity_to: spec.activityTo,
        attribute: spec.attribute,
        column: spec.column,
    };
}

// ---------- state ----------

export interface StagingView {
    /** Columns already on the case log, by column name. */
    appliedSpecs: Map<string, Spec>;
    stagedSpecs: Map<string, Spec>;
    removing: Set<string>;
}

export function buildView(applied: Spec[], staging: Staging): StagingView {
    return {
        appliedSpecs: new Map(applied.map((spec) => [spec.column, spec])),
        stagedSpecs: new Map(staging.add.map((spec) => [spec.column, spec])),
        removing: new Set(staging.remove),
    };
}

export function cellState(column: string, view: StagingView): ColState {
    if (view.appliedSpecs.has(column)) {
        return view.removing.has(column) ? "removing" : "applied";
    }
    return view.stagedSpecs.has(column) ? "staged" : "off";
}

/** The one click every picker wires up: advance a column to its opposite state.
 *
 *  Applied columns toggle between keeping and removing; unapplied ones between
 *  staged and off. A click is therefore always reversible by clicking again,
 *  which is what lets the whole staging area be explored without consequence.
 */
export function toggleSpec(staging: Staging, spec: Spec, view: StagingView): Staging {
    const state = cellState(spec.column, view);
    if (state === "applied" || state === "removing") {
        return toggleRemove(staging, spec.column);
    }
    return state === "staged" ? unstage(staging, [spec.column]) : stage(staging, [spec]);
}

/** Stage specs that are neither applied nor already staged. */
export function stage(staging: Staging, specs: Spec[], view?: StagingView): Staging {
    const known = new Set(staging.add.map((spec) => spec.column));
    const fresh = specs.filter((spec) => {
        if (known.has(spec.column)) return false;
        if (view?.appliedSpecs.has(spec.column)) return false;
        known.add(spec.column);
        return true;
    });
    return fresh.length ? { ...staging, add: [...staging.add, ...fresh] } : staging;
}

export function unstage(staging: Staging, columns: string[]): Staging {
    const drop = new Set(columns);
    const add = staging.add.filter((spec) => !drop.has(spec.column));
    return add.length === staging.add.length ? staging : { ...staging, add };
}

/** Drop every staged addition of one kind — the "Unstage added" buttons. */
export function unstageKind(staging: Staging, kind: Kind): Staging {
    const add = staging.add.filter((spec) => spec.kind !== kind);
    return add.length === staging.add.length ? staging : { ...staging, add };
}

export function toggleRemove(staging: Staging, column: string): Staging {
    const remove = staging.remove.includes(column)
        ? staging.remove.filter((name) => name !== column)
        : [...staging.remove, column];
    return { ...staging, remove };
}

// ---------- derived counts ----------

export interface StagingCounts {
    applied: number;
    staged: number;
    removing: number;
    /** Columns the case log would have after applying. */
    live: number;
    dirty: boolean;
}

export function countsFor(
    baseColumns: string[],
    applied: Spec[],
    staging: Staging,
): StagingCounts {
    // Only removals that actually hit an applied column count: a stale entry
    // must not make the apply button look like it has work to do.
    const appliedColumns = new Set(applied.map((spec) => spec.column));
    const removing = staging.remove.filter((column) => appliedColumns.has(column)).length;
    const total = baseColumns.length + applied.length;
    return {
        applied: applied.length,
        staged: staging.add.length,
        removing,
        live: total + staging.add.length - removing,
        dirty: staging.add.length + removing > 0,
    };
}

/** Per-kind tally for the catalog rail: applied, staged, staged-for-removal. */
export function countsByKind(
    applied: Spec[],
    staging: Staging,
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
