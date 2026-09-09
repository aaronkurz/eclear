import { formatCount } from "../data";
import { EVENT_KIND_TAG } from "./copy";
import type { EventPreviewResult } from "./types";

interface EventPreviewModalProps {
    result: EventPreviewResult | null;
    pending: boolean;
    scope: string;
    onScope: (scope: string) => void;
    onResample: () => void;
    onClose: () => void;
}

/** Real values on a handful of real cases, in sequence.
 *
 *  Grouped by case and ordered in time, because every event enrichment is
 *  defined relative to its neighbours — a column of values with the sequence
 *  taken away cannot be checked against anything.
 */
export default function EventPreviewModal({
    result,
    pending,
    scope,
    onScope,
    onResample,
    onClose,
}: EventPreviewModalProps) {
    const columns = result?.columns ?? [];
    const rows = result?.rows ?? [];
    const width = 4 + columns.length;

    return (
        <div className="en-overlay" role="dialog" aria-label="Sample events">
            <div className="en-modal">
                <div className="en-modal-head">
                    <span className="en-modal-title">Sample events</span>
                    <span className="en-modal-meta">
                        {result?.ok
                            ? `${columns.length} column${columns.length === 1 ? "" : "s"} on ${formatCount(result.events ?? 0)} events from ${formatCount(result.sampled ?? 0)} cases`
                            : pending
                              ? "computing…"
                              : "no preview"}
                    </span>
                    <div className="en-modal-actions">
                        <span className="en-ev-seg">
                            {[
                                { value: "touching", label: "cases touching staged types" },
                                { value: "any", label: "any case" },
                            ].map((option) => (
                                <button
                                    type="button"
                                    key={option.value}
                                    className={`en-ev-seg-item${option.value === scope ? " en-on" : ""}`}
                                    onClick={() => onScope(option.value)}
                                >
                                    {option.label}
                                </button>
                            ))}
                        </span>
                        <button
                            type="button"
                            className="en-mini"
                            onClick={onResample}
                            disabled={pending}
                        >
                            Resample
                        </button>
                        <button type="button" className="en-dark" onClick={onClose}>
                            Close
                        </button>
                    </div>
                </div>
                <div className="en-modal-body">
                    {result && result.ok === false ? (
                        <div className="en-error">{result.error ?? "preview failed"}</div>
                    ) : (
                        <table className="en-table">
                            <thead>
                                <tr>
                                    <th>case</th>
                                    <th>#</th>
                                    <th>activity</th>
                                    <th>timestamp</th>
                                    {columns.map((column) => (
                                        <th className={`en-${column.state}`} key={column.name}>
                                            <span className={`en-dot en-${column.state}`} />
                                            {EVENT_KIND_TAG[column.kind]} {column.name}
                                        </th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {rows.map((row, rowIndex) =>
                                    row.group ? (
                                        // eslint-disable-next-line react/no-array-index-key
                                        <tr className="en-ev-group" key={`g${rowIndex}`}>
                                            <td colSpan={width}>
                                                {row.case} · {row.events} events
                                            </td>
                                        </tr>
                                    ) : (
                                        // eslint-disable-next-line react/no-array-index-key
                                        <tr key={rowIndex}>
                                            <td>{row.case}</td>
                                            <td className="en-ev-dim">{row.index}</td>
                                            <td>{row.activity}</td>
                                            <td className="en-ev-dim">{row.timestamp}</td>
                                            {columns.map((column, index) => {
                                                const value = row.values?.[index] ?? null;
                                                const missing =
                                                    value === "NaN" || value === "NaT" || value === "None";
                                                return (
                                                    <td
                                                        key={column.name}
                                                        className={
                                                            value === null
                                                                ? "en-ev-na"
                                                                : missing
                                                                  ? "en-ev-missing"
                                                                  : `en-${column.state}`
                                                        }
                                                    >
                                                        {value ?? "—"}
                                                    </td>
                                                );
                                            })}
                                        </tr>
                                    ),
                                )}
                            </tbody>
                        </table>
                    )}
                </div>
                <div className="en-modal-foot">
                    <span>
                        Computed on this sample only — applying recomputes over all{" "}
                        {formatCount(result?.total_events ?? 0)} events. Rows are grouped by
                        case: a value is only ever derived from its own case&apos;s events, never
                        the ones across the rule above it.{" "}
                        <span className="en-ev-na">—</span> means the column does not apply to
                        that event type; <span className="en-ev-missing">NaT</span> or{" "}
                        <span className="en-ev-missing">NaN</span> means it applies and came out
                        missing — for a time delta, that the event has no such neighbour in its
                        case.
                    </span>
                </div>
            </div>
        </div>
    );
}
