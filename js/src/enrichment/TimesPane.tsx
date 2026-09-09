import { actionTitle, MiniButton, SearchBox } from "./atoms";
import { formatCount } from "./data";
import { cellState, timesSpec } from "./staging";
import type { ColState, StagingView } from "./staging";
import type { Activity, Spec } from "./types";

interface TimesPaneProps {
    activities: Activity[];
    view: StagingView;
    query: string;
    onQuery: (query: string) => void;
    onToggle: (spec: Spec) => void;
    onStageMany: (specs: Spec[]) => void;
    onUnstageAll: () => void;
    hasStaged: boolean;
}

/** What each cell says when it is not already telling you a state. */
const OFF_LABEL: Record<"start" | "end", string> = { start: "first", end: "last" };
const STATE_LABEL: Record<Exclude<ColState, "off">, string> = {
    applied: "applied",
    removing: "remove",
    staged: "staged",
};

export default function TimesPane({
    activities,
    view,
    query,
    onQuery,
    onToggle,
    onStageMany,
    onUnstageAll,
    hasStaged,
}: TimesPaneProps) {
    const needle = query.trim().toLowerCase();
    const visible = activities.filter((a) => a.name.toLowerCase().includes(needle));
    const offSpecs = (which: "start" | "end") =>
        visible
            .map((activity) => timesSpec(activity, which))
            .filter((spec) => cellState(spec.column, view) === "off");

    return (
        <div className="en-pane">
            <div className="en-pane-tools">
                <SearchBox value={query} onChange={onQuery} placeholder="filter activities…" />
                <MiniButton
                    onClick={() => onStageMany(offSpecs("start"))}
                    disabled={offSpecs("start").length === 0}
                >
                    All first
                </MiniButton>
                <MiniButton
                    onClick={() => onStageMany(offSpecs("end"))}
                    disabled={offSpecs("end").length === 0}
                >
                    All last
                </MiniButton>
                <MiniButton onClick={onUnstageAll} disabled={!hasStaged}>
                    Unstage added
                </MiniButton>
            </div>
            <div className="en-list">
                <div className="en-thead">
                    <span className="en-th-name">Activity</span>
                    <span className="en-th-cell">::start</span>
                    <span className="en-th-cell">::end</span>
                    <span className="en-th-freq">Events</span>
                </div>
                {visible.map((activity) => (
                    <div className="en-trow" key={activity.name}>
                        <span className="en-row-name">{activity.display}</span>
                        {(["start", "end"] as const).map((which) => {
                            const spec = timesSpec(activity, which);
                            const state = cellState(spec.column, view);
                            return (
                                <button
                                    type="button"
                                    key={which}
                                    className={`en-tcell en-${state}`}
                                    title={`${spec.column} — ${actionTitle(state)}`}
                                    onClick={() => onToggle(spec)}
                                >
                                    {state === "off" ? OFF_LABEL[which] : STATE_LABEL[state]}
                                </button>
                            );
                        })}
                        <span className="en-row-freq">{formatCount(activity.events)} ev</span>
                    </div>
                ))}
                {visible.length === 0 ? (
                    <div className="en-empty">no activity matches “{query}”</div>
                ) : null}
            </div>
        </div>
    );
}
