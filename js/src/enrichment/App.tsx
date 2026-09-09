import { useMemo, useState } from "react";
import styles from "./styles.css";
import ApplyBar from "./ApplyBar";
import BasePane from "./BasePane";
import CatalogRail from "./CatalogRail";
import CountsPane from "./CountsPane";
import DelaysPane from "./DelaysPane";
import PreviewModal from "./PreviewModal";
import SchemaRail from "./SchemaRail";
import TimesPane from "./TimesPane";
import TrackingPane from "./TrackingPane";
import { InfoTip } from "./atoms";
import { KIND_HINTS, KIND_NOTES, KIND_USAGE, STATE_LEGEND } from "./copy";
import { formatCount } from "./data";
import EventPreviewModal from "./event/EventPreviewModal";
import EventTab from "./event/EventTab";
import { eventCountsFor } from "./event/staging";
import type { EventStaging } from "./event/staging";
import type { EventCatalog, EventPreviewResult, EventSpec } from "./event/types";
import {
    buildView,
    countsByKind,
    countsFor,
    stage,
    toggleRemove,
    toggleSpec,
    unstage,
    unstageKind,
} from "./staging";
import type { Staging } from "./staging";
import type { Catalog, Kind, LogSummary, PreviewResult, Spec } from "./types";

export type Tab = "event" | "case";

/** Everything one tab needs to stage, preview and apply. The two tabs are
 *  independent all the way down — separate staging, separate request cycle,
 *  separate error — so a failure on one cannot clear the other's work. */
interface Side<Staged, Preview> {
    staging: Staged;
    onStagingChange: (staging: Staged) => void;
    applying: boolean;
    error: string | null;
    toast: string | null;
    onApply: () => void;
    preview: Preview | null;
    previewPending: boolean;
    onPreview: () => void;
    previewOpen: boolean;
    onClosePreview: () => void;
}

export interface CaseSide extends Side<Staging, PreviewResult> {
    catalog: Catalog;
    applied: Spec[];
}

export interface EventSide extends Side<EventStaging, EventPreviewResult> {
    catalog: EventCatalog;
    applied: EventSpec[];
    baseColumnCount: number;
    blocked: { column: string; used_by: string[] }[] | null;
    onDismissBlocked: () => void;
    previewScope: string;
    onPreviewScope: (scope: string) => void;
}

interface AppProps {
    title: string;
    summary: LogSummary;
    caseSide: CaseSide;
    eventSide: EventSide;
}

export default function App({ title, summary, caseSide, eventSide }: AppProps) {
    const [tab, setTab] = useState<Tab>("event");
    const [active, setActive] = useState<Kind>("counts");
    const [query, setQuery] = useState("");

    const view = useMemo(
        () => buildView(caseSide.applied, caseSide.staging),
        [caseSide.applied, caseSide.staging],
    );
    const caseCounts = useMemo(
        () => countsFor(caseSide.catalog.baseColumns, caseSide.applied, caseSide.staging),
        [caseSide.catalog.baseColumns, caseSide.applied, caseSide.staging],
    );
    const eventCounts = useMemo(
        () => eventCountsFor(eventSide.baseColumnCount, eventSide.applied, eventSide.staging),
        [eventSide.baseColumnCount, eventSide.applied, eventSide.staging],
    );
    const tallies = useMemo(
        () => countsByKind(caseSide.applied, caseSide.staging),
        [caseSide.applied, caseSide.staging],
    );

    const side = tab === "event" ? eventSide : caseSide;
    const counts = tab === "event" ? eventCounts : caseCounts;

    // Staged work belongs to the tab it was staged on: applying is one request
    // per side, so letting the user wander off with changes pending would leave
    // them staged behind a tab they can no longer see the apply bar for.
    const locked = tab === "event" ? eventCounts.dirty : caseCounts.dirty;
    const lockReason = locked
        ? `Apply or discard the ${counts.staged + counts.removing} staged change${
              counts.staged + counts.removing === 1 ? "" : "s"
          } on the ${tab} log before switching tab.`
        : "";

    const activeLabel = caseSide.catalog.kinds.find((kind) => kind.key === active)?.label ?? "";
    const stagedOfKind = (kind: Kind) => caseSide.staging.add.some((spec) => spec.kind === kind);
    const byKind = (specs: Spec[], kind: Kind) => specs.filter((spec) => spec.kind === kind);
    const toggle = (spec: Spec) =>
        caseSide.onStagingChange(toggleSpec(caseSide.staging, spec, view));
    const stageMany = (specs: Spec[]) =>
        caseSide.onStagingChange(stage(caseSide.staging, specs, view));

    return (
        <>
            <style>{styles}</style>
            <div className="en-root">
                <div className="en-header">
                    <span className="en-title">{title}</span>
                    <span className="en-tabs">
                        {(["event", "case"] as Tab[]).map((key) => {
                            const disabled = locked && key !== tab;
                            return (
                                <button
                                    type="button"
                                    key={key}
                                    className={`en-tab${key === tab ? " en-on" : ""}`}
                                    title={disabled ? lockReason : ""}
                                    disabled={disabled}
                                    onClick={() => setTab(key)}
                                >
                                    {key === "event" ? "Event log" : "Case log"}
                                </button>
                            );
                        })}
                    </span>
                    {locked ? (
                        <span className="en-lock" title={lockReason}>
                            tab locked
                        </span>
                    ) : null}
                    <span className="en-counts">
                        {formatCount(summary.cases)} cases · {formatCount(summary.events)} events ·{" "}
                        {formatCount(summary.activities)} event types
                    </span>
                    <span className="en-legend">
                        {STATE_LEGEND.map((entry) => (
                            <span className="en-legend-item" key={entry.key}>
                                <span className={`en-dot en-${entry.key}`} />
                                {entry.label}
                            </span>
                        ))}
                    </span>
                </div>

                {tab === "event" ? (
                    <EventTab
                        catalog={eventSide.catalog}
                        applied={eventSide.applied}
                        staging={eventSide.staging}
                        onStagingChange={eventSide.onStagingChange}
                        counts={eventCounts}
                        blocked={eventSide.blocked}
                        onDismissBlocked={eventSide.onDismissBlocked}
                        baseColumnCount={eventSide.baseColumnCount}
                    />
                ) : (
                    <div className="en-body">
                        <CatalogRail
                            kinds={caseSide.catalog.kinds}
                            active={active}
                            onSelect={setActive}
                            tallies={tallies}
                            baseColumnCount={caseSide.catalog.baseColumns.length}
                        />

                        <div className="en-config">
                            <div className="en-config-head">
                                <div className="en-config-titles">
                                    <span className="en-config-title">{activeLabel}</span>
                                    <InfoTip label={`About ${activeLabel}`}>
                                        <strong>What it computes</strong>
                                        <p>{KIND_NOTES[active]}</p>
                                        <strong>How to use it</strong>
                                        <p>{KIND_USAGE[active]}</p>
                                    </InfoTip>
                                </div>
                                <span className="en-config-hint">{KIND_HINTS[active]}</span>
                            </div>

                            {active === "base" ? (
                                <BasePane columns={caseSide.catalog.baseColumns} />
                            ) : null}
                            {active === "counts" ? (
                                <CountsPane
                                    activities={caseSide.catalog.activities}
                                    view={view}
                                    query={query}
                                    onQuery={setQuery}
                                    onToggle={toggle}
                                    onStageMany={stageMany}
                                    onUnstageAll={() =>
                                        caseSide.onStagingChange(
                                            unstageKind(caseSide.staging, "counts"),
                                        )
                                    }
                                    hasStaged={stagedOfKind("counts")}
                                />
                            ) : null}
                            {active === "times" ? (
                                <TimesPane
                                    activities={caseSide.catalog.activities}
                                    view={view}
                                    query={query}
                                    onQuery={setQuery}
                                    onToggle={toggle}
                                    onStageMany={stageMany}
                                    onUnstageAll={() =>
                                        caseSide.onStagingChange(
                                            unstageKind(caseSide.staging, "times"),
                                        )
                                    }
                                    hasStaged={stagedOfKind("times")}
                                />
                            ) : null}
                            {active === "delays" ? (
                                <DelaysPane
                                    activities={caseSide.catalog.activities}
                                    view={view}
                                    applied={byKind(caseSide.applied, "delays")}
                                    staged={byKind(caseSide.staging.add, "delays")}
                                    onToggle={toggle}
                                />
                            ) : null}
                            {active === "tracking" ? (
                                <TrackingPane
                                    groups={caseSide.catalog.trackGroups}
                                    methods={caseSide.catalog.trackMethods}
                                    allEvents={caseSide.catalog.allEvents}
                                    view={view}
                                    onToggle={toggle}
                                />
                            ) : null}
                        </div>

                        <SchemaRail
                            baseColumns={caseSide.catalog.baseColumns}
                            applied={caseSide.applied}
                            staged={caseSide.staging.add}
                            view={view}
                            counts={caseCounts}
                            onToggleRemove={(column) =>
                                caseSide.onStagingChange(toggleRemove(caseSide.staging, column))
                            }
                            onUnstage={(column) =>
                                caseSide.onStagingChange(unstage(caseSide.staging, [column]))
                            }
                        />
                    </div>
                )}

                <ApplyBar
                    counts={counts}
                    applying={side.applying}
                    error={side.error}
                    toast={side.toast}
                    note={
                        tab === "event"
                            ? "Case columns are not recomputed on apply."
                            : "Case columns are computed from the applied event log."
                    }
                    previewLabel={
                        tab === "event" ? "Preview sample events" : "Preview sample cases"
                    }
                    onDiscard={() =>
                        tab === "event"
                            ? eventSide.onStagingChange({ add: [], remove: [] })
                            : caseSide.onStagingChange({ add: [], remove: [] })
                    }
                    onPreview={side.onPreview}
                    onApply={side.onApply}
                />

                {caseSide.previewOpen ? (
                    <PreviewModal
                        result={caseSide.preview}
                        pending={caseSide.previewPending}
                        onResample={caseSide.onPreview}
                        onClose={caseSide.onClosePreview}
                    />
                ) : null}
                {eventSide.previewOpen ? (
                    <EventPreviewModal
                        result={eventSide.preview}
                        pending={eventSide.previewPending}
                        scope={eventSide.previewScope}
                        onScope={eventSide.onPreviewScope}
                        onResample={eventSide.onPreview}
                        onClose={eventSide.onClosePreview}
                    />
                ) : null}
            </div>
        </>
    );
}
