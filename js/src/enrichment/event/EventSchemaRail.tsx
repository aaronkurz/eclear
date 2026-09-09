import { useState } from "react";
import { formatCount } from "../data";
import { EVENT_KIND_TAG, isGlyphEventKind } from "./copy";
import { eventCellState } from "./staging";
import type { EventCounts, EventStaging } from "./staging";
import type { EventCatalog, EventSpec } from "./types";

interface EventSchemaRailProps {
    catalog: EventCatalog;
    applied: EventSpec[];
    staging: EventStaging;
    counts: EventCounts;
    onToggleRemove: (column: string) => void;
    onUnstage: (column: string) => void;
}

/** The event log's schema, by event type, and what applying would do to it.
 *
 *  Grouped by type rather than listed flat because that is the only grouping an
 *  event column has: which events carry a value for it. It doubles as the undo
 *  surface, the way the case tab's schema rail does — every derived column
 *  carries the control that reverses whatever was done to it.
 */
export default function EventSchemaRail({
    catalog,
    applied,
    staging,
    counts,
    onToggleRemove,
    onUnstage,
}: EventSchemaRailProps) {
    const [open, setOpen] = useState<Set<string>>(
        () => new Set(catalog.eventTypes.slice(0, 1).map((type) => type.name)),
    );
    const toggle = (name: string) =>
        setOpen((prev) => {
            const next = new Set(prev);
            if (next.has(name)) next.delete(name);
            else next.add(name);
            return next;
        });

    const columns = [...applied, ...staging.add];
    const delta: string[] = [];
    if (counts.staged) delta.push(`+${counts.staged}`);
    if (counts.removing) delta.push(`−${counts.removing}`);

    return (
        <div className="en-rail-right">
            <div className="en-rail-title">Event log schema</div>
            <div className="en-schema-head">
                <span className="en-schema-n">{formatCount(counts.live)}</span>
                <span className="en-schema-unit">columns</span>
                <span className={`en-delta${counts.dirty ? " en-dirty" : ""}`}>
                    {counts.dirty ? `${delta.join(" / ")} staged` : "in sync"}
                </span>
            </div>
            <div className="en-schema-body">
                {catalog.eventTypes.map((type) => {
                    const derived = columns.filter(
                        (spec) => spec.eventType === null || spec.eventType === type.name,
                    );
                    const expanded = open.has(type.name);
                    const tally = {
                        applied: derived.filter(
                            (spec) => eventCellState(spec.column, applied, staging) === "applied",
                        ).length,
                        staged: derived.filter(
                            (spec) => eventCellState(spec.column, applied, staging) === "staged",
                        ).length,
                        removing: derived.filter(
                            (spec) => eventCellState(spec.column, applied, staging) === "removing",
                        ).length,
                    };
                    return (
                        <div
                            className={`en-ev-type${expanded ? " en-on" : ""}`}
                            key={type.name}
                        >
                            <button
                                type="button"
                                className="en-ev-type-head"
                                onClick={() => toggle(type.name)}
                            >
                                <span className="en-arrow">{expanded ? "▾" : "›"}</span>
                                <span className="en-ev-type-name">{type.name}</span>
                                <span className="en-ev-type-meta">
                                    {type.attributes.length + derived.length} attrs
                                </span>
                                {tally.applied ? (
                                    <span className="en-pill en-applied">✓ {tally.applied}</span>
                                ) : null}
                                {tally.staged ? (
                                    <span className="en-pill en-staged">+{tally.staged}</span>
                                ) : null}
                                {tally.removing ? (
                                    <span className="en-pill en-removing">−{tally.removing}</span>
                                ) : null}
                            </button>
                            {expanded ? (
                                <div className="en-ev-attrs">
                                    {type.attributes.map((attr) => (
                                        <div className="en-ev-attr" key={attr.name}>
                                            <span className="en-ev-attr-name">{attr.name}</span>
                                            <span className={`en-typetag en-ev-t-${attr.kind}`}>
                                                {attr.kind}
                                            </span>
                                        </div>
                                    ))}
                                    {derived.map((spec) => {
                                        const state = eventCellState(spec.column, applied, staging);
                                        return (
                                            <div
                                                className={`en-ev-attr en-${state}`}
                                                key={spec.column}
                                            >
                                                <span className="en-ev-attr-name">
                                                    {spec.column}
                                                </span>
                                                <span
                                                    className={`en-typetag${isGlyphEventKind(spec.kind) ? " en-glyph" : ""}`}
                                                >
                                                    {EVENT_KIND_TAG[spec.kind]}
                                                </span>
                                                <button
                                                    type="button"
                                                    className="en-col-x"
                                                    title={
                                                        state === "staged"
                                                            ? "Unstage"
                                                            : state === "removing"
                                                              ? "Keep this column"
                                                              : "Stage this column for removal"
                                                    }
                                                    onClick={() =>
                                                        state === "staged"
                                                            ? onUnstage(spec.column)
                                                            : onToggleRemove(spec.column)
                                                    }
                                                >
                                                    {state === "removing" ? "undo" : "×"}
                                                </button>
                                            </div>
                                        );
                                    })}
                                </div>
                            ) : null}
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
