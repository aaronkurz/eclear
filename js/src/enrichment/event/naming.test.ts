import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { normalizeOp, slug, suggestColumn, uniqueName } from "./naming";
import type { EventKind } from "./types";

/** The shared table, also read by `tests/test_contracts.py`. Both sides assert
 *  the same rows, so `suggestColumn` and `suggest_column` cannot drift without
 *  one of the two suites failing. */
const contract = JSON.parse(
    readFileSync(new URL("../../../../eclear/contracts/naming.json", import.meta.url), "utf8"),
) as {
    columns: { kind: string; params: Record<string, unknown>; expected: string }[];
    slugs: { input: string; expected: string }[];
};

describe("suggestColumn matches Python's suggest_column", () => {
    for (const row of contract.columns) {
        it(`${row.kind}: ${row.expected}`, () => {
            expect(suggestColumn(row.kind as EventKind, row.params)).toBe(row.expected);
        });
    }
});

describe("slug matches Python's slug", () => {
    for (const row of contract.slugs) {
        it(`${JSON.stringify(row.input)} → ${JSON.stringify(row.expected)}`, () => {
            expect(slug(row.input)).toBe(row.expected);
        });
    }

    it("keeps non-ASCII letters, the way str.isalnum() does", () => {
        // The divergence this table was written for: an ASCII-only character
        // class turned `Ünïcode` into `n_code` while Python left it alone.
        expect(slug("Ünïcode")).toBe("Ünïcode");
        expect(slug("Prüfung")).toBe("Prüfung");
    });
});

describe("normalizeOp", () => {
    it("folds the typographic operators the widget renders", () => {
        expect(["−", "–", "×", "÷"].map(normalizeOp)).toEqual(["-", "-", "*", "/"]);
    });

    it("leaves an ASCII operator alone", () => {
        expect(["+", "-", "*", "/"].map(normalizeOp)).toEqual(["+", "-", "*", "/"]);
    });

    it("passes an operator it does not know through untouched", () => {
        expect(normalizeOp("%")).toBe("%");
    });
});

describe("uniqueName", () => {
    it("leaves a free name alone", () => {
        expect(uniqueName("dose_level", new Set())).toBe("dose_level");
        expect(uniqueName("dose_level", new Set(["other"]))).toBe("dose_level");
    });

    it("walks past every taken suffix rather than reusing one", () => {
        const taken = new Set(["gap", "gap_2", "gap_3"]);
        expect(uniqueName("gap", taken)).toBe("gap_4");
    });

    it("starts at _2, since the bare name is the first", () => {
        expect(uniqueName("gap", new Set(["gap"]))).toBe("gap_2");
    });

    it("returns an empty base untouched, for the caller to reject", () => {
        expect(uniqueName("", new Set(["a"]))).toBe("");
    });
});
