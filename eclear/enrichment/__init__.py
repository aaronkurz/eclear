"""Case-log enrichment: producing columns from an event log, and describing them.

An enrichment is a :class:`~eclear.enrichment.specs.EnrichmentSpec` -- a kind
and its arguments -- and the case-log column it produces is derived from it.
Applying specs records them on the frame, so the case log carries its own
provenance and consumers no longer have to re-parse a column name to learn what
it means:

>>> case_log = create_case_log(event_log)
>>> case_log = apply_specs(case_log, event_log, [
...     counts_spec('Payment'),
...     times_spec('Send Fine', 'end'),
...     tracking_spec('paymentAmount', 'sum', event_type='Payment'),
... ])
>>> describe_attribute('Payment.paymentAmount::sum', provenance_of(case_log)).family
'sum'

:func:`describe_attribute` is what the rule builder uses to group and filter
attributes. It falls back to :func:`parse_attribute_name` for columns with no
record -- ones written by hand, or by an earlier version of this package.

:mod:`~eclear.enrichment.event_enrichers` is the same idea one level down: an
:class:`~eclear.enrichment.event_specs.EventEnrichmentSpec` produces a column on
the *event* log -- a cut into labelled bins, arithmetic over two attributes of
one event, the gap to a neighbour, a running aggregation along the case. Those
columns then become sources the case-log side can track, which is the one place
the two halves meet. :mod:`~eclear.enrichment.event_log` adds the one
log-relative time column the widget writes onto every base log.

:mod:`~eclear.enrichment.catalog` reports what a given event log has to offer to
either half, which is what the enrichment widget renders.
"""
from .specs import (
    ALL_EVENTS,
    ALL_EVENTS_COLUMN,
    ACTIVITY_METHODS,
    BASE_CASE_COLUMNS,
    CATEGORICAL_TRACK_METHODS,
    KIND_BASE,
    KIND_COUNTS,
    KIND_DELAYS,
    KIND_LABELS,
    KIND_TIMES,
    KIND_TRACKING,
    KINDS,
    TRACK_METHODS,
    AttributeMeta,
    EnrichmentSpec,
    column_name,
    convert_name,
    counts_spec,
    delay_spec,
    describe_attribute,
    family_label,
    parse_attribute_name,
    scope_token,
    times_spec,
    tracking_spec,
)
from .enrichers import (
    ACTIVITY_COL,
    CASE_ID_COL,
    PROVENANCE_KEY,
    REL_TIME_COL,
    TIME_COL,
    add_activity_counts,
    add_activity_delay,
    add_activity_times,
    add_tracked_attribute,
    apply_specs,
    base_columns,
    create_case_log,
    drop_columns,
    ensure_relative_time,
    missing_columns,
    provenance_of,
    record_specs,
    specs_from_dicts,
    specs_of,
)
from .event_specs import (
    ALL_EVENT_TYPES,
    BIN_METHODS,
    BINNING_MODES,
    DELTA_DIRECTIONS,
    DELTA_MISSING,
    DELTA_NEIGHBOURS,
    EVENT_KIND_ARITHMETIC,
    EVENT_KIND_BINNING,
    EVENT_KIND_DELTA,
    EVENT_KIND_GROUPS,
    EVENT_KIND_LABELS,
    EVENT_KIND_RUNNING_AGG,
    EVENT_KINDS,
    FORMULA_OPS,
    RUNNING_AGG_CARRY,
    RUNNING_AGGREGATES,
    TIME_PARTS,
    TIME_UNITS,
    WEEKDAY_LABELS,
    EventEnrichmentSpec,
    arithmetic_spec,
    binning_mode,
    binning_spec,
    default_bin_labels,
    delta_spec,
    event_specs_from_dicts,
    normalize_op,
    running_agg_spec,
    slug,
    suggest_column,
    time_binning_spec,
    validate_event_spec,
)
from .event_enrichers import (
    EVENT_PROVENANCE_KEY,
    all_event_types,
    apply_event_specs,
    base_event_columns,
    event_columns_using,
    event_provenance_of,
    event_scope_label,
    event_specs_of,
    record_event_specs,
)
from .catalog import (
    DERIVED_EVENT_COLUMNS,
    QUANTILE_POINTS,
    activity_catalog,
    attribute_kind,
    event_type_catalog,
    is_numeric_series,
    log_summary,
    neighbour_coverage,
    numeric_profiles,
    time_columns,
    track_methods_for,
    trackable_attributes,
)

__all__ = [
    # specs
    'ALL_EVENTS', 'ALL_EVENTS_COLUMN', 'ACTIVITY_METHODS', 'BASE_CASE_COLUMNS',
    'CATEGORICAL_TRACK_METHODS',
    'KIND_BASE', 'KIND_COUNTS', 'KIND_DELAYS', 'KIND_LABELS', 'KIND_TIMES',
    'KIND_TRACKING', 'KINDS', 'TRACK_METHODS',
    'AttributeMeta', 'EnrichmentSpec', 'column_name', 'convert_name', 'counts_spec',
    'delay_spec', 'describe_attribute', 'family_label', 'parse_attribute_name',
    'scope_token', 'times_spec', 'tracking_spec',
    # enrichers
    'ACTIVITY_COL', 'CASE_ID_COL', 'PROVENANCE_KEY', 'REL_TIME_COL', 'TIME_COL',
    'add_activity_counts', 'add_activity_delay', 'add_activity_times',
    'add_tracked_attribute', 'apply_specs', 'base_columns', 'create_case_log',
    'drop_columns', 'ensure_relative_time', 'missing_columns', 'provenance_of',
    'record_specs', 'specs_from_dicts', 'specs_of',
    # event specs
    'ALL_EVENT_TYPES', 'BIN_METHODS', 'BINNING_MODES',
    'DELTA_DIRECTIONS', 'DELTA_MISSING', 'DELTA_NEIGHBOURS',
    'EVENT_KIND_ARITHMETIC', 'EVENT_KIND_BINNING', 'EVENT_KIND_DELTA',
    'EVENT_KIND_GROUPS', 'EVENT_KIND_LABELS', 'EVENT_KIND_RUNNING_AGG', 'EVENT_KINDS',
    'FORMULA_OPS', 'RUNNING_AGG_CARRY', 'RUNNING_AGGREGATES', 'TIME_PARTS',
    'TIME_UNITS', 'WEEKDAY_LABELS',
    'EventEnrichmentSpec', 'arithmetic_spec', 'binning_mode', 'binning_spec',
    'default_bin_labels', 'delta_spec', 'event_specs_from_dicts', 'normalize_op',
    'running_agg_spec', 'slug', 'suggest_column', 'time_binning_spec',
    'validate_event_spec',
    # event enrichers
    'EVENT_PROVENANCE_KEY', 'all_event_types', 'apply_event_specs',
    'base_event_columns', 'event_columns_using', 'event_provenance_of',
    'event_scope_label', 'event_specs_of', 'record_event_specs',
    # catalog
    'DERIVED_EVENT_COLUMNS', 'QUANTILE_POINTS',
    'activity_catalog', 'attribute_kind', 'event_type_catalog', 'is_numeric_series',
    'log_summary', 'neighbour_coverage', 'numeric_profiles', 'time_columns',
    'track_methods_for', 'trackable_attributes',
]
