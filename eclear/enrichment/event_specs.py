"""What an *event*-log enrichment is, and what it is allowed to say.

An :class:`EventEnrichmentSpec` is the stable identity of one event-log column:
the kind of enrichment that produced it, the event type it is written on, and
the arguments it was produced with.

======================  =========================================================
kind                    what the column holds
======================  =========================================================
``binning``             a column cut into labelled categories -- numeric
                        intervals, or a part of a timestamp
``arithmetic``          arithmetic on two numeric attributes of one event
``delta``               the gap to a neighbouring event in the same case
``running_agg``         a running aggregation along each case, on every event
======================  =========================================================

The four kinds fall into two groups, and :data:`EVENT_KIND_GROUPS` is where that
is written down: a *local* column is computed from the event's own attributes, a
*contextual* one from where the event sits among the other events of its case.

Unlike a case-log :class:`~eclear.enrichment.specs.EnrichmentSpec`, whose
column name is *derived* from the spec by
:func:`~eclear.enrichment.specs.column_name`, an event enrichment carries its
column name as a stored field: the kinds take heterogeneous arguments with no
readable canonical rendering, and the name is a feature name the user is
choosing. :func:`suggest_column` offers a default, and nothing depends on the
user keeping it.

The consequence is that uniqueness has to be *validated* rather than guaranteed.
:func:`validate_event_spec` is that check, and it is the backstop rather than the
first line: the widget disables staging on the same conditions, so a rejection
reaching Python means the frontend and the log disagreed about the log.
"""
from typing import (AbstractSet, Any, Dict, Iterable, List, Mapping, NamedTuple, Optional,
                    Sequence, Tuple)

#: Enrichment kinds.
EVENT_KIND_BINNING = 'binning'
EVENT_KIND_ARITHMETIC = 'arithmetic'
EVENT_KIND_DELTA = 'delta'
EVENT_KIND_RUNNING_AGG = 'running_agg'

#: How the widget's rail groups the kinds, and in what order it lists them.
#: :data:`EVENT_KINDS` is flattened from this, so membership and order cannot
#: drift apart. A *local* column reads the event's own attributes; a
#: *contextual* one reads the event's position among its case's other events.
EVENT_KIND_GROUPS: Tuple[Tuple[str, str, Tuple[str, ...]], ...] = (
    ('local', 'Local', (EVENT_KIND_BINNING, EVENT_KIND_ARITHMETIC)),
    ('contextual', 'Contextual', (EVENT_KIND_DELTA, EVENT_KIND_RUNNING_AGG)),
)

EVENT_KINDS: Tuple[str, ...] = tuple(
    kind for _, _, kinds in EVENT_KIND_GROUPS for kind in kinds)

#: Human-readable label per kind, for the widget's rail.
EVENT_KIND_LABELS: Dict[str, str] = {
    EVENT_KIND_BINNING: 'Binning',
    EVENT_KIND_ARITHMETIC: 'Arithmetic',
    EVENT_KIND_DELTA: 'Time delta',
    EVENT_KIND_RUNNING_AGG: 'Running aggregation',
}

#: Event-type scope of an enrichment written on every event of the log. Shared
#: spelling with :data:`~eclear.enrichment.specs.ALL_EVENTS`; unlike a tracking
#: scope it never reaches a column name, so it needs no second spelling.
ALL_EVENT_TYPES = '*'

#: Arithmetic ``arithmetic`` understands. Keys are ASCII -- the widget renders
#: the typographic forms, but only these cross the trait boundary.
FORMULA_OPS: Tuple[str, ...] = ('+', '-', '*', '/')

#: Which neighbour a ``delta`` measures against.
DELTA_DIRECTIONS: Tuple[str, ...] = ('prev', 'next')
DELTA_NEIGHBOURS: Tuple[str, ...] = ('any', 'same', 'type')

#: What an event with no neighbour gets. ``zero`` is offered because a model may
#: not accept a missing value; it is lossy, and the widget says so.
DELTA_MISSING: Tuple[str, ...] = ('NaT', 'zero')

#: Units a timespan can be expressed in. ``timedelta`` keeps the pandas dtype.
TIME_UNITS: Tuple[str, ...] = ('timedelta', 'min', 'hours', 'days')

#: Running aggregations ``running_agg`` understands.
RUNNING_AGGREGATES: Tuple[str, ...] = ('cumsum', 'count', 'runmax', 'runmin', 'ffill')

#: Whether the running value is carried onto events that hold no source value.
RUNNING_AGG_CARRY: Tuple[str, ...] = ('carry', 'zero')

#: What a ``binning`` column is cut from: a numeric range, or a timestamp.
BINNING_MODES: Tuple[str, ...] = ('numeric', 'time')

#: How numeric ``binning`` arrived at its edges. Informational only -- ``edges``
#: is what is applied, whichever way the user got to it.
BIN_METHODS: Tuple[str, ...] = ('equal', 'quantile', 'custom')

#: Parts of a timestamp time ``binning`` can cut on.
TIME_PARTS: Tuple[str, ...] = ('year', 'month', 'weekday', 'hour')

#: Labels for the ``weekday`` part, Monday first as ``Series.dt.weekday`` numbers
#: them.
WEEKDAY_LABELS: Tuple[str, ...] = ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')

#: Hours per unit, for rendering a timespan as a float.
UNIT_HOURS: Dict[str, float] = {'min': 1.0 / 60.0, 'hours': 1.0, 'days': 24.0}

_OP_ALIASES: Dict[str, str] = {'−': '-', '–': '-', '×': '*', '÷': '/'}


class EventEnrichmentSpec(NamedTuple):
    """One event-log enrichment, identified by the column it produces.

    Specs cross traitlets and are stored on the event log, so :attr:`params`
    holds only JSON-able values; :meth:`to_dict` / :meth:`from_dict` are the
    round-trip.
    """

    kind: str
    """One of :data:`EVENT_KINDS`."""

    column: str
    """The event-log column this spec produces -- its stable identity, and the
    name the user chose."""

    event_type: Optional[str] = None
    """Activity the column is written on. :data:`ALL_EVENT_TYPES` or ``None``
    writes it on every event, which is what ``running_agg`` does."""

    params: Mapping[str, Any] = {}
    """Kind-specific arguments. See the module table and
    :func:`validate_event_spec` for what each kind expects."""

    @property
    def scoped(self) -> bool:
        """Whether the column is written on one event type rather than all."""
        return bool(self.event_type) and self.event_type != ALL_EVENT_TYPES

    def to_dict(self) -> Dict[str, Any]:
        """JSON-able form, as the frontend sends and receives it."""
        return {
            'kind': self.kind,
            'column': self.column,
            'event_type': self.event_type,
            'params': dict(self.params),
        }

    @staticmethod
    def from_dict(record: Mapping[str, Any]) -> 'EventEnrichmentSpec':
        """Rebuild a spec from :meth:`to_dict`."""
        return EventEnrichmentSpec(
            kind=str(record['kind']),
            column=str(record['column']),
            event_type=_optional_str(record.get('event_type')),
            params=dict(record.get('params') or {}),
        )


def event_specs_from_dicts(
        records: Iterable[Mapping[str, Any]]) -> List[EventEnrichmentSpec]:
    """Rebuild a list of specs from the frontend's payload."""
    return [EventEnrichmentSpec.from_dict(record) for record in records]


def _optional_str(value: Any) -> Optional[str]:
    return None if value is None else str(value)


def normalize_op(op: str) -> str:
    """The ASCII spelling of an arithmetic operator.

    The widget shows ``− × ÷``; a spec hand-written in a notebook may well use
    them too. Only :data:`FORMULA_OPS` reaches the enrichers.
    """
    return _OP_ALIASES.get(str(op), str(op))


def binning_mode(spec: EventEnrichmentSpec) -> str:
    """Which kind of cut a ``binning`` spec describes.

    Defaults to ``numeric``: the mode was added after the kind existed, and a
    spec recorded on a frame before that says nothing about it.
    """
    return str(spec.params.get('mode') or 'numeric')


# ----------------------------------------------------------------------
# constructors
# ----------------------------------------------------------------------
def arithmetic_spec(column: str, event_type: str, left: str, op: str,  # pylint: disable=too-many-arguments, too-many-positional-arguments
                    right: Optional[str] = None,
                    constant: Optional[float] = None) -> EventEnrichmentSpec:
    """Arithmetic on two numeric attributes of one event, or one and a constant."""
    return EventEnrichmentSpec(
        kind=EVENT_KIND_ARITHMETIC, column=column, event_type=event_type,
        params={'left': left, 'op': normalize_op(op), 'right': right,
                'constant': constant})


def delta_spec(column: str, event_type: str,  # pylint: disable=too-many-arguments, too-many-positional-arguments
               direction: str = 'prev',
               neighbour: str = 'any',
               neighbour_type: Optional[str] = None,
               unit: str = 'hours',
               missing: str = 'NaT') -> EventEnrichmentSpec:
    """Gap between an event and its neighbour in the same case."""
    return EventEnrichmentSpec(
        kind=EVENT_KIND_DELTA, column=column, event_type=event_type,
        params={'direction': direction, 'neighbour': neighbour,
                'neighbour_type': neighbour_type, 'unit': unit,
                'missing': missing})


def running_agg_spec(column: str, source: str,
                     aggregate: str = 'cumsum',
                     carry: str = 'carry') -> EventEnrichmentSpec:
    """Running aggregation of one numeric column along each case, on every event."""
    return EventEnrichmentSpec(
        kind=EVENT_KIND_RUNNING_AGG, column=column, event_type=ALL_EVENT_TYPES,
        params={'source': source, 'aggregate': aggregate, 'carry': carry})


def binning_spec(column: str, event_type: str, source: str,  # pylint: disable=too-many-arguments, too-many-positional-arguments
                 edges: Sequence[float],
                 labels: Optional[Sequence[str]] = None,
                 method: str = 'custom') -> EventEnrichmentSpec:
    """Cut a numeric column into labelled intervals with unbounded outer edges."""
    sorted_edges = sorted(float(edge) for edge in edges)
    return EventEnrichmentSpec(
        kind=EVENT_KIND_BINNING, column=column, event_type=event_type,
        params={'mode': 'numeric', 'source': source, 'edges': sorted_edges,
                'labels': list(labels) if labels is not None
                          else default_bin_labels(len(sorted_edges)),
                'method': method})


def time_binning_spec(column: str, event_type: str, source: str,
                      part: str) -> EventEnrichmentSpec:
    """Cut a timestamp column into one of its natural parts.

    The parts are categories rather than numbers -- ``month`` is one of twelve,
    not a quantity -- and every category exists whether or not the log happens to
    contain it, so a rule written on a sample still reads on the full log.
    """
    return EventEnrichmentSpec(
        kind=EVENT_KIND_BINNING, column=column, event_type=event_type,
        params={'mode': 'time', 'source': source, 'part': part})


def default_bin_labels(edge_count: int) -> List[str]:
    """``bin_1 .. bin_n`` for ``n`` edges, which make ``n + 1`` intervals."""
    return [f'bin_{index + 1}' for index in range(edge_count + 1)]


# ----------------------------------------------------------------------
# naming
# ----------------------------------------------------------------------
def slug(text: str) -> str:
    """A column-name-safe rendering of an attribute or value name."""
    out: List[str] = []
    for char in str(text):
        out.append(char if char.isalnum() else '_')
    return '_'.join(part for part in ''.join(out).split('_') if part)


_OP_WORDS = {'+': 'plus', '-': 'minus', '*': 'x', '/': 'per'}
_UNIT_SUFFIX = {'min': '_min', 'hours': '_h', 'days': '_d', 'timedelta': ''}
_AGG_SUFFIX = {'cumsum': '_cum', 'count': '_count_so_far',
               'runmax': '_running_max', 'runmin': '_running_min',
               'ffill': '_last_seen'}


def suggest_column(kind: str, params: Mapping[str, Any]) -> str:  # pylint: disable=too-many-return-statements
    """A default column name for a half-built spec.

    A *suggestion*: the widget shows it, the user may overwrite it, and nothing
    downstream re-derives it. Python owns this rather than the frontend so a
    spec built in a notebook gets the same default as one built by clicking.
    """
    if kind == EVENT_KIND_ARITHMETIC:
        right = params.get('right')
        tail = slug(right) if right else slug(str(params.get('constant', 'const')))
        word = _OP_WORDS.get(normalize_op(str(params.get('op', '+'))), 'op')
        return f'{slug(str(params.get("left", "")))}_{word}_{tail}'
    if kind == EVENT_KIND_DELTA:
        head = 'since_prev' if params.get('direction') == 'prev' else 'until_next'
        neighbour = params.get('neighbour')
        middle = ('_same' if neighbour == 'same'
                  else f'_{slug(str(params.get("neighbour_type", "")))}'
                  if neighbour == 'type' else '')
        return f'{head}{middle}{_UNIT_SUFFIX.get(str(params.get("unit")), "")}'
    if kind == EVENT_KIND_RUNNING_AGG:
        suffix = _AGG_SUFFIX.get(str(params.get('aggregate')), '')
        return f'{slug(str(params.get("source", ""))).lower()}{suffix}'
    if kind == EVENT_KIND_BINNING:
        source = slug(str(params.get('source', '')))
        if str(params.get('mode') or 'numeric') == 'time':
            return f'{source}_{slug(str(params.get("part", "")))}'
        return f'{source}_level'
    return ''


# ----------------------------------------------------------------------
# validation
# ----------------------------------------------------------------------
def validate_event_spec(spec: EventEnrichmentSpec,  # pylint: disable=too-many-return-statements, too-many-branches, too-many-arguments, too-many-positional-arguments
                        columns: Sequence[str],
                        event_types: Sequence[str],
                        numeric_columns: Sequence[str] = (),
                        time_columns: Sequence[str] = ()) -> Optional[str]:
    """Why this spec cannot be applied, or ``None`` if it can.

    Takes the log's shape rather than the log itself: the widget already holds
    these lists from the catalog, and a validator that does not read a frame can
    be exercised without one.

    Args:
        spec: The spec to check.
        columns: Column names the event log already carries, including the ones
            earlier specs in the same batch would add.
        event_types: Activities present in the log.
        numeric_columns: Numeric columns *in this spec's scope* -- the ones its
            own event type carries, or every numeric column for an unscoped
            spec. Scoped rather than log-wide because an arithmetic column
            reading an attribute its event type never carries would apply
            cleanly and produce a column of nothing.
        time_columns: Timestamp columns in this spec's scope, scoped for the same
            reason.
    """
    if spec.kind not in EVENT_KINDS:
        return f'unknown enrichment kind {spec.kind!r}'
    if not spec.column:
        return 'the column needs a name'
    if spec.column in columns:
        return f'{spec.column} already exists on the event log'
    if spec.scoped and spec.event_type not in event_types:
        return f'no event type named {spec.event_type!r} in this log'

    params = spec.params
    numeric = set(numeric_columns)

    if spec.kind == EVENT_KIND_ARITHMETIC:
        if normalize_op(str(params.get('op', ''))) not in FORMULA_OPS:
            return f'unknown operator {params.get("op")!r}'
        left = params.get('left')
        if not left or left not in numeric:
            return f'{left!r} is not a numeric attribute'
        right = params.get('right')
        if right is None:
            if params.get('constant') is None:
                return 'an arithmetic column needs a right operand or a constant'
        elif right not in numeric:
            return f'{right!r} is not a numeric attribute'
        return None

    if spec.kind == EVENT_KIND_DELTA:
        if params.get('direction') not in DELTA_DIRECTIONS:
            return f'unknown direction {params.get("direction")!r}'
        if params.get('neighbour') not in DELTA_NEIGHBOURS:
            return f'unknown neighbour rule {params.get("neighbour")!r}'
        if params.get('neighbour') == 'type' and params.get('neighbour_type') not in event_types:
            return f'no event type named {params.get("neighbour_type")!r} in this log'
        if params.get('unit') not in TIME_UNITS:
            return f'unknown time unit {params.get("unit")!r}'
        if params.get('missing') not in DELTA_MISSING:
            return f'unknown missing-value rule {params.get("missing")!r}'
        return None

    if spec.kind == EVENT_KIND_RUNNING_AGG:
        source = params.get('source')
        if not source or source not in numeric:
            return f'{source!r} is not a numeric column'
        if params.get('aggregate') not in RUNNING_AGGREGATES:
            return f'unknown aggregation {params.get("aggregate")!r}'
        if params.get('carry') not in RUNNING_AGG_CARRY:
            return f'unknown carry rule {params.get("carry")!r}'
        return None

    return _validate_binning(spec, numeric, time_columns)


def _validate_binning(spec: EventEnrichmentSpec,  # pylint: disable=too-many-return-statements
                      numeric: AbstractSet[str],
                      time_columns: Sequence[str]) -> Optional[str]:
    """Why a ``binning`` spec cannot be applied, or ``None``."""
    params = spec.params
    mode = binning_mode(spec)
    if mode not in BINNING_MODES:
        return f'unknown binning mode {params.get("mode")!r}'

    source = params.get('source')
    if mode == 'time':
        if not source or source not in set(time_columns):
            return f'{source!r} is not a timestamp column'
        if params.get('part') not in TIME_PARTS:
            return f'unknown time part {params.get("part")!r}'
        return None

    if not source or source not in numeric:
        return f'{source!r} is not a numeric column'
    edges = params.get('edges') or []
    if not edges:
        return 'bins need at least one edge'
    if len(set(edges)) != len(edges):
        return 'bin edges must be distinct'
    labels = params.get('labels') or []
    if len(labels) != len(edges) + 1:
        return f'{len(edges)} edges need {len(edges) + 1} labels, got {len(labels)}'
    if len(set(labels)) != len(labels):
        return 'bin labels must be distinct'
    return None
