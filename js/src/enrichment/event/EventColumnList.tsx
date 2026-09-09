import { summaryOf } from "./describe";
import { eventCellState } from "./staging";
import type { EventStaging } from "./staging";
import type { EventSpec } from "./types";

interface EventColumnListProps {
    columns: EventSpec[];
    applied: EventSpec[];
    staging: EventStaging;
    allEvents: string;
    onToggleRemove: (column: string) => void;
    onUnstage: (column: string) => void;
}

/** Every column this category has produced, in one of the four states. */
export default function EventColumnList({
    columns,
    applied,
    staging,
    allEvents,
    onToggleRemove,
    onUnstage,
}: EventColumnListProps) {
    if (!columns.length) {
        return <div className="en-empty">Nothing configured in this category yet.</div>;
    }
    return (
        <div className="en-ev-list">
            {columns.map((spec) => {
                const state = eventCellState(spec.column, applied, staging);
                return (
                    <div className={`en-ev-list-row en-${state}`} key={spec.column}>
                        <span className={`en-box en-${state}`}>
                            {state === "removing" ? "×" : state === "staged" ? "+" : "✓"}
                        </span>
                        <span className="en-ev-list-name">
                            {(spec.eventType ?? allEvents) === allEvents
                                ? "event"
                                : spec.eventType}
                            .{spec.column}
                        </span>
                        <span className="en-ev-list-summary">{summaryOf(spec)}</span>
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
                                state === "staged" ? onUnstage(spec.column) : onToggleRemove(spec.column)
                            }
                        >
                            {state === "removing" ? "undo" : "×"}
                        </button>
                    </div>
                );
            })}
        </div>
    );
}
