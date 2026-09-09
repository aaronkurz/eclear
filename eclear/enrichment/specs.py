"""What an enrichment is, what it is called, and what it says about itself.

An :class:`EnrichmentSpec` is the stable identity of one case-log column: the
kind of enrichment that produced it and the arguments it was produced with. The
column *name* is derived from the spec, never the other way around --
:func:`column_name` is the only place the naming scheme is written down.

======================  ================================  ==========================
kind                    column                            example
======================  ================================  ==========================
``counts``              ``{Activity}::count``             ``Payment::count``
``times``               ``{Activity}::start`` / ``::end`` ``Send_Fine::start``
``delays``              ``{A}:{B}::delay``                ``Payment:Add_penalty::delay``
``tracking``            ``{EventType}.{attr}::{method}``  ``ER_Registration.Age::latest``
======================  ================================  ==========================

The event type in a tracking column is :data:`ALL_EVENTS_COLUMN` when the
attribute is tracked over every event of the case rather than one activity's
events, so ``all_events.concept:name::append`` is the whole activity sequence.
The scope is :data:`ALL_EVENTS` -- ``*`` -- everywhere *except* in the column
name: rule induction turns a column name into a ``trxf`` ``Feature``, which
parses it as an arithmetic expression, and a leading ``*`` reads as a
multiplication with nothing to its left. :func:`scope_token` is the one place
that translation happens; :func:`parse_attribute_name` still reads the old
``*.`` spelling so frames written before it keep describing correctly.

:func:`describe_attribute` turns a column back into the :class:`AttributeMeta`
the rule builder groups and filters by. It reads the provenance record when the
case log carries one and falls back to :func:`parse_attribute_name` when it does
not -- a notebook that rebuilds the frame by hand still gets a useful answer,
just a guessed one.

Where the fallback parser has to guess, it guesses conservatively:

* An activity name containing ``.`` makes ``Foo.bar::count`` ambiguous between
  activity incidence and a tracked count. The parser reads a dot as tracking;
  the provenance record, when present, settles it properly.
* Sources are reported verbatim, never un-mangled. :func:`convert_name` replaces
  spaces with underscores and does not escape colons, so it is neither
  invertible nor unambiguous; a delay whose stem does not split cleanly in two
  reports no sources at all rather than a guess.
"""
from typing import Any, Dict, Mapping, NamedTuple, Optional, Tuple

#: Aggregations ``tracking`` understands. The first four apply to any attribute;
#: the rest need one that is numeric. ``is_unique`` sits inside that prefix
#: deliberately, so the methods a categorical attribute cannot offer stay a
#: contiguous tail in the widget's pane.
TRACK_METHODS: Tuple[str, ...] = ('latest', 'count', 'append', 'is_unique',
                                  'sum', 'min', 'max')

#: The subset of :data:`TRACK_METHODS` a non-numeric attribute can be folded with.
CATEGORICAL_TRACK_METHODS: Tuple[str, ...] = ('latest', 'count', 'append', 'is_unique')

#: Suffixes the activity-level enrichers produce.
ACTIVITY_METHODS: Tuple[str, ...] = ('count', 'start', 'end', 'delay')

#: Event-type scope of a tracking spec that follows the whole case.
ALL_EVENTS = '*'

#: How :data:`ALL_EVENTS` is spelled in a column name. ``*`` is a ``trxf``
#: arithmetic operator, so it must never reach one.
ALL_EVENTS_COLUMN = 'all_events'

#: Enrichment kinds, in the order the widget's catalog lists them.
KIND_BASE = 'base'
KIND_COUNTS = 'counts'
KIND_TIMES = 'times'
KIND_DELAYS = 'delays'
KIND_TRACKING = 'tracking'

KINDS: Tuple[str, ...] = (KIND_BASE, KIND_COUNTS, KIND_TIMES, KIND_DELAYS, KIND_TRACKING)

#: Columns ``create_case_log`` always produces, plus the event-log columns the
#: enrichers add. No enrichment family applies to them.
BASE_CASE_COLUMNS: Tuple[str, ...] = ('start_time', 'end_time', 'no_of_events', 'duration')

_EVENT_BASE_COLUMNS = frozenset({'rel_time', 'rel_log_time', 'order_class', 'ordered_case_id'})

#: Display label per family key. Every family the parser can return has one.
_FAMILY_LABELS: Dict[str, str] = {
    'count': 'Activity count',
    'start': 'First occurrence',
    'end': 'Last occurrence',
    'delay': 'Delay',
    'latest': 'Latest value',
    'sum': 'Sum',
    'min': 'Minimum',
    'max': 'Maximum',
    'append': 'Value sequence',
    'is_unique': 'Constant within case',
    'track_count': 'Tracked count',
    'case': 'Case basics',
    'other': 'Other',
}

#: Human-readable label per kind, for the widget's catalog rail.
KIND_LABELS: Dict[str, str] = {
    KIND_BASE: 'Base case log',
    KIND_COUNTS: 'Activity counts',
    KIND_TIMES: 'First/last occurrence',
    KIND_DELAYS: 'Activity delays',
    KIND_TRACKING: 'Attribute tracking',
}

_OTHER = 'other'


class AttributeMeta(NamedTuple):
    """What a case-log column says about how it came to be."""

    family: str
    """Stable family key, one of the keys of ``_FAMILY_LABELS``."""

    family_label: str
    """Human-readable label for ``family``."""

    sources: Tuple[str, ...]
    """Data points the attribute derives from: one activity for the activity
    families, two for a delay, the event type and the attribute for a scoped
    tracking column, none when the name does not say."""


class EnrichmentSpec(NamedTuple):
    """One enrichment, identified by the case-log column it produces.

    Specs cross traitlets and are stored on the case log, so every field is a
    plain string or ``None``; :meth:`to_dict` / :meth:`from_dict` are the
    round-trip.
    """

    kind: str
    """One of :data:`KINDS`."""

    method: str
    """``count`` / ``start`` / ``end`` / ``delay`` for the activity families,
    one of :data:`TRACK_METHODS` for ``tracking``."""

    activity: Optional[str] = None
    """Activity for ``counts`` / ``times`` / the *from* side of ``delays``; the
    event-type scope (possibly :data:`ALL_EVENTS`) for ``tracking``."""

    activity_to: Optional[str] = None
    """The *to* side of a ``delays`` spec."""

    attribute: Optional[str] = None
    """Event attribute a ``tracking`` spec folds."""

    @property
    def column(self) -> str:
        """The case-log column this spec produces -- its stable identity."""
        return column_name(self)

    @property
    def meta(self) -> AttributeMeta:
        """Family and sources, straight from the spec rather than its name."""
        return _meta_of_spec(self)

    def to_dict(self) -> Dict[str, Any]:
        """JSON-able form, with the derived column included for consumers that
        only ever need the name."""
        record = {
            'kind': self.kind,
            'method': self.method,
            'activity': self.activity,
            'activity_to': self.activity_to,
            'attribute': self.attribute,
        }
        record['column'] = self.column
        return record

    @staticmethod
    def from_dict(record: Mapping[str, Any]) -> 'EnrichmentSpec':
        """Rebuild a spec from :meth:`to_dict`, ignoring the derived column."""
        return EnrichmentSpec(
            kind=str(record['kind']),
            method=str(record['method']),
            activity=_optional_str(record.get('activity')),
            activity_to=_optional_str(record.get('activity_to')),
            attribute=_optional_str(record.get('attribute')),
        )


def _optional_str(value: Any) -> Optional[str]:
    return None if value is None else str(value)


def convert_name(name: str) -> str:
    """Make an activity name usable in a column name: spaces become underscores.

    Kept identical to the original enricher's helper so column names produced
    before and after this module are the same string.
    """
    return '_'.join(str(name).split(' '))


def scope_token(scope: Optional[str]) -> str:
    """The column-name spelling of a tracking spec's event-type scope.

    An activity scope is written as-is (bar :func:`convert_name`); the log-wide
    scope is written :data:`ALL_EVENTS_COLUMN` rather than :data:`ALL_EVENTS`,
    because ``*`` in a column name breaks the rule engine that parses it.
    """
    if not scope or scope == ALL_EVENTS:
        return ALL_EVENTS_COLUMN
    return convert_name(scope)


def column_name(spec: EnrichmentSpec) -> str:
    """The case-log column a spec produces. The only place the scheme is written."""
    if spec.kind == KIND_DELAYS:
        return (f'{convert_name(spec.activity or "")}'
                f':{convert_name(spec.activity_to or "")}::delay')
    if spec.kind == KIND_TRACKING:
        return f'{scope_token(spec.activity)}.{spec.attribute}::{spec.method}'
    return f'{convert_name(spec.activity or "")}::{spec.method}'


def counts_spec(activity: str) -> EnrichmentSpec:
    """Number of occurrences of ``activity`` in each case."""
    return EnrichmentSpec(kind=KIND_COUNTS, method='count', activity=activity)


def times_spec(activity: str, which: str = 'start') -> EnrichmentSpec:
    """Relative time of the first (``start``) or last (``end``) occurrence."""
    if which not in ('start', 'end'):
        raise ValueError(f"activity time must be 'start' or 'end', got {which!r}")
    return EnrichmentSpec(kind=KIND_TIMES, method=which, activity=activity)


def delay_spec(activity_from: str, activity_to: str) -> EnrichmentSpec:
    """Time from the first occurrence of one activity to that of another."""
    return EnrichmentSpec(kind=KIND_DELAYS, method='delay',
                          activity=activity_from, activity_to=activity_to)


def tracking_spec(attribute: str, method: str,
                  event_type: Optional[str] = None) -> EnrichmentSpec:
    """Fold ``attribute`` over a case with ``method``.

    ``event_type`` restricts the fold to the events of one activity; ``None`` or
    :data:`ALL_EVENTS` folds over every event of the case.
    """
    if method not in TRACK_METHODS:
        raise ValueError(f'unknown tracking method {method!r}')
    return EnrichmentSpec(kind=KIND_TRACKING, method=method,
                          activity=event_type or ALL_EVENTS, attribute=attribute)


def _sources(*names: Optional[str]) -> Tuple[str, ...]:
    """Non-empty source names, de-duplicated, in the order given.

    Consumers group and facet by source, so a repeat -- ``Leucocytes.Leucocytes``,
    where the attribute is named after the event type that carries it -- would
    otherwise list the same attribute twice under the same heading.
    """
    seen: Dict[str, None] = {}
    for name in names:
        if name:
            seen.setdefault(name, None)
    return tuple(seen)


def _is_all_events(scope: str) -> bool:
    """Whether a scope token in a column name means "every event of the case".

    Both spellings count: the column has said :data:`ALL_EVENTS_COLUMN` since
    ``*`` turned out to break the rule engine, but frames written before that,
    and notebooks that spell a column by hand, still say ``*``.
    """
    return scope in (ALL_EVENTS, ALL_EVENTS_COLUMN)


def _meta_of_spec(spec: EnrichmentSpec) -> AttributeMeta:
    if spec.kind == KIND_DELAYS:
        return AttributeMeta('delay', _FAMILY_LABELS['delay'],
                             _sources(convert_name(spec.activity) if spec.activity else None,
                                      convert_name(spec.activity_to) if spec.activity_to else None))

    if spec.kind == KIND_TRACKING:
        family = 'track_count' if spec.method == 'count' else spec.method
        # An unscoped fold has no activity to attribute the value to, so the
        # attribute itself is the only source worth naming.
        scope = scope_token(spec.activity)
        sources = (_sources(spec.attribute) if _is_all_events(scope)
                   else _sources(scope, spec.attribute))
        return AttributeMeta(family, _FAMILY_LABELS.get(family, _FAMILY_LABELS[_OTHER]),
                             sources)

    if spec.kind in (KIND_COUNTS, KIND_TIMES):
        family = spec.method
        sources = _sources(convert_name(spec.activity) if spec.activity else None)
        return AttributeMeta(family, _FAMILY_LABELS.get(family, _FAMILY_LABELS[_OTHER]),
                             sources)

    return AttributeMeta('case', _FAMILY_LABELS['case'], ())


def parse_attribute_name(name: str) -> AttributeMeta:
    """Derive family and source(s) of a case-log column from its name alone.

    The fallback for columns with no provenance record: the fixed case-log
    columns, the ones an earlier version wrote, and the ones notebooks write by
    hand. Names that follow no known scheme come back as ``case`` or
    ``other`` with no sources, so an unrecognized name never invents a family of
    its own.
    """
    stem, separator, suffix = name.rpartition('::')

    if not separator:
        family = ('case' if name in BASE_CASE_COLUMNS or name in _EVENT_BASE_COLUMNS
                  else _OTHER)
        return AttributeMeta(family, _FAMILY_LABELS[family], ())

    if suffix == 'delay':
        # 'A:B::delay' holds start(B) - start(A), so the sources stay in the
        # order the name gives them. An activity name containing a colon breaks
        # the split beyond repair -- report the family, admit the sources.
        parts = stem.split(':')
        sources = tuple(parts) if len(parts) == 2 and all(parts) else ()
        return AttributeMeta('delay', _FAMILY_LABELS['delay'], sources)

    if suffix in TRACK_METHODS and '.' in stem:
        scope, _, attribute = stem.partition('.')
        family = 'track_count' if suffix == 'count' else suffix
        sources = (_sources(attribute) if _is_all_events(scope)
                   else _sources(scope, attribute))
        return AttributeMeta(family, _FAMILY_LABELS[family], sources)

    if suffix in ACTIVITY_METHODS or suffix in TRACK_METHODS:
        return AttributeMeta(suffix, _FAMILY_LABELS[suffix], _sources(stem))

    return AttributeMeta(_OTHER, _FAMILY_LABELS[_OTHER], ())


def describe_attribute(name: str,
                       provenance: Optional[Mapping[str, Any]] = None) -> AttributeMeta:
    """Family and sources of a case-log column: the record first, the name second.

    Args:
        name: Case-log column name.
        provenance: Mapping from column name to a spec dict, as returned by
            ``enrichers.provenance_of``. Anything missing from it falls through
            to :func:`parse_attribute_name`.
    """
    if provenance:
        record = provenance.get(name)
        if record:
            try:
                return EnrichmentSpec.from_dict(record).meta
            except (KeyError, TypeError, ValueError):
                # A record we cannot read is worse than no record: fall through
                # rather than let a malformed frame break the rule builder.
                pass
    return parse_attribute_name(name)


def family_label(family: str) -> str:
    """Display label for a family key, ``'Other'`` for anything unrecognized."""
    return _FAMILY_LABELS.get(family, _FAMILY_LABELS[_OTHER])
