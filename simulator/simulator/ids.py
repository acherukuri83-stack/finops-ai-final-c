"""Deterministic id and calendar helpers shared by baseline and planter."""

from __future__ import annotations

from datetime import date, timedelta


def business_days_ending(end: date, count: int) -> list[date]:
    """`count` weekday dates ending at (and including) `end`, oldest first."""
    days: list[date] = []
    d = end
    while len(days) < count:
        if d.weekday() < 5:
            days.append(d)
        d -= timedelta(days=1)
    return list(reversed(days))


def business_days_between(start: date, end: date) -> list[date]:
    days: list[date] = []
    d = start
    while d <= end:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    return days
