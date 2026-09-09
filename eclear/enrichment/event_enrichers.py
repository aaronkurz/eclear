"""Specs to *event*-log columns.

The event-log counterpart of :mod:`~eclear.enrichment.enrichers`. Same two
properties, for the same reason: :func:`apply_event_specs` returns a copy, and
applying is idempotent, so the widget can replay its whole applied set onto the
pristine log after a removal rather than patching a column out of a frame.

Specs are applied in order onto the accumulating frame, so an arithmetic column
may read a column an earlier spec in the same batch produced. That is also why
the replay is the only correct way to remove one: dropping a column that a later
spec read would leave the later column standing on nothing.

Every enrichment reads its case in *timestamp* order regardless of row order, and
writes back on the log's own index -- an event log that arrives unsorted comes
back unsorted, with the right values.
"""
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

import numpy as np
import pandas as pd
from pandas import DataFrame, Series

from .event_specs import (
    ALL_EVENT_TYPES,
    EVENT_KIND_ARITHMETIC,
    EVENT_KIND_BINNING,
    EVENT_KIND_DELTA,
    EVENT_KIND_RUNNING_AGG,
    UNIT_HOURS,
    WEEKDAY_LABELS,
    EventEnrichmentSpec,
    binning_mode,
    normalize_op,
)

CASE_ID_COL = 'case:concept:name'
TIME_COL = 'time:timestamp'
ACTIVITY_COL = 'concept:name'

#: ``DataFrame.attrs`` key the applied event specs are recorded under, so an
#: enriched event log carries its own provenance the way a case log does.
EVENT_PROVENANCE_KEY = 'interox_event_enrichment'

#: Seconds in an hour: every timespan is rendered through hours, because
#: :data:`~eclear.enrichment.event_specs.UNIT_HOURS` is written in them.
_SECONDS_PER_HOUR = 3600.0


# ----------------------------------------------------------------------
# provenance
# ----------------------------------------------------------------------
def event_provenance_of(event_log: DataFrame) -> Dict[str, Dict[str, Any]]:
    """The ``{column: spec dict}`` record an enriched event log carries."""
    record = event_log.attrs.get(EVENT_PROVENANCE_KEY)
    return dict(record) if isinstance(record, dict) else {}


def event_specs_of(event_log: DataFrame) -> List[EventEnrichmentSpec]:
    """The event enrichments recorded on a log, in column order.

    Only records whose column is still present are returned: a frame that has
    been sliced or rebuilt by hand keeps its ``attrs`` but may have lost the
    columns they describe.
    """
    provenance = event_provenance_of(event_log)
    specs = []
    for column in event_log.columns:
        record = provenance.get(str(column))
        if record:
            try:
                specs.append(EventEnrichmentSpec.from_dict(record))
            except (KeyError, TypeError, ValueError):
                continue
    return specs


def record_event_specs(event_log: DataFrame,
                       specs: Iterable[EventEnrichmentSpec]) -> DataFrame:
    """Record specs on the frame, replacing any earlier record for the same column."""
    record = event_provenance_of(event_log)
    for spec in specs:
        record[spec.column] = spec.to_dict()
    event_log.attrs[EVENT_PROVENANCE_KEY] = record
    return event_log


# ----------------------------------------------------------------------
# batch application
# ----------------------------------------------------------------------
def apply_event_specs(event_log: DataFrame,
                      specs: Iterable[EventEnrichmentSpec],
                      case_id_col: str = CASE_ID_COL,
                      time_col: str = TIME_COL,
                      activity_col: str = ACTIVITY_COL) -> DataFrame:
    """Materialize every spec as a column on a copy of ``event_log``."""
    result = event_log.copy()
    result.attrs = dict(event_log.attrs)
    specs = list(specs)
    if not specs:
        return result

    order = _time_order(result, case_id_col, time_col)
    for spec in specs:
        result[spec.column] = _column_for(spec, result, order, case_id_col,
                                          time_col, activity_col)
    return record_event_specs(result, specs)


def _column_for(spec: EventEnrichmentSpec, log: DataFrame, order: pd.Index,  # pylint: disable=too-many-arguments, too-many-positional-arguments
                case_id_col: str, time_col: str, activity_col: str) -> Series:
    if spec.kind == EVENT_KIND_ARITHMETIC:
        return _apply_arithmetic(spec, log, activity_col)
    if spec.kind == EVENT_KIND_DELTA:
        return _apply_delta(spec, log, order, case_id_col, time_col, activity_col)
    if spec.kind == EVENT_KIND_RUNNING_AGG:
        return _apply_running_agg(spec, log, order, case_id_col)
    if spec.kind == EVENT_KIND_BINNING:
        return _apply_binning(spec, log, activity_col)
    raise ValueError(f'unknown event enrichment kind {spec.kind!r}')


def _time_order(log: DataFrame, case_id_col: str, time_col: str) -> pd.Index:
    """The log's index, sorted by case and then timestamp.

    ``mergesort`` is stable, so events sharing a timestamp keep the order the
    log gives them -- which is the only order there is to go on.
    """
    return log.sort_values([case_id_col, time_col], kind='mergesort').index


def _scope_mask(spec: EventEnrichmentSpec, log: DataFrame, activity_col: str) -> Series:
    """Which rows the column is written on: one event type's, or every row's."""
    if not spec.scoped:
        return pd.Series(True, index=log.index)
    return log[activity_col].astype(str) == str(spec.event_type)


# ----------------------------------------------------------------------
# arithmetic
# ----------------------------------------------------------------------
def _apply_arithmetic(spec: EventEnrichmentSpec, log: DataFrame,
                      activity_col: str) -> Series:
    """Arithmetic on two numeric attributes of one event, or one and a constant.

    Division by zero yields ``NaN`` rather than an infinity: the widget warns
    about it, but a column that would otherwise be usable is still produced.
    """
    params = spec.params
    left = _numeric(log[params['left']])
    if params.get('right') is not None:
        right = _numeric(log[params['right']])
    else:
        right = pd.Series(float(params['constant']), index=log.index)

    op = normalize_op(str(params['op']))
    if op == '+':
        values = left + right
    elif op == '-':
        values = left - right
    elif op == '*':
        values = left * right
    else:
        values = (left / right.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)

    return values.where(_scope_mask(spec, log, activity_col))


def _numeric(series: Series) -> Series:
    return pd.to_numeric(series, errors='coerce')


# ----------------------------------------------------------------------
# time delta
# ----------------------------------------------------------------------
def _apply_delta(spec: EventEnrichmentSpec, log: DataFrame, order: pd.Index,  # pylint: disable=too-many-arguments, too-many-positional-arguments, too-many-locals
                 case_id_col: str, time_col: str, activity_col: str) -> Series:
    """Gap between an event and its neighbour in the same case.

    ``since previous`` and ``until next`` differ only in which neighbour is read,
    which is why direction is a parameter here rather than two kinds.
    """
    params = spec.params
    ordered = log.loc[order]
    times = pd.to_datetime(ordered[time_col])
    cases = ordered[case_id_col]
    backwards = params['direction'] == 'prev'

    neighbour = params['neighbour']
    if neighbour == 'any':
        shifted = times.groupby(cases).shift(1 if backwards else -1)
    else:
        target = (spec.event_type if neighbour == 'same'
                  else params.get('neighbour_type'))
        candidates = times.where(ordered[activity_col].astype(str) == str(target))
        grouped = candidates.groupby(cases)
        shifted = (grouped.shift(1).groupby(cases).ffill() if backwards
                   else grouped.shift(-1).groupby(cases).bfill())

    gap = (times - shifted) if backwards else (shifted - times)
    gap = gap.reindex(log.index)
    return _as_unit(gap, str(params['unit']), str(params.get('missing', 'NaT')),
                    _scope_mask(spec, log, activity_col))


def _as_unit(gap: Series, unit: str, missing: str, in_scope: Series) -> Series:
    """Render a timespan in the requested unit, then apply the missing rule.

    The missing rule only reaches events the column is written on: an event of
    another type has no value here at all, which is not the same as an event
    with no neighbour.
    """
    if unit == 'timedelta':
        values = gap.where(in_scope)
        if missing == 'zero':
            values = values.mask(in_scope & values.isna(), pd.Timedelta(0))
        return values
    hours = pd.to_timedelta(gap).dt.total_seconds() / _SECONDS_PER_HOUR
    values = (hours / UNIT_HOURS[unit]).where(in_scope)
    if missing == 'zero':
        values = values.mask(in_scope & values.isna(), 0.0)
    return values


# ----------------------------------------------------------------------
# running aggregation
# ----------------------------------------------------------------------
def _apply_running_agg(spec: EventEnrichmentSpec, log: DataFrame,
                       order: pd.Index, case_id_col: str) -> Series:
    """Running aggregation of one numeric column along each case, on every event.

    ``cumsum``, ``count`` and ``runmax`` start a case at 0 rather than missing:
    the question they answer -- how much has accumulated so far -- has the answer
    "none" before the first value.

    ``runmin`` and ``ffill`` stay missing until the case's first value, because
    theirs does not. "The smallest value so far" and "the last value seen" have
    no answer before there is a value, and 0 would be both a spuriously low
    minimum and a reading nobody took.
    """
    params = spec.params
    ordered = log.loc[order]
    values = _numeric(ordered[params['source']])
    cases = ordered[case_id_col]

    aggregate = params['aggregate']
    if aggregate == 'cumsum':
        running = values.fillna(0.0).groupby(cases).cumsum()
    elif aggregate == 'count':
        running = values.notna().astype('float64').groupby(cases).cumsum()
    elif aggregate == 'runmax':
        running = values.groupby(cases).cummax()
        running = running.groupby(cases).ffill().fillna(0.0)
    elif aggregate == 'runmin':
        running = values.groupby(cases).cummin()
        running = running.groupby(cases).ffill()
    else:
        running = values.groupby(cases).ffill()

    if params.get('carry', 'carry') != 'carry':
        running = running.where(values.notna(), 0.0)
    return running.reindex(log.index)


# ----------------------------------------------------------------------
# binning
# ----------------------------------------------------------------------
def _apply_binning(spec: EventEnrichmentSpec, log: DataFrame,
                   activity_col: str) -> Series:
    """Cut a column into labelled categories: numeric intervals, or a time part."""
    if binning_mode(spec) == 'time':
        return _apply_time_binning(spec, log, activity_col)
    return _apply_numeric_binning(spec, log, activity_col)


def _apply_numeric_binning(spec: EventEnrichmentSpec, log: DataFrame,
                           activity_col: str) -> Series:
    """Cut a numeric column into labelled intervals with unbounded outer edges.

    No value can fall outside a bin, so a missing result means a missing input
    or an event of another type -- never a value the edges failed to cover.
    """
    params = spec.params
    edges = [-np.inf, *sorted(float(edge) for edge in params['edges']), np.inf]
    values = _numeric(log[params['source']]).where(_scope_mask(spec, log, activity_col))
    return pd.cut(values, bins=edges, labels=list(params['labels']))


def _apply_time_binning(spec: EventEnrichmentSpec, log: DataFrame,
                        activity_col: str) -> Series:
    """Cut a timestamp column into one of its natural parts.

    The result is an *ordered* category carrying every category the part has,
    whether or not the log contains it: all twelve months, all seven weekdays,
    all twenty-four hours, and every year between the earliest and the latest
    seen. A rule written against a preview sample therefore still reads on the
    full log, and a bar chart of the column keeps its empty slots.
    """
    params = spec.params
    times = pd.to_datetime(log[params['source']], errors='coerce')
    times = times.where(_scope_mask(spec, log, activity_col))
    part = str(params['part'])

    if part == 'weekday':
        codes = times.dt.weekday
        categories = list(WEEKDAY_LABELS)
        labels = codes.map(lambda code: WEEKDAY_LABELS[int(code)]
                           if pd.notna(code) else None)
    else:
        codes = getattr(times.dt, part)
        categories = [str(value) for value in _time_categories(part, codes)]
        labels = codes.map(lambda code: str(int(code)) if pd.notna(code) else None)

    return pd.Series(
        pd.Categorical(labels, categories=categories, ordered=True),
        index=log.index)


def _time_categories(part: str, codes: Series) -> List[int]:
    """Every category a time part has, in order.

    Months, hours and weekdays have a fixed vocabulary. Years do not, so the
    observed range is used -- contiguous rather than only the years present, so
    a gap year still has a slot.
    """
    if part == 'month':
        return list(range(1, 13))
    if part == 'hour':
        return list(range(24))
    present = codes.dropna()
    if present.empty:
        return []
    return list(range(int(present.min()), int(present.max()) + 1))


# ----------------------------------------------------------------------
# introspection
# ----------------------------------------------------------------------
def event_columns_using(specs: Iterable[EventEnrichmentSpec],
                        column: str) -> List[str]:
    """Columns produced by ``specs`` that read ``column`` as an input.

    Removing an event column that a later one derives from would leave that
    later column standing on nothing, so the widget refuses rather than cascade.
    """
    users = []
    for spec in specs:
        inputs = _inputs_of(spec)
        if column in inputs:
            users.append(spec.column)
    return users


def _inputs_of(spec: EventEnrichmentSpec) -> List[str]:
    params: Mapping[str, Any] = spec.params
    if spec.kind == EVENT_KIND_ARITHMETIC:
        return [name for name in (params.get('left'), params.get('right')) if name]
    if spec.kind in (EVENT_KIND_RUNNING_AGG, EVENT_KIND_BINNING):
        return [name for name in (params.get('source'),) if name]
    return []


def base_event_columns(event_log: DataFrame,
                       specs: Optional[Sequence[EventEnrichmentSpec]] = None) -> List[str]:
    """Columns the log carries that no event enrichment produced."""
    produced = {spec.column for spec in (specs if specs is not None
                                         else event_specs_of(event_log))}
    return [str(name) for name in event_log.columns if str(name) not in produced]


def event_scope_label(spec: EventEnrichmentSpec) -> str:
    """How the widget names a spec's scope: the event type, or every event."""
    return 'every event' if not spec.scoped else str(spec.event_type)


def all_event_types(event_log: DataFrame,
                    activity_col: str = ACTIVITY_COL) -> List[str]:
    """Every activity in the log, in the order the log first mentions it."""
    return [str(activity) for activity in event_log[activity_col].dropna().unique()]


ALL_EVENTS_SCOPE = ALL_EVENT_TYPES
