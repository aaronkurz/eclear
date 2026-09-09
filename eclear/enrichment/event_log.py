"""Relative-time columns on the *event* log.

One function, because one is all the widget needs: every event's offset from the
start of the log, which :class:`~eclear.widget.EnrichmentWidget` writes
onto the base log so the notebooks downstream have a numeric time axis.

The case-relative counterpart lives in
:mod:`~eclear.enrichment.enrichers` as
:func:`~eclear.enrichment.enrichers.ensure_relative_time`, which derives
``rel_time`` on demand rather than requiring a caller to have added it first.

An earlier version of this module carried a good deal more -- positional
classifiers, ordered case ids, a row-by-row tracked-variable walk -- none of
which anything called. It was removed rather than left to rot untested.
"""
from pandas import DataFrame

TIME_COL = 'time:timestamp'


def event_add_relative_log_time(event_log: DataFrame,
                                time_col: str = TIME_COL) -> DataFrame:
    """Add ``rel_log_time``: each event's offset from the first event of the log.

    Measured from the log's own minimum rather than the frame's first row, so a
    log that arrives unsorted gets the same column as one that does not.
    """
    event_log['rel_log_time'] = event_log[time_col] - event_log[time_col].min()
    return event_log
