# Cross-language contracts

Tables read by *both* test suites, so a function and its twin in the other language
cannot drift apart without a test failing.

| fixture | Python side | TypeScript side |
|---|---|---|
| `naming.json` | `suggest_column`, `slug` (`event_specs.py`) | `suggestColumn`, `slug` (`event/naming.ts`) |
| `params.json` | `validate_event_spec` + `apply_event_specs` | `draftParams` (`event/staging.ts`) |
| `rejections.json` | `validate_event_spec` (`event_specs.py`) | `stageBlocker` (`event/EventTab.tsx`) |

Python is the reference in every case: a spec is stored on the frame and replayed
through Python, so Python's answer is the one that has to survive. When the two
disagree, change the TypeScript.

Both suites reach these files by a relative path from their own location: pytest
from `tests/`, vitest from `js/src/enrichment/event/`. Moving either suite means
fixing its path.

Adding a row is the cheapest way to pin a behaviour: it costs one line and is asserted
on both sides.
