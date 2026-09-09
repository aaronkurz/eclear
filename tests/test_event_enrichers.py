"""Tests for eclear.enrichment.event_enrichers: specs to event-log columns.

Every expectation is a literal read off the ``lifecycle_event_log`` fixture in
``conftest.py``, whose docstring is the working. Two properties get their own
tests because the widget depends on them rather than on any single column: a
batch is idempotent, and a removal is expressed by re-applying without the spec.

The fixture's third case is deliberately out of time order in row order, so an
enrichment that trusted the frame instead of sorting would fail here rather than
on somebody's real log.
"""
import numpy as np
import pandas as pd
import pytest

from eclear.enrichment import (
    apply_event_specs,
    arithmetic_spec,
    binning_spec,
    delta_spec,
    event_columns_using,
    event_specs_of,
    running_agg_spec,
    time_binning_spec,
)

STAMP = 'time:timestamp'


def values(log: pd.DataFrame, specs) -> list:
    """The one column ``specs`` produces, in the log's own row order."""
    specs = specs if isinstance(specs, list) else [specs]
    return apply_event_specs(log, specs)[specs[-1].column].tolist()


def labels(log: pd.DataFrame, spec) -> list:
    """A categorical column with its missing values spelled ``None``."""
    return [None if pd.isna(value) else value
            for value in apply_event_specs(log, [spec])[spec.column]]


# ----------------------------------------------------------------------
# arithmetic
# ----------------------------------------------------------------------
def test_arithmetic_writes_only_on_its_own_event_type(lifecycle_event_log):
    result = values(lifecycle_event_log,
                    arithmetic_spec('doubled', 'Check', 'dose', '*', constant=2))
    assert result == pytest.approx(
        [np.nan, np.nan, 8.0, np.nan, np.nan, np.nan, 0.0, np.nan, np.nan], nan_ok=True)


@pytest.mark.parametrize('op, expected', [
    ('+', [5.0, np.nan, 11.0, 5.0, np.nan]),
    ('-', [-3.0, np.nan, -5.0, 5.0, np.nan]),
    ('*', [4.0, np.nan, 24.0, 0.0, np.nan]),
    ('/', [0.25, np.nan, 0.375, np.nan, np.nan]),
])
def test_every_operator_computes_what_it_says(contract_event_log, op, expected):
    """All four, because a sign error is silent.

    ``dose`` and ``reading`` on the three ``Treat`` rows are (1, 4), (3, 8) and
    (5, 0); the two ``Check`` rows are out of scope. The last ``Treat`` divides
    by zero, which is the NaN in the ``/`` row rather than an infinity.
    """
    result = values(contract_event_log,
                    arithmetic_spec('r', 'Treat', 'dose', op, 'reading'))
    assert result == pytest.approx(expected, nan_ok=True)


@pytest.mark.parametrize('op, expected', [
    ('+', [3.0, np.nan, 5.0, 7.0, np.nan]),
    ('-', [-1.0, np.nan, 1.0, 3.0, np.nan]),
    ('*', [2.0, np.nan, 6.0, 10.0, np.nan]),
    ('/', [0.5, np.nan, 1.5, 2.5, np.nan]),
])
def test_every_operator_works_against_a_constant_too(contract_event_log, op, expected):
    result = values(contract_event_log,
                    arithmetic_spec('r', 'Treat', 'dose', op, constant=2))
    assert result == pytest.approx(expected, nan_ok=True)


def test_dividing_by_zero_gives_nan_rather_than_an_infinity(lifecycle_event_log):
    """The widget warns about it; the column is still worth producing."""
    result = values(lifecycle_event_log,
                    arithmetic_spec('ratio', 'Check', 'dose', '/', 'dose'))
    assert result == pytest.approx(
        [np.nan, np.nan, 1.0, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan], nan_ok=True)


def test_arithmetic_may_read_a_column_an_earlier_spec_produced(lifecycle_event_log):
    result = values(lifecycle_event_log, [
        running_agg_spec('total', 'dose'),
        arithmetic_spec('half_total', 'Check', 'total', '/', constant=2),
    ])
    assert result == pytest.approx(
        [np.nan, np.nan, 3.0, np.nan, np.nan, np.nan, 1.5, np.nan, 0.0], nan_ok=True)


# ----------------------------------------------------------------------
# time delta
# ----------------------------------------------------------------------
def test_the_gap_to_any_previous_event_reads_the_case_in_time_order(lifecycle_event_log):
    result = values(lifecycle_event_log, delta_spec('gap', 'Treat', unit='hours'))
    assert result == pytest.approx(
        [np.nan, 2.0, np.nan, 2.0, 3.0, np.nan, np.nan, 3.0, np.nan], nan_ok=True)


def test_the_gap_to_the_previous_event_of_the_same_type_skips_the_others(lifecycle_event_log):
    result = values(lifecycle_event_log,
                    delta_spec('gap', 'Treat', neighbour='same', unit='hours'))
    assert result == pytest.approx(
        [np.nan, 2.0, np.nan, 3.0, 3.0, np.nan, np.nan, np.nan, np.nan], nan_ok=True)


def test_the_gap_to_a_chosen_type_reads_only_that_type(lifecycle_event_log):
    result = values(lifecycle_event_log,
                    delta_spec('gap', 'Treat', neighbour='type',
                               neighbour_type='Check', unit='hours'))
    assert result == pytest.approx(
        [np.nan, np.nan, np.nan, 2.0, 5.0, np.nan, np.nan, 3.0, np.nan], nan_ok=True)


def test_an_event_with_no_neighbour_may_take_a_zero_instead_of_a_nat(lifecycle_event_log):
    result = values(lifecycle_event_log,
                    delta_spec('gap', 'Treat', direction='next', unit='hours',
                               missing='zero'))
    assert result == pytest.approx(
        [2.0, 1.0, np.nan, 3.0, 0.0, 1.0, np.nan, 0.0, np.nan], nan_ok=True)


def test_the_zero_rule_does_not_reach_events_of_another_type(lifecycle_event_log):
    """An event of another type has no value here at all, which is a different
    statement from an event with no neighbour."""
    column = apply_event_specs(lifecycle_event_log, [
        delta_spec('gap', 'Treat', unit='hours', missing='zero')])['gap']
    assert column[[2, 6, 8]].isna().all()


def test_an_event_type_that_is_always_first_has_no_previous_neighbour(lifecycle_event_log):
    """An all-missing since-previous column can be the *right* answer.

    ``Treat`` opens c1 and c2, and c3's ``Check`` sorts ahead of its ``Treat``, so
    on this log only c3's ``Treat`` has anything before it. In a log where the
    opening activity opens *every* case -- ``Create Fine`` in the road-traffic
    log -- the column is empty on every row, and that is the enrichment working.
    The widget warns before the column is staged rather than computing something
    else; see ``neighbour_coverage`` in ``catalog.py``.
    """
    opening = lifecycle_event_log[lifecycle_event_log['concept:name'] == 'Register']
    assert opening.empty  # no opening activity here; build one that opens every case

    start = pd.Timestamp('2024-01-01')
    rows = [('c1', 'Open', 0), ('c1', 'Work', 1),
            ('c2', 'Open', 0), ('c2', 'Work', 2), ('c2', 'Work', 5)]
    log = pd.DataFrame({
        'case:concept:name': [row[0] for row in rows],
        'concept:name': [row[1] for row in rows],
        'time:timestamp': [start + pd.Timedelta(hours=row[2]) for row in rows],
    })

    column = apply_event_specs(log, [delta_spec('gap', 'Open', unit='hours')])['gap']
    assert column.isna().all()

    # The same type measured the other way is fully populated, which is what the
    # widget points the user at.
    forward = apply_event_specs(log, [delta_spec('gap', 'Open', direction='next',
                                                 unit='hours')])['gap']
    assert forward[log['concept:name'] == 'Open'].notna().all()


def test_the_zero_rule_reaches_the_timedelta_unit_too(lifecycle_event_log):
    """`zero` has to mean `Timedelta(0)` when the column keeps the pandas dtype,
    not `0.0` -- a float in a timedelta column would not survive the assignment."""
    column = apply_event_specs(lifecycle_event_log, [
        delta_spec('gap', 'Treat', unit='timedelta', missing='zero')])['gap']
    assert pd.api.types.is_timedelta64_dtype(column)
    # rows 0 and 5 open their case: in scope, no neighbour, so they take the zero
    assert column[0] == pd.Timedelta(0)
    assert column[5] == pd.Timedelta(0)
    assert column[1] == pd.Timedelta(hours=2)
    # rows 2, 6 and 8 are Check events: out of scope, and the rule never reaches them
    assert column[[2, 6, 8]].isna().all()


def test_a_time_binning_on_a_column_of_no_times_produces_no_categories():
    """`year` reads its vocabulary off the observed range, and an all-missing
    column has none -- the cut has to come back empty rather than raise."""
    log = pd.DataFrame({
        'case:concept:name': ['c1', 'c1'],
        'concept:name': ['Treat', 'Check'],
        'time:timestamp': pd.to_datetime(['2024-01-01', '2024-01-02']),
        'sampled_at': pd.to_datetime([None, None]),
    })
    column = apply_event_specs(
        log, [time_binning_spec('year', 'Treat', 'sampled_at', 'year')])['year']
    assert list(column.cat.categories) == []
    assert column.isna().all()


def test_the_timedelta_unit_keeps_the_pandas_dtype(lifecycle_event_log):
    column = apply_event_specs(lifecycle_event_log, [
        delta_spec('gap', 'Treat', unit='timedelta')])['gap']
    assert pd.api.types.is_timedelta64_dtype(column)
    assert column[1] == pd.Timedelta(hours=2)


# ----------------------------------------------------------------------
# running aggregation
# ----------------------------------------------------------------------
def test_a_running_total_is_written_on_every_event_of_the_case(lifecycle_event_log):
    result = values(lifecycle_event_log, running_agg_spec('total', 'dose'))
    assert result == pytest.approx([1.0, 2.0, 6.0, 8.0, 10.0, 3.0, 3.0, 4.0, 0.0])


def test_a_running_count_counts_only_events_that_carry_a_value(lifecycle_event_log):
    result = values(lifecycle_event_log, running_agg_spec('seen', 'dose', 'count'))
    assert result == pytest.approx([1.0, 2.0, 3.0, 4.0, 5.0, 1.0, 2.0, 1.0, 0.0])


def test_a_running_max_carries_over_events_with_no_value(lifecycle_event_log):
    result = values(lifecycle_event_log, running_agg_spec('peak', 'dose', 'runmax'))
    assert result == pytest.approx([1.0, 1.0, 4.0, 4.0, 4.0, 3.0, 3.0, 4.0, 0.0])


def test_a_running_min_stays_missing_until_the_first_value(lifecycle_event_log):
    """Unlike cumsum, count and runmax, a minimum has no answer before there is
    a value -- and 0 would be a low no event reported."""
    result = values(lifecycle_event_log, running_agg_spec('floor', 'dose', 'runmin'))
    assert result == pytest.approx(
        [1.0, 1.0, 1.0, 1.0, 1.0, 3.0, 0.0, 4.0, np.nan], nan_ok=True)


def test_forward_fill_carries_the_last_value_seen(lifecycle_event_log):
    result = values(lifecycle_event_log, running_agg_spec('last', 'dose', 'ffill'))
    assert result == pytest.approx(
        [1.0, 1.0, 4.0, 2.0, 2.0, 3.0, 0.0, 4.0, np.nan], nan_ok=True)


def test_zero_between_writes_the_total_only_where_a_value_lands(event_log):
    """The ``event_log`` fixture has whole activities with no ``amount`` at all,
    which is what makes the two carry rules differ."""
    carried = values(event_log, running_agg_spec('total', 'amount'))
    between = values(event_log, running_agg_spec('total', 'amount', carry='zero'))
    assert carried == pytest.approx([0, 10, 30, 30, 0, 0, 0, 7.5, 7.5, 0])
    assert between == pytest.approx([0, 10, 30, 0, 0, 0, 0, 7.5, 0, 0])


# ----------------------------------------------------------------------
# binning: numeric
# ----------------------------------------------------------------------
def test_bins_label_every_value_and_leave_the_others_missing(lifecycle_event_log):
    result = labels(lifecycle_event_log,
                    binning_spec('level', 'Treat', 'dose', [1.5], ['low', 'high']))
    assert result == ['low', 'low', None, 'high', 'high', 'high', None, 'high', None]


def test_the_outer_edges_are_unbounded_so_nothing_falls_outside_a_bin(lifecycle_event_log):
    """A single edge gives the two-way column a threshold flag would produce."""
    column = apply_event_specs(lifecycle_event_log, [
        binning_spec('level', 'Check', 'dose', [100.0], ['under', 'over'])])['level']
    assert list(column.cat.categories) == ['under', 'over']
    assert column[2] == 'under' and column[6] == 'under' and pd.isna(column[8])


def test_a_missing_input_stays_missing(lifecycle_event_log):
    column = apply_event_specs(lifecycle_event_log, [
        binning_spec('level', 'Check', 'dose', [1.0])])['level']
    assert pd.isna(column[8])


# ----------------------------------------------------------------------
# binning: time
# ----------------------------------------------------------------------
@pytest.mark.parametrize('part, expected', [
    ('year', ['2022', '2022', '2024', '2024', '2022', '2024']),
    ('month', ['3', '12', '7', '7', '3', '1']),
    ('weekday', ['Mon', 'Sun', 'Thu', 'Sat', 'Mon', 'Mon']),
    ('hour', ['9', '23', '0', '12', '9', '18']),
])
def test_a_timestamp_is_cut_into_its_natural_parts(time_event_log, part, expected):
    spec = time_binning_spec(part, '*', STAMP, part)
    assert labels(time_event_log, spec) == expected


@pytest.mark.parametrize('part, categories', [
    ('month', [str(value) for value in range(1, 13)]),
    ('hour', [str(value) for value in range(24)]),
    ('weekday', ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']),
    ('year', ['2022', '2023', '2024']),
])
def test_every_category_exists_whether_or_not_the_log_has_it(time_event_log, part, categories):
    """A rule written against a preview sample still reads on the full log. The
    fixture contains no 2023, so a year cut has to invent the gap year too."""
    column = apply_event_specs(time_event_log,
                               [time_binning_spec(part, '*', STAMP, part)])[part]
    assert list(column.cat.categories) == categories
    assert column.cat.ordered


def test_a_time_cut_scoped_to_one_type_leaves_the_others_missing(time_event_log):
    result = labels(time_event_log, time_binning_spec('wd', 'Check', STAMP, 'weekday'))
    assert result == [None, 'Sun', None, None, 'Mon', 'Mon']


# ----------------------------------------------------------------------
# batch properties
# ----------------------------------------------------------------------
def test_applying_the_same_batch_twice_changes_nothing(lifecycle_event_log):
    specs = [delta_spec('gap', 'Treat'), running_agg_spec('total', 'dose')]
    once = apply_event_specs(lifecycle_event_log, specs)
    twice = apply_event_specs(once, specs)
    pd.testing.assert_frame_equal(once, twice)


def test_removal_is_expressed_by_replaying_without_the_spec(lifecycle_event_log):
    keep = delta_spec('gap', 'Treat')
    both = apply_event_specs(lifecycle_event_log, [keep, running_agg_spec('total', 'dose')])
    assert 'total' in both.columns
    replayed = apply_event_specs(lifecycle_event_log, [keep])
    assert 'total' not in replayed.columns and 'gap' in replayed.columns


def test_the_source_log_is_left_alone(lifecycle_event_log):
    apply_event_specs(lifecycle_event_log, [running_agg_spec('total', 'dose')])
    assert 'total' not in lifecycle_event_log.columns


def test_an_enriched_log_carries_its_own_provenance(lifecycle_event_log):
    specs = [running_agg_spec('total', 'dose'), delta_spec('gap', 'Treat')]
    enriched = apply_event_specs(lifecycle_event_log, specs)
    assert event_specs_of(enriched) == specs


def test_provenance_ignores_a_record_whose_column_is_gone(lifecycle_event_log):
    enriched = apply_event_specs(lifecycle_event_log, [running_agg_spec('total', 'dose')])
    trimmed = enriched.drop(columns=['total'])
    trimmed.attrs = dict(enriched.attrs)
    assert event_specs_of(trimmed) == []


@pytest.mark.parametrize('column, users', [
    ('dose', ['total', 'half_total_of_dose']),
    ('total', ['from_total']),
    ('gap', []),
])
def test_a_column_reports_what_reads_it(column, users):
    """Removing an event column another one derives from would leave that one
    standing on nothing, so the widget refuses rather than cascade."""
    specs = [
        running_agg_spec('total', 'dose'),
        arithmetic_spec('half_total_of_dose', 'Check', 'dose', '/', constant=2),
        arithmetic_spec('from_total', 'Check', 'total', '*', constant=2),
        delta_spec('gap', 'Treat'),
    ]
    assert event_columns_using(specs, column) == users


def test_an_unknown_kind_is_refused_rather_than_silently_skipped(lifecycle_event_log):
    from eclear.enrichment import EventEnrichmentSpec  # pylint: disable=import-outside-toplevel
    with pytest.raises(ValueError, match='unknown event enrichment kind'):
        apply_event_specs(lifecycle_event_log,
                          [EventEnrichmentSpec(kind='sorcery', column='x')])
