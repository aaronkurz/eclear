import type { Drafts } from "./staging";
import type { EventCatalog, EventSpec } from "./types";

/** What every builder pane needs: the log's shape, the columns already in play,
 *  and the draft it is editing. Panes hold no state of their own — the tab owns
 *  the drafts so switching category and coming back does not lose a half-built
 *  configuration. */
export interface PaneProps {
    catalog: EventCatalog;
    /** Applied columns not staged for removal, plus staged ones: what a new
     *  column may read, and what its name must not collide with. */
    columns: EventSpec[];
    drafts: Drafts;
    patch: <K extends "binning" | "arithmetic" | "delta" | "running_agg">(
        key: K,
        value: Partial<Drafts[K]>,
    ) => void;
}
