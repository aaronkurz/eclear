import { actionTitle, MiniButton, SearchBox, StateBox, StateTag } from "./atoms";
import { formatCount } from "./data";
import { cellState, countsSpec } from "./staging";
import type { StagingView } from "./staging";
import type { Activity, Spec } from "./types";

interface CountsPaneProps {
    activities: Activity[];
    view: StagingView;
    query: string;
    onQuery: (query: string) => void;
    onToggle: (spec: Spec) => void;
    onStageMany: (specs: Spec[]) => void;
    onUnstageAll: () => void;
    hasStaged: boolean;
}

export default function CountsPane({
    activities,
    view,
    query,
    onQuery,
    onToggle,
    onStageMany,
    onUnstageAll,
    hasStaged,
}: CountsPaneProps) {
    const needle = query.trim().toLowerCase();
    const visible = activities.filter((a) => a.name.toLowerCase().includes(needle));
    const missing = visible
        .map(countsSpec)
        .filter((spec) => cellState(spec.column, view) === "off");

    return (
        <div className="en-pane">
            <div className="en-pane-tools">
                <SearchBox value={query} onChange={onQuery} placeholder="filter activities…" />
                <MiniButton onClick={() => onStageMany(missing)} disabled={missing.length === 0}>
                    Stage all missing
                </MiniButton>
                <MiniButton onClick={onUnstageAll} disabled={!hasStaged}>
                    Unstage added
                </MiniButton>
            </div>
            <div className="en-list">
                {visible.map((activity) => {
                    const spec = countsSpec(activity);
                    const state = cellState(spec.column, view);
                    return (
                        <button
                            type="button"
                            key={activity.name}
                            className={`en-row en-${state}`}
                            title={actionTitle(state)}
                            onClick={() => onToggle(spec)}
                        >
                            <StateBox state={state} />
                            <span className="en-row-name">{spec.column}</span>
                            <StateTag state={state} />
                            <span className="en-row-freq">{formatCount(activity.events)} ev</span>
                        </button>
                    );
                })}
                {visible.length === 0 ? (
                    <div className="en-empty">no activity matches “{query}”</div>
                ) : null}
            </div>
        </div>
    );
}
