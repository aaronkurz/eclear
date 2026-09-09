import { Field, Note, Row, Segmented, Select, TextInput } from "./controls";
import { OP_LABELS } from "./copy";
import { numericAttrsOf } from "./staging";
import type { PaneProps } from "./paneProps";

const CONSTANT = "__const";

/** Arithmetic on two numeric attributes of one event.
 *
 *  Both operand pickers offer numeric attributes only, so a type mismatch is not
 *  something the user can configure and then be told about — the note says how
 *  many attributes that hides, because a picker that is quietly short is worse
 *  than one that explains itself.
 */
export default function ArithmeticPane({ catalog, columns, drafts, patch }: PaneProps) {
    const draft = drafts.arithmetic;
    const numeric = numericAttrsOf(draft.type, catalog, columns);
    const entry = catalog.eventTypes.find((type) => type.name === draft.type);
    const hidden = (entry?.attributes ?? []).filter((attr) => attr.kind !== "num");

    const changeType = (type: string) => {
        const attrs = numericAttrsOf(type, catalog, columns);
        patch("arithmetic", { type, left: attrs[0] ?? "", right: attrs[1] ?? null });
    };

    return (
        <>
            <Row>
                <Field label="Event type" width={180}>
                    <Select
                        mono
                        value={draft.type}
                        onChange={changeType}
                        options={catalog.eventTypes.map((type) => ({
                            value: type.name,
                            label: type.name,
                        }))}
                    />
                </Field>
                <Field label="Left operand" width={186}>
                    <Select
                        mono
                        value={draft.left}
                        onChange={(left) => patch("arithmetic", { left })}
                        options={numeric.map((name) => ({ value: name, label: name }))}
                    />
                </Field>
                <Field label="Operator">
                    <Segmented
                        mono
                        value={draft.op}
                        onChange={(op) => patch("arithmetic", { op })}
                        options={Object.entries(OP_LABELS).map(([value, label]) => ({
                            value,
                            label,
                        }))}
                    />
                </Field>
                <Field label="Right operand" width={186}>
                    <Select
                        mono
                        value={draft.right ?? CONSTANT}
                        onChange={(value) =>
                            patch("arithmetic", { right: value === CONSTANT ? null : value })
                        }
                        options={[
                            ...numeric
                                .filter((name) => name !== draft.left)
                                .map((name) => ({ value: name, label: name })),
                            { value: CONSTANT, label: "constant…" },
                        ]}
                    />
                </Field>
                {draft.right === null ? (
                    <Field label="Constant" width={110}>
                        <TextInput
                            mono
                            value={draft.constant}
                            onChange={(constant) => patch("arithmetic", { constant })}
                        />
                    </Field>
                ) : null}
            </Row>
            <Note tone="good">
                <strong>numeric operands only</strong>
                <span>
                    {hidden.length
                        ? `${hidden.length} non-numeric attribute${hidden.length === 1 ? "" : "s"} hidden from both pickers (${hidden
                              .slice(0, 3)
                              .map((attr) => attr.name)
                              .join(", ")}${hidden.length > 3 ? ", …" : ""}), so a type mismatch cannot be configured.`
                        : "This event type has no non-numeric attributes."}
                </span>
            </Note>
        </>
    );
}
