"""Team radio (spec 19): topic tags from fixed keyword rules, and matching a clip to the driver's lap."""

from __future__ import annotations

import re
from bisect import bisect_right

TAGS: dict[str, list[str]] = {
    "box": ["box", "boxing", "pit this lap", "pit now", "stay out", "plan a", "plan b", "plan c", "extend"],
    "tyres": ["tyre", "tyres", "tire", "tires", "grip", "deg", "degradation", "graining", "blistering", "rears",
              "fronts", "softs", "mediums", "hards"],
    "pace": ["push", "pace", "gap", "delta", "faster", "slower", "lift and coast", "manage"],
    "issue": ["problem", "issue", "damage", "broken", "lost power", "engine", "gearbox", "brakes", "puncture"],
}  # fmt: skip
_PATTERNS = {k: re.compile(r"\b(" + "|".join(re.escape(w) for w in v) + r")\b", re.IGNORECASE) for k, v in TAGS.items()}


def tags(text: str) -> set[str]:
    """The spec 19 topic tags of a transcript (whole words, case-insensitive)."""
    return {k for k, p in _PATTERNS.items() if p.search(text or "")}


def lap_of(clip_time: str, lap_starts: list[tuple[str, int]]) -> int | None:
    """The lap whose start is the last one before the clip. lap_starts: (ISO time, lap) sorted by time."""
    times = [t for t, _ in lap_starts]
    i = bisect_right(times, clip_time) - 1
    return lap_starts[i][1] if i >= 0 else None
