[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/ronscar/gta6-twitch-ccu-forecast-01/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/ronscar/gta6-twitch-ccu-forecast-01/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

# GTA VI launch-day Twitch viewership forecast — make.fun entry

Entry for the [make.fun bounty "Forecast GTA VI's launch-day Twitch viewers hour by hour"](https://make.fun/bounty/gta6-twitch-ccu-forecast-01) ($250, 20 places). Referral: https://make.fun/r/5f12b2ma

Competition: **gta6-twitch-ccu-forecast-01** — "Forecast GTA VI's launch-day
Twitch viewers hour by hour" ($250, 20 places). One program, `main.py`
(Python 3.13, standard library only, deterministic, no network): reads the
case file(s) in `$MAKEFUN_INPUT_DIR` (else `/input`) and writes one
`<id>.out` per case to `$MAKEFUN_OUTPUT_DIR` (else `/output`): for each of
hours 2–24 of 2026-11-19 (UTC), five quantiles (5%, 25%, 50%, 75%, 95%) of
the concurrent live viewers in Twitch's "Grand Theft Auto VI" category.

## Model

The launch-day shape of a big game is mostly its *unlock shape*. GTA VI
unlocks at midnight local time, rolling country by country (NZ first
2026-11-18T11:00Z, CET 23:00Z, UK 00:00Z, US East 05:00Z, US West 08:00Z),
console-only, no PC at launch — so hour 1 already has real viewers (early
regions unlocked, hype streams running) and the day climbs to an evening
peak as the US unlocks. Games with one simultaneous global unlock have a
near-empty hour 1 and explode 100–1000× in a few hours: a different animal.

The reference set is therefore built from the case's own `comparables`,
filtered to launches with that rolling shape:

- complete release-day curve (≥20 of 24 hourly points, hour 1 present);
- tier `"comparable"` as tagged in the case file itself (early-access
  contaminated and weak tiers excluded; the GTA VI target-history entry has
  no release day, so it drops out);
- rolling: hour-1 viewers ≥ 3% of that launch's release-day peak
  (simultaneous launches sit below 1%: Silksong 0.05%, Wukong 1.1%,
  Battlefield 6 0.4%, Baldur's Gate 3 0.7%).

Per forecast hour h, the centre is the **weighted median** across the
reference launches of `ln(viewers_h / viewers_1)`; console-only launches
(no PC in platforms) get weight 2, the rest weight 1. The spread is the
cross-launch IQR of the same log-ratios as a log-sigma (IQR / 1.349),
floored at 0.30 and capped at 0.70:

```
q_tau(h) = p1 * exp(centre_h + z_tau * sigma_h),  z = (-1.645, -0.674, 0, 0.674, 1.645)
```

with p1 the case's hour-1 print. The median curve dips to ~0.87× p1 in hour
2 (late-night lull), recovers through the US unlocks (hours 6–9), and peaks
at ~2.6× p1 in hours 19–20 UTC (US afternoon + EU evening), easing to
~2.0× p1 by hour 24. References are picked per hour (rolling → all
tier-comparable → all usable launches → house persistence baseline), so a
case is never invalid.

## Backtest (leave-one-out, exact pinball loss from the rules)

`backtest.py` (kept beside the repo, not in it) builds a pseudo-case per
comparable launch — its hour 1 as the print, its hours 2–24 as the answer,
all other comparables as the reference — runs this exact `main.py` on it,
and scores it. The house baseline is scored the same way.

| population | n | this model | house baseline |
|---|---|---|---|
| GTA-VI-like (rolling, peak at hour ≥ 7) | 24 | **0.296** (typical miss 67%, 90% coverage 0.88) | 0.383 |
| all complete launches | 37 | **0.815** | 0.930 |

The simultaneous-global launches are near-unforecastable from hour 1 alone
and unlike GTA VI, so the GTA-VI-like row is the relevant one. An
evening-trend adjustment (target's hour 1 vs its evening peak) was tried
and rejected: it scored worse in backtest.

## Assumptions and demand context

- The forecast scales with hour 1; it does not guess an absolute level.
  Hour 1 is expected to be very large: GTA V is Twitch's most-watched game
  ever by hours watched (1.4B hours in 2024, ~133k average concurrent
  viewers in 2026) with an all-time Twitch peak of 1.16M viewers; the GTA VI
  category itself drew 1,418,094 concurrent viewers in a single hour at its
  2026-08-27 extended-look premiere (from the case's own comparables), and
  its first trailer set a record with 93M views in 24 hours.
- The evening peak (hours 19–20 UTC) reflects US afternoon viewing plus
  EU prime time; the early hours reflect the late-night lull before the US
  unlocks at 05:00/08:00 UTC.
- The two worst backtest misses are slow-burn launches (Resident Evil
  Requiem, Clair Obscur: Expedition 33, peak 11–12× hour 1); GTA VI, the
  most anticipated launch on record, is not a slow burn, so the median
  curve — not the slow-burn tail — is the forecast.

## Run locally

```sh
mkdir -p out
MAKEFUN_INPUT_DIR=<kit>/input MAKEFUN_OUTPUT_DIR=out python3 main.py
python3 backtest.py   # leave-one-out pinball loss vs the house baseline
```

Runtime is ~0.25 s for the 4 practice cases (limit is 8 s per case);
two runs produce byte-identical output.
