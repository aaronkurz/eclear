import type { ReactNode } from "react";
import type { ColState } from "./staging";

/** The glyph each state shows in a checkbox-sized box. */
const STATE_MARK: Record<ColState, string> = {
    applied: "✓",
    removing: "×",
    staged: "+",
    off: "",
};

const STATE_TAG: Record<ColState, string> = {
    applied: "applied",
    removing: "− remove",
    staged: "+ add",
    off: "",
};

/** What a click does from here, for the native tooltip on an interactive cell. */
const ACTION_TITLE: Record<ColState, string> = {
    applied: "click to stage a removal",
    removing: "click to keep the column",
    staged: "click to unstage",
    off: "click to stage",
};

export function actionTitle(state: ColState): string {
    return ACTION_TITLE[state];
}

export function StateBox({ state }: { state: ColState }) {
    return <span className={`en-box en-${state}`}>{STATE_MARK[state]}</span>;
}

export function StateTag({ state }: { state: ColState }) {
    if (state === "off") return null;
    return <span className={`en-tag en-${state}`}>{STATE_TAG[state]}</span>;
}

export function SearchBox({
    value,
    onChange,
    placeholder,
}: {
    value: string;
    onChange: (value: string) => void;
    placeholder: string;
}) {
    return (
        <input
            className="en-search"
            type="search"
            value={value}
            placeholder={placeholder}
            onChange={(e) => onChange(e.target.value)}
        />
    );
}

export function MiniButton({
    onClick,
    disabled,
    title,
    children,
}: {
    onClick: () => void;
    disabled?: boolean;
    title?: string;
    children: ReactNode;
}) {
    return (
        <button type="button" className="en-mini" onClick={onClick} disabled={disabled} title={title}>
            {children}
        </button>
    );
}

/** Reference copy behind a hover: the pane keeps its title and one hint line,
 *  and everything that is true but not needed at every glance lives in here. */
export function InfoTip({ label, children }: { label: string; children: ReactNode }) {
    return (
        <span className="en-info">
            <button type="button" className="en-info-btn" aria-label={label}>
                i
            </button>
            <span className="en-info-pop" role="tooltip">
                {children}
            </span>
        </span>
    );
}

export function Empty({ children }: { children: ReactNode }) {
    return <div className="en-empty">{children}</div>;
}
