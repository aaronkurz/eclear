# eclear

Event and case log enrichment widget for Python notebooks.

`eclear` sits between loading an event log and analysing it. It derives new
columns on the event log (binning, arithmetic, time deltas, running
aggregations) and folds the event log into a case log (activity counts,
first/last occurrence, delays, attribute tracking) — through a widget, so the
columns are chosen by clicking rather than by writing another `groupby`.

Every applied column records the spec that produced it on the frame's `attrs`,
so an enriched log carries its own provenance and can be replayed.

```bash
pip install eclear
```

## Use

Hand it an event log and the three column names that identify its axes:

```python
from eclear import EnrichmentWidget

enricher = EnrichmentWidget(
    event_log,
    case_id_col="case:concept:name",
    time_col="time:timestamp",
    activity_col="concept:name",
)
enricher
```

Stage the enrichments you want in the widget, preview them on a handful of real
cases, then apply. Two frames come back out:

```python
enricher.event_log   # the enriched event log
enricher.case_log    # the case log folded out of it
```

Both are ordinary pandas DataFrames — adjust either by hand afterwards.

In a reactive notebook (marimo), pass `on_apply` so downstream cells re-run when
the user applies:

```python
enricher = EnrichmentWidget(event_log, ..., on_apply=lambda: set_applied(True))
```

### How staging works

Enrichments are staged, not applied on click. Staging is free — it costs a chip
in the schema rail and nothing else — so you can assemble a whole batch, see
what it would do to the schema, preview the values, and only then pay for the
computation over the full log. Removals stage the same way, which is what makes
an over-enriched log recoverable without starting over.

Applying recomputes rather than patches: the surviving specs are re-applied to a
fresh base log. Both `apply_specs` and `apply_event_specs` are idempotent, so
this is cheap insurance against a column drifting out of step with the spec that
claims to have produced it.

An applied *event* column becomes a source the *case* tab can track, which is
also why removing one can be refused.

## Requirements

Python 3.13+, and pandas 3. The engine itself needs nothing but pandas and
numpy; the widget adds `anywidget` and `traitlets`. Rendering needs a notebook
that speaks anywidget — marimo, Jupyter, VS Code.

## Development

```bash
uv sync
uv run pytest
```

The frontend is React + TypeScript, bundled with esbuild:

```bash
cd js
npm install
npm run build      # writes ../eclear/static/enrichment.js
npm test           # vitest
npm run typecheck
```

`eclear/static/enrichment.js` is **committed on purpose**. It is what the widget
loads at import, so installing from PyPI needs no Node toolchain. Rebuild and
commit it whenever the frontend changes.

### Cross-language contracts

Three functions are written twice, once in Python and once in TypeScript.
`eclear/contracts/*.json` holds tables asserted by *both* suites, so a change to
one half fails on the other. Python is the reference: a spec is stored on the
frame and replayed through Python, so Python's answer is the one that has to
survive. See [`eclear/contracts/README.md`](eclear/contracts/README.md).

### Implementation notes

- `enrichment/enrichers.py` folds `append` with `groupby.apply(list)` rather
  than `agg(list)`. On pandas 3 the latter tries to fit the list back into the
  column's own dtype and raises on a categorical, which is what every binning
  enrichment produces. Pinned by `test_tracking_a_categorical_column`.
- Two tests assert that a missing-activity column is a timedelta without pinning
  its resolution: pandas infers that from the log's timestamps and changed it
  between 2.x (`ns`) and 3.x (`us`).

## License

GNU Affero General Public License v3.0 or later — see [LICENSE](LICENSE).
