`python analysis/hazard_calibration.py`
Generated 2026-10-01, seed 20260928, n_eff=50 is an assumption

## 1-3. Weekly hazards WITHOUT treatment (closed form, Weibull by DE, Monte Carlo band)

| Lesion | Interval (weeks) | Weekly hazard, exact | Weibull shape | Hazard wk 1 / 4 / 26 / 52 (Weibull) | p5-p95 of wk-4 hazard, n_eff=50 |
|---|---|---|---|---|---|
| ToF | 0-520 | 0-52: 0.80%; 52-156: 0.29%; 156-520: 0.20% | 0.54 | 4.79% / 1.47% / 0.58% / 0.42% | 0.75%-2.13% |
| TGA (simple) | 0-52 | 0-52: 4.33% | n/a (1 anchor) | 4.33% / 4.33% / 4.33% / 4.33% | 3.24%-7.25% |
| Complete AVSD | 0-52 | 0-26: 2.34%; 26-52: 1.65% | 0.77 | 4.91% / 2.86% / 1.81% / 1.54% | 0.83%-3.70% |
| Large VSD (death) | 0-52 | 0-52: 0.20% | n/a (1 anchor) | 0.20% / 0.20% / 0.20% / 0.20% | 0.04%-0.38% |
| Large VSD (irreversible PVD) | 0-52 | 0-52: 1.03% | n/a (1 anchor) | 1.03% / 1.03% / 1.03% / 1.03% | 0.74%-1.40% |
| HLHS | 0-4 | 0-1: 50.00%; 1-4: 53.58% | 0.42 | 73.81% / 24.04% / 8.33% / 5.63% | 10.22%-45.35% |

## 4. Simulation-based calibration check (Complete AVSD), noisy objective, DE + CRN

closed-form Weibull fit : shape 0.77, scale 48.8 wk
simulation-calibrated   : shape 0.71, scale 48.1 wk (loss 2.50e-07)
fresh 20,000-patient run: S(26 wk) = 0.521 (target 0.54), S(52 wk) = 0.347 (target 0.35)
Fresh-run gap vs target (~0.02 at 26 wk) is about 1.7 Monte Carlo SE: the DE fit is slightly over-tuned to its fixed 2,000-patient random sample; re-validate on fresh draws, as here.
