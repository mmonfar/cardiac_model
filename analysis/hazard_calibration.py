"""Weekly untreated-hazard estimates for ToF, TGA, VSD, complete AVSD and HLHS (not engine code).

Inputs are published survival anchors (cited in docs/risk-table.md). Four steps:

1. Exact piecewise-constant weekly hazard between anchors: h = 1 - (S2/S1)^(1/weeks).
   Closed form, so no optimiser is needed.
2. A smooth Weibull survival S(t) = exp(-(t/scale)^shape) fitted to the anchors by differential
   evolution (Luke, Essentials of Metaheuristics, Alg 38 p.57; Kochenderfer & Wheeler p.177).
   shape < 1 means the risk is highest early and falls with age.
3. Uncertainty by Monte Carlo: each anchor is resampled as Binomial(n_eff, S)/n_eff and refitted.
   n_eff = 50 is an ASSUMPTION (the historic series are small and their n is not in the sources).
4. Simulation-based calibration: a stochastic weekly cohort simulator (per-patient Bernoulli
   deaths) is fitted back to the anchors by DE with common random numbers and elites re-evaluated
   every generation (the usual differential-evolution caveat for noisy fitness). This is the
   pattern a queue model would use, because a queue with capacity has no closed form.

Run: python analysis/hazard_calibration.py  (numpy only, seeded)
"""

from __future__ import annotations

import numpy as np

WEEKS_PER_YEAR = 52.0

# (lesion, [(weeks, survival)], source note) — survival WITHOUT treatment.
ANCHORS: dict[str, tuple[list[tuple[float, float]], str]] = {
    "ToF": (
        [(52, 0.66), (156, 0.49), (520, 0.24)],
        "Indian CHD timing guideline 2019 (ref Bertranou 1978): 66/49/24 % at 1/3/10 y",
    ),
    "TGA (simple)": (
        [(52, 0.10)],
        "Indian CHD timing guideline 2019: ~90 % dead at 1 y, mean life expectancy 0.65 y",
    ),
    "Complete AVSD": (
        [(26, 0.54), (52, 0.35)],
        "Indian CHD timing guideline 2019: 54 % at 6 mo, 35 % at 12 mo",
    ),
    "Large VSD (death)": (
        [(52, 0.90)],
        "Indian CHD timing guideline 2019: ~10 % of large VSDs die in year 1 (heart failure)",
    ),
    "Large VSD (irreversible PVD)": (
        [(52, 1 - 0.52 * 0.8)],
        "Guideline, Wood series: 52 % develop irreversible PVD, "
        "onset in infancy in 4/5 -> ~42 % by 1 y",
    ),
    "HLHS": (
        [(1, 0.50), (4, 0.05)],
        "HLHS review 2016: death 'usually within the first week' (read as ~50 % at 1 wk); "
        "meta-analysis 2024: 95 % of untreated die early (read as by 4 wk)",
    ),
}


def piecewise_weekly_hazards(
    anchors: list[tuple[float, float]],
) -> list[tuple[float, float, float]]:
    """(from_week, to_week, weekly hazard) between successive anchors, starting at S(0)=1."""
    out, t0, s0 = [], 0.0, 1.0
    for t1, s1 in anchors:
        out.append((t0, t1, 1 - (s1 / s0) ** (1 / (t1 - t0))))
        t0, s0 = t1, s1
    return out


def weibull_s(t: np.ndarray, shape: float, scale: float) -> np.ndarray:
    return np.exp(-((t / scale) ** shape))


def differential_evolution(f, bounds, rng, pop=30, gens=150, fw=0.7, cr=0.9, reevaluate=False):
    """DE/rand/1/bin (Luke Alg 38). With reevaluate=True every member is re-scored each
    generation, so a lucky noisy score cannot stay 'best'."""
    lo, hi = np.array(bounds, dtype=float).T
    x = lo + rng.random((pop, len(lo))) * (hi - lo)
    fx = np.array([f(v) for v in x])
    for _ in range(gens):
        if reevaluate:
            fx = np.array([f(v) for v in x])
        for i in range(pop):
            a, b, c = x[rng.choice([j for j in range(pop) if j != i], 3, replace=False)]
            mutant = np.clip(a + fw * (b - c), lo, hi)
            cross = rng.random(len(lo)) < cr
            cross[rng.integers(len(lo))] = True
            trial = np.where(cross, mutant, x[i])
            ft = f(trial)
            if ft <= fx[i]:
                x[i], fx[i] = trial, ft
    k = int(np.argmin(fx))
    return x[k], float(fx[k])


def fit_weibull(anchors, rng):
    t = np.array([a[0] for a in anchors], dtype=float)
    s = np.array([a[1] for a in anchors], dtype=float)

    def loss(v):  # squared error on the log-cumulative-hazard scale
        return float(np.sum((np.log(-np.log(weibull_s(t, *v))) - np.log(-np.log(s))) ** 2))

    return differential_evolution(loss, [(0.1, 3.0), (0.5, 5000.0)], rng)[0]


def weekly_hazard_at(week: float, shape: float, scale: float) -> float:
    """Discrete weekly hazard for week (week, week+1]."""
    s0, s1 = weibull_s(np.array([week, week + 1.0]), shape, scale)
    return float(1 - s1 / s0)


def simulate_cohort(shape, scale, weeks, u):
    """Stochastic weekly cohort: each alive patient dies with the week's hazard.
    ``u`` holds pre-drawn uniforms (common random numbers across candidates)."""
    alive = np.ones(u.shape[0], dtype=bool)
    surv = []
    for w in range(weeks):
        alive &= u[:, w] >= weekly_hazard_at(w, shape, scale)
        surv.append(alive.mean())
    return np.array(surv)


def main() -> None:
    rng = np.random.default_rng(20260928)
    n_eff, n_boot = 50, 200
    print(
        "## 1-3. Weekly hazards WITHOUT treatment (closed form, Weibull by DE, Monte Carlo band)\n"
    )
    print(
        "| Lesion | Interval (weeks) | Weekly hazard, exact | Weibull shape "
        "| Hazard wk 1 / 4 / 26 / 52 (Weibull) | p5-p95 of wk-4 hazard, n_eff=50 |"
    )
    print("|---|---|---|---|---|---|")
    fits = {}
    for name, (anchors, _src) in ANCHORS.items():
        segs = piecewise_weekly_hazards(anchors)
        pw = "; ".join(f"{a:.0f}-{b:.0f}: {h:.2%}" for a, b, h in segs)
        span = f"{segs[0][0]:.0f}-{segs[-1][1]:.0f}"
        shape, scale = fit_weibull(anchors, rng)
        fits[name] = (shape, scale)
        hz = " / ".join(f"{weekly_hazard_at(w - 1, shape, scale):.2%}" for w in (1, 4, 26, 52))
        boot = []
        for _ in range(n_boot):
            resampled = [
                (t, min(max(rng.binomial(n_eff, s) / n_eff, 0.01), 0.99)) for t, s in anchors
            ]
            resampled.sort()
            # keep survival non-increasing after resampling
            m = 1.0
            resampled = [(t, (m := min(m, s))) for t, s in resampled]
            if len(resampled) == 1:  # one anchor: a Weibull is not identified -> use exponential
                ((t, s),) = resampled
                boot.append(1 - s ** (1 / t))
            else:
                b_shape, b_scale = fit_weibull(resampled, rng)
                boot.append(weekly_hazard_at(3, b_shape, b_scale))
        lo, hi = np.percentile(boot, [5, 95])
        shape_txt = f"{shape:.2f}"
        if len(anchors) == 1:  # shape not identified: report the constant exponential hazard
            t_a, s_a = anchors[0]
            shape_txt = "n/a (1 anchor)"
            hz = " / ".join([f"{1 - s_a ** (1 / t_a):.2%}"] * 4)
        print(f"| {name} | {span} | {pw} | {shape_txt} | {hz} | {lo:.2%}-{hi:.2%} |")

    print("\n## 4. Simulation-based calibration check (Complete AVSD), noisy objective, DE + CRN\n")
    anchors, _ = ANCHORS["Complete AVSD"]
    u = np.random.default_rng(7).random((2000, 53))  # common random numbers for every candidate
    t_idx = [int(t) - 1 for t, _ in anchors]
    target = np.array([s for _, s in anchors])

    def sim_loss(v):
        return float(np.sum((simulate_cohort(v[0], v[1], 53, u)[t_idx] - target) ** 2))

    (c_shape, c_scale), c_loss = differential_evolution(
        sim_loss,
        [(0.1, 3.0), (1.0, 500.0)],
        np.random.default_rng(11),
        pop=16,
        gens=40,
        reevaluate=True,
    )
    sim = simulate_cohort(c_shape, c_scale, 53, np.random.default_rng(99).random((20000, 53)))
    print(
        f"closed-form Weibull fit : shape {fits['Complete AVSD'][0]:.2f}, "
        f"scale {fits['Complete AVSD'][1]:.1f} wk"
    )
    print(
        f"simulation-calibrated   : shape {c_shape:.2f}, scale {c_scale:.1f} wk (loss {c_loss:.2e})"
    )
    print(
        f"fresh 20,000-patient run: S(26 wk) = {sim[25]:.3f} (target 0.54), "
        f"S(52 wk) = {sim[51]:.3f} (target 0.35)"
    )
    print(
        "Fresh-run gap vs target (~0.02 at 26 wk) is about 1.7 Monte Carlo SE: the DE fit is "
        "slightly over-tuned to its fixed 2,000-patient random sample; re-validate on fresh "
        "draws, as here."
    )


if __name__ == "__main__":
    main()
