// ---------- raw traits (Python -> JS) ----------

/** One enrichment, as `EnrichmentSpec.to_dict()` sends it. */
export interface RawSpec {
    kind?: string;
    method?: string;
    activity?: string | null;
    activity_to?: string | null;
    attribute?: string | null;
    column?: string;
}

export interface RawActivity {
    name?: string;
    /** The name as it appears inside a column: spaces converted to underscores. */
    display?: string;
    events?: number;
    cases?: number;
}

export interface RawTrackAttribute {
    attribute?: string;
    numeric?: boolean;
    events?: number;
    methods?: string[];
    /** Everything before the method in the column name, e.g. `ER_Registration.Age::`. */
    column_prefix?: string;
}

export interface RawTrackGroup {
    event_type?: string;
    display?: string;
    label?: string;
    events?: number;
    attributes?: RawTrackAttribute[];
}

export interface RawCatalog {
    kinds?: { key?: string; label?: string }[];
    base_columns?: string[];
    activities?: RawActivity[];
    track_groups?: RawTrackGroup[];
    track_methods?: string[];
    all_events?: string;
}

export interface RawLogSummary {
    cases?: number;
    events?: number;
    activities?: number;
    case_id_col?: string;
    time_col?: string;
    activity_col?: string;
}

export interface ApplyResult {
    ok?: boolean;
    added?: string[];
    removed?: string[];
    columns?: number;
    cases?: number;
    error?: string;
    request_id?: number;
}

export interface PreviewColumn {
    name: string;
    /** `key` is the case id, `base` a fixed case-log column. */
    state: "key" | "base" | "applied" | "staged" | "removing";
}

export interface PreviewResult {
    ok?: boolean;
    columns?: PreviewColumn[];
    rows?: string[][];
    sampled?: number;
    total_cases?: number;
    total_events?: number;
    error?: string;
    request_id?: number;
}

// ---------- normalized ----------

export type Kind = "base" | "counts" | "times" | "delays" | "tracking";

export interface KindEntry {
    key: Kind;
    label: string;
}

export interface Activity {
    name: string;
    display: string;
    events: number;
    cases: number;
}

export interface TrackAttribute {
    attribute: string;
    numeric: boolean;
    events: number;
    methods: string[];
    columnPrefix: string;
}

export interface TrackGroup {
    eventType: string;
    display: string;
    label: string;
    events: number;
    attributes: TrackAttribute[];
}

export interface Catalog {
    kinds: KindEntry[];
    baseColumns: string[];
    activities: Activity[];
    trackGroups: TrackGroup[];
    trackMethods: string[];
    allEvents: string;
}

export interface LogSummary {
    cases: number;
    events: number;
    activities: number;
    caseIdCol: string;
}

/** A spec plus the column it produces. The column is the stable identity: it is
 *  what staging, removal and the schema rail are all keyed by. */
export interface Spec {
    kind: Kind;
    method: string;
    activity: string | null;
    activityTo: string | null;
    attribute: string | null;
    column: string;
}
