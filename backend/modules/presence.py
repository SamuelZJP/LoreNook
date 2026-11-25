"""How many people the home page says are by the fire.

Not a real count yet: a daily curve by Beijing time (quiet in working hours, a lunch bump, the most before
bed, more on weekend days), with slow noise that changes every ten minutes and blends between slots, so
reloading never makes the number jump. Replace `online_count` with a real count when there is one.
"""

from datetime import UTC, datetime, timedelta
import math

LOWEST, HIGHEST = 3, 60
SLOT_SECONDS = 600
NOISE = 0.12
# Share of the peak at each Beijing hour.
CURVE = (.85, .6, .35, .2, .12, .1, .12, .18, .22, .2, .2, .25,
         .42, .38, .22, .2, .22, .3, .4, .55, .68, .8, .95, 1.0)
BEIJING = timedelta(hours=8)


def _hash(slot: int) -> float:
    """A fixed value in [-1, 1) for each slot."""
    value = math.sin(slot * 12.9898) * 43758.5453
    return (value - math.floor(value)) * 2 - 1


def online_count(now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    local = now.astimezone(UTC) + BEIJING
    hour = local.hour + local.minute / 60
    index, part = int(hour), hour - int(hour)
    share = CURVE[index] + (CURVE[(index + 1) % 24] - CURVE[index]) * part
    if local.weekday() >= 5 and 9 <= hour < 19:
        share += (1 - share) * 0.35
    slot_position = now.timestamp() / SLOT_SECONDS
    slot, offset = math.floor(slot_position), slot_position - math.floor(slot_position)
    smooth = offset * offset * (3 - 2 * offset)
    share *= 1 + NOISE * (_hash(slot) + (_hash(slot + 1) - _hash(slot)) * smooth)
    share = min(1.0, max(0.0, share))
    return round(LOWEST + (HIGHEST - LOWEST) * share)
