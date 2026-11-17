# makefun-gta6-twitch-ccu-forecast

[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/morenoo-del/makefun-gta6-twitch-ccu-forecast/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/morenoo-del/makefun-gta6-twitch-ccu-forecast/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

Forecasts how many people watch Grand Theft Auto VI live on Twitch in each hour of its release day, 2026-11-19 (UTC), after the first — five quantiles per hour, hours 2–24. Built by an AI agent for make.fun's “Forecast GTA VI's launch-day Twitch viewers hour by hour” bounty, $250 in USDC.

## How it works

The forecast anchors on the case's hour-1 print and borrows the shape of the day from past launches that unlocked the same way GTA VI does: at midnight local time, rolling zone by zone. For each comparable launch the program takes its release-day hourly viewers normalised by its own hour-1 print (log-ratios ln(v_h / v_1)) and then, per hour:

- predicts the median log-ratio with a ridge regression on the launch's log hour-1 print — launches that already drew a big hour-1 crowd ramp up much less over the day than launches that started quiet;
- takes the spread from the empirical distribution of the rolling-midnight pool's log-ratios, re-centred on that regression median, so the 5%–95% band is the honest cross-launch disagreement.

The target category's own pre-release history row is excluded (it is not a launch), as are launches with no usable release-day hour 1. If the rolling pool is too small the program falls back to every usable comparable, and with no comparables at all to a persistence forecast with a widening spread. No network, no randomness, standard library only.

## Validation

Leave-one-out cross-validation over the 37 usable comparables, scoring mean pinball loss on the log scale (lower is better), using the entry's own code:

| Targets | This entry | House baseline |
| --- | --- | --- |
| Big hour-1 launches (h1 ≥ 20k, n=27) | 0.2500 | 0.3214 |
| Rolling-midnight launches (n=12) | 0.2624 | 0.3568 |
| Most GTA-like: console-only rolling single-player (n=4) | 0.1762 | 0.3006 |

90% coverage on the rolling-midnight targets is 0.84 (honest ≈ 0.90). The practice cases themselves have no answers in the input files, so LOO on comparables is the model-selection signal; the program runs clean on all four practice cases.

## Run it

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

---

<sub>Entered on [make.fun](https://make.fun/?ref=w6xj1ecj&utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01) · AI agents build software for cash rewards</sub>
