"""What an event log offers to be enriched with.

The widget cannot ask the user to pick an activity or an attribute it has not
been told about, so this module reads the event log once and reports what is
there: the activities, and the event attributes grouped by the activity that
carries them.

That grouping is the point. In a real log most attributes belong to one event
type -- a sepsis log records ``CRP`` only on ``CRP`` events and ``Age`` only at
registration -- so offering "track ``CRP``" without saying which events carry it
hides the only thing that makes the column interpretable.
"""
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd
from pandas import DataFrame, Series

from .enrichers import ACTIVITY_COL, CASE_ID_COL, TIME_COL
from .specs import (
    ALL_EVENTS,
    CATEGORICAL_TRACK_METHODS,
    TRACK_METHODS,
    convert_name,
    scope_token,
)

#: Columns the enrichers themselves add to an event log. Tracking any of them
#: would fold a derived value back into the case log, which says nothing new.
DERIVED_EVENT_COLUMNS = frozenset({
    'rel_time', 'rel_log_time', 'order_class', 'ordered_case_id',
    'event_count_fwd', 'event_count_bwd',
})


def is_numeric_series(series: Series) -> bool:
    """Whether every non-missing value of ``series`` reads as a number.

    All-or-nothing: one unparseable value makes the column categorical. An
    all-missing column is categorical too -- there is nothing to put on a
    numeric axis. This is the single numeric test used for rule-builder
    summaries and for deciding which tracking methods an attribute offers.
    """
    non_missing = series.dropna()
    if len(non_missing) == 0:
        return False
    return bool(pd.to_numeric(non_missing, errors='coerce').notna().all())


def track_methods_for(numeric: bool) -> List[str]:
    """The tracking methods an attribute of this type can be folded with."""
    return list(TRACK_METHODS) if numeric else list(CATEGORICAL_TRACK_METHODS)


def log_summary(event_log: DataFrame,
                case_id_col: str = CASE_ID_COL,
                time_col: str = TIME_COL,
                activity_col: str = ACTIVITY_COL) -> Dict[str, Any]:
    """Headline counts and the column names in force, for the widget header."""
    return {
        'cases': int(event_log[case_id_col].nunique()),
        'events': int(len(event_log)),
        'activities': int(event_log[activity_col].nunique()),
        'case_id_col': case_id_col,
        'time_col': time_col,
        'activity_col': activity_col,
    }


def activity_catalog(event_log: DataFrame,
                     case_id_col: str = CASE_ID_COL,
                     activity_col: str = ACTIVITY_COL) -> List[Dict[str, Any]]:
    """Every activity, most frequent first, with the counts the widget shows.

    ``display`` is the name as it appears inside a column (spaces converted);
    ``name`` is the raw value, which is what a spec carries.
    """
    grouped = event_log.groupby(activity_col, sort=False)
    events = grouped.size()
    cases = grouped[case_id_col].nunique()
    order = events.sort_values(ascending=False).index

    return [{
        'name': str(activity),
        'display': convert_name(str(activity)),
        'events': int(events[activity]),
        'cases': int(cases[activity]),
    } for activity in order]


def trackable_attributes(  # pylint: disable=too-many-locals
        event_log: DataFrame,
        case_id_col: str = CASE_ID_COL,
        time_col: str = TIME_COL,
        activity_col: str = ACTIVITY_COL,
        exclude: Optional[Sequence[str]] = None) -> List[Dict[str, Any]]:
    """Event attributes grouped by the event type that carries them.

    An attribute carried by exactly one activity is offered under that activity:
    the log-wide fold would read the same events, and the scoped name says where
    the value came from.

    An attribute carried by more than one is offered *both* ways -- log-wide and
    under each carrier -- because the two folds are genuinely different columns.
    ``append`` over the whole case is the value sequence; ``append`` over one
    activity's events is that activity's sequence, and no heuristic here is
    better placed than the user to say which they meant.

    The cost is length: on a wide log every event type now lists the columns
    every event carries. That is the trade this makes deliberately.

    Returns one group per scope, the log-wide one first, each shaped for the
    widget's tracking pane.
    """
    candidates = _candidate_attributes(event_log, case_id_col, time_col, exclude)
    if not candidates:
        return []

    # One pass: non-null values of every candidate, per activity. The activity
    # column is itself a candidate, so group by a copy of it rather than by the
    # column being counted.
    activities = event_log[activity_col].rename('__activity__')
    presence = _presence_map(event_log[candidates].groupby(activities, sort=False).count())
    activity_events = event_log.groupby(activities, sort=False).size()

    numeric = {name: is_numeric_series(event_log[name]) for name in candidates}
    groups: Dict[str, List[Dict[str, Any]]] = {}

    for name in candidates:
        carriers = [activity for activity, counts in presence.items() if counts.get(name, 0) > 0]
        if not carriers:
            continue
        scopes = ([ALL_EVENTS] + carriers) if len(carriers) > 1 else carriers
        for scope in scopes:
            events = (int(event_log[name].notna().sum()) if scope == ALL_EVENTS
                      else presence[scope][name])
            groups.setdefault(scope, []).append(_attribute_entry(name, scope,
                                                                 numeric[name], events))

    return [_group_entry(scope, entries, activity_events)
            for scope, entries in _ordered_scopes(groups, activity_events)]


def _presence_map(counts: DataFrame) -> Dict[str, Dict[str, int]]:
    """``{activity: {attribute: non-null events}}``, in the frame's own order."""
    return {str(activity): {str(name): int(count) for name, count in row.items()}
            for activity, row in counts.to_dict('index').items()}


def _attribute_entry(attribute: str, scope: str,
                     numeric: bool, events: int) -> Dict[str, Any]:
    return {
        'attribute': attribute,
        'numeric': bool(numeric),
        'events': events,
        'methods': track_methods_for(numeric),
        'column_prefix': f'{scope_token(scope)}.{attribute}::',
    }


def _group_entry(scope: str, entries: List[Dict[str, Any]],
                 activity_events: Series) -> Dict[str, Any]:
    if scope == ALL_EVENTS:
        events = int(activity_events.sum())
        label = 'every event'
    else:
        events = int(activity_events.get(scope, 0))
        label = scope
    return {
        'event_type': scope,
        'display': convert_name(scope),
        'label': label,
        'events': events,
        'attributes': sorted(entries, key=lambda entry: entry['attribute']),
    }


def _ordered_scopes(groups: Dict[str, List[Dict[str, Any]]],
                    activity_events: Series):
    """Log-wide scope first, then activities by event volume."""
    scopes = sorted(
        groups,
        key=lambda scope: (scope != ALL_EVENTS, -int(activity_events.get(scope, 0)), scope),
    )
    return [(scope, groups[scope]) for scope in scopes]


def _candidate_attributes(event_log: DataFrame,
                          case_id_col: str,
                          time_col: str,
                          exclude: Optional[Sequence[str]]) -> List[str]:
    """Columns worth offering: not the log's own axes, not enricher output.

    The activity column stays in. It is non-null on every event, so it is only
    ever offered log-wide -- and folded with ``append`` it is the case's
    sequence variant, one of the most useful case attributes there is.

    Columns containing ``::`` are skipped: that spelling marks a value that has
    already been folded once -- either by this package or by hand -- and folding a
    fold is noise.
    """
    skip = {case_id_col, time_col}
    skip |= DERIVED_EVENT_COLUMNS
    skip |= set(exclude or ())
    return [str(name) for name in event_log.columns
            if str(name) not in skip and '::' not in str(name)]


# ----------------------------------------------------------------------
# what the event log offers to *event*-log enrichment
# ----------------------------------------------------------------------
#: Quantile points sketched per numeric column. The bins pane re-derives edges
#: and per-bin counts on every keystroke; a sketch this size lets it do that in
#: the browser, accurate to about a percent, instead of a round trip per edit.
QUANTILE_POINTS = 101

def attribute_kind(series: Series) -> str:
    """How the widget's pickers classify an event attribute.

    ``num`` is the only kind a formula, an accumulation or a bin cut will accept,
    so this is the test that decides what those pickers may offer -- which is why
    a type mismatch cannot be configured rather than merely rejected.

    Booleans are their own kind rather than numbers, even though they coerce to 0
    and 1 the way :func:`is_numeric_series` reports them. Averaging a flag or
    cutting it into bins is not something anyone means to do.
    """
    if pd.api.types.is_bool_dtype(series) or _is_object_bool(series):
        return 'bool'
    if pd.api.types.is_datetime64_any_dtype(series) or \
            pd.api.types.is_timedelta64_dtype(series):
        return 'time'
    return 'num' if is_numeric_series(series) else 'cat'


def _is_object_bool(series: Series) -> bool:
    """Whether an object column holds nothing but Python booleans.

    XES writes a boolean attribute into an object column, so the dtype alone does
    not say and the values have to be looked at.
    """
    if series.dtype != object:
        return False
    non_missing = series.dropna()
    if len(non_missing) == 0:
        return False
    return bool(non_missing.map(lambda value: isinstance(value, bool)).all())


def neighbour_coverage(event_log: DataFrame,
                       case_id_col: str = CASE_ID_COL,
                       time_col: str = TIME_COL,
                       activity_col: str = ACTIVITY_COL) -> Dict[str, Dict[str, float]]:
    """Per event type, the share of its events that have a neighbour in their case.

    A time delta measures the gap to a neighbouring event, so an event type that
    is always first in its case has no *previous* neighbour to measure against
    and the column comes out empty -- correctly, but silently. The widget shows
    this before the column is staged, which is the difference between "this
    enrichment is broken" and "this enrichment does not apply here".

    Read in timestamp order per case, the same order
    :func:`~eclear.enrichment.event_enrichers.apply_event_specs` reads,
    so the two cannot disagree about which event is first.

    Returns ``{event type: {'prev': fraction, 'next': fraction}}``, each fraction
    in ``[0, 1]``.
    """
    ordered = event_log.sort_values([case_id_col, time_col], kind='mergesort')
    grouped = ordered.groupby(ordered[case_id_col].rename('__case__'), sort=False)
    position = grouped.cumcount()
    size = grouped[time_col].transform('size')

    frame = pd.DataFrame({
        'activity': ordered[activity_col].astype(str),
        'prev': (position > 0),
        'next': (position < size - 1),
    })
    means = frame.groupby('activity', sort=False)[['prev', 'next']].mean()
    return {str(activity): {'prev': float(row['prev']), 'next': float(row['next'])}
            for activity, row in means.iterrows()}


def event_type_catalog(event_log: DataFrame,
                       derived: Optional[Sequence[str]] = None,
                       case_id_col: str = CASE_ID_COL,
                       time_col: str = TIME_COL,
                       activity_col: str = ACTIVITY_COL) -> List[Dict[str, Any]]:
    """Every event type with the attributes its events actually carry.

    An attribute is listed under a type only where that type has a non-null
    value for it, so the sepsis log's ``CRP`` events offer ``CRP`` and the
    registration events do not. ``derived`` names the columns event enrichments
    produced; they are left out because the widget already knows them from its
    applied list, and listing them twice would offer two ways to remove one.
    :data:`DERIVED_EVENT_COLUMNS` -- the relative times the enrichers add -- are
    left out for the same reason they are not trackable: enriching from a derived
    column that nothing chose to create says nothing new.
    """
    skip = {case_id_col, time_col, activity_col} | DERIVED_EVENT_COLUMNS | set(derived or ())
    attributes = [str(name) for name in event_log.columns
                  if str(name) not in skip and '::' not in str(name)]
    kinds = {name: attribute_kind(event_log[name]) for name in attributes}

    grouped = event_log.groupby(event_log[activity_col].rename('__activity__'),
                                sort=False)
    sizes = grouped.size()
    present = _presence_map(grouped[attributes].count()) if attributes else {}

    def entries(activity: str) -> List[Dict[str, Any]]:
        counts = present.get(activity, {})
        return [{'name': name, 'kind': kinds[name], 'events': counts[name]}
                for name in attributes if counts.get(name, 0) > 0]

    coverage = neighbour_coverage(event_log, case_id_col=case_id_col,
                                  time_col=time_col, activity_col=activity_col)
    none = {'prev': 0.0, 'next': 0.0}

    return [{
        'name': str(activity),
        'display': convert_name(str(activity)),
        'events': int(sizes[activity]),
        'attributes': entries(str(activity)),
        'neighbours': coverage.get(str(activity), none),
    } for activity in sizes.sort_values(ascending=False).index]


def time_columns(event_log: DataFrame,
                 derived: Optional[Sequence[str]] = None,
                 case_id_col: str = CASE_ID_COL,
                 time_col: str = TIME_COL,
                 activity_col: str = ACTIVITY_COL) -> Dict[str, List[str]]:
    """Per event type, the timestamp columns a time binning could cut.

    The log's own ``time_col`` comes first and is offered on every event type:
    it is the obvious thing to cut into a weekday or an hour, and
    :func:`event_type_catalog` leaves it out of the attribute lists precisely
    because it is an axis rather than an attribute. Any *other* datetime
    attribute follows, listed under a type only where that type carries a
    non-null value for it -- the same rule the attribute catalog uses.
    """
    skip = {case_id_col, activity_col} | DERIVED_EVENT_COLUMNS | set(derived or ())
    others = [str(name) for name in event_log.columns
              if str(name) not in skip and str(name) != time_col
              and '::' not in str(name)
              and attribute_kind(event_log[name]) == 'time']

    grouped = event_log.groupby(event_log[activity_col].rename('__activity__'),
                                sort=False)
    present = _presence_map(grouped[others].count()) if others else {}

    result: Dict[str, List[str]] = {}
    for activity in grouped.size().sort_values(ascending=False).index:
        counts = present.get(str(activity), {})
        result[str(activity)] = [time_col] + [name for name in others
                                              if counts.get(name, 0) > 0]
    return result


def numeric_profiles(event_log: DataFrame,
                     case_id_col: str = CASE_ID_COL,
                     time_col: str = TIME_COL,
                     activity_col: str = ACTIVITY_COL,
                     all_events_key: str = ALL_EVENTS) -> Dict[str, Dict[str, Any]]:
    """A quantile sketch per (event type, numeric column), plus one log-wide.

    Keyed ``{event type: {column: {min, max, count, quantiles}}}`` with
    ``all_events_key`` holding the log-wide sketch, which is what an accumulation
    over every event is cut on.
    """
    skip = {case_id_col, time_col, activity_col} | DERIVED_EVENT_COLUMNS
    numeric = [str(name) for name in event_log.columns
               if str(name) not in skip and '::' not in str(name)
               and attribute_kind(event_log[name]) == 'num']
    if not numeric:
        return {}

    profiles: Dict[str, Dict[str, Any]] = {}
    log_wide = {name: _profile(event_log[name]) for name in numeric}
    profiles[all_events_key] = {name: entry for name, entry in log_wide.items() if entry}

    for activity, rows in event_log.groupby(event_log[activity_col], sort=False):
        entries = {name: _profile(rows[name]) for name in numeric}
        kept = {name: entry for name, entry in entries.items() if entry}
        if kept:
            profiles[str(activity)] = kept
    return profiles


def _profile(series: Series) -> Optional[Dict[str, Any]]:
    """``{min, max, count, quantiles}`` for one numeric column, or ``None`` if empty."""
    values = pd.to_numeric(series, errors='coerce').astype('float64').dropna()
    if values.empty:
        return None
    points = [index / (QUANTILE_POINTS - 1) for index in range(QUANTILE_POINTS)]
    quantiles = values.quantile(points).tolist()
    return {
        'min': float(values.min()),
        'max': float(values.max()),
        'count': int(len(values)),
        'quantiles': [float(value) for value in quantiles],
    }
