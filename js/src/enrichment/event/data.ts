import type {
    AttrKind,
    EventAttribute,
    EventCatalog,
    EventKind,
    EventKindEntry,
    EventKindGroup,
    EventSpec,
    EventType,
    NumericProfile,
    RawEventCatalog,
    RawEventSpec,
} from "./types";

/** The rail's order, flattened from the groups below. Mirrors `EVENT_KINDS` in
 *  `eclear/enrichment/event_specs.py`, which is derived the same way. */
export const EVENT_KIND_ORDER: EventKind[] = [
    "binning",
    "arithmetic",
    "delta",
    "running_agg",
];

const FALLBACK_LABELS: Record<EventKind, string> = {
    binning: "Binning",
    arithmetic: "Arithmetic",
    delta: "Time delta",
    running_agg: "Running aggregation",
};

/** Used only when Python sends no grouping, the way `FALLBACK_LABELS` is. */
const FALLBACK_GROUPS: EventKindGroup[] = [
    { key: "local", label: "Local", kinds: ["binning", "arithmetic"] },
    { key: "contextual", label: "Contextual", kinds: ["delta", "running_agg"] },
];

const ATTR_KINDS: AttrKind[] = ["num", "cat", "bool", "time"];

export function isEventKind(value: string): value is EventKind {
    return (EVENT_KIND_ORDER as string[]).includes(value);
}

export function normalizeEventCatalog(raw: RawEventCatalog | undefined): EventCatalog {
    const kinds: EventKindEntry[] = (raw?.kinds ?? [])
        .map((entry) => ({ key: String(entry.key ?? ""), label: String(entry.label ?? "") }))
        .filter((entry) => isEventKind(entry.key))
        .map((entry) => ({
            key: entry.key as EventKind,
            label: entry.label || FALLBACK_LABELS[entry.key as EventKind],
        }));

    return {
        kinds: kinds.length
            ? kinds
            : EVENT_KIND_ORDER.map((key) => ({ key, label: FALLBACK_LABELS[key] })),
        kindGroups: normalizeKindGroups(raw?.kind_groups),
        eventTypes: (raw?.event_types ?? []).map(normalizeEventType),
        timeColumns: normalizeTimeColumns(raw?.time_columns),
        numericProfiles: normalizeProfiles(raw?.numeric_profiles),
        allEvents: raw?.all_events ?? "*",
        columns: (raw?.columns ?? []).map(String),
    };
}

function normalizeKindGroups(raw: RawEventCatalog["kind_groups"]): EventKindGroup[] {
    const groups = (raw ?? [])
        .map((entry) => ({
            key: String(entry.key ?? ""),
            label: String(entry.label ?? ""),
            kinds: (entry.kinds ?? []).map(String).filter(isEventKind),
        }))
        .filter((group) => group.key && group.kinds.length);
    return groups.length ? groups : FALLBACK_GROUPS;
}

function normalizeEventType(raw: NonNullable<RawEventCatalog["event_types"]>[number]): EventType {
    const name = String(raw.name ?? "");
    return {
        name,
        display: String(raw.display ?? name),
        events: Number(raw.events ?? 0),
        attributes: (raw.attributes ?? []).map(normalizeAttribute),
        neighbours: {
            prev: Number(raw.neighbours?.prev ?? 0),
            next: Number(raw.neighbours?.next ?? 0),
        },
    };
}

function normalizeAttribute(
    raw: NonNullable<NonNullable<RawEventCatalog["event_types"]>[number]["attributes"]>[number],
): EventAttribute {
    const kind = String(raw.kind ?? "cat");
    return {
        name: String(raw.name ?? ""),
        kind: (ATTR_KINDS as string[]).includes(kind) ? (kind as AttrKind) : "cat",
        events: Number(raw.events ?? 0),
    };
}

function normalizeTimeColumns(raw: RawEventCatalog["time_columns"]): Record<string, string[]> {
    const out: Record<string, string[]> = {};
    for (const [type, columns] of Object.entries(raw ?? {})) {
        out[type] = (columns ?? []).map(String);
    }
    return out;
}

function normalizeProfiles(
    raw: RawEventCatalog["numeric_profiles"],
): Record<string, Record<string, NumericProfile>> {
    const out: Record<string, Record<string, NumericProfile>> = {};
    for (const [type, columns] of Object.entries(raw ?? {})) {
        const entries: Record<string, NumericProfile> = {};
        for (const [column, profile] of Object.entries(columns ?? {})) {
            entries[column] = {
                min: Number(profile.min ?? 0),
                max: Number(profile.max ?? 0),
                count: Number(profile.count ?? 0),
                quantiles: (profile.quantiles ?? []).map(Number),
            };
        }
        out[type] = entries;
    }
    return out;
}

/** Applied event specs as Python reports them. A spec whose kind we do not know
 *  is dropped rather than rendered into a category that cannot exist. */
export function normalizeEventSpecs(raw: RawEventSpec[] | undefined): EventSpec[] {
    const specs: EventSpec[] = [];
    for (const entry of raw ?? []) {
        const kind = String(entry.kind ?? "");
        const column = String(entry.column ?? "");
        if (!isEventKind(kind) || !column) continue;
        specs.push({
            kind,
            column,
            eventType: entry.event_type ?? null,
            params: { ...(entry.params ?? {}) },
        });
    }
    return specs;
}

/** Send a spec back to Python in the shape `EventEnrichmentSpec.from_dict` expects. */
export function toRawEventSpec(spec: EventSpec): RawEventSpec {
    return {
        kind: spec.kind,
        column: spec.column,
        event_type: spec.eventType,
        params: spec.params,
    };
}
