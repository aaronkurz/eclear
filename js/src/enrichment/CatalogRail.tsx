import type { Kind, KindEntry } from "./types";

/** Short tag per kind, so the rail reads at a glance.
 *
 *  A picture where the kind has one -- a flag for where an activity starts and
 *  ends, two joined dots for the gap between two of them, a list for the values
 *  an attribute took -- and a mono abbreviation where it does not. */
const KIND_TAG: Record<Kind, string> = {
    base: "base",
    counts: "cnt",
    times: "⚑",
    delays: "•–•",
    tracking: "☰",
};

/** Glyph fonts are not monospaced and 9.5px turns a flag into a smudge, so these
 *  take `.en-glyph`: same box height, larger and proportional type. */
const GLYPH_KINDS = new Set<Kind>(["times", "delays", "tracking"]);

interface CatalogRailProps {
    kinds: KindEntry[];
    active: Kind;
    onSelect: (kind: Kind) => void;
    tallies: Record<string, { applied: number; staged: number; removing: number }>;
    baseColumnCount: number;
}

export default function CatalogRail({
    kinds,
    active,
    onSelect,
    tallies,
    baseColumnCount,
}: CatalogRailProps) {
    return (
        <div className="en-rail-left">
            <div className="en-rail-title">Enrichments</div>
            {kinds.map((kind) => {
                const tally = tallies[kind.key] ?? { applied: 0, staged: 0, removing: 0 };
                // The base columns are not specs, so they never appear in the
                // tally — count them here or the one section that is always
                // populated would read as empty.
                const applied = kind.key === "base" ? baseColumnCount : tally.applied;
                const empty = applied + tally.staged + tally.removing === 0;
                return (
                    <button
                        type="button"
                        key={kind.key}
                        className={`en-rail-item${kind.key === active ? " en-on" : ""}`}
                        onClick={() => onSelect(kind.key)}
                    >
                        <span className="en-rail-head">
                            <span
                                className={`en-kindtag en-kind-${kind.key}${GLYPH_KINDS.has(kind.key) ? " en-glyph" : ""}`}
                            >
                                {KIND_TAG[kind.key]}
                            </span>
                            <span className="en-rail-name">{kind.label}</span>
                        </span>
                        <span className="en-rail-tallies">
                            {applied > 0 ? (
                                <span className="en-pill en-applied">✓ {applied}</span>
                            ) : null}
                            {tally.staged > 0 ? (
                                <span className="en-pill en-staged">+{tally.staged}</span>
                            ) : null}
                            {tally.removing > 0 ? (
                                <span className="en-pill en-removing">−{tally.removing}</span>
                            ) : null}
                            {empty ? <span className="en-rail-none">not configured</span> : null}
                        </span>
                    </button>
                );
            })}
        </div>
    );
}
