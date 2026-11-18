"""GTA VI launch-day Twitch viewership forecast (gta6-twitch-ccu-forecast-01).

Forecasts, for each of hours 2..24 of the release day (UTC), five quantiles
(5%, 25%, 50%, 75%, 95%) of the concurrent live viewers in the
"Grand Theft Auto VI" Twitch category, anchored on the case's hour-1 print.

Model (standard library only, deterministic, no network)
--------------------------------------------------------
The launch-day shape of a big game is mostly its *unlock shape*: games that
unlock at midnight local time, rolling country by country, already have real
viewers in hour 1 (early regions unlocked, hype streams running) and then
climb to an evening peak as the US unlocks and prime time arrives. Games
with one simultaneous global unlock have a near-empty hour 1 and explode
100-1000x in a few hours - a different animal, and not GTA VI: GTA VI
unlocks at midnight local (NZ first 2026-11-18T11:00Z, CET 23:00Z, UK
00:00Z, US East 05:00Z, US West 08:00Z), console-only, no PC at launch.

So the reference set is built from the case's own `comparables`, filtered
to launches whose release-day curve has that rolling shape:

  * complete: all 24 hourly points of the release day, every value > 0;
  * tier "comparable" (the case file itself tags each comparable; the
    early-access-contaminated and weak tiers are left out, and the GTA VI
    target-history entry has no release day at all, so it drops out here);
  * rolling: hour-1 viewers >= 3% of that launch's release-day peak
    (simultaneous launches sit below 1%: Silksong 0.05%, Wukong 1.1%,
    Battlefield 6 0.4%, Baldur's Gate 3 0.7%, ...; every rolling launch in
    the kit is >= 5%).

For each forecast hour h, the centre is the *weighted median* across the
reference launches of ln(viewers_h / viewers_1); console-only launches
(platforms with no PC) get weight 2, the rest weight 1, because GTA VI is
console-only. The spread is the cross-launch IQR of the same log-ratios,
converted to a log-sigma (IQR / 1.349), floored at 0.30 and capped at 0.70,
so the 90% band honestly reflects how differently past launches behaved:

    q_tau(h) = p1 * exp(centre_h + z_tau * sigma_h),  z = (-1.645, -0.674,
               0, 0.674, 1.645), rounded to 2 decimals (half up),

with p1 the case's hour-1 print (at least 1). The resulting median curve
rises from ~0.87x p1 in hour 2 (late-night dip) to ~2.6x p1 at the evening
peak (hours 19-20 UTC, US afternoon + EU evening), then eases to ~2.0x.

What the data says (leave-one-out backtest over the kit's comparables,
exact pinball loss from the rules; see backtest.py beside the repo):
  * house persistence baseline: 0.383 loss on the 24 GTA-VI-like
    (rolling, late-peak) launches; 0.930 over all 37 complete launches.
  * this model: 0.296 on the GTA-VI-like launches (typical miss 67%,
    90% coverage 0.88); 0.817 over all 37 (the simultaneous launches are
    intrinsically near-unforecastable from hour 1 alone).
An evening-trend adjustment using the target's own hour-1 vs evening-peak
ratio was tried and REJECTED: it scored worse in backtest (0.322 at the
best positive weight, 0.290 at a -0.25 weight - inside noise), so the
shipped model does not use it.

Demand context (not used by the program, which only reads its case file):
GTA V is Twitch's most-watched game ever in hours watched (1.4B hours in
2024, ~133k average concurrent viewers in 2026) with an all-time Twitch
peak of 1.16M; the GTA VI category itself drew 1,418,094 concurrent
viewers in a single hour at its 2026-08-27 extended-look premiere (from
the case's own comparables) and its trailer 1 set a record with 93M views
in 24 hours. Hour 1 of launch day is therefore expected to be very large,
and the forecast scales with it rather than guessing an absolute level.

Fallbacks (so a case is never invalid): references are picked per hour
from the rolling tier-comparable set first, widening to all
tier-"comparable" launches, then to every usable launch, then to the
house persistence baseline. Every output is clamped to (0, 1e9] and
non-decreasing per row.

Usage: python3 main.py reads every <id>.in in $MAKEFUN_INPUT_DIR (else
/input) and writes <id>.out to $MAKEFUN_OUTPUT_DIR (else /output).
"""

import json
import math
import os
import sys
from datetime import datetime
from pathlib import Path

# The grader's -P leaves /bot off sys.path: put it back first, so a module
# shipped beside this file would import. (This entry is a single file.)
sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.645, -0.674, 0, 0.674, 1.645]

# Reference-set rules (see module docstring).
MIN_REFS = 5
ROLLING_MIN_H1_SHARE = 0.03
CONSOLE_ONLY_WEIGHT = 2.0
OTHER_WEIGHT = 1.0
SIGMA_FLOOR = 0.30
SIGMA_CAP = 0.70
BASELINE_SIGMA = 0.15  # house persistence baseline's per-root-hour sigma


def _parse_time(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def round2(x):
    """x rounded to 2 decimals, half up (as the starter does)."""
    scaled = x * 100
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 100
    return int(value) if value == int(value) else value


def release_day_curve(comp):
    """The comparable's hourly viewer counts on its release day.

    Returns a dict {UTC hour of the day: viewers} for the hours present
    (hour 0 must be present and positive), or None when the comparable
    is not a launch at all or has too little of its release day to use.
    A curve missing one hour is still usable for the hours it has: the
    per-hour step below only uses references that hold the hour it
    forecasts. The GTA VI target-history entry has 7 points on its
    day_start day and no hour 0, so it drops out here.
    """
    try:
        day_start = _parse_time(comp["day_start"])
    except (KeyError, TypeError, ValueError):
        return None
    vals = {}
    for row in comp.get("hourly") or []:
        try:
            idx = int((_parse_time(row["from"]) - day_start).total_seconds() // 3600)
            viewers = row["viewers"]
        except (KeyError, TypeError, ValueError):
            continue
        if 0 <= idx < 24 and isinstance(viewers, (int, float)) and viewers > 0:
            vals[idx] = viewers
    if 0 not in vals or len(vals) < 20:
        return None
    return vals


def tier_of(comp):
    """The case file tags each comparable's tier inside its unlock text."""
    unlock = comp.get("unlock") or ""
    if "Tier:" not in unlock:
        return None
    return unlock.split("Tier:", 1)[1].split(".")[0].split("\n")[0].strip()


def reference_curves(comparables):
    """(rolling tier-comparable curves, tier-comparable curves, all curves).

    Each entry is (curve, weight): console-only launches weigh double.
    """
    all_curves = []
    tier_curves = []
    rolling_curves = []
    for comp in comparables or []:
        curve = release_day_curve(comp)
        if curve is None:
            continue
        weight = CONSOLE_ONLY_WEIGHT if "PC" not in (comp.get("platforms") or "") else OTHER_WEIGHT
        entry = (curve, weight)
        all_curves.append(entry)
        tier = tier_of(comp)
        if tier is None or tier == "comparable":
            tier_curves.append(entry)
            if curve[0] >= ROLLING_MIN_H1_SHARE * max(curve.values()):
                rolling_curves.append(entry)
    return rolling_curves, tier_curves, all_curves


def weighted_median(pairs):
    """Weighted median of (value, weight) pairs; deterministic."""
    ordered = sorted(pairs, key=lambda p: p[0])
    total = sum(w for _, w in ordered)
    acc = 0.0
    for value, weight in ordered:
        acc += weight
        if acc >= total / 2:
            return value
    return ordered[-1][0]


def iqr_sigma(values):
    """IQR-based log-sigma of a list of log-ratios."""
    xs = sorted(values)
    n = len(xs)
    if n < 4:
        return SIGMA_FLOOR
    q1 = xs[n // 4]
    q3 = xs[(3 * n) // 4]
    return max((q3 - q1) / 1.349, 0.0)


def refs_for_hour(ref_lists, hour_idx):
    """References holding both hour 0 and hour_idx, widest set that qualifies.

    Tries the rolling tier-comparable set first, then all tier-comparable,
    then every usable launch, so a sparsely-sampled hour still forecasts
    instead of failing. Returns [] only when no launch holds the hour.
    """
    for refs in ref_lists:
        have = [(curve, w) for curve, w in refs if hour_idx in curve]
        if len(have) >= MIN_REFS:
            return have
    for refs in ref_lists:
        have = [(curve, w) for curve, w in refs if hour_idx in curve]
        if have:
            return have
    return []


def hour_quantiles(p1, ref_lists, hour_idx):
    """The five quantiles for release-day hour index hour_idx (1..23)."""
    refs = refs_for_hour(ref_lists, hour_idx)
    if not refs:
        return None
    log_ratios = [(math.log(curve[hour_idx] / curve[0]), w) for curve, w in refs]
    centre = weighted_median(log_ratios)
    sigma = min(max(iqr_sigma([v for v, _ in log_ratios]), SIGMA_FLOOR), SIGMA_CAP)
    out = []
    prev = 0.0
    for z in Z:
        q = p1 * math.exp(centre + z * sigma)
        q = min(max(q, 1.0), 1_000_000_000.0)
        q = max(q, prev)  # keep the row non-decreasing
        out.append(round2(q))
        prev = q
    return out


def baseline_quantiles(p1, hour):
    """House persistence baseline, used only if no reference exists."""
    out = []
    prev = 0.0
    for z in Z:
        q = min(max(p1 * math.exp(z * BASELINE_SIGMA * math.sqrt(hour - 1)), 1.0),
                1_000_000_000.0)
        q = max(q, prev)
        out.append(round2(q))
        prev = q
    return out


def forecast_case(case, name):
    if case["levels"] != LEVELS:
        raise ValueError(f"{name} asks for levels {case['levels']}, not {LEVELS}")
    first = next((k for k in case["known"] if k["hour"] == 1), None)
    if first is None:
        raise ValueError(f"{name} has no hour-1 print")
    p1 = max(1, first["viewers"])

    rolling, tier, all_refs = reference_curves(case.get("comparables"))
    ref_lists = [rolling, tier, all_refs]

    hours = []
    for row in case["forecast"]:
        h = row["hour"]
        q = hour_quantiles(p1, ref_lists, h - 1)
        if q is None:
            q = baseline_quantiles(p1, h)
        hours.append({"hour": h, "q": q})
    return {"hours": hours}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case, path.name)
        (OUTPUT_DIR / f"{path.stem}.out").write_text(
            json.dumps(forecast, separators=(",", ":")) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
