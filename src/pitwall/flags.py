"""Official neutralised laps from OpenF1 race control messages (spec 14).

A lap number is the leader's lap, as in OpenF1's `lap_number` and in the per-lap field median of `pitwall.laps`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

KINDS = ("sc", "vsc", "red")


def _periods(msgs: list[Mapping], last_lap: int) -> dict[str, list[tuple[int, int]]]:
    """Return {kind: [(first_lap, last_lap), ...]} from time-ordered messages."""
    out: dict[str, list[tuple[int, int]]] = {k: [] for k in KINDS}
    open_at: dict[str, int | None] = {k: None for k in KINDS}

    def close(kind: str, lap: int) -> None:
        start = open_at[kind]
        if start is not None:
            out[kind].append((start, max(start, lap)))
            open_at[kind] = None

    for m in msgs:
        lap = m.get("lap_number")
        if lap is None:
            continue
        text = (m.get("message") or "").upper()
        cat = m.get("category")
        if cat == "SafetyCar":
            if text.startswith("VIRTUAL SAFETY CAR DEPLOYED"):
                if open_at["vsc"] is None:
                    open_at["vsc"] = lap
            elif text.startswith("VIRTUAL SAFETY CAR ENDING"):
                close("vsc", lap)
            elif text.startswith("SAFETY CAR DEPLOYED"):
                if open_at["sc"] is None:
                    open_at["sc"] = lap
            elif text.startswith("SAFETY CAR IN THIS LAP"):
                close("sc", lap)
        elif cat == "Flag" and m.get("flag") == "RED" and m.get("scope") in (None, "Track"):
            if open_at["red"] is None:
                open_at["red"] = lap
        elif cat == "SessionStatus" and text.startswith("SESSION STARTED"):
            close("red", lap)
    for kind in KINDS:
        close(kind, last_lap)
    return out


def neutral_laps(messages: Iterable[Mapping], last_lap: int) -> dict[int, set[str]]:
    """Map each officially neutral lap (1..last_lap) to the kinds that cover it (spec 14, section 3).

    Lap 1 is always neutral (standing start) and gets the kind "start".
    """
    msgs = sorted(messages, key=lambda m: m.get("date") or "")
    laps: dict[int, set[str]] = {1: {"start"}}
    for kind, spans in _periods(msgs, last_lap).items():
        for a, b in spans:
            for lap in range(max(1, a), min(b, last_lap) + 1):
                laps.setdefault(lap, set()).add(kind)
    return laps


def sector_yellows(messages: Iterable[Mapping]) -> int:
    """Count sector yellow and double yellow flags (counted, not used; spec 14, section 3)."""
    return sum(
        1
        for m in messages
        if m.get("category") == "Flag" and m.get("scope") == "Sector" and "YELLOW" in (m.get("flag") or "")
    )
