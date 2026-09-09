// ---------- raw traits (Python -> JS) ----------

export interface RawEventAttribute {
    name?: string;
    kind?: string;
    events?: number;
}

export interface RawEventType {
    name?: string;
    display?: string;
    events?: number;
    attributes?: RawEventAttribute[];
    neighbours?: { prev?: number; next?: number };
}

export interface RawNumericProfile {
    min?: number;
    max?: number;
    count?: number;
    quantiles?: number[];
}

export interface RawEventCatalog {
    kinds?: { key?: string; label?: string }[];
    kind_groups?: { key?: string; label?: string; kinds?: string[] }[];
    event_types?: RawEventType[];
    time_columns?: Record<string, string[]>;
    numeric_profiles?: Record<string, Record<string, RawNumericProfile>>;
    all_events?: string;
    axis_columns?: string[];
    columns?: string[];
}

/** One event enrichment, as `EventEnrichmentSpec.to_dict()` sends it. Params are
 *  passed through untouched in snake_case: Python reads them as given, so the
 *  frontend must not rename a key on the way out and back. */
export interface RawEventSpec {
    kind?: string;
    column?: string;
    event_type?: string | null;
    params?: Record<string, unknown>;
}

export interface EventApplyResult {
    ok?: boolean;
    added?: string[];
    removed?: string[];
    columns?: number;
    events?: number;
    error?: string;
    blocked?: { column: string; used_by: string[] }[];
    request_id?: number;
}

export interface EventPreviewColumn {
    name: string;
    kind: EventKind;
    event_type: string | null;
    state: "applied" | "staged";
}

export interface EventPreviewRow {
    group: boolean;
    case: string;
    events?: number;
    index?: number;
    activity?: string;
    timestamp?: string;
    /** One entry per column. `null` means the column does not apply to this
     *  event's type, which is not the same as a missing value. */
    values?: (string | null)[];
}

export interface EventPreviewResult {
    ok?: boolean;
    columns?: EventPreviewColumn[];
    rows?: EventPreviewRow[];
    sampled?: number;
    events?: number;
    total_cases?: number;
    total_events?: number;
    scope?: string;
    error?: string;
    request_id?: number;
}

// ---------- normalized ----------

export type EventKind = "binning" | "arithmetic" | "delta" | "running_agg";

/** Which part of a timestamp a time binning cuts on. */
export type TimePart = "year" | "month" | "weekday" | "hour";

/** The four types a picker distinguishes. Only `num` is offered as an arithmetic
 *  operand, a running-aggregation source or a numeric bin source, and only
 *  `time` as a time bin source — which is why a type mismatch cannot be
 *  configured rather than merely rejected. */
export type AttrKind = "num" | "cat" | "bool" | "time";

export interface EventKindEntry {
    key: EventKind;
    label: string;
}

/** A rail section: `local` reads the event's own attributes, `contextual` reads
 *  where the event sits among the other events of its case. Python owns both the
 *  membership and the order — see `EVENT_KIND_GROUPS` in `event_specs.py`. */
export interface EventKindGroup {
    key: string;
    label: string;
    kinds: EventKind[];
}

export interface EventAttribute {
    name: string;
    kind: AttrKind;
    events: number;
}

/** The share of an event type's events that have a neighbour in their case, per
 *  direction. A time delta against a neighbour that is never there comes out
 *  empty, and 0 here is what lets the pane say so before the column is staged.
 *  See `neighbour_coverage` in `catalog.py`. */
export interface NeighbourCoverage {
    prev: number;
    next: number;
}

export interface EventType {
    name: string;
    display: string;
    events: number;
    attributes: EventAttribute[];
    neighbours: NeighbourCoverage;
}

/** A quantile sketch of one numeric column: enough to derive equal-width and
 *  quantile edges, and to estimate how many events land in each bin, without a
 *  round trip to Python on every keystroke. */
export interface NumericProfile {
    min: number;
    max: number;
    count: number;
    quantiles: number[];
}

export interface EventCatalog {
    kinds: EventKindEntry[];
    kindGroups: EventKindGroup[];
    eventTypes: EventType[];
    /** Keyed by event type; the log's own timestamp column comes first. */
    timeColumns: Record<string, string[]>;
    /** Keyed by event type, then column; `allEvents` holds the log-wide sketch. */
    numericProfiles: Record<string, Record<string, NumericProfile>>;
    allEvents: string;
    columns: string[];
}

/** A spec plus the column it produces. Unlike a case spec the column is *not*
 *  derived from the rest — the user names it — so this is the only place the
 *  name exists and there is nothing for Python to disagree with. */
export interface EventSpec {
    kind: EventKind;
    column: string;
    eventType: string | null;
    params: Record<string, unknown>;
}
