"""Forecast Grand Theft Auto VI's launch-day Twitch viewers, hours 2-24.

Approach, in short: anchor everything on the case's hour-1 print and
borrow the shape of the day from past launches that unlocked the same
way GTA VI does -- at midnight local time, rolling zone by zone.

For each comparable launch we take its release-day hourly viewer counts
and normalise them by that launch's own hour-1 print, giving log-ratios
ln(v_h / v_1) for every hour h.  Two facts about those ratios drive the
forecast:

* Launches that already drew a big crowd in hour 1 ramp up much less
  over the day than launches that started quiet (their hour 1 only
  caught New Zealand and a few early zones).  So for each hour we fit
  a ridge regression of the log-ratio on the launch's log hour-1 print
  and predict the target's median log-ratio at its own hour-1 print.
* The honest spread is the cross-launch spread itself: the quantiles
  come from the empirical distribution of the rolling-midnight pool's
  log-ratios, re-centred on the regression median.

Only comparables whose unlock was a rolling midnight are used.  The
target's own category history (a pre-release row, not a launch) is
excluded, as are launches whose release-day hour 1 is missing.

The program is deterministic: comparables are processed in name order,
there is no randomness, and the same input always yields the same bytes.
It reads every *.in in $MAKEFUN_INPUT_DIR (else /input) and writes one
<id>.out per case to $MAKEFUN_OUTPUT_DIR (else /output).
"""

import json
import math
import os
from datetime import datetime
from pathlib import Path

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
# Standard-normal quantiles at the scored levels.
Z = [-1.6448536269514722, -0.6744897501960817, 0.0, 0.6744897501960817, 1.6448536269514722]
# Ridge penalty on the log(hour-1) slope of the per-hour regressions.
RIDGE = 5.0
# The rolling-midnight pool is the shape donor; below this size the
# forecast falls back to every usable comparable instead.
MIN_POOL = 3


def _parse_time(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def _release_day(comp):
    """Hour -> viewers for the comparable's release day (hours 1..24).

    Returns an empty dict when the launch has no usable release-day
    points.  A point counts only when it lands exactly on an hour
    boundary of the release day.
    """
    day_start = _parse_time(comp["day_start"])
    day = {}
    for point in comp.get("hourly") or []:
        viewers = point.get("viewers")
        if viewers is None:
            continue
        delta = (_parse_time(point["from"]) - day_start).total_seconds() / 3600
        hour = int(delta) + 1
        if 1 <= hour <= 24 and delta == int(delta):
            day[hour] = max(1, viewers)
    return day


def _is_rolling_midnight(comp):
    """True when the launch unlocked at midnight local, zone by zone.

    The notes phrase this several ways -- "midnight local", "12 AM
    local", or just "rolling" -- so accept any of them.
    """
    unlock = (comp.get("unlock") or "").lower()
    return (
        "midnight local" in unlock
        or "12 am local" in unlock
        or "rolling" in unlock
    )


def _is_launch(comp):
    """False for the target category's own pre-release history row."""
    unlock = (comp.get("unlock") or "").lower()
    name = (comp.get("name") or "").lower()
    return "not a launch" not in unlock and "before release" not in name


def _usable_pool(case):
    """Release-day series of every comparable that can anchor a ratio."""
    pool = []
    for comp in case.get("comparables") or []:
        if not _is_launch(comp):
            continue
        day = _release_day(comp)
        if day.get(1):
            pool.append((day, comp))
    return pool


def _regression_quantiles(pool, hour, p1):
    """The five quantiles of the log-ratio for `hour`, from a ridge
    regression of ln(v_h / v_1) on centred ln(v_1) across the pool.

    The slope is shrunk toward zero so a small pool cannot chase noise;
    the quantiles are the regression prediction plus the empirical
    quantiles of its residuals.  Returns None when no pool member has
    this hour.
    """
    xs = []
    ys = []
    for day, _comp in pool:
        if hour in day:
            xs.append(math.log(day[1]))
            ys.append(math.log(day[hour] / day[1]))
    n = len(xs)
    if n == 0:
        return None
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    sxx = sum((x - mean_x) ** 2 for x in xs)
    slope = 0.0
    if sxx > 0:
        slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / (sxx + RIDGE)
    prediction = mean_y + slope * (math.log(p1) - mean_x)
    residuals = sorted(
        y - (mean_y + slope * (x - mean_x)) for x, y in zip(xs, ys)
    )
    return [prediction + residuals[int(tau * (n - 1))] for tau in LEVELS]


def _hour_quantiles(pool, hour, p1):
    """The five quantiles for one hour, as ratios to the hour-1 print.

    The centre is the regression's median forecast; the spread is the
    empirical spread of the pool's own log-ratios around their median,
    so the width is the honest cross-launch disagreement.
    """
    ratios = sorted(math.log(day[hour] / day[1]) for day, _c in pool if hour in day)
    n = len(ratios)
    if n == 0:
        return None
    centre = _regression_quantiles(pool, hour, p1)
    if centre is None:
        return None
    spread_median = ratios[n // 2]
    centre_log = centre[2]
    return [
        math.exp(centre_log + (ratios[int(tau * (n - 1))] - spread_median))
        for tau in LEVELS
    ]


def _persistence_quantiles(p1, hour):
    """Fallback: stay at the hour-1 print with a widening spread."""
    width = 0.15 * math.sqrt(hour - 1)
    return [math.exp(z * width) for z in Z]


def _round2(value):
    """Round to 2 decimals, half up, returning an int when whole."""
    scaled = value * 100
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    rounded = whole / 100
    return int(rounded) if rounded.is_integer() else rounded


def forecast_case(case, name):
    if case["levels"] != LEVELS:
        raise ValueError(f"{name} asks for levels {case['levels']}, not {LEVELS}")
    known = [row for row in case.get("known") or [] if row.get("hour") == 1]
    if known:
        p1 = max(1, known[0]["viewers"])
    else:
        hourly = case.get("history_hourly") or []
        p1 = max(1, hourly[-1]["viewers"]) if hourly else 1

    pool = _usable_pool(case)
    # Name order, so the pool order (and the floating-point sums over
    # it) never depends on how the case file listed the comparables.
    pool.sort(key=lambda item: (item[1].get("name") or ""))
    rolling = [(day, comp) for day, comp in pool if _is_rolling_midnight(comp)]
    shape_pool = rolling if len(rolling) >= MIN_POOL else pool

    hours = []
    for row in case["forecast"]:
        hour = row["hour"]
        ratios = _hour_quantiles(shape_pool, hour, p1) if shape_pool else None
        if ratios is None:
            ratios = _persistence_quantiles(p1, hour)
        quantiles = []
        previous = 0.0
        for ratio in ratios:
            value = p1 * ratio
            value = min(max(value, 0.01), 1e9)
            value = max(value, previous)  # keep the row non-decreasing
            quantiles.append(_round2(value))
            previous = quantiles[-1]
        hours.append({"hour": hour, "q": quantiles})
    return {"hours": hours}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case, path.name)
        text = json.dumps(forecast, separators=(",", ":")) + "\n"
        (OUTPUT_DIR / f"{path.stem}.out").write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
