import type { ReactNode } from "react";

/** The three controls every pane is built from.
 *
 *  A segmented control wherever the options are few and named, a select where
 *  they come from the log, a labelled field around either — so two panes
 *  configuring different things still read the same way.
 */

export function Field({
    label,
    width,
    children,
}: {
    label: string;
    width?: number;
    children: ReactNode;
}) {
    return (
        <label className="en-ev-field" style={width ? { width: `${width}px` } : undefined}>
            <span className="en-ev-field-label">{label}</span>
            {children}
        </label>
    );
}

export function Select({
    value,
    options,
    onChange,
    mono,
}: {
    value: string;
    options: { value: string; label: string }[];
    onChange: (value: string) => void;
    mono?: boolean;
}) {
    return (
        <select
            className={`en-ev-select${mono ? " en-ev-mono" : ""}`}
            value={value}
            onChange={(event) => onChange(event.target.value)}
        >
            {options.map((option) => (
                <option value={option.value} key={option.value}>
                    {option.label}
                </option>
            ))}
        </select>
    );
}

export function Segmented<T extends string>({
    value,
    options,
    onChange,
    mono,
}: {
    value: T;
    options: { value: T; label: string; title?: string }[];
    onChange: (value: T) => void;
    mono?: boolean;
}) {
    return (
        <span className={`en-ev-seg${mono ? " en-ev-mono" : ""}`}>
            {options.map((option) => (
                <button
                    type="button"
                    key={option.value}
                    title={option.title}
                    className={`en-ev-seg-item${option.value === value ? " en-on" : ""}`}
                    onClick={() => onChange(option.value)}
                >
                    {option.label}
                </button>
            ))}
        </span>
    );
}

export function TextInput({
    value,
    onChange,
    onEnter,
    width,
    mono,
}: {
    value: string;
    onChange: (value: string) => void;
    onEnter?: () => void;
    width?: number;
    mono?: boolean;
}) {
    return (
        <input
            className={`en-ev-input${mono ? " en-ev-mono" : ""}`}
            style={width ? { width: `${width}px` } : undefined}
            value={value}
            onChange={(event) => onChange(event.target.value)}
            onKeyDown={(event) => {
                if (event.key === "Enter" && onEnter) onEnter();
            }}
        />
    );
}

/** A row of fields. Wraps rather than scrolls: a pane is configured left to
 *  right, and a control pushed off the edge is a control nobody finds. */
export function Row({ children }: { children: ReactNode }) {
    return <div className="en-ev-row">{children}</div>;
}

export function Note({ tone, children }: { tone: "plain" | "warn" | "good"; children: ReactNode }) {
    return <div className={`en-ev-note en-ev-note-${tone}`}>{children}</div>;
}
