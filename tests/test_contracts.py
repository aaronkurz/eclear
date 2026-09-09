"""The contracts the frontend and Python have to keep between them.

Three functions on each side are twins: they are written twice, once in Python
and once in TypeScript, and nothing but a test stops them drifting. Each table
below lives in ``eclear/contracts/`` and is asserted by *both* suites --
here, and in the matching ``*.test.ts`` -- so a change to one half fails on the
other.

Python is the reference. A spec is stored on the frame and replayed through
Python, so Python's answer is the one that has to survive; when the two
disagree, the TypeScript is what changes.

Adding a row to a table is the cheapest way to pin a behaviour: one line, checked
on both sides.
"""
import json
import pathlib

import pytest

from eclear.enrichment import (
    EventEnrichmentSpec,
    apply_event_specs,
    arithmetic_spec,
    binning_spec,
    slug,
    suggest_column,
    time_binning_spec,
    validate_event_spec,
)

CONTRACTS = pathlib.Path(__file__).parent.parent / 'eclear' / 'contracts'

#: The shape of the log the wire-format and rejection cases are written against;
#: mirrors ``catalogOf`` in ``staging.test.ts``.
TYPES = ['Treat', 'Check']
NUMERIC = ['dose', 'reading']
TIMES = ['time:timestamp', 'sampled_at']


def load(name: str) -> dict:
    return json.loads((CONTRACTS / f'{name}.json').read_text(encoding='utf-8'))


def resolve_labels(labels, edge_count: int) -> list:
    """The frontend's `resolveLabels`, which runs before Python ever sees a spec.

    Reproduced rather than imported: it belongs to the pane, and what reaches
    Python is its *output*. A contract case that names only some bins has to
    arrive here filled in the same way the widget would fill it.
    """
    labels = list(labels or [])
    return [labels[index] if index < len(labels) and str(labels[index]).strip()
            else f'bin_{index + 1}'
            for index in range(edge_count + 1)]


# ----------------------------------------------------------------------
# naming
# ----------------------------------------------------------------------
NAMING = load('naming')


@pytest.mark.parametrize('row', NAMING['columns'],
                         ids=[f"{r['kind']}-{r['expected']}" for r in NAMING['columns']])
def test_the_suggested_name_matches_the_frontend(row):
    assert suggest_column(row['kind'], row['params']) == row['expected']


@pytest.mark.parametrize('row', NAMING['slugs'],
                         ids=[r['input'] or 'empty' for r in NAMING['slugs']])
def test_the_slug_matches_the_frontend(row):
    assert slug(row['input']) == row['expected']


def test_the_slug_keeps_non_ascii_letters():
    """``str.isalnum()`` is Unicode-aware, and the frontend's character class has
    to be too -- an ASCII-only one turned ``Ünïcode`` into ``n_code``."""
    assert slug('Ünïcode') == 'Ünïcode'
    assert slug('città') == 'città'


# ----------------------------------------------------------------------
# the wire format
# ----------------------------------------------------------------------
PARAMS = load('params')


def spec_of(row) -> EventEnrichmentSpec:
    """A spec carrying the frontend's params *verbatim*, which is the point:
    Python reads ``spec.params`` as given rather than translating it."""
    return EventEnrichmentSpec(kind=row['kind'], column=row['column'],
                               event_type=row['event_type'], params=row['params'])


@pytest.mark.parametrize('row', PARAMS['cases'], ids=[r['name'] for r in PARAMS['cases']])
def test_what_the_frontend_sends_is_a_spec_python_accepts(row):
    reason = validate_event_spec(spec_of(row), [], TYPES, NUMERIC, TIMES)
    assert reason is None, f'{row["name"]}: {reason}'


@pytest.mark.parametrize('row', PARAMS['cases'], ids=[r['name'] for r in PARAMS['cases']])
def test_what_the_frontend_sends_materializes_a_column(row, contract_event_log):
    """The round trip that matters: a payload the pane would emit, applied to a
    real frame. A key renamed on either side lands here as a ``KeyError``."""
    result = apply_event_specs(contract_event_log, [spec_of(row)])
    assert row['column'] in result.columns
    assert len(result) == len(contract_event_log)


def test_every_kind_is_covered_by_the_wire_format_table():
    """A new enrichment kind must arrive with its params pinned, or this table
    stops describing the wire format."""
    from eclear.enrichment import EVENT_KINDS  # pylint: disable=import-outside-toplevel
    assert {row['kind'] for row in PARAMS['cases']} == set(EVENT_KINDS)


# ----------------------------------------------------------------------
# what cannot be staged
# ----------------------------------------------------------------------
REJECTIONS = load('rejections')


def rejection_spec(row) -> EventEnrichmentSpec:
    """Build the spec a rejection scenario describes, the way the pane would."""
    draft, kind = row['draft'], row['kind']
    if kind == 'binning' and draft.get('mode') == 'time':
        return time_binning_spec(row['column'], draft['type'], draft['timeSource'],
                                 draft['part'])
    if kind == 'binning':
        edges = row['edges']
        return binning_spec(row['column'], draft['type'], draft['source'], edges,
                            resolve_labels(draft.get('labels'), len(edges)),
                            draft.get('method', 'custom'))
    if kind == 'arithmetic':
        right = draft.get('right')
        constant = None
        if right is None:
            try:
                constant = float(draft['constant'])
            except (TypeError, ValueError):
                constant = float('nan')
        return arithmetic_spec(row['column'], draft['type'], draft['left'],
                               draft['op'], right=right, constant=constant)
    raise AssertionError(f'no adapter for kind {kind!r}')


@pytest.mark.parametrize('row', REJECTIONS['cases'], ids=[r['name'] for r in REJECTIONS['cases']])
def test_the_backstop_agrees_with_the_stage_button(row):
    reason = validate_event_spec(rejection_spec(row), list(row['taken']), TYPES,
                                 NUMERIC, TIMES)
    expected = row['python']
    if expected is None:
        assert reason is None, f'{row["name"]}: unexpectedly rejected with {reason!r}'
    else:
        assert reason is not None and expected in reason, \
            f'{row["name"]}: expected {expected!r}, got {reason!r}'


def test_a_rejection_row_states_both_sides():
    """Neither side may go quiet on a case without the table recording that it
    did -- an accepted case is `null`, never a missing key."""
    for row in REJECTIONS['cases']:
        assert 'python' in row and 'ts' in row, row['name']
