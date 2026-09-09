import { formatCount } from "../data";
import { Field, Note, Row, Segmented, Select } from "./controls";
import type { PaneProps } from "./paneProps";

/** Gap to a neighbouring event in the same case.
 *
 *  Since previous and until next differ only in which neighbour is read, which
 *  is why direction is a control here rather than two categories that would
 *  otherwise be identical twice over.
 */
export default function DeltaPane({ catalog, drafts, patch }: PaneProps) {
    const draft = drafts.delta;
    const typeOptions = catalog.eventTypes.map((type) => ({ value: type.name, label: type.name }));
    const entry = catalog.eventTypes.find((type) => type.name === draft.type);

    return (
        <>
        <Row>
            <Field label="Event type" width={180}>
                <Select
                    mono
                    value={draft.type}
                    onChange={(type) => patch("delta", { type })}
                    options={typeOptions}
                />
            </Field>
            <Field label="Direction">
                <Segmented
                    value={draft.direction}
                    onChange={(direction) => patch("delta", { direction })}
                    options={[
                        { value: "prev", label: "← since previous" },
                        { value: "next", label: "until next →" },
                    ]}
                />
            </Field>
            <Field label="Neighbour">
                <Segmented
                    value={draft.neighbour}
                    onChange={(neighbour) => patch("delta", { neighbour })}
                    options={[
                        { value: "any", label: "any event" },
                        { value: "same", label: "same type" },
                        { value: "type", label: "chosen type" },
                    ]}
                />
            </Field>
            {draft.neighbour === "type" ? (
                <Field label="Neighbour type" width={170}>
                    <Select
                        mono
                        value={draft.neighbourType}
                        onChange={(neighbourType) => patch("delta", { neighbourType })}
                        options={typeOptions}
                    />
                </Field>
            ) : null}
            <Field label="Unit">
                <Segmented
                    mono
                    value={draft.unit}
                    onChange={(unit) => patch("delta", { unit })}
                    options={[
                        { value: "timedelta", label: "timedelta" },
                        { value: "min", label: "min" },
                        { value: "hours", label: "hours" },
                        { value: "days", label: "days" },
                    ]}
                />
            </Field>
            <Field label="No neighbour">
                <Segmented
                    mono
                    value={draft.missing}
                    onChange={(missing) => patch("delta", { missing })}
                    options={[
                        { value: "NaT", label: "NaT", title: "leave it missing" },
                        { value: "zero", label: "0", title: "write a zero gap" },
                    ]}
                />
            </Field>
        </Row>
        <NeighbourNote
            type={draft.type}
            events={entry?.events ?? 0}
            coverage={
                draft.direction === "prev"
                    ? entry?.neighbours.prev ?? 0
                    : entry?.neighbours.next ?? 0
            }
            direction={draft.direction}
            missing={draft.missing}
            exact={draft.neighbour === "any"}
        />
        </>
    );
}

/** What the chosen event type and direction will actually yield.
 *
 *  A gap needs a neighbour, and an event type that is always first in its case
 *  has no previous one — the column comes out empty, correctly and silently.
 *  Saying so here is the difference between "this enrichment is broken" and
 *  "this enrichment does not apply to this event type", which is a distinction
 *  the values alone cannot make.
 *
 *  The catalog counts *any* neighbour, so for the same-type and chosen-type
 *  rules this is an upper bound and says so. A 0% upper bound still rules the
 *  stricter rules out, which is the case worth warning about.
 */
function NeighbourNote({
    type,
    events,
    coverage,
    direction,
    missing,
    exact,
}: {
    type: string;
    events: number;
    coverage: number;
    direction: "prev" | "next";
    missing: string;
    exact: boolean;
}) {
    const side = direction === "prev" ? "previous" : "next";
    const other = direction === "prev" ? "until next →" : "← since previous";

    if (coverage === 0) {
        return (
            <Note tone="warn">
                <strong>this column would be empty</strong>
                <span>
                    No <span className="en-ev-mono">{type}</span> event has a {side} event
                    in its case, so the gap is undefined on all {formatCount(events)} of
                    them. Try <strong>{other}</strong>, or another event type.
                </span>
            </Note>
        );
    }
    if (exact && coverage >= 1) return null;

    const percent = Math.round(coverage * 100);
    return (
        <Note tone="plain">
            <strong>{exact ? "" : "at most "}{percent}% have a {side} event</strong>
            <span>
                The rest of <span className="en-ev-mono">{type}</span>&apos;s{" "}
                {formatCount(events)} events get{" "}
                <span className="en-ev-mono">{missing === "zero" ? "0" : "NaT"}</span>
                {exact
                    ? "."
                    : " — and fewer will have one once the neighbour rule narrows it further."}
            </span>
        </Note>
    );
}
