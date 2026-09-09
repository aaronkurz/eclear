import { formatCount } from "./data";
import type { StagingCounts, StagingView } from "./staging";
import { cellState } from "./staging";
import type { Spec } from "./types";

interface SchemaRailProps {
    baseColumns: string[];
    applied: Spec[];
    staged: Spec[];
    view: StagingView;
    counts: StagingCounts;
    onToggleRemove: (column: string) => void;
    onUnstage: (column: string) => void;
}

/** The case log's schema, and what applying would do to it.
 *
 *  This is the only place the whole schema is visible at once, so it doubles as
 *  the undo surface: every column carries the control that reverses whatever
 *  was done to it, without having to find the pane it was staged from.
 */
export default function SchemaRail({
    baseColumns,
    applied,
    staged,
    view,
    counts,
    onToggleRemove,
    onUnstage,
}: SchemaRailProps) {
    const delta: string[] = [];
    if (counts.staged) delta.push(`+${counts.staged}`);
    if (counts.removing) delta.push(`−${counts.removing}`);

    return (
        <div className="en-rail-right">
            <div className="en-rail-title">Case log schema</div>
            <div className="en-schema-head">
                <span className="en-schema-n">{formatCount(counts.live)}</span>
                <span className="en-schema-unit">columns</span>
                <span className={`en-delta${counts.dirty ? " en-dirty" : ""}`}>
                    {counts.dirty ? `${delta.join(" / ")} staged` : "in sync"}
                </span>
            </div>
            <div className="en-schema-body">
                <Group label="Always present" dot="base" count={`${baseColumns.length}`}>
                    {baseColumns.map((column) => (
                        <div className="en-col en-base" key={column}>
                            <span className="en-col-name">{column}</span>
                        </div>
                    ))}
                </Group>
                <Group
                    label="Applied"
                    dot="applied"
                    count={`${counts.applied - counts.removing} live · ${counts.removing} staged out`}
                >
                    {applied.map((spec) => {
                        const state = cellState(spec.column, view);
                        return (
                            <div className={`en-col en-${state}`} key={spec.column}>
                                <span className="en-col-name">{spec.column}</span>
                                <button
                                    type="button"
                                    className="en-col-x"
                                    title={
                                        state === "removing"
                                            ? "Keep this column"
                                            : "Stage this column for removal"
                                    }
                                    onClick={() => onToggleRemove(spec.column)}
                                >
                                    {state === "removing" ? "undo" : "×"}
                                </button>
                            </div>
                        );
                    })}
                    {applied.length === 0 ? <span className="en-col-none">nothing yet</span> : null}
                </Group>
                {staged.length > 0 ? (
                    <Group label="Staged to add" dot="staged" count={`${staged.length}`}>
                        {staged.map((spec) => (
                            <div className="en-col en-staged" key={spec.column}>
                                <span className="en-col-name">{spec.column}</span>
                                <button
                                    type="button"
                                    className="en-col-x"
                                    title="Unstage"
                                    onClick={() => onUnstage(spec.column)}
                                >
                                    ×
                                </button>
                            </div>
                        ))}
                    </Group>
                ) : null}
            </div>
        </div>
    );
}

function Group({
    label,
    dot,
    count,
    children,
}: {
    label: string;
    dot: string;
    count: string;
    children: React.ReactNode;
}) {
    return (
        <div className="en-schema-group">
            <div className="en-schema-group-head">
                <span className={`en-dot en-${dot}`} />
                <span className="en-schema-group-label">{label}</span>
                <span className="en-schema-group-count">{count}</span>
            </div>
            {children}
        </div>
    );
}
