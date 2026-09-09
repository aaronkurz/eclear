import type {
    Activity,
    Catalog,
    Kind,
    KindEntry,
    LogSummary,
    RawCatalog,
    RawLogSummary,
    RawSpec,
    Spec,
    TrackAttribute,
    TrackGroup,
} from "./types";

const KIND_ORDER: Kind[] = ["base", "counts", "times", "delays", "tracking"];

const FALLBACK_LABELS: Record<Kind, string> = {
    base: "Base case log",
    counts: "Activity counts",
    times: "First/last occurrence",
    delays: "Activity delays",
    tracking: "Attribute tracking",
};

function isKind(value: string): value is Kind {
    return (KIND_ORDER as string[]).includes(value);
}

export function normalizeCatalog(raw: RawCatalog | undefined): Catalog {
    const kinds: KindEntry[] = (raw?.kinds ?? [])
        .map((entry) => String(entry.key ?? ""))
        .filter(isKind)
        .map((key) => ({ key, label: raw?.kinds?.find((k) => k.key === key)?.label ?? FALLBACK_LABELS[key] }));

    return {
        kinds: kinds.length ? kinds : KIND_ORDER.map((key) => ({ key, label: FALLBACK_LABELS[key] })),
        baseColumns: (raw?.base_columns ?? []).map(String),
        activities: (raw?.activities ?? []).map(normalizeActivity),
        trackGroups: (raw?.track_groups ?? []).map(normalizeTrackGroup),
        trackMethods: (raw?.track_methods ?? []).map(String),
        allEvents: raw?.all_events ?? "*",
    };
}

function normalizeActivity(raw: NonNullable<RawCatalog["activities"]>[number]): Activity {
    const name = String(raw.name ?? "");
    return {
        name,
        display: String(raw.display ?? name),
        events: Number(raw.events ?? 0),
        cases: Number(raw.cases ?? 0),
    };
}

function normalizeTrackGroup(raw: NonNullable<RawCatalog["track_groups"]>[number]): TrackGroup {
    const eventType = String(raw.event_type ?? "");
    return {
        eventType,
        display: String(raw.display ?? eventType),
        label: String(raw.label ?? eventType),
        events: Number(raw.events ?? 0),
        attributes: (raw.attributes ?? []).map(normalizeTrackAttribute),
    };
}

function normalizeTrackAttribute(
    raw: NonNullable<NonNullable<RawCatalog["track_groups"]>[number]["attributes"]>[number],
): TrackAttribute {
    const attribute = String(raw.attribute ?? "");
    return {
        attribute,
        numeric: Boolean(raw.numeric),
        events: Number(raw.events ?? 0),
        methods: (raw.methods ?? []).map(String),
        columnPrefix: String(raw.column_prefix ?? `${attribute}::`),
    };
}

export function normalizeSummary(raw: RawLogSummary | undefined): LogSummary {
    return {
        cases: Number(raw?.cases ?? 0),
        events: Number(raw?.events ?? 0),
        activities: Number(raw?.activities ?? 0),
        caseIdCol: String(raw?.case_id_col ?? "case"),
    };
}

/** Applied specs as Python reports them. A spec whose kind we do not know is
 *  dropped rather than rendered into a catalog section that cannot exist. */
export function normalizeSpecs(raw: RawSpec[] | undefined): Spec[] {
    const specs: Spec[] = [];
    for (const entry of raw ?? []) {
        const kind = String(entry.kind ?? "");
        const column = String(entry.column ?? "");
        if (!isKind(kind) || !column) continue;
        specs.push({
            kind,
            method: String(entry.method ?? ""),
            activity: entry.activity ?? null,
            activityTo: entry.activity_to ?? null,
            attribute: entry.attribute ?? null,
            column,
        });
    }
    return specs;
}

export function formatCount(value: number): string {
    return value.toLocaleString("en-US");
}
