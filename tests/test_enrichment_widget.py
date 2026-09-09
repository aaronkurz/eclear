"""Tests for the enrichment widget's Python side.

The widget's logic lives entirely in its trait observers, so it can be driven
without a kernel: instantiate it, assign a request trait, read the result. The
guards against marimo's double-application of frontend state are asserted here
too -- a replayed request has to be a no-op, not a second apply.
"""
import pandas as pd
import pytest

from eclear.enrichment import (
    arithmetic_spec,
    binning_spec,
    counts_spec,
    delay_spec,
    delta_spec,
    provenance_of,
    running_agg_spec,
    time_binning_spec,
    times_spec,
    tracking_spec,
)
from eclear import EnrichmentWidget


@pytest.fixture
def widget(event_log) -> EnrichmentWidget:
    return EnrichmentWidget(event_log, initial_specs=[counts_spec('Pay')])


def columns_of(widget: EnrichmentWidget) -> list:
    return [spec['column'] for spec in widget.applied]


# ----------------------------------------------------------------------
# construction
# ----------------------------------------------------------------------
def test_starts_from_the_initial_specs(widget):
    assert columns_of(widget) == ['Pay::count']
    assert 'Pay::count' in widget.case_log.columns


def test_event_log_gains_relative_times(widget):
    assert 'rel_time' in widget.event_log.columns
    assert 'rel_log_time' in widget.event_log.columns


def test_the_source_event_log_is_left_alone(event_log):
    EnrichmentWidget(event_log)
    assert 'rel_time' not in event_log.columns


def test_case_log_is_a_copy(widget):
    """A notebook cell adjusting the case log must not disturb the widget."""
    case_log = widget.case_log
    case_log['case_outcome'] = True
    assert 'case_outcome' not in widget.case_log.columns


def test_catalog_describes_the_log(widget):
    catalog = widget.catalog
    assert catalog['base_columns'] == ['start_time', 'end_time', 'no_of_events', 'duration']
    assert [kind['key'] for kind in catalog['kinds']] == [
        'base', 'counts', 'times', 'delays', 'tracking']
    assert {activity['name'] for activity in catalog['activities']} == {
        'Register', 'Pay', 'Close'}
    assert widget.log_summary['cases'] == 3
    assert widget.log_summary['events'] == 10


# ----------------------------------------------------------------------
# apply
# ----------------------------------------------------------------------
def test_apply_adds_and_removes(widget):
    widget.apply_request = {
        'add': [times_spec('Pay', 'end').to_dict(), delay_spec('Register', 'Close').to_dict()],
        'remove': ['Pay::count'],
        'request_id': 1,
    }

    assert widget.apply_result['ok'] is True
    assert widget.apply_result['added'] == ['Pay::end', 'Register:Close::delay']
    assert widget.apply_result['removed'] == ['Pay::count']
    assert columns_of(widget) == ['Pay::end', 'Register:Close::delay']
    assert 'Pay::count' not in widget.case_log.columns


def test_applying_records_provenance(widget):
    widget.apply_request = {
        'add': [tracking_spec('amount', 'sum', 'Pay').to_dict()],
        'remove': [],
        'request_id': 1,
    }
    assert 'Pay.amount::sum' in provenance_of(widget.case_log)


def test_a_replayed_request_is_a_no_op(widget):
    """marimo applies each frontend state message twice; the second must do nothing."""
    request = {'add': [times_spec('Pay', 'end').to_dict()], 'remove': [], 'request_id': 1}
    widget.apply_request = dict(request)
    after_first = columns_of(widget)

    widget.apply_request = dict(request)
    assert columns_of(widget) == after_first


def test_a_replay_carrying_new_content_is_still_ignored(widget):
    """The guard the request id exists for, driven so it is actually reached.

    Assigning two *equal* dicts does not exercise it: traitlets compares old and
    new, never fires the observer, and the widget's own check is never entered --
    which is why the test above passes whether or not the guard is there. A
    marimo replay can arrive after the user has moved on, so the payload differs
    while the id does not, and that is the one the widget has to refuse.
    """
    widget.apply_request = {'add': [counts_spec('Close').to_dict()], 'remove': [],
                            'request_id': 1}
    after_first = columns_of(widget)
    assert 'Close::count' in after_first

    widget.apply_request = {'add': [times_spec('Pay', 'end').to_dict()], 'remove': [],
                            'request_id': 1}
    assert columns_of(widget) == after_first

    # and the id moving on releases it again
    widget.apply_request = {'add': [times_spec('Pay', 'end').to_dict()], 'remove': [],
                            'request_id': 2}
    assert 'Pay::end' in columns_of(widget)


def test_a_replayed_preview_request_is_ignored(widget):
    """Same guard, on the preview side: a replay must not recompute a different
    sample under an id the frontend has already had an answer for."""
    widget.preview_request = {'add': [], 'remove': [], 'seed': 1, 'cases': 2,
                              'request_id': 1}
    first = widget.preview_result

    widget.preview_request = {'add': [], 'remove': [], 'seed': 99, 'cases': 3,
                              'request_id': 1}
    assert widget.preview_result is first

    widget.preview_request = {'add': [], 'remove': [], 'seed': 99, 'cases': 3,
                              'request_id': 2}
    assert widget.preview_result['request_id'] == 2


def test_removing_and_re_adding_in_one_request_keeps_the_column(widget):
    widget.apply_request = {
        'add': [counts_spec('Pay').to_dict()],
        'remove': ['Pay::count'],
        'request_id': 1,
    }
    assert 'Pay::count' in widget.case_log.columns


def test_a_failing_apply_reports_instead_of_raising(widget):
    widget.apply_request = {
        'add': [tracking_spec('nope', 'latest', 'Pay').to_dict()],
        'remove': [],
        'request_id': 1,
    }
    assert widget.apply_result['ok'] is False
    assert widget.apply_result['error']
    # The case log is untouched, so the user can fix the request and retry.
    assert columns_of(widget) == ['Pay::count']


def test_on_apply_is_called_once_per_successful_apply(event_log):
    calls = []
    widget = EnrichmentWidget(event_log, on_apply=lambda: calls.append(1))

    widget.apply_request = {'add': [counts_spec('Pay').to_dict()], 'remove': [],
                            'request_id': 1}
    widget.apply_request = {'add': [counts_spec('Pay').to_dict()], 'remove': [],
                            'request_id': 1}
    assert len(calls) == 1


def test_on_apply_is_not_called_when_the_apply_fails(event_log):
    calls = []
    widget = EnrichmentWidget(event_log, on_apply=lambda: calls.append(1))
    widget.apply_request = {'add': [tracking_spec('nope', 'latest').to_dict()],
                            'remove': [], 'request_id': 1}
    assert calls == []


# ----------------------------------------------------------------------
# preview
# ----------------------------------------------------------------------
def test_preview_computes_real_values(widget):
    widget.preview_request = {
        'add': [tracking_spec('amount', 'sum', 'Pay').to_dict()],
        'remove': [],
        'seed': 0,
        'cases': 3,
        'request_id': 1,
    }
    result = widget.preview_result

    assert result['ok'] is True
    assert result['sampled'] == 3
    assert result['total_cases'] == 3
    assert result['total_events'] == 10

    names = [column['name'] for column in result['columns']]
    assert names[0] == 'case:concept:name'
    assert 'Pay.amount::sum' in names

    # The staged column holds what applying would compute, per case.
    sums = dict(zip([row[0] for row in result['rows']],
                    [row[names.index('Pay.amount::sum')] for row in result['rows']]))
    assert sums == {'c1': '30', 'c2': '0', 'c3': '7.5'}


def test_preview_labels_each_column_by_state(widget):
    widget.preview_request = {
        'add': [counts_spec('Close').to_dict()],
        'remove': ['Pay::count'],
        'seed': 0,
        'cases': 2,
        'request_id': 1,
    }
    states = {column['name']: column['state'] for column in widget.preview_result['columns']}

    assert states['case:concept:name'] == 'key'
    assert states['duration'] == 'base'
    assert states['Close::count'] == 'staged'
    # A column staged for removal stays in the preview, marked: the point is to
    # show what the removal would cost.
    assert states['Pay::count'] == 'removing'


def test_preview_sampling_is_deterministic(widget):
    def sample(seed, request_id):
        widget.preview_request = {'add': [], 'remove': [], 'seed': seed, 'cases': 2,
                                  'request_id': request_id}
        return [row[0] for row in widget.preview_result['rows']]

    assert sample(7, 1) == sample(7, 2)


def test_preview_never_asks_for_more_cases_than_there_are(widget):
    widget.preview_request = {'add': [], 'remove': [], 'seed': 0, 'cases': 99,
                              'request_id': 1}
    assert widget.preview_result['sampled'] == 3


def test_preview_of_a_delay_whose_activity_is_absent(widget):
    """A delay may name an activity these events do not have.

    The preview computes over a handful of cases, so an activity the log as a
    whole carries is routinely missing from *that* slice -- which is how the
    road-fines notebook, the one that seeds a delay per activity pair, hit this.
    Staging ``Refund`` (which no case does) reproduces it without a sample.
    """
    widget.preview_request = {
        'add': [delay_spec('Refund', 'Pay').to_dict()],
        'remove': [], 'seed': 0, 'cases': 3, 'request_id': 1,
    }
    result = widget.preview_result

    assert result['ok'] is True, result.get('error')
    names = [column['name'] for column in result['columns']]
    values = {row[0]: row[names.index('Refund:Pay::delay')] for row in result['rows']}
    assert values == {'c1': 'NaT', 'c2': 'NaT', 'c3': 'NaT'}


def test_a_failing_preview_reports_instead_of_raising(widget):
    widget.preview_request = {
        'add': [tracking_spec('nope', 'latest', 'Pay').to_dict()],
        'remove': [], 'seed': 0, 'cases': 2, 'request_id': 1,
    }
    assert widget.preview_result['ok'] is False
    assert widget.preview_result['error']


# ----------------------------------------------------------------------
# handing the case log on
# ----------------------------------------------------------------------
def test_case_log_carries_readable_provenance(widget):
    """The case log the widget hands out describes its own derived columns."""
    widget.apply_request = {
        'add': [times_spec('Pay', 'end').to_dict(),
                tracking_spec('amount', 'max', 'Pay').to_dict()],
        'remove': [], 'request_id': 1,
    }
    case_log = widget.case_log

    from eclear.enrichment import describe_attribute  # pylint: disable=import-outside-toplevel
    provenance = provenance_of(case_log)
    assert describe_attribute('Pay::end', provenance).family == 'end'
    assert describe_attribute('Pay.amount::max', provenance).sources == ('Pay', 'amount')
    assert isinstance(case_log.index, pd.Index)


# ----------------------------------------------------------------------
# the event tab
# ----------------------------------------------------------------------
@pytest.fixture
def event_widget(lifecycle_event_log) -> EnrichmentWidget:
    """A widget on the lifecycle log, which has a status column to pair on."""
    return EnrichmentWidget(lifecycle_event_log)


def event_columns_of(widget: EnrichmentWidget) -> list:
    return [spec['column'] for spec in widget.event_applied]


def test_the_event_catalog_describes_the_log(event_widget):
    catalog = event_widget.event_catalog
    assert [kind['key'] for kind in catalog['kinds']] == [
        'binning', 'arithmetic', 'delta', 'running_agg']
    assert {entry['name'] for entry in catalog['event_types']} == {'Treat', 'Check'}

    treat = next(e for e in catalog['event_types'] if e['name'] == 'Treat')
    assert {(a['name'], a['kind']) for a in treat['attributes']} == {
        ('lifecycle:transition', 'cat'), ('dose', 'num')}
    # The log's own axes are never offered as attributes to enrich from.
    assert 'case:concept:name' not in {a['name'] for a in treat['attributes']}


def test_the_catalog_groups_the_kinds_the_rail_lists(event_widget):
    """The rail renders sections off this, and its flattening has to be the
    order Python sent -- otherwise a category could go missing between them."""
    groups = event_widget.event_catalog['kind_groups']
    assert [(group['key'], group['kinds']) for group in groups] == [
        ('local', ['binning', 'arithmetic']),
        ('contextual', ['delta', 'running_agg']),
    ]
    flattened = [kind for group in groups for kind in group['kinds']]
    assert flattened == [kind['key'] for kind in event_widget.event_catalog['kinds']]


def test_the_catalog_offers_the_log_timestamp_on_every_event_type(event_widget):
    """`event_type_catalog` leaves the timestamp out of the attribute lists, so
    a time binning would have nothing to cut if this did not put it back."""
    stamps = event_widget.event_catalog['time_columns']
    assert set(stamps) == {'Treat', 'Check'}
    assert all(columns == ['time:timestamp'] for columns in stamps.values())


def test_the_catalog_sketches_every_numeric_column(event_widget):
    profiles = event_widget.event_catalog['numeric_profiles']
    assert profiles['*']['dose']['min'] == 0.0
    assert profiles['*']['dose']['max'] == 4.0
    assert len(profiles['Treat']['dose']['quantiles']) == 101


def test_the_catalog_reports_which_event_types_have_neighbours(event_widget):
    """A time delta needs a neighbour, so the pane has to know whether one exists
    before the column is staged rather than after it comes back empty."""
    types = event_widget.event_catalog['event_types']
    treat = next(entry for entry in types if entry['name'] == 'Treat')
    assert treat['neighbours']['prev'] == pytest.approx(4 / 6)
    assert treat['neighbours']['next'] == pytest.approx(4 / 6)


def test_an_event_type_that_opens_every_case_reports_no_previous_neighbour():
    """The road-traffic shape: the most frequent activity opens every case, so
    the pane's default -- most frequent type, since previous -- is empty by
    construction and has to say so."""
    start = pd.Timestamp('2024-01-01')
    rows = [('c1', 'Open', 0), ('c1', 'Work', 1),
            ('c2', 'Open', 0), ('c2', 'Work', 2)]
    log = pd.DataFrame({
        'case:concept:name': [row[0] for row in rows],
        'concept:name': [row[1] for row in rows],
        'time:timestamp': [start + pd.Timedelta(hours=row[2]) for row in rows],
    })
    types = EnrichmentWidget(log).event_catalog['event_types']
    opening = next(entry for entry in types if entry['name'] == 'Open')
    closing = next(entry for entry in types if entry['name'] == 'Work')

    assert opening['neighbours'] == {'prev': 0.0, 'next': 1.0}
    assert closing['neighbours'] == {'prev': 1.0, 'next': 0.0}


def test_a_replay_carrying_new_content_is_ignored_on_the_event_side_too(event_widget):
    """Both event observers hold the same guard, for the same reason -- see
    ``test_a_replay_carrying_new_content_is_still_ignored``."""
    event_widget.event_apply_request = {
        'add': [running_agg_spec('total', 'dose').to_dict()], 'remove': [], 'request_id': 1}
    after_first = event_columns_of(event_widget)
    assert after_first == ['total']

    event_widget.event_apply_request = {
        'add': [delta_spec('gap', 'Treat').to_dict()], 'remove': [], 'request_id': 1}
    assert event_columns_of(event_widget) == after_first

    event_widget.event_apply_request = {
        'add': [delta_spec('gap', 'Treat').to_dict()], 'remove': [], 'request_id': 2}
    assert 'gap' in event_columns_of(event_widget)


def test_a_replayed_event_preview_request_is_ignored(event_widget):
    event_widget.event_preview_request = {
        'add': [], 'remove': [], 'seed': 1, 'cases': 2, 'request_id': 1}
    first = event_widget.event_preview_result

    event_widget.event_preview_request = {
        'add': [], 'remove': [], 'seed': 99, 'cases': 3, 'request_id': 1}
    assert event_widget.event_preview_result is first

    event_widget.event_preview_request = {
        'add': [], 'remove': [], 'seed': 99, 'cases': 3, 'request_id': 2}
    assert event_widget.event_preview_result['request_id'] == 2


def test_initial_event_specs_are_applied_before_the_catalog_is_built(lifecycle_event_log):
    """A seeded event column has to be trackable from the first render."""
    widget = EnrichmentWidget(lifecycle_event_log,
                              initial_event_specs=[running_agg_spec('total', 'dose')])
    assert 'total' in widget.event_log.columns
    tracked = {attribute['attribute']
               for group in widget.catalog['track_groups']
               for attribute in group['attributes']}
    assert 'total' in tracked


def test_event_apply_adds_a_column_and_refreshes_the_tracking_catalog(event_widget):
    event_widget.event_apply_request = {
        'add': [delta_spec('gap_h', 'Treat', unit='hours').to_dict()],
        'remove': [], 'request_id': 1,
    }
    assert event_widget.event_apply_result['ok'] is True
    assert event_columns_of(event_widget) == ['gap_h']
    assert 'gap_h' in event_widget.event_log.columns

    treat = next(group for group in event_widget.catalog['track_groups']
                 if group['event_type'] == 'Treat')
    assert 'gap_h' in {attribute['attribute'] for attribute in treat['attributes']}


def test_event_apply_leaves_the_case_log_alone(event_widget):
    """Recomputing case columns silently would move numbers already looked at."""
    event_widget.apply_request = {'add': [counts_spec('Treat').to_dict()],
                                  'remove': [], 'request_id': 1}
    before = event_widget.case_log

    event_widget.event_apply_request = {
        'add': [running_agg_spec('total', 'dose').to_dict()], 'remove': [], 'request_id': 1}
    pd.testing.assert_frame_equal(before, event_widget.case_log)


def test_an_applied_event_column_is_removed_by_replaying_without_it(event_widget):
    event_widget.event_apply_request = {
        'add': [running_agg_spec('total', 'dose').to_dict(),
                delta_spec('gap_h', 'Treat').to_dict()],
        'remove': [], 'request_id': 1}
    event_widget.event_apply_request = {
        'add': [], 'remove': ['total'], 'request_id': 2}

    assert event_widget.event_apply_result['ok'] is True
    assert event_columns_of(event_widget) == ['gap_h']
    assert 'total' not in event_widget.event_log.columns


def test_removing_a_column_a_case_column_tracks_is_refused(event_widget):
    event_widget.event_apply_request = {
        'add': [running_agg_spec('total', 'dose').to_dict()], 'remove': [], 'request_id': 1}
    event_widget.apply_request = {
        'add': [tracking_spec('total', 'max', 'Treat').to_dict()],
        'remove': [], 'request_id': 1}

    event_widget.event_apply_request = {'add': [], 'remove': ['total'], 'request_id': 2}

    result = event_widget.event_apply_result
    assert result['ok'] is False
    assert result['blocked'] == [{'column': 'total', 'used_by': ['Treat.total::max']}]
    assert 'total' in event_widget.event_log.columns


def test_removing_a_column_another_event_column_derives_from_is_refused(event_widget):
    event_widget.event_apply_request = {
        'add': [running_agg_spec('total', 'dose').to_dict(),
                arithmetic_spec('half', 'Check', 'total', '/', constant=2).to_dict()],
        'remove': [], 'request_id': 1}

    event_widget.event_apply_request = {'add': [], 'remove': ['total'], 'request_id': 2}

    assert event_widget.event_apply_result['blocked'] == [
        {'column': 'total', 'used_by': ['half']}]


def test_removing_both_a_column_and_its_reader_is_allowed(event_widget):
    """Only a *surviving* reader holds a column down."""
    event_widget.event_apply_request = {
        'add': [running_agg_spec('total', 'dose').to_dict(),
                arithmetic_spec('half', 'Check', 'total', '/', constant=2).to_dict()],
        'remove': [], 'request_id': 1}

    event_widget.event_apply_request = {
        'add': [], 'remove': ['total', 'half'], 'request_id': 2}

    assert event_widget.event_apply_result['ok'] is True
    assert event_columns_of(event_widget) == []


def test_a_spec_the_log_cannot_support_is_rejected_with_a_reason(event_widget):
    event_widget.event_apply_request = {
        'add': [arithmetic_spec('x', 'Treat', 'lifecycle:transition', '+',
                             constant=1).to_dict()],
        'remove': [], 'request_id': 1}

    result = event_widget.event_apply_result
    assert result['ok'] is False
    assert 'not a numeric attribute' in result['error']
    assert event_columns_of(event_widget) == []


def test_a_batch_may_read_a_column_staged_alongside_it(event_widget):
    event_widget.event_apply_request = {
        'add': [running_agg_spec('total', 'dose').to_dict(),
                arithmetic_spec('half', 'Check', 'total', '/', constant=2).to_dict()],
        'remove': [], 'request_id': 1}
    assert event_widget.event_apply_result['ok'] is True
    assert event_columns_of(event_widget) == ['total', 'half']


def test_a_name_already_on_the_log_is_rejected(event_widget):
    event_widget.event_apply_request = {
        'add': [running_agg_spec('dose', 'dose').to_dict()], 'remove': [], 'request_id': 1}
    assert 'already exists' in event_widget.event_apply_result['error']


def test_a_replayed_event_request_is_a_no_op(event_widget):
    request = {'add': [delta_spec('gap_h', 'Treat').to_dict()], 'remove': [],
               'request_id': 1}
    event_widget.event_apply_request = dict(request)
    after_first = event_columns_of(event_widget)
    event_widget.event_apply_request = dict(request)
    assert event_columns_of(event_widget) == after_first


def test_on_apply_fires_for_the_event_tab_too(lifecycle_event_log):
    calls = []
    widget = EnrichmentWidget(lifecycle_event_log, on_apply=lambda: calls.append(1))
    widget.event_apply_request = {'add': [delta_spec('gap_h', 'Treat').to_dict()],
                                  'remove': [], 'request_id': 1}
    widget.event_apply_request = {'add': [], 'remove': ['nope'], 'request_id': 2}
    assert len(calls) == 2


# ----------------------------------------------------------------------
# the event preview
# ----------------------------------------------------------------------
def test_event_preview_computes_real_values_in_sequence(event_widget):
    event_widget.event_preview_request = {
        'add': [time_binning_spec('hour', 'Treat', 'time:timestamp', 'hour').to_dict()],
        'remove': [], 'seed': 0, 'cases': 3, 'scope': 'any', 'request_id': 1,
    }
    result = event_widget.event_preview_result

    assert result['ok'] is True
    assert result['columns'] == [
        {'name': 'hour', 'kind': 'binning', 'event_type': 'Treat', 'state': 'staged'}]
    assert result['total_events'] == 9

    c1 = [row for row in result['rows'] if row['case'] == 'c1' and not row['group']]
    assert [row['activity'] for row in c1] == ['Treat', 'Treat', 'Check', 'Treat', 'Treat']
    assert [row['values'][0] for row in c1] == ['0', '2', None, '5', '8']


def test_the_preview_tells_a_missing_value_apart_from_an_inapplicable_one(event_widget):
    """A dash means the column does not apply to that event type; NaN means it
    applies and there is nothing there."""
    event_widget.event_preview_request = {
        'add': [delta_spec('gap_h', 'Treat', unit='hours').to_dict()],
        'remove': [], 'seed': 0, 'cases': 3, 'scope': 'any', 'request_id': 1,
    }
    c1 = [row for row in event_widget.event_preview_result['rows']
          if row['case'] == 'c1' and not row['group']]
    assert [row['values'][0] for row in c1] == ['NaN', '2', None, '2', '3']


def test_the_preview_groups_its_rows_by_case(event_widget):
    event_widget.event_preview_request = {
        'add': [], 'remove': [], 'seed': 0, 'cases': 2, 'scope': 'any', 'request_id': 1}
    groups = [row for row in event_widget.event_preview_result['rows'] if row['group']]
    assert len(groups) == 2
    assert all(row['events'] for row in groups)


def test_the_touching_scope_samples_cases_that_carry_the_staged_type(event_widget):
    """Previewing a column on a rare activity must not come back cases that
    never see it."""
    event_widget.event_preview_request = {
        'add': [delta_spec('gap_h', 'Check').to_dict()],
        'remove': [], 'seed': 3, 'cases': 1, 'scope': 'touching', 'request_id': 1}
    rows = [row for row in event_widget.event_preview_result['rows'] if not row['group']]
    assert any(row['activity'] == 'Check' for row in rows)


def test_a_failing_event_preview_reports_instead_of_raising(event_widget):
    event_widget.event_preview_request = {
        'add': [running_agg_spec('total', 'nope').to_dict()],
        'remove': [], 'seed': 0, 'cases': 2, 'scope': 'any', 'request_id': 1}
    assert event_widget.event_preview_result['ok'] is False
    assert event_widget.event_preview_result['error']


def test_the_event_log_carries_the_applied_enrichments_to_the_notebook(event_widget):
    event_widget.event_apply_request = {
        'add': [running_agg_spec('total', 'dose').to_dict()], 'remove': [], 'request_id': 1}
    from eclear.enrichment import event_specs_of  # pylint: disable=import-outside-toplevel
    assert [spec.column for spec in event_specs_of(event_widget.event_log)] == ['total']
    assert event_widget.event_specs == [running_agg_spec('total', 'dose')]


def test_an_operand_the_event_type_does_not_carry_is_rejected(lifecycle_event_log):
    """``dose`` rides on both types, so give one type a numeric attribute of its
    own and try to read it from the other. Applying would succeed and produce a
    column of nothing, which is worse than a refusal."""
    log = lifecycle_event_log.copy()
    log['reading'] = [None, None, 1.0, None, None, None, 2.0, None, 3.0]  # Check only
    widget = EnrichmentWidget(log)

    widget.event_apply_request = {
        'add': [arithmetic_spec('x', 'Treat', 'reading', '*', constant=2).to_dict()],
        'remove': [], 'request_id': 1}

    assert widget.event_apply_result['ok'] is False
    assert "'reading' is not a numeric attribute" in widget.event_apply_result['error']


def test_an_unscoped_column_may_be_read_from_any_event_type(event_widget):
    """An accumulation is written on every event, so it is in scope everywhere."""
    event_widget.event_apply_request = {
        'add': [running_agg_spec('total', 'dose').to_dict(),
                arithmetic_spec('half', 'Check', 'total', '/', constant=2).to_dict()],
        'remove': [], 'request_id': 1}
    assert event_widget.event_apply_result['ok'] is True


def test_a_bin_column_is_not_offered_as_a_numeric_operand(event_widget):
    """It holds a label, so arithmetic on it is not a thing that means anything."""
    event_widget.event_apply_request = {
        'add': [binning_spec('level', 'Treat', 'dose', [1.5]).to_dict()],
        'remove': [], 'request_id': 1}
    event_widget.event_apply_request = {
        'add': [arithmetic_spec('x', 'Treat', 'level', '*', constant=2).to_dict()],
        'remove': [], 'request_id': 2}
    assert "'level' is not a numeric attribute" in event_widget.event_apply_result['error']


# ----------------------------------------------------------------------
# preview rendering
# ----------------------------------------------------------------------
@pytest.mark.parametrize('value, rendered', [
    (None, 'None'),
    (pd.NaT, 'NaT'),
    (float('nan'), 'NaN'),
    (1.5, '1.5'),
    (1000000.0, '1e+06'),
    ('text', 'text'),
    (True, 'True'),
    (pd.Timedelta(hours=3), '0 days 03:00:00'),
    ([], '[]'),
    ([1, 2, 3], '[1, 2, 3]'),
    (['a', 'b'], '[a, b]'),
    ([1.5, None], '[1.5, None]'),
])
def test_a_preview_cell_names_the_kind_of_nothing_it_holds(value, rendered):
    """Which kind of missing a cell holds is exactly what a preview is for, so
    ``NaT`` and ``NaN`` keep the names pandas gives them rather than blanking.

    Lists get their own line because ``append`` tracking produces one per cell,
    and rendering it as a Python repr would put quotes round every element.
    """
    from eclear.widget import _format_value  # pylint: disable=import-outside-toplevel
    assert _format_value(value) == rendered


def test_a_preview_renders_an_append_column_as_a_list(widget):
    """The end-to-end path for the branch above: ``append`` folds a case's values
    into a list, and the preview has to show it as one."""
    widget.preview_request = {
        'add': [tracking_spec('amount', 'append', 'Pay').to_dict()],
        'remove': [], 'seed': 0, 'cases': 3, 'request_id': 1}
    result = widget.preview_result
    assert result['ok'] is True
    at = [column['name'] for column in result['columns']].index('Pay.amount::append')
    rendered = [row[at] for row in result['rows']]
    assert any(value.startswith('[') and value.endswith(']') for value in rendered)

