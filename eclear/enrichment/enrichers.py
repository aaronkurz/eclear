"""Turning an event log into a case log, one :class:`EnrichmentSpec` at a time.

Every function here is vectorized: an enrichment is a ``groupby`` over the event
log, never a row-by-row walk. Each one also records what it produced, so the case
log knows its own provenance instead of leaving the column name to be re-parsed
(see :func:`provenance_of`).

``apply_specs`` is the entry point the widget uses; the single-enrichment
functions are there for notebooks that want one column without assembling a spec.
"""
# Every enricher takes the same tail of arguments -- the case log, the event log,
# what to enrich with, and the three column names that identify a log's axes.
# Splitting that into an options object would obscure the one signature the whole
# module shares, so the argument-count checks are switched off here rather than
# repeated on each function.
# pylint: disable=too-many-arguments, too-many-positional-arguments
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import pandas as pd
from pandas import DataFrame, Series

from .specs import (
    ALL_EVENTS,
    BASE_CASE_COLUMNS,
    KIND_COUNTS,
    KIND_DELAYS,
    KIND_TIMES,
    KIND_TRACKING,
    EnrichmentSpec,
    convert_name,
)

#: Standard XES column names, the defaults everywhere in this package.
CASE_ID_COL = 'case:concept:name'
TIME_COL = 'time:timestamp'
ACTIVITY_COL = 'concept:name'

#: Event-log column holding each event's offset from the start of its case.
REL_TIME_COL = 'rel_time'

#: Key under which the provenance record lives in ``DataFrame.attrs``.
PROVENANCE_KEY = 'eclear_enrichment'


# ----------------------------------------------------------------------
# provenance
# ----------------------------------------------------------------------
def provenance_of(case_log: DataFrame) -> Dict[str, Dict[str, Any]]:
    """The enrichment record a case log carries: column name -> spec dict.

    Empty for a frame that was never enriched, or one rebuilt in a way that
    dropped ``DataFrame.attrs``. Callers must treat an empty record as "unknown"
    rather than "nothing was enriched" -- ``specs.describe_attribute`` does.
    """
    record = case_log.attrs.get(PROVENANCE_KEY)
    if not isinstance(record, dict):
        return {}
    # Only report columns that are actually there: a notebook that dropped a
    # column should not leave a ghost entry behind.
    return {name: spec for name, spec in record.items() if name in case_log.columns}


def specs_of(case_log: DataFrame) -> List[EnrichmentSpec]:
    """The specs a case log was built from, in column order."""
    record = provenance_of(case_log)
    specs = []
    for name in case_log.columns:
        entry = record.get(name)
        if entry:
            specs.append(EnrichmentSpec.from_dict(entry))
    return specs


def record_specs(case_log: DataFrame, specs: Iterable[EnrichmentSpec]) -> DataFrame:
    """Attach (or extend) the provenance record. Mutates and returns ``case_log``."""
    record = dict(case_log.attrs.get(PROVENANCE_KEY) or {})
    for spec in specs:
        record[spec.column] = spec.to_dict()
    case_log.attrs[PROVENANCE_KEY] = record
    return case_log


def drop_columns(case_log: DataFrame, columns: Iterable[str]) -> DataFrame:
    """Remove enriched columns and their provenance entries.

    The base columns of :data:`~eclear.enrichment.specs.BASE_CASE_COLUMNS` are
    never dropped: the case log is not a case log without them.
    """
    removable = [name for name in dict.fromkeys(columns)
                 if name in case_log.columns and name not in BASE_CASE_COLUMNS]
    result = case_log.drop(columns=removable)
    record = {name: spec for name, spec in (case_log.attrs.get(PROVENANCE_KEY) or {}).items()
              if name not in removable}
    result.attrs[PROVENANCE_KEY] = record
    return result


# ----------------------------------------------------------------------
# base case log
# ----------------------------------------------------------------------
def create_case_log(event_log: DataFrame,
                    case_id_col: str = CASE_ID_COL,
                    time_col: str = TIME_COL,
                    activity_col: str = ACTIVITY_COL) -> DataFrame:
    """Build the base case log: one row per case, indexed by case id.

    Produces :data:`~eclear.enrichment.specs.BASE_CASE_COLUMNS` --
    ``start_time``, ``end_time``, ``no_of_events``, ``duration``.

    ``start_time`` and ``end_time`` are the earliest and latest timestamps of the
    case rather than the first and last *rows*, so an event log that is not
    sorted by time still yields a non-negative ``duration``.
    """
    del activity_col  # kept for signature symmetry with the other enrichers
    cases = event_log.groupby(case_id_col)
    case_log = cases.agg(
        start_time=(time_col, 'min'),
        end_time=(time_col, 'max'),
        no_of_events=(time_col, 'size'))
    case_log['duration'] = case_log['end_time'] - case_log['start_time']
    case_log.attrs[PROVENANCE_KEY] = {}
    return case_log


def ensure_relative_time(event_log: DataFrame,
                         case_id_col: str = CASE_ID_COL,
                         time_col: str = TIME_COL) -> DataFrame:
    """Return an event log that has :data:`REL_TIME_COL`, adding it if missing.

    Every activity-time enrichment is measured on it, so rather than require
    callers to have added it first, the enrichers derive it on demand.
    """
    if REL_TIME_COL in event_log.columns:
        return event_log
    result = event_log.copy()
    result[REL_TIME_COL] = result.groupby(case_id_col)[time_col].transform(
        lambda times: times - times.min())
    return result


# ----------------------------------------------------------------------
# activity enrichments
# ----------------------------------------------------------------------
def _activity_counts(event_log: DataFrame,
                     case_id_col: str,
                     activity_col: str) -> DataFrame:
    """Case x activity occurrence counts, zero-filled."""
    return event_log.groupby([case_id_col, activity_col]).size().unstack(fill_value=0)


def _activity_extreme_times(event_log: DataFrame,
                            case_id_col: str,
                            activity_col: str,
                            which: str) -> DataFrame:
    """Case x activity table of the first (``start``) or last (``end``) relative time."""
    with_rel = ensure_relative_time(event_log, case_id_col=case_id_col)
    grouped = with_rel.groupby([case_id_col, activity_col])[REL_TIME_COL]
    extreme = grouped.min() if which == 'start' else grouped.max()
    return extreme.unstack()


def add_activity_counts(case_log: DataFrame,
                        event_log: DataFrame,
                        activities: Optional[Sequence[str]] = None,
                        case_id_col: str = CASE_ID_COL,
                        activity_col: str = ACTIVITY_COL) -> DataFrame:
    """Add ``{Activity}::count`` for each activity: occurrences per case, 0 where absent."""
    specs = [EnrichmentSpec(kind=KIND_COUNTS, method='count', activity=activity)
             for activity in _activities_or_all(event_log, activities, activity_col)]
    return apply_specs(case_log, event_log, specs,
                       case_id_col=case_id_col, activity_col=activity_col)


def add_activity_times(case_log: DataFrame,
                       event_log: DataFrame,
                       activities: Optional[Sequence[str]] = None,
                       which: str = 'start',
                       case_id_col: str = CASE_ID_COL,
                       activity_col: str = ACTIVITY_COL) -> DataFrame:
    """Add ``{Activity}::start`` or ``::end``: relative time of the first or last
    occurrence, ``NaT`` in cases where the activity never happens."""
    specs = [EnrichmentSpec(kind=KIND_TIMES, method=which, activity=activity)
             for activity in _activities_or_all(event_log, activities, activity_col)]
    return apply_specs(case_log, event_log, specs,
                       case_id_col=case_id_col, activity_col=activity_col)


def add_activity_delay(case_log: DataFrame,
                       event_log: DataFrame,
                       activity_from: str,
                       activity_to: str,
                       case_id_col: str = CASE_ID_COL,
                       activity_col: str = ACTIVITY_COL) -> DataFrame:
    """Add ``{A}:{B}::delay`` -- first occurrence of B minus first occurrence of A.

    Negative where B happened first, ``NaT`` where either activity is missing
    from the case. Unlike the original enricher this reads the event log
    directly, so the two ``::start`` columns do not have to exist.
    """
    spec = EnrichmentSpec(kind=KIND_DELAYS, method='delay',
                          activity=activity_from, activity_to=activity_to)
    return apply_specs(case_log, event_log, [spec],
                       case_id_col=case_id_col, activity_col=activity_col)


def add_tracked_attribute(case_log: DataFrame,
                          event_log: DataFrame,
                          attribute: str,
                          method: str,
                          event_type: Optional[str] = None,
                          case_id_col: str = CASE_ID_COL,
                          time_col: str = TIME_COL,
                          activity_col: str = ACTIVITY_COL) -> DataFrame:
    """Add ``{EventType}.{attribute}::{method}``: the attribute folded over a case.

    ``event_type`` restricts the fold to one activity's events; ``None`` folds
    over every event of the case and names the column with
    :data:`~eclear.enrichment.specs.ALL_EVENTS`.
    """
    spec = EnrichmentSpec(kind=KIND_TRACKING, method=method,
                          activity=event_type or ALL_EVENTS, attribute=attribute)
    return apply_specs(case_log, event_log, [spec], case_id_col=case_id_col,
                       time_col=time_col, activity_col=activity_col)


def _activities_or_all(event_log: DataFrame,
                       activities: Optional[Sequence[str]],
                       activity_col: str) -> List[str]:
    if activities is not None:
        return list(activities)
    return [str(activity) for activity in event_log[activity_col].dropna().unique()]


# ----------------------------------------------------------------------
# batch application
# ----------------------------------------------------------------------
def apply_specs(case_log: DataFrame,  # pylint: disable=too-many-locals
                event_log: DataFrame,
                specs: Iterable[EnrichmentSpec],
                case_id_col: str = CASE_ID_COL,
                time_col: str = TIME_COL,
                activity_col: str = ACTIVITY_COL) -> DataFrame:
    """Materialize every spec as a column on a copy of ``case_log``.

    Specs are grouped by what they need before anything is computed, so N count
    columns cost one ``groupby`` rather than N. Re-applying a spec that is
    already present recomputes it in place -- applying is idempotent, which is
    what lets the widget replay its whole applied set after a removal.
    """
    specs = list(specs)
    result = case_log.copy()
    if not specs:
        return result

    counts_needed = any(spec.kind == KIND_COUNTS for spec in specs)
    starts_needed = any(spec.kind == KIND_DELAYS or (spec.kind == KIND_TIMES
                                                     and spec.method == 'start')
                        for spec in specs)
    ends_needed = any(spec.kind == KIND_TIMES and spec.method == 'end' for spec in specs)

    counts = (_activity_counts(event_log, case_id_col, activity_col)
              if counts_needed else None)
    starts = (_activity_extreme_times(event_log, case_id_col, activity_col, 'start')
              if starts_needed else None)
    ends = (_activity_extreme_times(event_log, case_id_col, activity_col, 'end')
            if ends_needed else None)

    tracked = _tracked_columns(event_log, specs, result.index,
                               case_id_col, time_col, activity_col)

    for spec in specs:
        column = spec.column
        if spec.kind == KIND_COUNTS:
            assert counts is not None
            result[column] = _lookup(counts, spec.activity, result.index, fill=0)
        elif spec.kind == KIND_TIMES:
            table = starts if spec.method == 'start' else ends
            assert table is not None
            result[column] = _lookup(table, spec.activity, result.index)
        elif spec.kind == KIND_DELAYS:
            assert starts is not None
            first = _lookup(starts, spec.activity, result.index)
            second = _lookup(starts, spec.activity_to, result.index)
            result[column] = second - first
        elif spec.kind == KIND_TRACKING:
            result[column] = tracked[column]
        else:
            raise ValueError(f'cannot apply enrichment of kind {spec.kind!r}')

    return record_specs(result, specs)


def _lookup(table: DataFrame,
            activity: Optional[str],
            index: pd.Index,
            fill: Any = None) -> Series:
    """One activity's column out of a case x activity table, aligned to the case log.

    An activity that occurs in none of these cases is missing from the table
    entirely; it still deserves a column, filled the same way a case without
    that activity is, and carrying the table's own dtype. The dtype matters: a
    delay subtracts two of these columns, and pandas stores a missing value in
    an object column as a float, which cannot be subtracted from a ``NaT``. The
    activity times of a sample that happens to miss an activity -- which is
    what the widget's preview computes -- are exactly that case.
    """
    if activity is not None and activity in table.columns:
        column = table[activity]
    else:
        dtype = table.dtypes.iloc[0] if len(table.columns) else None
        column = Series(fill, index=table.index, dtype=dtype)
    aligned = column.reindex(index)
    if fill is not None:
        aligned = aligned.fillna(fill)
        if pd.api.types.is_numeric_dtype(aligned):
            aligned = aligned.astype('int64')
    return aligned


def _tracked_columns(event_log: DataFrame,
                     specs: Sequence[EnrichmentSpec],
                     index: pd.Index,
                     case_id_col: str,
                     time_col: str,
                     activity_col: str) -> Dict[str, Series]:
    """Compute every tracking spec, one ``groupby`` per (scope, attribute) pair."""
    by_scope: Dict[Tuple[str, str], List[EnrichmentSpec]] = {}
    for spec in specs:
        if spec.kind != KIND_TRACKING:
            continue
        key = (spec.activity or ALL_EVENTS, spec.attribute or '')
        by_scope.setdefault(key, []).append(spec)

    columns: Dict[str, Series] = {}
    for (scope, attribute), scope_specs in by_scope.items():
        scoped = _scoped_events(event_log, scope, attribute, time_col, activity_col)
        grouped = scoped.groupby(case_id_col, sort=False)[attribute]
        for spec in scope_specs:
            columns[spec.column] = align_tracked(_fold(grouped, spec.method),
                                                 index, spec.method)
    return columns


def _scoped_events(event_log: DataFrame,
                   scope: str,
                   attribute: str,
                   time_col: str,
                   activity_col: str) -> DataFrame:
    """Events a tracking spec folds: one activity's or all, nulls dropped, time-sorted.

    Nulls are dropped rather than folded because that is what a tracked value
    means: ``latest`` is the last value the case actually carried, not the last
    event regardless of whether it said anything.
    """
    if attribute not in event_log.columns:
        raise KeyError(f'event log has no attribute {attribute!r} to track')
    scoped = event_log
    if scope != ALL_EVENTS:
        # Column names mangle spaces, so a scope arrives either as the raw
        # activity name or as its converted form; match both.
        activities = scoped[activity_col]
        scoped = scoped[(activities == scope)
                        | (activities.map(convert_name) == scope)]
    scoped = scoped[scoped[attribute].notna()]
    return scoped.sort_values(time_col, kind='stable')


def _fold(grouped, method: str) -> Series:  # pylint: disable=too-many-return-statements
    """Apply one tracking method to a per-case group of non-null values."""
    if method == 'latest':
        return grouped.last()
    if method == 'count':
        return grouped.count()
    if method == 'append':
        # ``apply`` rather than ``agg``: pandas 3 routes ``agg(list)`` through a
        # path that tries to fit the list back into the column's own dtype, and
        # a categorical -- which is what every binning enrichment produces --
        # raises on the unhashable list. ``apply`` returns the same object
        # column for every other dtype.
        return grouped.apply(list)
    if method == 'is_unique':
        # Nulls are already gone, so this asks whether the values the case
        # actually carried were all the same -- not whether it carried any.
        return grouped.nunique() <= 1
    if method == 'sum':
        summed = grouped.sum()
        return summed.round(2) if pd.api.types.is_float_dtype(summed) else summed
    if method == 'min':
        return grouped.min()
    if method == 'max':
        return grouped.max()
    raise ValueError(f'unknown tracking method {method!r}')


def align_tracked(column: Series, index: pd.Index, method: str) -> Series:
    """Align a folded column to the case log, filling cases the fold never saw.

    A case with no matching event has counted zero and summed zero; it has no
    latest, minimum or maximum, and its value sequence is empty. Nor does it
    have an ``is_unique``: whether a value it never carried changed is not a
    question with a true-or-false answer, so the column is a *nullable* boolean
    and that case is ``<NA>``.
    """
    aligned = column.reindex(index)
    if method == 'count':
        return aligned.fillna(0).astype('int64')
    if method == 'sum':
        return aligned.fillna(0)
    if method == 'is_unique':
        return aligned.astype('boolean')
    if method == 'append':
        return Series([value if isinstance(value, list) else []
                       for value in aligned], index=index, dtype='object')
    return aligned


def missing_columns(case_log: DataFrame, specs: Iterable[EnrichmentSpec]) -> List[str]:
    """Columns the given specs would add that the case log does not have yet."""
    return [spec.column for spec in specs if spec.column not in case_log.columns]


def base_columns(case_log: DataFrame) -> List[str]:
    """The fixed case-log columns present, in canonical order."""
    return [name for name in BASE_CASE_COLUMNS if name in case_log.columns]


def specs_from_dicts(records: Iterable[Mapping[str, Any]]) -> List[EnrichmentSpec]:
    """Rebuild specs from the dicts the widget sends over traitlets."""
    return [EnrichmentSpec.from_dict(record) for record in records]
