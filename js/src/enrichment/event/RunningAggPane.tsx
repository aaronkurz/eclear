import { Field, Note, Row, Segmented, Select } from "./controls";
import { CARRYLESS_AGGREGATES, logNumericColumns } from "./staging";
import type { PaneProps } from "./paneProps";

const AGGREGATES = [
    { value: "cumsum", label: "cumulative sum" },
    { value: "count", label: "count" },
    { value: "runmax", label: "running max" },
    { value: "runmin", label: "running min" },
    { value: "ffill", label: "forward fill" },
];

/** One numeric column aggregated along each case, on every event.
 *
 *  The only category written on every event type rather than one, which is why
 *  it has no event-type picker: the running value is a property of the case's
 *  history at that point, not of the event that happens to sit there.
 */
export default function RunningAggPane({ catalog, columns, drafts, patch }: PaneProps) {
    const draft = drafts.running_agg;
    const sources = logNumericColumns(catalog, columns);
    // Forward fill *is* carrying, and a 0 written between minima would read as a
    // new low — so the control is hidden rather than offered and then ignored.
    const carryable = !CARRYLESS_AGGREGATES.has(draft.aggregate);

    return (
        <>
            <Row>
                <Field label="Numeric column" width={200}>
                    <Select
                        mono
                        value={draft.source}
                        onChange={(source) => patch("running_agg", { source })}
                        options={sources.map((name) => ({ value: name, label: name }))}
                    />
                </Field>
                <Field label="Aggregate">
                    <Segmented
                        value={draft.aggregate}
                        onChange={(aggregate) => patch("running_agg", { aggregate })}
                        options={AGGREGATES}
                    />
                </Field>
                {carryable ? (
                    <Field label="Between occurrences">
                        <Segmented
                            value={draft.carry}
                            onChange={(carry) => patch("running_agg", { carry })}
                            options={[
                                { value: "carry", label: "carry value forward" },
                                { value: "zero", label: "0 between" },
                            ]}
                        />
                    </Field>
                ) : null}
            </Row>
            <Note tone="plain">
                <span>{describe(draft.aggregate, draft.carry, draft.source)}</span>
            </Note>
        </>
    );
}

function describe(aggregate: string, carry: string, source: string): string {
    if (aggregate === "ffill") {
        return (
            `Every event carries the last ${source} value seen in the case so far. Events before ` +
            `the first one stay NaN — there is no last value yet, and 0 would be a reading nobody took.`
        );
    }
    if (aggregate === "runmin") {
        return (
            `Every event carries the smallest ${source} seen in the case so far. Events before the ` +
            `first value stay NaN rather than 0, which would be a minimum no event reported.`
        );
    }
    const carried =
        carry === "carry"
            ? `Every event carries the value reached so far, including events of types that never hold ${source}.`
            : `Only events that hold a ${source} value carry it; every other row is 0.`;
    return `${carried} A case without a single ${source} value stays 0 throughout.`;
}
