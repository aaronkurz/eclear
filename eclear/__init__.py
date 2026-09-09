"""Interactive event and case log enrichment for Python notebooks.

:mod:`eclear.enrichment` is the engine: it turns an event log into a case log
one :class:`~eclear.enrichment.specs.EnrichmentSpec` at a time, and derives
columns on the event log itself from an
:class:`~eclear.enrichment.event_specs.EventEnrichmentSpec`. Both record what
produced each column on the frame, so an enriched log carries its own
provenance.

`EnrichmentWidget` is the notebook-facing surface: hand it an event log and the
three column names that identify its axes, and it hands back an enriched event
log through `.event_log` and a case log through `.case_log`.
"""
from .widget import EnrichmentWidget

__all__ = ["EnrichmentWidget"]
