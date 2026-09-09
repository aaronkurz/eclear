"""Tests for eclear.enrichment: producing case-log columns, and describing them.

Two halves. The naming half pins the scheme in both directions -- a spec always
produces the name the parser reads back -- because a mismatch there would show
one column in the enrichment widget and write another to the case log. The
enricher half asserts exact values against the hand-built ``event_log`` fixture
in ``conftest.py``, including which flavour of missing each family produces.
"""
import numpy as np
import pandas as pd
import pytest

from eclear.enrichment import (
    ALL_EVENTS,
    CATEGORICAL_TRACK_METHODS,
    EnrichmentSpec,
    apply_specs,
    column_name,
    counts_spec,
    create_case_log,
    delay_spec,
    describe_attribute,
    drop_columns,
    is_numeric_series,
    neighbour_coverage,
    parse_attribute_name,
    provenance_of,
    specs_of,
    times_spec,
    track_methods_for,
    trackable_attributes,
    tracking_spec,
)

HOUR = pd.Timedelta(hours=1)


# ----------------------------------------------------------------------
# naming and provenance
# ----------------------------------------------------------------------
@pytest.mark.parametrize('name, family, sources', [
    # activity enrichments
    ('Payment::count', 'count', ('Payment',)),
    ('Send_for_Credit_Collection::count', 'count', ('Send_for_Credit_Collection',)),
    ('Send_Fine::start', 'start', ('Send_Fine',)),
    ('Send_Fine::end', 'end', ('Send_Fine',)),
    # 'A:B::delay' is start(B) - start(A): the sources keep the name's order
    ('Payment:Add_penalty::delay', 'delay', ('Payment', 'Add_penalty')),
    # tracked event attributes, scoped to an event type
    ('ER_Registration.Age::latest', 'latest', ('ER_Registration', 'Age')),
    ('Payment.paymentAmount::sum', 'sum', ('Payment', 'paymentAmount')),
    # an attribute named after the event type carrying it has one source, not two
    ('Leucocytes.Leucocytes::min', 'min', ('Leucocytes',)),
    ('CRP.CRP::max', 'max', ('CRP',)),
    # a tracked *count* is its own family: it is not activity incidence
    ('Payment.amount::count', 'track_count', ('Payment', 'amount')),
    # is_unique is a family of its own: whether the case ever changed the value
    ('ER_Registration.org:group::is_unique', 'is_unique', ('ER_Registration', 'org:group')),
    # tracked over every event: only the attribute is a source
    ('all_events.concept:name::append', 'append', ('concept:name',)),
    # the '*' spelling this scope used to have still reads back the same way
    ('*.concept:name::append', 'append', ('concept:name',)),
    # legacy flat tracking names (event log, or written by hand) still parse
    ('concept:name::append', 'append', ('concept:name',)),
    ('paymentAmount::sum', 'sum', ('paymentAmount',)),
    ('x::latest::count', 'count', ('x::latest',)),
    # fixed case-log columns
    ('duration', 'case', ()),
    ('no_of_events', 'case', ()),
    ('start_time', 'case', ()),
    ('rel_time', 'case', ()),
    # hand-written notebook columns follow no scheme at all
    ('outstanding_balance', 'other', ()),
    ('seq_variant', 'other', ()),
    # a delay whose stem does not split cleanly: family known, sources not
    ('Payment::delay', 'delay', ()),
    ('a:b:c::delay', 'delay', ()),
    # closed method vocabulary: an unknown suffix must not spawn a family
    ('foo::bar', 'other', ()),
    # degenerate names must not raise
    ('', 'other', ()),
    ('::count', 'count', ()),
    ('::', 'other', ()),
])
def test_parse_attribute_name(name, family, sources):
    meta = parse_attribute_name(name)
    assert meta.family == family
    assert meta.sources == sources


def test_family_label_is_always_populated():
    names = [
        'Payment::count', 'Send_Fine::start', 'Send_Fine::end',
        'Payment:Add_penalty::delay', 'ER_Registration.Age::latest',
        'Payment.amount::count', 'all_events.concept:name::append', 'paymentAmount::sum',
        'duration', 'outstanding_balance', 'foo::bar',
    ]
    for name in names:
        meta = parse_attribute_name(name)
        assert meta.family_label, f'{name} has no family label'


def test_delay_sources_are_ordered_as_named():
    forward = parse_attribute_name('Payment:Add_penalty::delay')
    backward = parse_attribute_name('Add_penalty:Payment::delay')
    assert forward.sources == ('Payment', 'Add_penalty')
    assert backward.sources == ('Add_penalty', 'Payment')


@pytest.mark.parametrize('spec, expected', [
    (counts_spec('Send Fine'), 'Send_Fine::count'),
    (times_spec('Send Fine', 'start'), 'Send_Fine::start'),
    (times_spec('Send Fine', 'end'), 'Send_Fine::end'),
    (delay_spec('Send Fine', 'Add penalty'), 'Send_Fine:Add_penalty::delay'),
    (tracking_spec('Age', 'latest', 'ER Registration'), 'ER_Registration.Age::latest'),
    (tracking_spec('concept:name', 'append'), 'all_events.concept:name::append'),
])
def test_column_name(spec, expected):
    assert column_name(spec) == expected
    assert spec.column == expected


@pytest.mark.parametrize('spec', [
    counts_spec('Send Fine'),
    times_spec('Send Fine', 'start'),
    times_spec('Send Fine', 'end'),
    delay_spec('Send Fine', 'Add penalty'),
    tracking_spec('Age', 'latest', 'ER Registration'),
    tracking_spec('Age', 'count', 'ER Registration'),
    tracking_spec('concept:name', 'append'),
])
def test_name_round_trips_through_the_parser(spec):
    """Every spec's name parses back to the family and sources the spec claims.

    The parser is the fallback for columns with no provenance record, so it has
    to agree with the record for every name the enrichers actually write.
    """
    assert parse_attribute_name(spec.column) == spec.meta


def test_sources_are_deduplicated():
    """An attribute named after the event type that carries it has one source.

    The rule builder groups and facets by source, so a repeat would list the
    same attribute twice under the same heading.
    """
    spec = tracking_spec('Leucocytes', 'max', 'Leucocytes')
    assert spec.meta.sources == ('Leucocytes',)
    assert parse_attribute_name(spec.column).sources == ('Leucocytes',)


def test_spec_dict_round_trip():
    spec = tracking_spec('paymentAmount', 'sum', 'Payment')
    assert EnrichmentSpec.from_dict(spec.to_dict()) == spec


def test_describe_attribute_prefers_the_record_over_the_name():
    """The record wins even when the name says something else.

    ``Pay::count`` reads as activity incidence and nothing in the name can say
    otherwise -- which is precisely the ambiguity a provenance record exists to
    settle.
    """
    provenance = {'Pay::count': tracking_spec('amount', 'count', 'Pay').to_dict()}
    assert describe_attribute('Pay::count', provenance).family == 'track_count'
    assert describe_attribute('Pay::count', {}).family == 'count'
    assert describe_attribute('Pay::count').family == 'count'


def test_describe_attribute_falls_back_on_a_malformed_record():
    """A record we cannot read must degrade to name parsing, not raise."""
    meta = describe_attribute('Payment::count', {'Payment::count': {'nonsense': 1}})
    assert meta.family == 'count'


# ----------------------------------------------------------------------
# base case log
# ----------------------------------------------------------------------
def test_create_case_log(event_log):
    case_log = create_case_log(event_log)

    assert list(case_log.columns) == ['start_time', 'end_time', 'no_of_events', 'duration']
    assert list(case_log.index) == ['c1', 'c2', 'c3']
    assert case_log['no_of_events'].tolist() == [4, 2, 4]
    assert case_log['duration'].tolist() == [9 * HOUR, 3 * HOUR, 4 * HOUR]


def test_create_case_log_reads_extremes_not_row_order(event_log):
    """c3's rows are not in time order, and its duration must still be positive."""
    case_log = create_case_log(event_log)
    assert case_log.at['c3', 'start_time'] == pd.Timestamp('2024-01-01')
    assert case_log.at['c3', 'end_time'] == pd.Timestamp('2024-01-01 04:00')


def test_case_log_starts_with_an_empty_provenance_record(event_log):
    assert provenance_of(create_case_log(event_log)) == {}


# ----------------------------------------------------------------------
# activity enrichments
# ----------------------------------------------------------------------
def test_activity_counts_zero_fill_absent_activities(event_log):
    case_log = apply_specs(create_case_log(event_log), event_log,
                           [counts_spec('Pay'), counts_spec('Close')])
    assert case_log['Pay::count'].tolist() == [2, 0, 2]
    assert case_log['Close::count'].tolist() == [1, 1, 1]
    # A case without the activity counted zero, not missing.
    assert case_log['Pay::count'].isna().sum() == 0


def test_counting_an_activity_that_never_occurs(event_log):
    case_log = apply_specs(create_case_log(event_log), event_log, [counts_spec('Refund')])
    assert case_log['Refund::count'].tolist() == [0, 0, 0]


def test_times_of_an_activity_that_never_occurs(event_log):
    """An absent activity gets a column of the same flavour of missing as a case
    that simply never did it -- ``NaT``, not an object-dtype null.

    The dtype's *kind* is what matters and what is asserted; the resolution is
    not pinned because pandas infers it from the log's own timestamps and
    changed what it infers between 2.x (``ns``) and 3.x (``us``).
    """
    case_log = apply_specs(create_case_log(event_log), event_log,
                           [times_spec('Refund', 'start')])
    assert pd.api.types.is_timedelta64_dtype(case_log['Refund::start'])
    assert case_log['Refund::start'].isna().all()


@pytest.mark.parametrize('spec, column', [
    (delay_spec('Refund', 'Pay'), 'Refund:Pay::delay'),
    (delay_spec('Pay', 'Refund'), 'Pay:Refund::delay'),
])
def test_delay_against_an_activity_that_never_occurs(event_log, spec, column):
    """Both orders: the missing side used to arrive as an object column of NaN,
    and subtracting that from the ``NaT`` c2 carries raised a ``TypeError``.
    Which side is missing decides which pandas path is taken, so both are pinned.
    The resolution is not: see ``test_times_of_an_activity_that_never_occurs``.
    """
    case_log = apply_specs(create_case_log(event_log), event_log, [spec])
    assert pd.api.types.is_timedelta64_dtype(case_log[column])
    assert case_log[column].isna().all()


def test_activity_start_and_end_times(event_log):
    case_log = apply_specs(create_case_log(event_log), event_log,
                           [times_spec('Pay', 'start'), times_spec('Pay', 'end')])
    assert case_log['Pay::start'].tolist() == [2 * HOUR, pd.NaT, 3 * HOUR]
    assert case_log['Pay::end'].tolist() == [5 * HOUR, pd.NaT, 4 * HOUR]


def test_end_equals_start_for_a_single_occurrence(event_log):
    case_log = apply_specs(create_case_log(event_log), event_log,
                           [times_spec('Register', 'start'), times_spec('Register', 'end')])
    assert case_log['Register::start'].equals(case_log['Register::end'])


def test_delay_sign_and_missing(event_log):
    """``A:B::delay`` is start(B) - start(A): negative when B came first."""
    case_log = apply_specs(create_case_log(event_log), event_log,
                           [delay_spec('Pay', 'Close'), delay_spec('Register', 'Close')])
    assert case_log['Pay:Close::delay'].tolist() == [7 * HOUR, pd.NaT, -1 * HOUR]
    assert case_log['Register:Close::delay'].tolist() == [9 * HOUR, 3 * HOUR, 2 * HOUR]


def test_delay_does_not_need_the_start_columns(event_log):
    """The engine reads the event log, so a delay stands on its own."""
    case_log = apply_specs(create_case_log(event_log), event_log,
                           [delay_spec('Register', 'Pay')])
    assert 'Register::start' not in case_log.columns
    assert case_log['Register:Pay::delay'].tolist() == [2 * HOUR, pd.NaT, 3 * HOUR]


# ----------------------------------------------------------------------
# tracking
# ----------------------------------------------------------------------
@pytest.mark.parametrize('method, expected', [
    ('latest', [20.0, np.nan, 7.5]),
    ('sum', [30.0, 0.0, 7.5]),
    ('min', [10.0, np.nan, 7.5]),
    ('max', [20.0, np.nan, 7.5]),
])
def test_tracking_numeric_methods(event_log, method, expected):
    """c3's second Pay carries a null, which every fold skips."""
    spec = tracking_spec('amount', method, 'Pay')
    case_log = apply_specs(create_case_log(event_log), event_log, [spec])
    assert case_log[spec.column].tolist() == pytest.approx(expected, nan_ok=True)


def test_tracking_count_and_append(event_log):
    count = tracking_spec('amount', 'count', 'Pay')
    append = tracking_spec('amount', 'append', 'Pay')
    case_log = apply_specs(create_case_log(event_log), event_log, [count, append])
    # c1 has two values, c2 none, c3 one non-null out of two Pay events.
    assert case_log[count.column].tolist() == [2, 0, 1]
    assert case_log[append.column].tolist() == [[10.0, 20.0], [], [7.5]]


def test_tracking_a_categorical_column(event_log):
    """A binned event column arrives as a ``category``, and every method has to
    take one -- ``append`` above all, since folding a bin over the case is the
    whole point of binning it.

    Pinned because pandas routes ``groupby.agg(list)`` through a path that tries
    to fit the list back into the column's own dtype, which a categorical
    refuses. No other fixture here carries one, so nothing else would notice.
    """
    log = event_log.copy()
    # 'high' exactly where the event carries an amount, so c2 -- which never
    # pays -- comes out uniform and c1 and c3 do not.
    log['band'] = pd.Categorical(
        ['low' if pd.isna(amount) else 'high' for amount in log['amount']],
        categories=['low', 'high'], ordered=True)

    specs = [tracking_spec('band', method) for method in CATEGORICAL_TRACK_METHODS]
    case_log = apply_specs(create_case_log(log), log, specs)

    folded = {spec.method: case_log[spec.column].tolist() for spec in specs}
    # folds run over the case's events in time order, which for c3 is not row order
    assert folded['append'] == [['low', 'high', 'high', 'low'],
                                ['low', 'low'],
                                ['low', 'low', 'high', 'low']]
    assert folded['latest'] == ['low', 'low', 'low']
    assert folded['count'] == [4, 2, 4]
    assert folded['is_unique'] == [False, True, False]


def test_tracking_latest_follows_timestamp_not_row_order(event_log):
    """c3's rows are unsorted, so ``latest`` has to sort before folding."""
    spec = tracking_spec('concept:name', 'latest')
    case_log = apply_specs(create_case_log(event_log), event_log, [spec])
    assert case_log[spec.column].tolist() == ['Close', 'Close', 'Pay']


def test_tracking_over_every_event(event_log):
    spec = tracking_spec('concept:name', 'append')
    case_log = apply_specs(create_case_log(event_log), event_log, [spec])
    assert case_log[spec.column].tolist() == [
        ['Register', 'Pay', 'Pay', 'Close'],
        ['Register', 'Close'],
        ['Register', 'Close', 'Pay', 'Pay'],
    ]


def test_tracking_scoped_to_one_activity(event_log):
    spec = tracking_spec('dept', 'latest', 'Register')
    case_log = apply_specs(create_case_log(event_log), event_log, [spec])
    assert case_log['Register.dept::latest'].tolist() == ['north', 'south', 'north']


def test_is_unique_says_whether_the_case_ever_changed_the_value(multi_carrier_event_log):
    """c1 moves north -> south, c2 stays east, c3 carries no ward at all."""
    spec = tracking_spec('ward', 'is_unique')
    case_log = apply_specs(create_case_log(multi_carrier_event_log),
                           multi_carrier_event_log, [spec])
    assert case_log[spec.column].tolist() == [False, True, pd.NA]


def test_is_unique_is_a_nullable_boolean(multi_carrier_event_log):
    """A case with no matching event has no answer, not a False."""
    spec = tracking_spec('note', 'is_unique', 'Check')
    case_log = apply_specs(create_case_log(multi_carrier_event_log),
                           multi_carrier_event_log, [spec])
    assert case_log[spec.column].dtype == 'boolean'
    assert case_log[spec.column].isna().tolist() == [False, False, True]


def test_is_unique_answers_within_the_scope_it_is_given(multi_carrier_event_log):
    """c1 changed ward across the case but never within its Check events."""
    whole = tracking_spec('ward', 'is_unique')
    scoped = tracking_spec('ward', 'is_unique', 'Check')
    case_log = apply_specs(create_case_log(multi_carrier_event_log),
                           multi_carrier_event_log, [whole, scoped])
    assert case_log[whole.column].tolist() == [False, True, pd.NA]
    assert case_log[scoped.column].tolist() == [True, True, pd.NA]


def test_a_categorical_attribute_may_be_asked_whether_it_is_unique():
    """Unlike sum, min and max, is_unique needs no numeric axis."""
    assert 'is_unique' in track_methods_for(numeric=False)
    assert 'is_unique' in track_methods_for(numeric=True)


def test_tracking_an_unknown_attribute_raises(event_log):
    with pytest.raises(KeyError):
        apply_specs(create_case_log(event_log), event_log,
                    [tracking_spec('nope', 'latest', 'Pay')])


# ----------------------------------------------------------------------
# provenance lifecycle
# ----------------------------------------------------------------------
def test_apply_specs_records_what_it_produced(event_log):
    specs = [counts_spec('Pay'), times_spec('Pay', 'end'),
             tracking_spec('amount', 'sum', 'Pay')]
    case_log = apply_specs(create_case_log(event_log), event_log, specs)

    assert specs_of(case_log) == specs
    for spec in specs:
        assert describe_attribute(spec.column, provenance_of(case_log)) == spec.meta


def test_apply_specs_is_idempotent(event_log):
    specs = [counts_spec('Pay'), tracking_spec('amount', 'sum', 'Pay')]
    once = apply_specs(create_case_log(event_log), event_log, specs)
    twice = apply_specs(once, event_log, specs)
    pd.testing.assert_frame_equal(once, twice)


def test_apply_specs_leaves_the_input_alone(event_log):
    case_log = create_case_log(event_log)
    apply_specs(case_log, event_log, [counts_spec('Pay')])
    assert 'Pay::count' not in case_log.columns


def test_drop_columns_removes_the_record_too(event_log):
    case_log = apply_specs(create_case_log(event_log), event_log,
                           [counts_spec('Pay'), counts_spec('Close')])
    dropped = drop_columns(case_log, ['Pay::count'])

    assert 'Pay::count' not in dropped.columns
    assert 'Pay::count' not in provenance_of(dropped)
    assert 'Close::count' in provenance_of(dropped)


def test_drop_columns_refuses_the_base_columns(event_log):
    case_log = create_case_log(event_log)
    assert 'duration' in drop_columns(case_log, ['duration']).columns


def test_provenance_ignores_columns_that_are_gone(event_log):
    """A notebook that drops a column by hand must not leave a ghost entry."""
    case_log = apply_specs(create_case_log(event_log), event_log, [counts_spec('Pay')])
    trimmed = case_log.drop(columns=['Pay::count'])
    assert provenance_of(trimmed) == {}


def test_provenance_survives_column_and_row_subsetting(event_log):
    """Analysis subsets the case log by column and by row before reading it."""
    case_log = apply_specs(create_case_log(event_log), event_log, [counts_spec('Pay')])
    subset = case_log[['Pay::count']][case_log['Pay::count'] > 0]
    assert 'Pay::count' in provenance_of(subset)


# ----------------------------------------------------------------------
# catalog
# ----------------------------------------------------------------------
@pytest.mark.parametrize('values, numeric', [
    ([1, 2, 3], True),
    ([1.5, np.nan], True),
    (['1', '2'], True),
    (['a', 'b'], False),
    ([np.nan, np.nan], False),
    ([1, 'a'], False),
])
def test_is_numeric_series(values, numeric):
    assert is_numeric_series(pd.Series(values)) is numeric


def test_trackable_attributes_group_by_the_carrying_event_type(event_log):
    groups = {group['event_type']: group for group in trackable_attributes(event_log)}

    # `amount` only ever rides on Pay; `dept` only on Register.
    assert [entry['attribute'] for entry in groups['Pay']['attributes']] == [
        'amount', 'concept:name']
    assert [entry['attribute'] for entry in groups['Register']['attributes']] == [
        'concept:name', 'dept']
    # Only the attribute every event carries reaches the log-wide group.
    assert [entry['attribute'] for entry in groups[ALL_EVENTS]['attributes']] == [
        'concept:name']


def test_an_attribute_on_one_event_type_is_offered_under_that_type(event_log):
    """Not log-wide as well: the log-wide fold would read the same events, and
    the scoped name is the one that says where the value came from."""
    scopes = {group['event_type']
              for group in trackable_attributes(event_log)
              for entry in group['attributes'] if entry['attribute'] == 'dept'}
    assert scopes == {'Register'}


def test_an_attribute_on_several_types_is_offered_under_each_and_log_wide(event_log):
    """`append` over one activity's events is a different column from `append`
    over the whole case, so both are offered."""
    with_shared = event_log.copy()
    with_shared['note'] = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j']
    with_shared.loc[with_shared['concept:name'] == 'Close', 'note'] = np.nan

    scopes = {group['event_type']
              for group in trackable_attributes(with_shared)
              for entry in group['attributes'] if entry['attribute'] == 'note'}
    assert scopes == {ALL_EVENTS, 'Register', 'Pay'}


def test_a_case_attribute_replicated_onto_several_types_is_offered_under_each(event_log):
    """An earlier rule kept a constant-within-case attribute log-wide only. It
    is gone: `latest` reads the same under every scope, but `count` and `append`
    do not, and the user is better placed than a heuristic to say which is meant.
    """
    with_case_attribute = event_log.copy()
    ages = {'c1': 40, 'c2': 55, 'c3': 61}
    with_case_attribute['Age'] = with_case_attribute['case:concept:name'].map(ages)
    # Blank it out on Close, so it is carried by some event types but not all.
    with_case_attribute.loc[with_case_attribute['concept:name'] == 'Close', 'Age'] = np.nan

    scopes = {group['event_type']
              for group in trackable_attributes(with_case_attribute)
              for entry in group['attributes'] if entry['attribute'] == 'Age'}
    assert scopes == {ALL_EVENTS, 'Register', 'Pay'}


def test_an_attribute_on_every_event_type_is_offered_under_each_too(event_log):
    """The activity column is on every event; folding it over one activity is
    still a column somebody may want."""
    scopes = {group['event_type']
              for group in trackable_attributes(event_log)
              for entry in group['attributes'] if entry['attribute'] == 'concept:name'}
    assert scopes == {ALL_EVENTS, 'Register', 'Pay', 'Close'}


def test_trackable_attributes_offer_methods_by_type(event_log):
    groups = {group['event_type']: group for group in trackable_attributes(event_log)}
    amount = groups['Pay']['attributes'][0]
    dept = next(entry for entry in groups['Register']['attributes']
                if entry['attribute'] == 'dept')

    assert amount['numeric'] is True
    assert set(amount['methods']) >= {'sum', 'min', 'max'}
    assert dept['numeric'] is False
    assert set(dept['methods']) == {'latest', 'count', 'append', 'is_unique'}


def test_trackable_attributes_skip_enricher_output(event_log):
    """A column whose name says it has already been folded must not be offered
    for re-folding."""
    with_running = event_log.copy()
    with_running['amount::sum'] = 0.0
    offered = {entry['attribute']
               for group in trackable_attributes(with_running)
               for entry in group['attributes']}
    assert 'amount::sum' not in offered


def test_neighbour_coverage_reads_each_case_in_time_order(event_log):
    """c3's ``Close`` is the last *row* of its case but not its last *event*: it
    sits at +2h, ahead of the two ``Pay`` rows above it. Read off row order every
    ``Close`` would look final and ``next`` would come out 0; read in time order,
    c3's has two events after it.
    """
    coverage = neighbour_coverage(event_log)

    # Register opens all three cases, so it never has anything before it -- the
    # shape that makes a since-previous column empty.
    assert coverage['Register']['prev'] == 0.0
    assert coverage['Register']['next'] == 1.0
    # Close ends c1 and c2, but c3's falls mid-case.
    assert coverage['Close']['prev'] == 1.0
    assert coverage['Close']['next'] == pytest.approx(1 / 3)


def test_neighbour_coverage_is_zero_for_a_type_that_is_always_alone():
    """A single-event case has no neighbour in either direction, which is the
    reading a time delta on it would produce."""
    log = pd.DataFrame({
        'case:concept:name': ['c1', 'c2'],
        'concept:name': ['Only', 'Only'],
        'time:timestamp': [pd.Timestamp('2024-01-01'), pd.Timestamp('2024-01-02')],
    })
    assert neighbour_coverage(log) == {'Only': {'prev': 0.0, 'next': 0.0}}


# ----------------------------------------------------------------------
# event-log relative time
# ----------------------------------------------------------------------
def test_relative_log_time_is_measured_from_the_log_minimum(event_log):
    """The one function ``event_log.py`` still carries, and the widget runs it on
    every base log it builds.

    ``event_log``'s third case is out of time order in row order, so a column
    measured from the *first row* rather than the minimum would come out
    negative somewhere here.
    """
    from eclear.enrichment.event_log import (  # pylint: disable=import-outside-toplevel
        event_add_relative_log_time)

    shuffled = event_log.sample(frac=1, random_state=0)
    result = event_add_relative_log_time(shuffled.copy())

    earliest = event_log['time:timestamp'].min()
    assert (result['rel_log_time'] >= pd.Timedelta(0)).all()
    assert result['rel_log_time'].min() == pd.Timedelta(0)
    # written on the frame's own index, so a shuffled log stays shuffled
    assert list(result.index) == list(shuffled.index)
    for index, row in result.iterrows():
        assert row['rel_log_time'] == event_log.at[index, 'time:timestamp'] - earliest

