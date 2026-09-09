import { EVENT_GROUP_HINTS, EVENT_KIND_TAG, eventKindTagClass } from "./copy";
import type { EventKind, EventKindEntry, EventKindGroup } from "./types";

interface EventRailProps {
    kinds: EventKindEntry[];
    groups: EventKindGroup[];
    active: EventKind;
    onSelect: (kind: EventKind) => void;
    tallies: Record<string, { applied: number; staged: number; removing: number }>;
}

/** The event-enrichment categories, in two sections, with what each has produced.
 *
 *  The sections say what the categories have in common: a *local* column is
 *  computed from the event's own attributes, a *contextual* one from where the
 *  event sits among the other events of its case. Python owns both the grouping
 *  and the order (`EVENT_KIND_GROUPS`); anything it does not place lands in a
 *  trailing section rather than disappearing, so a stale catalog cannot hide a
 *  category the user can otherwise reach.
 */
export default function EventRail({ kinds, groups, active, onSelect, tallies }: EventRailProps) {
    const byKey = new Map(kinds.map((kind) => [kind.key, kind]));
    const placed = new Set(groups.flatMap((group) => group.kinds));
    const sections = [
        ...groups.map((group) => ({
            key: group.key,
            label: group.label,
            entries: group.kinds.map((key) => byKey.get(key)).filter(Boolean) as EventKindEntry[],
        })),
        {
            key: "other",
            label: "Other",
            entries: kinds.filter((kind) => !placed.has(kind.key)),
        },
    ].filter((section) => section.entries.length);

    return (
        <div className="en-rail-left">
            <div className="en-rail-title">Event enrichments</div>
            {sections.map((section) => (
                <div className="en-rail-section" key={section.key}>
                    <div className="en-rail-group" title={EVENT_GROUP_HINTS[section.key] ?? ""}>
                        {section.label}
                    </div>
                    {section.entries.map((kind) => {
                        const tally = tallies[kind.key] ?? { applied: 0, staged: 0, removing: 0 };
                        const empty = tally.applied + tally.staged + tally.removing === 0;
                        return (
                            <button
                                type="button"
                                key={kind.key}
                                className={`en-rail-item${kind.key === active ? " en-on" : ""}`}
                                onClick={() => onSelect(kind.key)}
                            >
                                <span className="en-rail-head">
                                    <span className={eventKindTagClass(kind.key)}>
                                        {EVENT_KIND_TAG[kind.key]}
                                    </span>
                                    <span className="en-rail-name">{kind.label}</span>
                                </span>
                                <span className="en-rail-tallies">
                                    {tally.applied > 0 ? (
                                        <span className="en-pill en-applied">✓ {tally.applied}</span>
                                    ) : null}
                                    {tally.staged > 0 ? (
                                        <span className="en-pill en-staged">+{tally.staged}</span>
                                    ) : null}
                                    {tally.removing > 0 ? (
                                        <span className="en-pill en-removing">−{tally.removing}</span>
                                    ) : null}
                                    {empty ? (
                                        <span className="en-rail-none">not configured</span>
                                    ) : null}
                                </span>
                            </button>
                        );
                    })}
                </div>
            ))}
        </div>
    );
}
