"""Interactive log enrichment: pick the columns, see them, then apply them.

Two logs, one widget. The **event** tab derives columns on the event log itself;
the **case** tab folds the event log into a case log. They share a staging model,
an apply bar and a colour vocabulary, and they meet in one place: an applied
event column becomes a source the case tab can track, which is also why removing
one can be refused.
"""
import pathlib
import random
from typing import Any, Dict, Iterable, List, Optional, Sequence

import pandas as pd
from pandas import DataFrame
import anywidget
import traitlets

from .enrichment import (
    ACTIVITY_COL,
    ALL_EVENTS,
    CASE_ID_COL,
    EVENT_KIND_BINNING,
    EVENT_KIND_GROUPS,
    EVENT_KIND_LABELS,
    EVENT_KINDS,
    KIND_LABELS,
    KINDS,
    TIME_COL,
    TRACK_METHODS,
    EnrichmentSpec,
    EventEnrichmentSpec,
    activity_catalog,
    apply_event_specs,
    apply_specs,
    base_columns,
    create_case_log,
    ensure_relative_time,
    event_columns_using,
    event_specs_from_dicts,
    event_type_catalog,
    log_summary,
    numeric_profiles,
    specs_from_dicts,
    specs_of,
    time_columns,
    trackable_attributes,
    validate_event_spec,
)
from .enrichment.event_log import event_add_relative_log_time

#: Cases shown in the sample preview unless the frontend asks for more.
PREVIEW_CASES = 5

#: Cases shown in the *event* preview. Fewer, because each contributes a row per
#: event rather than one row in total.
PREVIEW_EVENT_CASES = 3


class EnrichmentWidget(anywidget.AnyWidget):  # pylint: disable=too-many-instance-attributes, abstract-method
    """Enrich an event log, and build a case log from it, by staging and applying.

    The widget stands *between* loading a log and analysing it: it takes an
    event log and hands back both an enriched event log through
    :attr:`event_log` and a case log through :attr:`case_log`, leaving a notebook
    free to adjust either frame by hand afterwards. It reads nothing but the
    frame it is given.

    Enrichments are staged, not applied on click. Staging is free -- it costs a
    chip in the schema rail and nothing else -- so a user can assemble a whole
    batch, see what it would do to the schema, preview the values on a handful
    of real cases, and only then pay for the computation over the full log.
    Removals stage the same way, which is what makes an over-enriched log
    recoverable without starting over.

    Applying recomputes rather than patches, on both sides: the surviving specs
    are re-applied to a fresh base log. Both ``apply_specs`` and
    ``apply_event_specs`` are idempotent, so this is cheap insurance against a
    column drifting out of step with the spec that claims to have produced it.

    The two sides are deliberately *not* symmetric about what an apply touches.
    Applying an event enrichment rebuilds the catalog, so the new column shows up
    as a tracking source straight away, but it does **not** recompute the case
    log: a case column that already exists was computed from a log that did not
    have this column, and silently redoing that work would move numbers the user
    has already looked at. Removing an event column that a case column reads is
    refused for the mirror image of that reason.

    ``*_request`` traits are frontend-owned: the frontend writes a request
    carrying a monotonically increasing ``request_id``, Python answers on the
    matching ``*_result`` trait and never writes the request back. The observers
    below ignore any request id they have already handled, so a re-delivered
    change cannot re-run an apply.
    """
    _esm = pathlib.Path(__file__).parent / "static" / "enrichment.js"

    title = traitlets.Unicode(default_value="Log enrichment").tag(sync=True)
    log_summary = traitlets.Dict(default_value={}).tag(sync=True)  # type: ignore
    catalog = traitlets.Dict(default_value={}).tag(sync=True)  # type: ignore
    applied = traitlets.List(default_value=[]).tag(sync=True)  # type: ignore
    apply_request = traitlets.Dict(default_value={}).tag(sync=True)  # type: ignore
    apply_result = traitlets.Dict(default_value={}).tag(sync=True)  # type: ignore
    preview_request = traitlets.Dict(default_value={}).tag(sync=True)  # type: ignore
    preview_result = traitlets.Dict(default_value={}).tag(sync=True)  # type: ignore

    event_catalog = traitlets.Dict(default_value={}).tag(sync=True)  # type: ignore
    event_applied = traitlets.List(default_value=[]).tag(sync=True)  # type: ignore
    event_apply_request = traitlets.Dict(default_value={}).tag(sync=True)  # type: ignore
    event_apply_result = traitlets.Dict(default_value={}).tag(sync=True)  # type: ignore
    event_preview_request = traitlets.Dict(default_value={}).tag(sync=True)  # type: ignore
    event_preview_result = traitlets.Dict(default_value={}).tag(sync=True)  # type: ignore

    def __init__(self,  # pylint: disable=too-many-arguments, too-many-positional-arguments
                 event_log: DataFrame,
                 case_id_col: str = CASE_ID_COL,
                 time_col: str = TIME_COL,
                 activity_col: str = ACTIVITY_COL,
                 initial_specs: Optional[Iterable[EnrichmentSpec]] = None,
                 initial_event_specs: Optional[Iterable[EventEnrichmentSpec]] = None,
                 on_apply=None,
                 **kwargs):
        """
        Args:
            event_log: Event log to enrich. Left untouched; :attr:`event_log`
                returns a copy carrying ``rel_time``, ``rel_log_time`` and every
                applied event enrichment.
            case_id_col: Column identifying the case an event belongs to.
            time_col: Event timestamp column.
            activity_col: Event activity (event type) column.
            initial_specs: Case enrichments to start with, e.g. carried over from
                a previous session.
            initial_event_specs: Event enrichments to start with. Applied before
                the catalog is built, so a seeded column is trackable from the
                first render.
            on_apply: Called after each successful apply on either tab, e.g. to
                refresh dependent notebook cells.
        """
        super().__init__(**kwargs)
        self._case_id_col = case_id_col
        self._time_col = time_col
        self._activity_col = activity_col
        self._on_apply = on_apply
        self._handled_apply_id: Optional[int] = None
        self._handled_preview_id: Optional[int] = None
        self._handled_event_apply_id: Optional[int] = None
        self._handled_event_preview_id: Optional[int] = None

        self._base_event_log = event_add_relative_log_time(
            ensure_relative_time(event_log, case_id_col=case_id_col, time_col=time_col).copy(),
            time_col=time_col)
        self._event_specs: List[EventEnrichmentSpec] = list(initial_event_specs or [])
        self._event_log = self._materialize_events(self._event_specs)

        self._base_case_log = create_case_log(
            self._event_log, case_id_col=case_id_col, time_col=time_col,
            activity_col=activity_col)
        self._sorted_case_ids = sorted(str(case_id) for case_id in self._base_case_log.index)

        self.log_summary = log_summary(self._event_log, case_id_col=case_id_col,
                                       time_col=time_col, activity_col=activity_col)
        self.catalog = self._build_catalog()
        self.event_catalog = self._build_event_catalog()
        self.event_applied = self._event_applied_payload()
        self._case_log = self._materialize(list(initial_specs or []))
        self.applied = self._applied_payload()

    # ------------------------------------------------------------------
    # notebook-facing surface
    # ------------------------------------------------------------------
    @property
    def case_log(self) -> DataFrame:
        """The enriched case log, one row per case, carrying its provenance record.

        A copy, so adjusting it in a notebook cell -- adding an outcome column,
        folding indicators, dropping what turned out useless -- cannot disturb
        the widget's own state.
        """
        return self._case_log.copy()

    @property
    def event_log(self) -> DataFrame:
        """The event log with ``rel_time``, ``rel_log_time`` and the applied
        event enrichments, carrying its own provenance record."""
        return self._event_log

    @property
    def specs(self) -> List[EnrichmentSpec]:
        """The case enrichments currently applied, in column order."""
        return specs_of(self._case_log)

    @property
    def event_specs(self) -> List[EventEnrichmentSpec]:
        """The event enrichments currently applied, in the order they run."""
        return list(self._event_specs)

    # ------------------------------------------------------------------
    # catalog
    # ------------------------------------------------------------------
    def _build_catalog(self) -> Dict[str, Any]:
        return {
            'kinds': [{'key': kind, 'label': KIND_LABELS[kind]} for kind in KINDS],
            'base_columns': base_columns(self._base_case_log),
            'activities': activity_catalog(self._event_log,
                                           case_id_col=self._case_id_col,
                                           activity_col=self._activity_col),
            'track_groups': trackable_attributes(self._event_log,
                                                 case_id_col=self._case_id_col,
                                                 time_col=self._time_col,
                                                 activity_col=self._activity_col),
            'track_methods': list(TRACK_METHODS),
            'all_events': ALL_EVENTS,
        }

    def _build_event_catalog(self) -> Dict[str, Any]:
        derived = [spec.column for spec in self._event_specs]
        return {
            'kinds': [{'key': kind, 'label': EVENT_KIND_LABELS[kind]}
                      for kind in EVENT_KINDS],
            'kind_groups': [{'key': key, 'label': label, 'kinds': list(kinds)}
                            for key, label, kinds in EVENT_KIND_GROUPS],
            'event_types': event_type_catalog(self._event_log, derived=derived,
                                              case_id_col=self._case_id_col,
                                              time_col=self._time_col,
                                              activity_col=self._activity_col),
            'time_columns': time_columns(self._event_log, derived=derived,
                                         case_id_col=self._case_id_col,
                                         time_col=self._time_col,
                                         activity_col=self._activity_col),
            'numeric_profiles': numeric_profiles(self._event_log,
                                                 case_id_col=self._case_id_col,
                                                 time_col=self._time_col,
                                                 activity_col=self._activity_col),
            'all_events': ALL_EVENTS,
            'axis_columns': [self._case_id_col, self._time_col, self._activity_col],
            'columns': [str(name) for name in self._event_log.columns],
        }

    def _applied_payload(self) -> List[Dict[str, Any]]:
        return [spec.to_dict() for spec in specs_of(self._case_log)]

    def _event_applied_payload(self) -> List[Dict[str, Any]]:
        return [spec.to_dict() for spec in self._event_specs]

    def _materialize(self, specs: Sequence[EnrichmentSpec],
                     case_log: Optional[DataFrame] = None,
                     event_log: Optional[DataFrame] = None) -> DataFrame:
        """Apply case specs to a fresh base case log."""
        base = self._base_case_log if case_log is None else case_log
        return apply_specs(base, self._event_log if event_log is None else event_log,
                           specs, case_id_col=self._case_id_col, time_col=self._time_col,
                           activity_col=self._activity_col)

    def _materialize_events(self, specs: Sequence[EventEnrichmentSpec],
                            event_log: Optional[DataFrame] = None) -> DataFrame:
        """Apply event specs to a fresh base event log."""
        base = self._base_event_log if event_log is None else event_log
        return apply_event_specs(base, specs, case_id_col=self._case_id_col,
                                 time_col=self._time_col,
                                 activity_col=self._activity_col)

    # ------------------------------------------------------------------
    # case trait observers
    # ------------------------------------------------------------------
    @traitlets.observe('apply_request')
    def _handle_apply_request(self, change):
        request = change.get('new', {})
        request_id = request.get('request_id')
        if not request or request_id is None or request_id == self._handled_apply_id:
            return
        self._handled_apply_id = request_id

        added = specs_from_dicts(request.get('add', []))
        removed = [str(column) for column in request.get('remove', [])]
        try:
            # Removal is expressed by omission: the surviving specs are re-applied
            # to a fresh base case log, so a removed column is simply never
            # produced. Re-adding something staged for removal therefore works
            # without a special case -- it comes back through ``added``.
            surviving = [spec for spec in specs_of(self._case_log)
                         if spec.column not in removed]
            kept_columns = {spec.column for spec in surviving}
            added = [spec for spec in added if spec.column not in kept_columns]
            case_log = self._materialize(surviving + added)
        except Exception as exc:  # pylint: disable=broad-except
            self.apply_result = {'ok': False, 'error': str(exc), 'request_id': request_id}
            return

        self._case_log = case_log
        self.applied = self._applied_payload()
        self.apply_result = {
            'ok': True,
            'added': [spec.column for spec in added],
            'removed': removed,
            'columns': int(len(case_log.columns)),
            'cases': int(len(case_log)),
            'request_id': request_id,
        }
        if self._on_apply is not None:
            self._on_apply()

    @traitlets.observe('preview_request')
    def _handle_preview_request(self, change):
        request = change.get('new', {})
        request_id = request.get('request_id')
        if not request or request_id is None or request_id == self._handled_preview_id:
            return
        self._handled_preview_id = request_id
        try:
            self.preview_result = self._build_preview(
                specs_from_dicts(request.get('add', [])),
                [str(column) for column in request.get('remove', [])],
                int(request.get('seed', 0)),
                int(request.get('cases', PREVIEW_CASES)),
                request_id,
            )
        except Exception as exc:  # pylint: disable=broad-except
            self.preview_result = {'ok': False, 'error': str(exc), 'request_id': request_id}

    # ------------------------------------------------------------------
    # event trait observers
    # ------------------------------------------------------------------
    @traitlets.observe('event_apply_request')
    def _handle_event_apply_request(self, change):
        request = change.get('new', {})
        request_id = request.get('request_id')
        if not request or request_id is None or request_id == self._handled_event_apply_id:
            return
        self._handled_event_apply_id = request_id

        removed = [str(column) for column in request.get('remove', [])]
        blocked = self._blocked_removals(removed)
        if blocked:
            self.event_apply_result = {'ok': False, 'blocked': blocked,
                                       'request_id': request_id}
            return

        added = event_specs_from_dicts(request.get('add', []))
        surviving = [spec for spec in self._event_specs if spec.column not in removed]
        rejected = self._reject_reason(surviving, added)
        if rejected is not None:
            self.event_apply_result = {'ok': False, 'error': rejected,
                                       'request_id': request_id}
            return

        try:
            event_log = self._materialize_events(surviving + added)
        except Exception as exc:  # pylint: disable=broad-except
            self.event_apply_result = {'ok': False, 'error': str(exc),
                                       'request_id': request_id}
            return

        self._event_specs = surviving + added
        self._event_log = event_log
        # The case log keeps the values it already has -- see the class docstring
        # -- but the catalog is rebuilt so the new columns are trackable now.
        self.catalog = self._build_catalog()
        self.event_catalog = self._build_event_catalog()
        self.event_applied = self._event_applied_payload()
        self.event_apply_result = {
            'ok': True,
            'added': [spec.column for spec in added],
            'removed': removed,
            'columns': int(len(event_log.columns)),
            'events': int(len(event_log)),
            'request_id': request_id,
        }
        if self._on_apply is not None:
            self._on_apply()

    @traitlets.observe('event_preview_request')
    def _handle_event_preview_request(self, change):
        request = change.get('new', {})
        request_id = request.get('request_id')
        if not request or request_id is None or request_id == self._handled_event_preview_id:
            return
        self._handled_event_preview_id = request_id
        try:
            self.event_preview_result = self._build_event_preview(
                event_specs_from_dicts(request.get('add', [])),
                [str(column) for column in request.get('remove', [])],
                int(request.get('seed', 0)),
                int(request.get('cases', PREVIEW_EVENT_CASES)),
                str(request.get('scope', 'touching')),
                request_id,
            )
        except Exception as exc:  # pylint: disable=broad-except
            self.event_preview_result = {'ok': False, 'error': str(exc),
                                         'request_id': request_id}

    # ------------------------------------------------------------------
    # event-side guards
    # ------------------------------------------------------------------
    def _blocked_removals(self, removed: Sequence[str]) -> List[Dict[str, Any]]:
        """Removals that would leave something standing on nothing.

        Two readers can hold an event column down: a case column that tracks it,
        and a later event column derived from it. Both are reported rather than
        cascaded -- dropping the dependants along with it would delete work the
        user never asked to lose.
        """
        blocked = []
        case_specs = specs_of(self._case_log)
        surviving = [spec for spec in self._event_specs if spec.column not in removed]
        for column in removed:
            users = [spec.column for spec in case_specs if spec.attribute == column]
            users += event_columns_using(surviving, column)
            if users:
                blocked.append({'column': column, 'used_by': users})
        return blocked

    def _reject_reason(self, surviving: Sequence[EventEnrichmentSpec],
                       added: Sequence[EventEnrichmentSpec]) -> Optional[str]:
        """The first reason a batch cannot be applied, or ``None``.

        Each addition is validated against the log the *previous* additions would
        leave behind, so a formula reading a column staged alongside it validates
        and a name colliding with one does not.
        """
        columns = self._projected_columns(surviving)
        types = [entry['name'] for entry in self.event_catalog.get('event_types', [])]
        derived = list(surviving)
        for spec in added:
            reason = validate_event_spec(spec, columns, types,
                                         self._numeric_in_scope(spec.event_type, derived),
                                         self._time_in_scope(spec.event_type))
            if reason is not None:
                return f'{spec.column or "column"}: {reason}'
            columns.append(spec.column)
            derived.append(spec)
        return None

    def _projected_columns(self, surviving: Sequence[EventEnrichmentSpec]) -> List[str]:
        """The column names a batch would start from, after its removals."""
        dropped = {spec.column for spec in self._event_specs
                   if spec.column not in {kept.column for kept in surviving}}
        return [str(name) for name in self._event_log.columns if str(name) not in dropped]

    def _numeric_in_scope(self, event_type: Optional[str],
                          derived: Sequence[EventEnrichmentSpec]) -> List[str]:
        """Numeric columns an enrichment on ``event_type`` may read.

        Scoped by event type rather than log-wide, because that is what the
        frontend's operand pickers offer: a formula on ``ER Triage`` reading an
        attribute only ``CRP`` events carry would apply cleanly and produce a
        column of nothing. Mirrors ``numericAttrsOf`` in
        ``src/enrichment/event/staging.ts``.
        """
        scoped = bool(event_type) and event_type != ALL_EVENTS
        names = []
        for entry in self.event_catalog.get('event_types', []):
            if scoped and entry['name'] != event_type:
                continue
            names += [attribute['name'] for attribute in entry['attributes']
                      if attribute['kind'] == 'num']
        names += [spec.column for spec in derived
                  if spec.kind != EVENT_KIND_BINNING
                  and (not scoped or not spec.scoped or spec.event_type == event_type)]
        seen: Dict[str, None] = {}
        for name in names:
            seen.setdefault(name, None)
        return list(seen)

    def _time_in_scope(self, event_type: Optional[str]) -> List[str]:
        """Timestamp columns a binning on ``event_type`` may cut.

        Scoped the same way as :meth:`_numeric_in_scope`, and off the same
        catalog the pane's picker reads, so the two cannot disagree about what
        was offerable.
        """
        catalog: Dict[str, Any] = self.event_catalog.get('time_columns', {})
        scoped = bool(event_type) and event_type != ALL_EVENTS
        if scoped:
            return list(catalog.get(str(event_type), []))
        seen: Dict[str, None] = {}
        for names in catalog.values():
            for name in names:
                seen.setdefault(str(name), None)
        return list(seen)

    # ------------------------------------------------------------------
    # sample preview
    # ------------------------------------------------------------------
    def _build_preview(self,  # pylint: disable=too-many-locals
                       added: Sequence[EnrichmentSpec],
                       removed: Sequence[str],
                       seed: int,
                       cases: int,
                       request_id: int) -> Dict[str, Any]:
        """Compute the staged case log on a handful of real cases.

        Values are real, not illustrative -- the same enrichers run over a
        sample of the event log. Columns staged for removal stay in, marked, so
        the preview shows what a removal would cost rather than silently hiding
        it.
        """
        case_ids = self._sample_case_ids(seed, cases)
        events = self._event_log[
            self._event_log[self._case_id_col].astype(str).isin(case_ids)]
        sample_case_log = create_case_log(events, case_id_col=self._case_id_col,
                                          time_col=self._time_col,
                                          activity_col=self._activity_col)

        applied_specs = specs_of(self._case_log)
        specs = applied_specs + [spec for spec in added
                                 if spec.column not in
                                 {existing.column for existing in applied_specs}]
        sample_case_log = self._materialize(specs, case_log=sample_case_log,
                                            event_log=events)

        removing = set(removed)
        staged = {spec.column for spec in added}
        base = set(base_columns(self._base_case_log))

        columns = [{'name': self._case_id_col, 'state': 'key'}]
        for name in sample_case_log.columns:
            if name in removing:
                state = 'removing'
            elif name in staged:
                state = 'staged'
            elif name in base:
                state = 'base'
            else:
                state = 'applied'
            columns.append({'name': str(name), 'state': state})

        rows = []
        for case_id in sample_case_log.index:
            values = [str(case_id)] + [_format_value(value)
                                       for value in sample_case_log.loc[case_id]]
            rows.append(values)

        return {
            'ok': True,
            'columns': columns,
            'rows': rows,
            'sampled': int(len(sample_case_log)),
            'total_cases': int(len(self._base_case_log)),
            'total_events': int(len(self._event_log)),
            'request_id': request_id,
        }

    def _build_event_preview(self,  # pylint: disable=too-many-arguments, too-many-positional-arguments, too-many-locals
                             added: Sequence[EventEnrichmentSpec],
                             removed: Sequence[str],
                             seed: int,
                             cases: int,
                             scope: str,
                             request_id: int) -> Dict[str, Any]:
        """Compute the staged event columns on a handful of real cases.

        Rows are grouped by case and ordered in time, because every event
        enrichment is defined relative to its neighbours: a column of values with
        the sequence taken away cannot be checked against anything.
        """
        surviving = [spec for spec in self._event_specs if spec.column not in removed]
        specs = surviving + [spec for spec in added
                             if spec.column not in {kept.column for kept in surviving}]
        case_ids = self._sample_case_ids(seed, cases, staged=added, scope=scope)
        events = self._base_event_log[
            self._base_event_log[self._case_id_col].astype(str).isin(case_ids)]
        sample = self._materialize_events(specs, event_log=events)
        sample = sample.sort_values([self._case_id_col, self._time_col],
                                    kind='mergesort')

        staged_columns = {spec.column for spec in added}
        columns = [{'name': spec.column,
                    'kind': spec.kind,
                    'event_type': None if not spec.scoped else spec.event_type,
                    'state': 'staged' if spec.column in staged_columns else 'applied'}
                   for spec in specs]

        rows = []
        for case_id, group in sample.groupby(sample[self._case_id_col], sort=False):
            rows.append({'group': True, 'case': str(case_id),
                         'events': int(len(group))})
            for position, (index, event) in enumerate(group.iterrows(), start=1):
                del index
                rows.append({
                    'group': False,
                    'case': str(case_id),
                    'index': position,
                    'activity': str(event[self._activity_col]),
                    'timestamp': _format_value(event[self._time_col]),
                    'values': [self._preview_cell(spec, event) for spec in specs],
                })

        return {
            'ok': True,
            'columns': columns,
            'rows': rows,
            'sampled': int(sample[self._case_id_col].nunique()),
            'events': int(len(sample)),
            'total_cases': int(len(self._base_case_log)),
            'total_events': int(len(self._base_event_log)),
            'scope': scope,
            'request_id': request_id,
        }

    def _preview_cell(self, spec: EventEnrichmentSpec, event) -> Optional[str]:
        """One preview cell, or ``None`` where the column does not apply.

        A column scoped to one event type has nothing to say about an event of
        another type, which is a different statement from ``NaN`` -- the widget
        renders the two differently, so they must not collapse here.
        """
        if spec.scoped and str(event[self._activity_col]) != str(spec.event_type):
            return None
        return _format_value(event[spec.column])

    def _sample_case_ids(self, seed: int, cases: int,
                         staged: Sequence[EventEnrichmentSpec] = (),
                         scope: str = 'any') -> List[str]:
        """A deterministic sample of case ids: the same seed always picks the same cases.

        With ``scope='touching'`` the sample is drawn from the cases that carry at
        least one event of a staged column's type, so previewing a column on a
        rare activity does not come back three cases that never see it.
        """
        pool = self._sorted_case_ids
        if scope == 'touching':
            types = {spec.event_type for spec in staged if spec.scoped}
            if types:
                touching = self._base_event_log[
                    self._base_event_log[self._activity_col].astype(str).isin(
                        {str(name) for name in types})][self._case_id_col]
                candidates = sorted({str(case_id) for case_id in touching})
                pool = candidates or pool
        count = min(max(cases, 1), len(pool))
        return random.Random(seed).sample(pool, count)


def _format_value(value: Any) -> str:  # pylint: disable=too-many-return-statements
    """Render one cell for a preview table.

    Missing values keep the name pandas gives them (``NaT`` for a missing time,
    ``NaN`` for a missing number) rather than collapsing to a blank: which kind
    of nothing a column holds is exactly what a preview is for.
    """
    if isinstance(value, list):
        return '[' + ', '.join(_format_value(item) for item in value) + ']'
    if value is None:
        return 'None'
    if value is pd.NaT:
        return 'NaT'
    try:
        if pd.isna(value):
            return 'NaN'
    except (TypeError, ValueError):
        pass
    if isinstance(value, pd.Timedelta):
        return str(value)
    if isinstance(value, float):
        return f'{value:g}'
    return str(value)
