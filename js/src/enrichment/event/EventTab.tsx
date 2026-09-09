import { useMemo, useState } from "react";
import { InfoTip } from "../atoms";
import { formatCount } from "../data";
import ArithmeticPane from "./ArithmeticPane";
import BinningPane from "./BinningPane";
import DeltaPane from "./DeltaPane";
import EventColumnList from "./EventColumnList";
import EventRail from "./EventRail";
import EventSchemaRail from "./EventSchemaRail";
import RunningAggPane from "./RunningAggPane";
import { dtypeOf, formulaTextOf, warningOf } from "./describe";
import {
    EVENT_KIND_HINTS,
    EVENT_KIND_NOTES,
    EVENT_KIND_TAG,
    EVENT_KIND_USAGE,
    eventKindTagClass,
} from "./copy";
import { suggestColumn, uniqueName } from "./naming";
import {
    buildEventSpec,
    draftEventType,
    draftParams,
    effectiveBinEdges,
    eventCountsByKind,
    eventCountsFor,
    initialDrafts,
    stageBlocker,
    stageEvent,
    toggleEventRemove,
    unstageEvent,
} from "./staging";
import type { Drafts, EventCounts, EventStaging } from "./staging";
import type { EventCatalog, EventKind, EventSpec } from "./types";

interface EventTabProps {
    catalog: EventCatalog;
    applied: EventSpec[];
    staging: EventStaging;
    onStagingChange: (staging: EventStaging) => void;
    counts: EventCounts;
    blocked: { column: string; used_by: string[] }[] | null;
    onDismissBlocked: () => void;
    baseColumnCount: number;
}

const PANES: Record<EventKind, typeof ArithmeticPane> = {
    binning: BinningPane,
    arithmetic: ArithmeticPane,
    delta: DeltaPane,
    running_agg: RunningAggPane,
};

/** Derive a column on the event log itself: pick a category, configure it, name
 *  it, stage it.
 *
 *  The drafts live here rather than in the panes, so switching category and
 *  coming back does not lose a half-built configuration — and so the name, the
 *  summary line and the stage button can all read the same draft the pane is
 *  editing.
 */
export default function EventTab({
    catalog,
    applied,
    staging,
    onStagingChange,
    counts,
    blocked,
    onDismissBlocked,
    baseColumnCount,
}: EventTabProps) {
    const [active, setActive] = useState<EventKind>("binning");
    const [drafts, setDrafts] = useState<Drafts>(() => initialDrafts(catalog));

    const columns = useMemo(
        () => [
            ...applied.filter((spec) => !staging.remove.includes(spec.column)),
            ...staging.add,
        ],
        [applied, staging],
    );
    const tallies = useMemo(() => eventCountsByKind(applied, staging), [applied, staging]);

    // Editing any control clears the name the *suggestion* filled in, so the
    // name keeps following the configuration until the user takes it over.
    const patch = <K extends keyof Omit<Drafts, "names">>(key: K, value: Partial<Drafts[K]>) =>
        setDrafts((prev) => ({
            ...prev,
            [key]: { ...prev[key], ...value },
            names: { ...prev.names, [key]: "" },
        }));

    const edges = effectiveBinEdges(drafts, catalog);
    const params = draftParams(active, drafts, edges);
    const taken = useMemo(
        () => new Set([...catalog.columns, ...applied.map((s) => s.column), ...staging.add.map((s) => s.column)]),
        [catalog.columns, applied, staging.add],
    );
    const suggested = uniqueName(suggestColumn(active, params), taken);
    const name = drafts.names[active] || suggested;
    const eventType = draftEventType(active, drafts, catalog.allEvents);
    const scoped = eventType !== catalog.allEvents;
    const typeEntry = catalog.eventTypes.find((type) => type.name === eventType);

    const blocker = stageBlocker(active, drafts, edges, name, taken);
    const warning = warningOf(active, params);
    const Pane = PANES[active];
    const label = catalog.kinds.find((kind) => kind.key === active)?.label ?? "";

    const stage = () => {
        if (blocker) return;
        onStagingChange(
            stageEvent(staging, buildEventSpec(active, drafts, edges, name, catalog.allEvents)),
        );
        setDrafts((prev) => ({ ...prev, names: { ...prev.names, [active]: "" } }));
    };

    return (
        <>
            {blocked?.length ? (
                <div className="en-ev-blocked">
                    <strong>Cannot remove</strong>
                    <span>
                        {blocked
                            .map(
                                (entry) =>
                                    `${entry.column} is read by ${entry.used_by.join(", ")}`,
                            )
                            .join("; ")}
                        . Remove those columns first.
                    </span>
                    <button type="button" className="en-mini" onClick={onDismissBlocked}>
                        Dismiss
                    </button>
                </div>
            ) : null}

            <div className="en-body">
                <EventRail
                    kinds={catalog.kinds}
                    groups={catalog.kindGroups}
                    active={active}
                    onSelect={setActive}
                    tallies={tallies}
                />

                <div className="en-config en-ev-config">
                    <div className="en-config-head">
                        <div className="en-config-titles">
                            <span className="en-config-title">{label}</span>
                            <InfoTip label={`About ${label}`}>
                                <strong>What it computes</strong>
                                <p>{EVENT_KIND_NOTES[active]}</p>
                                <strong>How to use it</strong>
                                <p>{EVENT_KIND_USAGE[active]}</p>
                            </InfoTip>
                        </div>
                        <span className="en-config-hint">{EVENT_KIND_HINTS[active]}</span>
                    </div>

                    <div className="en-ev-builder">
                        <div className="en-ev-builder-head">
                            <span className={eventKindTagClass(active)}>
                                {EVENT_KIND_TAG[active]}
                            </span>
                            <span className="en-ev-scope">
                                {scoped ? eventType : "all event types"}
                            </span>
                            <span className="en-ev-scope-meta">
                                {scoped && typeEntry
                                    ? `${formatCount(typeEntry.events)} events · ${typeEntry.attributes.filter((a) => a.kind === "num").length} numeric attributes`
                                    : "written at every event position"}
                            </span>
                        </div>

                        <div className="en-ev-builder-body">
                            <Pane
                                catalog={catalog}
                                columns={columns}
                                drafts={drafts}
                                patch={patch}
                            />

                            <div className="en-ev-name-row">
                                <label className="en-ev-field" style={{ width: "320px" }}>
                                    <span className="en-ev-field-label">Column name</span>
                                    <input
                                        className="en-ev-input en-ev-mono"
                                        value={name}
                                        onChange={(event) =>
                                            setDrafts((prev) => ({
                                                ...prev,
                                                names: {
                                                    ...prev.names,
                                                    [active]: event.target.value,
                                                },
                                            }))
                                        }
                                    />
                                </label>
                                <span className="en-ev-stage">
                                    {blocker ? (
                                        <span className="en-error-inline">{blocker}</span>
                                    ) : null}
                                    <button
                                        type="button"
                                        className="en-primary"
                                        onClick={stage}
                                        disabled={Boolean(blocker)}
                                    >
                                        Stage column
                                    </button>
                                </span>
                            </div>

                            <div className="en-ev-summary">
                                <span className="en-ev-formula">
                                    {formulaTextOf(active, params)}
                                </span>
                                <span className="en-ev-target">
                                    {scoped ? eventType : "every event"}.{name}
                                </span>
                                <span className="en-ev-dtype">
                                    {dtypeOf(active, params)} ·{" "}
                                    {scoped && typeEntry
                                        ? `written on ${formatCount(typeEntry.events)} events`
                                        : "written on every event"}
                                </span>
                            </div>

                            {warning ? (
                                <div className="en-warn">
                                    <strong>{warning.title}</strong>
                                    <span>{warning.text}</span>
                                </div>
                            ) : null}
                        </div>
                    </div>

                    <div className="en-ev-list-title">{label} columns on this log</div>
                    <EventColumnList
                        columns={columns
                            .concat(
                                applied.filter(
                                    (spec) =>
                                        staging.remove.includes(spec.column) &&
                                        spec.kind === active,
                                ),
                            )
                            .filter(
                                (spec, index, all) =>
                                    spec.kind === active &&
                                    all.findIndex((other) => other.column === spec.column) === index,
                            )}
                        applied={applied}
                        staging={staging}
                        allEvents={catalog.allEvents}
                        onToggleRemove={(column) =>
                            onStagingChange(toggleEventRemove(staging, column))
                        }
                        onUnstage={(column) => onStagingChange(unstageEvent(staging, column))}
                    />
                </div>

                <EventSchemaRail
                    catalog={catalog}
                    applied={applied}
                    staging={staging}
                    counts={eventCountsFor(baseColumnCount, applied, staging)}
                    onToggleRemove={(column) =>
                        onStagingChange(toggleEventRemove(staging, column))
                    }
                    onUnstage={(column) => onStagingChange(unstageEvent(staging, column))}
                />
            </div>
        </>
    );
}
