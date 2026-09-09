"""Shared fixtures for the log enrichment test suite.

Every log below is intentionally small and hand-verifiable, so that the tests
can spell out expected values as exact literals rather than recomputing them
with the code under test.
"""
import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def event_log() -> pd.DataFrame:
    """10-event log over three cases, hand-verifiable for every enrichment.

    Times are hours from 2024-01-01; ``amount`` rides on ``Pay`` events and
    ``dept`` on ``Register`` events, so the two tracking scopes (one activity vs
    every event) are both exercised.

        row  case  activity   +h   amount  dept
         0   c1    Register    0     -     north
         1   c1    Pay         2    10.0    -
         2   c1    Pay         5    20.0    -    repeated: ::start 2h, ::end 5h
         3   c1    Close       9     -      -
         4   c2    Register    0     -     south
         5   c2    Close       3     -      -    no Pay at all
         6   c3    Register    0     -     north
         7   c3    Pay         3     7.5    -
         8   c3    Pay         4     NaN    -    null value, skipped by every fold
         9   c3    Close       2     -      -    earlier than the Pay rows above it

    c3 is deliberately out of time order in row order, and its ``Close`` precedes
    its first ``Pay``, so ``Pay:Close::delay`` comes out negative there.
    """
    start = pd.Timestamp('2024-01-01')
    rows = [
        ('c1', 'Register', 0, None, 'north'),
        ('c1', 'Pay', 2, 10.0, None),
        ('c1', 'Pay', 5, 20.0, None),
        ('c1', 'Close', 9, None, None),
        ('c2', 'Register', 0, None, 'south'),
        ('c2', 'Close', 3, None, None),
        ('c3', 'Register', 0, None, 'north'),
        ('c3', 'Pay', 3, 7.5, None),
        ('c3', 'Pay', 4, np.nan, None),
        ('c3', 'Close', 2, None, None),
    ]
    return pd.DataFrame({
        'case:concept:name': [row[0] for row in rows],
        'concept:name': [row[1] for row in rows],
        'time:timestamp': [start + pd.Timedelta(hours=row[2]) for row in rows],
        'amount': [row[3] for row in rows],
        'dept': [row[4] for row in rows],
    })


@pytest.fixture
def lifecycle_event_log() -> pd.DataFrame:
    """9-event log over three cases, built for the event-log enrichments.

    Times are hours from 2024-01-01. ``Treat`` carries a lifecycle column and a
    numeric ``dose``; ``Check`` carries ``dose`` too, so a formula scoped to one
    type can be shown not to touch the other.

        row  case  activity   +h   lifecycle  dose
         0   c1    Treat       0   start      1.0     paired with row 1: 2h
         1   c1    Treat       2   complete   1.0
         2   c1    Check       3   -          4.0
         3   c1    Treat       5   start      2.0     paired with row 4: 3h
         4   c1    Treat       8   complete   2.0
         5   c2    Treat       0   start      3.0     never completes -> NaN
         6   c2    Check       1   -          0.0     a zero, for the divide case
         7   c3    Treat       4   complete   4.0     an end with no start -> NaN
         8   c3    Check       1   -          NaN     out of row order, missing dose

    c3's rows are out of time order in row order, so every enrichment that reads
    a case in sequence has to sort rather than trust the frame.
    """
    start = pd.Timestamp('2024-01-01')
    rows = [
        ('c1', 'Treat', 0, 'start', 1.0),
        ('c1', 'Treat', 2, 'complete', 1.0),
        ('c1', 'Check', 3, None, 4.0),
        ('c1', 'Treat', 5, 'start', 2.0),
        ('c1', 'Treat', 8, 'complete', 2.0),
        ('c2', 'Treat', 0, 'start', 3.0),
        ('c2', 'Check', 1, None, 0.0),
        ('c3', 'Treat', 4, 'complete', 4.0),
        ('c3', 'Check', 1, None, np.nan),
    ]
    return pd.DataFrame({
        'case:concept:name': [row[0] for row in rows],
        'concept:name': [row[1] for row in rows],
        'time:timestamp': [start + pd.Timedelta(hours=row[2]) for row in rows],
        'lifecycle:transition': [row[3] for row in rows],
        'dose': [row[4] for row in rows],
    })


@pytest.fixture
def time_event_log() -> pd.DataFrame:
    """6-event log spanning two years, for the time-binning cuts.

    ``lifecycle_event_log`` sits entirely inside 2024-01-01, which exercises
    ``hour`` and nothing else, and too many exact-value tests pin its rows to
    perturb it. This one is chosen so every part has at least two values and
    ``year`` has a gap the observed range still has to cover.

        row  case  activity   timestamp            weekday  month  hour
         0   c1    Treat      2022-03-07 09:00     Mon        3      9
         1   c1    Check      2022-12-25 23:30     Sun       12     23
         2   c1    Treat      2024-07-04 00:15     Thu        7      0
         3   c2    Treat      2024-07-06 12:00     Sat        7     12
         4   c2    Check      2022-03-07 09:00     Mon        3      9
         5   c3    Check      2024-01-01 18:45     Mon        1     18

    2023 appears nowhere, so a ``year`` cut has to produce a category the log
    never sees.
    """
    rows = [
        ('c1', 'Treat', '2022-03-07 09:00'),
        ('c1', 'Check', '2022-12-25 23:30'),
        ('c1', 'Treat', '2024-07-04 00:15'),
        ('c2', 'Treat', '2024-07-06 12:00'),
        ('c2', 'Check', '2022-03-07 09:00'),
        ('c3', 'Check', '2024-01-01 18:45'),
    ]
    return pd.DataFrame({
        'case:concept:name': [row[0] for row in rows],
        'concept:name': [row[1] for row in rows],
        'time:timestamp': [pd.Timestamp(row[2]) for row in rows],
    })


@pytest.fixture
def multi_carrier_event_log() -> pd.DataFrame:
    """6-event log where one attribute rides on two event types.

    ``ward`` is carried by both ``Treat`` and ``Check``, so it is offered
    log-wide *and* under each of them; ``note`` rides on ``Check`` alone, so it
    is offered under ``Check`` only.

        row  case  activity   +h   ward   note
         0   c1    Treat       0   north   -
         1   c1    Check       1   south   a      c1 changed ward
         2   c1    Check       2   south   a
         3   c2    Treat       0   east    -
         4   c2    Check       1   east    b      c2 never changed it
         5   c3    Treat       0    -      -      c3 carries no ward at all
    """
    start = pd.Timestamp('2024-01-01')
    rows = [
        ('c1', 'Treat', 0, 'north', None),
        ('c1', 'Check', 1, 'south', 'a'),
        ('c1', 'Check', 2, 'south', 'a'),
        ('c2', 'Treat', 0, 'east', None),
        ('c2', 'Check', 1, 'east', 'b'),
        ('c3', 'Treat', 0, None, None),
    ]
    return pd.DataFrame({
        'case:concept:name': [row[0] for row in rows],
        'concept:name': [row[1] for row in rows],
        'time:timestamp': [start + pd.Timedelta(hours=row[2]) for row in rows],
        'ward': [row[3] for row in rows],
        'note': [row[4] for row in rows],
    })


@pytest.fixture
def contract_event_log() -> pd.DataFrame:
    """The log the cross-language contract cases are written against.

    Two event types and *two* numeric attributes on one of them, because the
    wire-format cases include an arithmetic column over two operands, which
    neither ``event_log`` nor ``lifecycle_event_log`` can express.

        row  case  activity   +h   dose  reading
         0   c1    Treat       0    1.0    4.0
         1   c1    Check       1    2.0    NaN
         2   c1    Treat       4    3.0    8.0
         3   c2    Treat       0    5.0    0.0    a zero, for the divide case
         4   c2    Check       2    NaN    NaN
    """
    start = pd.Timestamp('2024-01-01')
    rows = [
        ('c1', 'Treat', 0, 1.0, 4.0),
        ('c1', 'Check', 1, 2.0, np.nan),
        ('c1', 'Treat', 4, 3.0, 8.0),
        ('c2', 'Treat', 0, 5.0, 0.0),
        ('c2', 'Check', 2, np.nan, np.nan),
    ]
    return pd.DataFrame({
        'case:concept:name': [row[0] for row in rows],
        'concept:name': [row[1] for row in rows],
        'time:timestamp': [start + pd.Timedelta(hours=row[2]) for row in rows],
        'dose': [row[3] for row in rows],
        'reading': [row[4] for row in rows],
    })

