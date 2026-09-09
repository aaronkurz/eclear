import { addEdge, binCounts, intervalLabels, removeEdge, resolveLabels } from "./bins";
import { TIME_PART_EXAMPLES, TIME_PART_LABELS } from "./copy";
import { Field, Note, Row, Segmented, Select, TextInput } from "./controls";
import {
    effectiveBinEdges,
    numericAttrsOf,
    profileOf,
    requestedBins,
    timeColumnsOf,
} from "./staging";
import type { PaneProps } from "./paneProps";
import type { TimePart } from "./types";

const TIME_PARTS: TimePart[] = ["year", "month", "weekday", "hour"];

/** A column cut into labelled categories: numeric intervals, or a time part.
 *
 *  One category rather than two, because both modes produce the same thing —
 *  one categorical column cut from one source column — and the mode switch sits
 *  inside the pane so the choice reads as what it is: which *kind* of thing is
 *  being cut, not which enrichment is being built.
 */
export default function BinningPane({ catalog, columns, drafts, patch }: PaneProps) {
    const draft = drafts.binning;
    const numeric = numericAttrsOf(draft.type, catalog, columns);
    const times = timeColumnsOf(catalog, draft.type);

    const changeType = (type: string) => {
        const attrs = numericAttrsOf(type, catalog, columns);
        const stamps = timeColumnsOf(catalog, type);
        patch("binning", {
            type,
            source: attrs[0] ?? "",
            timeSource: stamps.includes(draft.timeSource) ? draft.timeSource : stamps[0] ?? "",
        });
    };

    return (
        <>
            <Row>
                <Field label="Event type" width={170}>
                    <Select
                        mono
                        value={draft.type}
                        onChange={changeType}
                        options={catalog.eventTypes.map((type) => ({
                            value: type.name,
                            label: type.name,
                        }))}
                    />
                </Field>
                <Field label="Cut">
                    <Segmented
                        value={draft.mode}
                        onChange={(mode) => patch("binning", { mode })}
                        options={[
                            { value: "numeric", label: "a number", title: "into intervals you choose" },
                            { value: "time", label: "a timestamp", title: "into one of its natural parts" },
                        ]}
                    />
                </Field>
            </Row>

            {draft.mode === "time" ? (
                <TimeMode
                    times={times}
                    source={draft.timeSource}
                    part={draft.part}
                    onSource={(timeSource) => patch("binning", { timeSource })}
                    onPart={(part) => patch("binning", { part })}
                />
            ) : (
                <NumericMode
                    catalog={catalog}
                    columns={columns}
                    drafts={drafts}
                    patch={patch}
                    numeric={numeric}
                />
            )}
        </>
    );
}

function TimeMode({
    times,
    source,
    part,
    onSource,
    onPart,
}: {
    times: string[];
    source: string;
    part: TimePart;
    onSource: (value: string) => void;
    onPart: (value: TimePart) => void;
}) {
    return (
        <>
            <Row>
                <Field label="Timestamp column" width={220}>
                    <Select
                        mono
                        value={source}
                        onChange={onSource}
                        options={times.map((name) => ({ value: name, label: name }))}
                    />
                </Field>
                <Field label="Part">
                    <Segmented
                        value={part}
                        onChange={onPart}
                        options={TIME_PARTS.map((value) => ({
                            value,
                            label: TIME_PART_LABELS[value],
                            title: TIME_PART_EXAMPLES[value],
                        }))}
                    />
                </Field>
                <Field label="Values" width={150}>
                    <span className="en-ev-hint en-ev-mono">{TIME_PART_EXAMPLES[part]}</span>
                </Field>
            </Row>
            <Note tone="good">
                <strong>every category exists</strong>
                <span>
                    The column carries all {part === "weekday" ? "seven weekdays" : part === "month" ? "twelve months" : part === "hour" ? "twenty-four hours" : "years between the earliest and the latest"}
                    , whether or not this log contains them — so a rule written against a preview
                    sample still reads on the full log. There is nothing else to configure.
                </span>
            </Note>
        </>
    );
}

function NumericMode({
    catalog,
    columns,
    drafts,
    patch,
    numeric,
}: PaneProps & { numeric: string[] }) {
    const draft = drafts.binning;
    const profile = profileOf(catalog, draft.type, draft.source);
    const edges = effectiveBinEdges(drafts, catalog);
    const labels = resolveLabels(draft.labels, edges.length);
    const intervals = intervalLabels(edges);
    const counts = profile ? binCounts(profile, edges) : edges.map(() => 0);
    const custom = draft.method === "custom";

    const setLabel = (index: number, value: string) => {
        const next = [...draft.labels];
        while (next.length <= index) next.push("");
        next[index] = value;
        patch("binning", { labels: next });
    };

    const commitDraft = () => {
        const value = parseFloat(draft.draft);
        if (Number.isNaN(value)) return;
        const next = addEdge(draft.edges, draft.labels, value);
        patch("binning", { edges: next.edges, labels: next.labels, draft: "" });
    };

    return (
        <>
            <Row>
                <Field label="Numeric column" width={186}>
                    <Select
                        mono
                        value={draft.source}
                        onChange={(source) => patch("binning", { source })}
                        options={numeric.map((name) => ({ value: name, label: name }))}
                    />
                </Field>
                <Field label="Method">
                    <Segmented
                        value={draft.method}
                        onChange={(method) => patch("binning", { method })}
                        options={[
                            { value: "equal", label: "equal width" },
                            { value: "quantile", label: "quantile" },
                            { value: "custom", label: "custom edges" },
                        ]}
                    />
                </Field>
                {custom ? null : (
                    <Field label="Bins" width={96}>
                        <TextInput
                            mono
                            value={draft.bins}
                            onChange={(bins) => patch("binning", { bins })}
                        />
                    </Field>
                )}
            </Row>

            <div className="en-ev-edges">
                <div className="en-ev-edges-head">
                    <span className="en-ev-field-label">Edges</span>
                    <span className="en-ev-range">
                        {profile
                            ? `observed range ${round(profile.min)} – ${round(profile.max)}`
                            : "no values on this event type"}
                    </span>
                    <span className="en-ev-edge-count">
                        {edgeSummary(edges, custom ? null : requestedBins(draft.bins), draft.source)}
                    </span>
                </div>

                <div className="en-ev-chips">
                    <span className="en-ev-bound">−∞</span>
                    {edges.map((edge, index) => (
                        <span className="en-ev-edge" key={index}>
                            <span className="en-ev-dash">—</span>
                            <span className="en-ev-chip">
                                {edge}
                                {custom ? (
                                    <button
                                        type="button"
                                        className="en-col-x"
                                        title="Remove this edge"
                                        onClick={() => {
                                            const next = removeEdge(
                                                draft.edges,
                                                draft.labels,
                                                index,
                                            );
                                            patch("binning", next);
                                        }}
                                    >
                                        ×
                                    </button>
                                ) : null}
                            </span>
                        </span>
                    ))}
                    <span className="en-ev-dash">—</span>
                    <span className="en-ev-bound">+∞</span>
                    {custom ? (
                        <span className="en-ev-add">
                            <TextInput
                                mono
                                width={78}
                                value={draft.draft}
                                onChange={(value) => patch("binning", { draft: value })}
                                onEnter={commitDraft}
                            />
                            <button type="button" className="en-primary" onClick={commitDraft}>
                                + Add
                            </button>
                            <span className="en-ev-hint">sorted automatically</span>
                        </span>
                    ) : null}
                </div>

                <div className="en-ev-bins">
                    <div className="en-ev-bins-head">Interval</div>
                    <div className="en-ev-bins-head">Label</div>
                    <div className="en-ev-bins-head en-ev-right" title="Estimated from a sketch of the column; the preview is exact.">
                        Events ≈
                    </div>
                    {intervals.map((interval, index) => (
                        <div className="en-ev-bin-row" key={index}>
                            <div className="en-ev-interval">{interval}</div>
                            <div>
                                <TextInput
                                    value={labels[index]}
                                    onChange={(value) => setLabel(index, value)}
                                />
                            </div>
                            <div className="en-ev-count">
                                {(counts[index] ?? 0).toLocaleString("en-US")}
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {profile && !edges.length && !custom ? (
                <Note tone="warn">
                    <strong>nothing to cut</strong>
                    <span>
                        Every {draft.source} on {draft.type} is{" "}
                        <span className="en-ev-mono">{round(profile.min)}</span>, so no edge
                        would put values on both sides of it. Pick another column, or switch
                        to custom edges if you want the cut anyway.
                    </span>
                </Note>
            ) : null}

            <Note tone="warn">
                <strong>categorical result</strong>
                <span>
                    The column holds a label, so on the case log it can only be tracked as latest,
                    count, append or is_unique. The outer edges are unbounded, so a missing input
                    stays missing rather than falling out of the last bin.
                </span>
            </Note>
        </>
    );
}

/** What the edge row adds up to, and where it fell short.
 *
 *  `requested` is the bin count a derived method asked for, or `null` in custom
 *  mode where the user places every edge themselves. A derived method that could
 *  not place that many says so here: a column whose values repeat cannot be cut
 *  as finely as the spinner allows, and a coarser column arriving unannounced is
 *  the thing that reads as a bug.
 */
function edgeSummary(edges: number[], requested: number | null, source: string): string {
    const bins = edges.length + 1;
    if (!edges.length) return requested === null ? "no edges yet" : "no cut possible";
    const got = `${edges.length} edge${edges.length === 1 ? "" : "s"} → ${bins} bins`;
    if (requested === null || bins >= requested) return got;
    return `${got} · ${source} repeats too much to cut ${requested} ways`;
}

function round(value: number): number {
    return Math.round(value * 100) / 100;
}
