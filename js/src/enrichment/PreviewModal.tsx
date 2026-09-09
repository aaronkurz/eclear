import { useState } from "react";
import { formatCount } from "./data";
import { STATE_LEGEND } from "./copy";
import type { PreviewResult } from "./types";

interface PreviewModalProps {
    result: PreviewResult | null;
    pending: boolean;
    onResample: () => void;
    onClose: () => void;
}

/** Real values on a handful of real cases.
 *
 *  The sample is computed by the same enrichers that would run on apply, so
 *  what shows here is what the column will hold — including which flavour of
 *  missing it uses, which is the thing a schema listing cannot tell you.
 */
export default function PreviewModal({
    result,
    pending,
    onResample,
    onClose,
}: PreviewModalProps) {
    // Hiding a state narrows a preview that is often far wider than the panel.
    const [hidden, setHidden] = useState<Set<string>>(new Set());
    const toggle = (key: string) =>
        setHidden((prev) => {
            const next = new Set(prev);
            if (next.has(key)) next.delete(key);
            else next.add(key);
            return next;
        });

    const columns = result?.columns ?? [];
    const rows = result?.rows ?? [];
    const shown = columns
        .map((column, index) => ({ column, index }))
        .filter(({ column }) => !hidden.has(column.state));

    return (
        <div className="en-overlay" role="dialog" aria-label="Sample cases">
            <div className="en-modal">
                <div className="en-modal-head">
                    <span className="en-modal-title">Sample cases</span>
                    <span className="en-modal-meta">
                        {result?.ok
                            ? `${formatCount(result.sampled ?? 0)} of ${formatCount(
                                  result.total_cases ?? 0,
                              )} cases · ${shown.length} columns`
                            : pending
                              ? "computing…"
                              : "no preview"}
                    </span>
                    <div className="en-modal-actions">
                        <button type="button" className="en-mini" onClick={onResample} disabled={pending}>
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
                                    {shown.map(({ column }) => (
                                        <th className={`en-${column.state}`} key={column.name}>
                                            <span className={`en-dot en-${column.state}`} />
                                            {column.name}
                                        </th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {rows.map((row, rowIndex) => (
                                    // eslint-disable-next-line react/no-array-index-key
                                    <tr key={rowIndex}>
                                        {shown.map(({ column, index }) => (
                                            <td className={`en-${column.state}`} key={column.name}>
                                                {row[index] ?? ""}
                                            </td>
                                        ))}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}
                </div>
                <div className="en-modal-foot">
                    <span>
                        Values are computed on this sample only — applying recomputes over all{" "}
                        {formatCount(result?.total_events ?? 0)} events.
                    </span>
                    <span className="en-legend">
                        {STATE_LEGEND.map((entry) => (
                            <button
                                type="button"
                                key={entry.key}
                                className={`en-legend-item${hidden.has(entry.key) ? " en-off" : ""}`}
                                title="click to show or hide these columns"
                                onClick={() => toggle(entry.key)}
                            >
                                <span className={`en-dot en-${entry.key}`} />
                                {entry.label}
                            </button>
                        ))}
                    </span>
                </div>
            </div>
        </div>
    );
}
