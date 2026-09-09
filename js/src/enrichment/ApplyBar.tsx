import type { StagingCounts } from "./staging";

interface ApplyBarProps {
    counts: { staged: number; removing: number; dirty: boolean } | StagingCounts;
    applying: boolean;
    error: string | null;
    toast: string | null;
    /** What applying this tab does *not* do, which is the part a user cannot
     *  see from the schema. */
    note: string;
    previewLabel: string;
    onDiscard: () => void;
    onPreview: () => void;
    onApply: () => void;
}

export default function ApplyBar({
    counts,
    applying,
    error,
    toast,
    note,
    previewLabel,
    onDiscard,
    onPreview,
    onApply,
}: ApplyBarProps) {
    const delta: string[] = [];
    if (counts.staged) delta.push(`+${counts.staged}`);
    if (counts.removing) delta.push(`−${counts.removing}`);

    return (
        <div className="en-applybar">
            <span className={`en-pending${counts.dirty ? " en-dirty" : ""}`}>
                {counts.dirty ? `${delta.join(" / ")} columns staged` : "no staged changes"}
            </span>
            <span className="en-applybar-note">{note}</span>
            {error ? <span className="en-error-inline">{error}</span> : null}
            {toast && !error ? <span className="en-toast">{toast}</span> : null}
            <div className="en-applybar-actions">
                <button
                    type="button"
                    className="en-mini"
                    onClick={onDiscard}
                    disabled={!counts.dirty || applying}
                >
                    Discard staged
                </button>
                <button type="button" className="en-mini" onClick={onPreview} disabled={applying}>
                    {previewLabel}
                </button>
                <button
                    type="button"
                    className="en-primary"
                    onClick={onApply}
                    disabled={!counts.dirty || applying}
                >
                    {applying ? "Applying…" : "Apply enrichments"}
                </button>
            </div>
        </div>
    );
}
