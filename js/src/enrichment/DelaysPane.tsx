import { useState } from "react";
import { actionTitle } from "./atoms";
import { cellState, delaySpec } from "./staging";
import type { StagingView } from "./staging";
import type { Activity, Spec } from "./types";

interface DelaysPaneProps {
    activities: Activity[];
    view: StagingView;
    applied: Spec[];
    staged: Spec[];
    onToggle: (spec: Spec) => void;
}

export default function DelaysPane({
    activities,
    view,
    applied,
    staged,
    onToggle,
}: DelaysPaneProps) {
    const [from, setFrom] = useState(activities[0]?.name ?? "");
    const [to, setTo] = useState(activities[1]?.name ?? activities[0]?.name ?? "");

    const fromActivity = activities.find((a) => a.name === from);
    const toActivity = activities.find((a) => a.name === to);
    const pending = fromActivity && toActivity ? delaySpec(fromActivity, toActivity) : null;
    const pendingState = pending ? cellState(pending.column, view) : "off";
    const canAdd = Boolean(pending) && from !== to && pendingState === "off";

    // Every pair is n·(n−1) columns and the user only ever wants a handful, so
    // the count of what "all pairs" would cost is stated rather than offered.
    const pairCount = activities.length * (activities.length - 1);

    const chips = [...applied, ...staged];
    const hint = pairHint(from, to, pendingState);

    return (
        <div className="en-pane">
            <div className="en-pair">
                <label className="en-field">
                    <span className="en-field-label">From</span>
                    <select value={from} onChange={(e) => setFrom(e.target.value)}>
                        {activities.map((a) => (
                            <option key={a.name} value={a.name}>
                                {a.name}
                            </option>
                        ))}
                    </select>
                </label>
                <span className="en-arrow">→</span>
                <label className="en-field">
                    <span className="en-field-label">To</span>
                    <select value={to} onChange={(e) => setTo(e.target.value)}>
                        {activities.map((a) => (
                            <option key={a.name} value={a.name}>
                                {a.name}
                            </option>
                        ))}
                    </select>
                </label>
                <button
                    type="button"
                    className="en-primary en-small"
                    disabled={!canAdd}
                    onClick={() => pending && onToggle(pending)}
                >
                    Add pair
                </button>
            </div>
            {pairCount > 40 ? (
                <div className="en-warn">
                    All pairs would add {pairCount} columns — pick the ones you care about.
                </div>
            ) : null}
            <div className="en-pane-sub">Delay columns</div>
            <div className="en-chips en-chips-grow">
                {chips.map((spec) => {
                    const state = cellState(spec.column, view);
                    return (
                        <button
                            type="button"
                            key={spec.column}
                            className={`en-chip en-clickable en-${state}`}
                            title={`${spec.column} — ${actionTitle(state)}`}
                            onClick={() => onToggle(spec)}
                        >
                            <span className={`en-dot en-${state}`} />
                            {spec.activity} → {spec.activityTo}
                            {state === "removing" ? <span className="en-chip-note">remove</span> : null}
                            {state === "staged" ? <span className="en-chip-note">add</span> : null}
                        </button>
                    );
                })}
                {chips.length === 0 ? <span className="en-empty">no delay columns yet</span> : null}
            </div>
            {hint ? <div className="en-pane-foot">{hint}</div> : null}
        </div>
    );
}

/** Only speaks up when the chosen pair cannot be added as-is — the ordinary
 *  "adding a pair stages it right away" lives in the pane's info tip. */
function pairHint(from: string, to: string, state: string): string | null {
    if (from === to) return "pick two different activities";
    if (state === "applied" || state === "removing")
        return "that pair is already applied — click its chip to stage a removal";
    if (state === "staged") return "that pair is already staged";
    return null;
}
