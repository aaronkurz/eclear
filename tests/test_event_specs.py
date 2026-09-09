"""Tests for eclear.enrichment.event_specs: what a spec is and what it may say.

Two halves, mirroring the module. The naming half pins the suggestions, which
are only *defaults* -- a user may overwrite any of them -- but which have to stay
in step with the frontend helper of the same name so a column built by clicking
and one built in a notebook cell come out called the same thing.

The validation half is the backstop the widget sits in front of: every rejection
here is also a disabled Stage button, so a reason reaching Python means the two
disagreed about the log.
"""
import pytest

from eclear.enrichment import (
    EVENT_KIND_GROUPS,
    EVENT_KINDS,
    EventEnrichmentSpec,
    arithmetic_spec,
    binning_mode,
    binning_spec,
    default_bin_labels,
    delta_spec,
    event_specs_from_dicts,
    normalize_op,
    running_agg_spec,
    suggest_column,
    time_binning_spec,
    validate_event_spec,
)

COLUMNS = ['case:concept:name', 'time:timestamp', 'concept:name', 'dose',
           'lifecycle:transition', 'taken']
NUMERIC = ['dose']
TIMES = ['time:timestamp']
TYPES = ['Treat', 'Check']


# ----------------------------------------------------------------------
# kinds and their grouping
# ----------------------------------------------------------------------
def test_the_rail_order_is_the_grouping_flattened():
    """One source of truth: membership and order cannot drift apart."""
    assert EVENT_KINDS == tuple(kind for _, _, kinds in EVENT_KIND_GROUPS
                                for kind in kinds)


def test_every_kind_belongs_to_exactly_one_group():
    placed = [kind for _, _, kinds in EVENT_KIND_GROUPS for kind in kinds]
    assert sorted(placed) == sorted(set(EVENT_KINDS))


# ----------------------------------------------------------------------
# round-trip
# ----------------------------------------------------------------------
def test_a_spec_survives_the_trait_boundary():
    spec = arithmetic_spec('dose_per_two', 'Treat', 'dose', '/', constant=2)
    assert EventEnrichmentSpec.from_dict(spec.to_dict()) == spec


def test_specs_from_dicts_reads_a_whole_payload():
    specs = [delta_spec('gap', 'Treat'), running_agg_spec('total', 'dose')]
    assert event_specs_from_dicts([spec.to_dict() for spec in specs]) == specs


def test_an_unscoped_spec_reports_itself_as_unscoped():
    assert running_agg_spec('total', 'dose').scoped is False
    assert delta_spec('gap', 'Treat').scoped is True


@pytest.mark.parametrize('written, canonical', [
    ('−', '-'), ('×', '*'), ('÷', '/'), ('+', '+'), ('-', '-'),
])
def test_typographic_operators_normalize(written, canonical):
    """The widget shows − × ÷; only the ASCII forms reach an enricher."""
    assert normalize_op(written) == canonical


def test_an_arithmetic_spec_stores_the_normalized_operator():
    assert arithmetic_spec('x', 'Treat', 'dose', '÷', 'dose').params['op'] == '/'


def test_bins_sort_their_edges_and_get_one_more_label_than_edge():
    spec = binning_spec('level', 'Treat', 'dose', [10, 4, 20])
    assert spec.params['edges'] == [4.0, 10.0, 20.0]
    assert spec.params['labels'] == default_bin_labels(3) == [
        'bin_1', 'bin_2', 'bin_3', 'bin_4']


# ----------------------------------------------------------------------
# binning modes
# ----------------------------------------------------------------------
def test_the_two_binning_modes_are_one_kind():
    numeric = binning_spec('level', 'Treat', 'dose', [4])
    timed = time_binning_spec('hour', 'Treat', 'time:timestamp', 'hour')
    assert numeric.kind == timed.kind
    assert binning_mode(numeric) == 'numeric'
    assert binning_mode(timed) == 'time'


def test_a_binning_spec_without_a_mode_is_read_as_numeric():
    """A spec recorded on a frame before the mode existed says nothing about it."""
    legacy = EventEnrichmentSpec(kind='binning', column='level', event_type='Treat',
                                 params={'source': 'dose', 'edges': [4.0],
                                         'labels': ['low', 'high'], 'method': 'custom'})
    assert binning_mode(legacy) == 'numeric'
    assert validate_event_spec(legacy, COLUMNS, TYPES, NUMERIC, TIMES) is None


# ----------------------------------------------------------------------
# suggested names
# ----------------------------------------------------------------------
@pytest.mark.parametrize('spec, expected', [
    (arithmetic_spec('_', 'Treat', 'dose', '/', 'Age'), 'dose_per_Age'),
    (arithmetic_spec('_', 'Treat', 'dose', '*', constant=2), 'dose_x_2'),
    (delta_spec('_', 'Treat', unit='hours'), 'since_prev_h'),
    (delta_spec('_', 'Treat', direction='next', neighbour='same', unit='min'),
     'until_next_same_min'),
    (delta_spec('_', 'Treat', neighbour='type', neighbour_type='Check', unit='timedelta'),
     'since_prev_Check'),
    (running_agg_spec('_', 'Dose', 'cumsum'), 'dose_cum'),
    (running_agg_spec('_', 'Dose', 'runmin'), 'dose_running_min'),
    (running_agg_spec('_', 'Dose', 'ffill'), 'dose_last_seen'),
    (binning_spec('_', 'Treat', 'dose', [4]), 'dose_level'),
    (time_binning_spec('_', 'Treat', 'time:timestamp', 'weekday'),
     'time_timestamp_weekday'),
    (time_binning_spec('_', 'Treat', 'time:timestamp', 'hour'), 'time_timestamp_hour'),
])
def test_the_suggested_name_reads_off_the_configuration(spec, expected):
    assert suggest_column(spec.kind, spec.params) == expected


def test_the_suggestion_survives_a_name_that_is_not_column_safe():
    spec = arithmetic_spec('_', 'Treat', 'org:group', '+', 'lifecycle:transition')
    assert suggest_column(spec.kind, spec.params) == 'org_group_plus_lifecycle_transition'


# ----------------------------------------------------------------------
# validation
# ----------------------------------------------------------------------
def test_a_well_formed_spec_has_no_reason_not_to_apply():
    spec = arithmetic_spec('doubled', 'Treat', 'dose', '*', constant=2)
    assert validate_event_spec(spec, COLUMNS, TYPES, NUMERIC, TIMES) is None


def test_a_well_formed_time_binning_has_no_reason_not_to_apply():
    spec = time_binning_spec('weekday', 'Treat', 'time:timestamp', 'weekday')
    assert validate_event_spec(spec, COLUMNS, TYPES, NUMERIC, TIMES) is None


@pytest.mark.parametrize('spec, fragment', [
    (arithmetic_spec('', 'Treat', 'dose', '+', constant=1), 'needs a name'),
    (arithmetic_spec('dose', 'Treat', 'dose', '+', constant=1), 'already exists'),
    (arithmetic_spec('x', 'Nope', 'dose', '+', constant=1), 'no event type'),
    (arithmetic_spec('x', 'Treat', 'lifecycle:transition', '+', constant=1), 'not a numeric'),
    (arithmetic_spec('x', 'Treat', 'dose', '%', constant=1), 'unknown operator'),
    (arithmetic_spec('x', 'Treat', 'dose', '+'), 'right operand or a constant'),
    (delta_spec('x', 'Treat', neighbour='type', neighbour_type='Nope'), 'no event type'),
    (delta_spec('x', 'Treat', unit='fortnights'), 'unknown time unit'),
    (delta_spec('x', 'Treat', missing='blank'), 'unknown missing-value rule'),
    (running_agg_spec('x', 'lifecycle:transition'), 'not a numeric column'),
    (running_agg_spec('x', 'dose', 'median'), 'unknown aggregation'),
    (arithmetic_spec('x', 'Treat', 'dose', '+', 'lifecycle:transition'),
     'is not a numeric attribute'),
    (delta_spec('x', 'Treat', direction='sideways'), 'unknown direction'),
    (delta_spec('x', 'Treat', neighbour='cousin'), 'unknown neighbour rule'),
    (running_agg_spec('x', 'dose', 'cumsum', carry='maybe'), 'unknown carry rule'),
    (binning_spec('x', 'Treat', 'lifecycle:transition', [4]), 'is not a numeric column'),
    (binning_spec('x', 'Treat', 'dose', []), 'at least one edge'),
    (binning_spec('x', 'Treat', 'dose', [4], ['only']), '2 labels'),
    (binning_spec('x', 'Treat', 'dose', [4], ['same', 'same']), 'labels must be distinct'),
    (time_binning_spec('x', 'Treat', 'time:timestamp', 'fortnight'), 'unknown time part'),
    (time_binning_spec('x', 'Treat', 'dose', 'hour'), 'not a timestamp column'),
])
def test_a_spec_the_log_cannot_support_says_why(spec, fragment):
    reason = validate_event_spec(spec, COLUMNS, TYPES, NUMERIC, TIMES)
    assert reason is not None and fragment in reason


def test_an_unknown_binning_mode_is_rejected():
    spec = EventEnrichmentSpec(kind='binning', column='x', event_type='Treat',
                               params={'mode': 'astrological', 'source': 'dose'})
    reason = validate_event_spec(spec, COLUMNS, TYPES, NUMERIC, TIMES)
    assert reason is not None and 'unknown binning mode' in reason


def test_an_unknown_kind_is_rejected_before_anything_else_is_read():
    spec = EventEnrichmentSpec(kind='sorcery', column='x', event_type='Treat')
    assert 'unknown enrichment kind' in (validate_event_spec(spec, COLUMNS, TYPES) or '')


def test_duplicate_edges_are_rejected():
    spec = binning_spec('x', 'Treat', 'dose', [4, 4])
    assert 'distinct' in (validate_event_spec(spec, COLUMNS, TYPES, NUMERIC, TIMES) or '')
