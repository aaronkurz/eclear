import { actionTitle, Empty } from "./atoms";
import { METHOD_HINTS } from "./copy";
import { formatCount } from "./data";
import { cellState, trackingSpec } from "./staging";
import type { StagingView } from "./staging";
import type { Spec, TrackGroup } from "./types";

interface TrackingPaneProps {
    groups: TrackGroup[];
    methods: string[];
    allEvents: string;
    view: StagingView;
    onToggle: (spec: Spec) => void;
}

/** Attributes grouped by the event type that carries them.
 *
 *  The grouping is the whole point: an attribute recorded only at registration
 *  means something different from the same name recorded on every event, and
 *  the event type is in the column name for exactly that reason. Methods a
 *  given attribute's type cannot support are shown greyed rather than hidden,
 *  so the vocabulary stays the same everywhere.
 */
export default function TrackingPane({
    groups,
    methods,
    allEvents,
    view,
    onToggle,
}: TrackingPaneProps) {
    if (groups.length === 0) {
        return (
            <div className="en-pane">
                <Empty>This event log carries no attributes beyond its own case, time and activity columns.</Empty>
            </div>
        );
    }

    return (
        <div className="en-pane">
            <div className="en-list">
                {groups.map((group) => {
                    const tracked = group.attributes.reduce(
                        (total, attr) =>
                            total +
                            attr.methods.filter((method) => {
                                const state = cellState(
                                    trackingSpec(group.eventType, attr, method).column,
                                    view,
                                );
                                return state === "applied" || state === "staged";
                            }).length,
                        0,
                    );
                    return (
                        <div className="en-group" key={group.eventType}>
                            <div className="en-group-head">
                                <span className="en-kindtag en-kind-tracking">
                                    {group.eventType === allEvents ? "all" : "evt"}
                                </span>
                                <span className="en-group-name">{group.display}</span>
                                <span className="en-group-note">
                                    {formatCount(group.events)} events
                                    {group.eventType === allEvents ? " · every event type" : ""}
                                </span>
                                {tracked > 0 ? (
                                    <span className="en-pill en-applied">{tracked} tracked</span>
                                ) : null}
                            </div>
                            {group.attributes.map((attr) => {
                                const allowed = new Set(attr.methods);
                                return (
                                    <div className="en-attr" key={attr.attribute}>
                                        <div className="en-attr-head">
                                            <span className="en-attr-name">{attr.attribute}</span>
                                            <span
                                                className={`en-typetag ${attr.numeric ? "en-num" : "en-cat"}`}
                                            >
                                                {attr.numeric ? "numeric" : "categorical"}
                                            </span>
                                            <span className="en-attr-hint">
                                                {attr.columnPrefix}…
                                            </span>
                                        </div>
                                        <div className="en-methods">
                                            {methods.map((method) => {
                                                if (!allowed.has(method)) {
                                                    return (
                                                        <span
                                                            key={method}
                                                            className="en-method en-na"
                                                            title={`${method} needs a numeric attribute`}
                                                        >
                                                            {method}
                                                        </span>
                                                    );
                                                }
                                                const spec = trackingSpec(
                                                    group.eventType,
                                                    attr,
                                                    method,
                                                );
                                                const state = cellState(spec.column, view);
                                                return (
                                                    <button
                                                        type="button"
                                                        key={method}
                                                        className={`en-method en-${state}`}
                                                        title={`${spec.column} — ${METHOD_HINTS[method] ?? ""} · ${actionTitle(state)}`}
                                                        onClick={() => onToggle(spec)}
                                                    >
                                                        {method}
                                                    </button>
                                                );
                                            })}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
