#!/usr/bin/env python3
"""De-risk the A3a constant-ratio bridge.

Question: does hit_before_S(ideal_count_kernel, health={count>=tau_n}, ext={count=0},
horizon=tau_n, founder count=1) >= 1 - 4/9 = 5/9  hold, with margin, at the worst cases?

We simulate the CONSERVATIVE PROVABLE dynamics (a stochastic LOWER bound on the true kernel):
the keep-mass lemma `ideal_offspring_slot_weight_keep_mass_fixed_j_real_ge` gives, per offspring
slot, P(slot lands at level >= j) >= m/(4*mu) where m = current count. With lambda i.i.d. slots,
the next count stochastically dominates  Binomial(lambda, m/(4*mu))  (capped at mu by selection).
So if THIS lower-bound process clears the threshold with prob >= 5/9, the real kernel does too,
AND it is provable from the lemmas already in the repo.

tau_n = ceil(9 + 7 ln n). Worst case: mu = tau_n (health = full takeover, count>=mu),
lambda = 9*mu (critical ratio lambda/mu = 9, the hsel boundary). Horizon H = tau_n steps.
"""
from __future__ import annotations

import math
import numpy as np

TARGET = 1.0 - 4.0 / 9.0  # 5/9 ~= 0.5556
RNG = np.random.default_rng(20260616)


def tau_of_n(n: int) -> int:
    return math.ceil(9.0 + 7.0 * math.log(n))


def hit_prob(n: int, mu: int, ratio: float, trials: int = 200_000) -> dict:
    """Monte-Carlo P(reach count>=tau before count=0, within tau steps), founder count=1.

    Conservative model: count' = min(mu, Binomial(lambda, count/(4 mu))).
    """
    tau = tau_of_n(n)
    lam = int(round(ratio * mu))
    horizon = tau  # the bridge uses H = tau_n
    counts = np.ones(trials, dtype=np.int64)        # all start at founder count 1
    alive = np.ones(trials, dtype=bool)             # not yet absorbed
    hit = np.zeros(trials, dtype=bool)              # reached health
    ext = np.zeros(trials, dtype=bool)              # went extinct
    for _ in range(horizon):
        act = alive & ~hit & ~ext
        if not act.any():
            break
        m = counts[act]
        p = np.minimum(m / (4.0 * mu), 1.0)         # per-slot keep prob (provable lower bound)
        nxt = RNG.binomial(lam, p)                  # offspring slots landing >= j
        nxt = np.minimum(nxt, mu)                    # selection caps at mu
        counts_act = counts.copy()
        counts_act[act] = nxt
        counts = counts_act
        newext = act & (counts == 0)
        newhit = act & (counts >= tau)
        ext |= newext
        hit |= newhit
    p_hit = hit.mean()
    se = math.sqrt(p_hit * (1 - p_hit) / trials)
    return {"n": n, "tau": tau, "mu": mu, "lambda": lam, "ratio": round(lam / mu, 3),
            "horizon": tau, "p_hit": p_hit, "se": se,
            "margin": p_hit - TARGET, "pass": p_hit - 3 * se > TARGET}


def main() -> None:
    print(f"TARGET = 1 - 4/9 = {TARGET:.4f}\n")
    print(f"{'n':>5} {'tau':>4} {'mu':>5} {'lambda':>7} {'L/mu':>5} {'H':>4} "
          f"{'p_hit':>7} {'+-3se':>7} {'margin':>7} {'pass':>5}")
    print("-" * 70)
    rows = []
    # Worst case mu = tau (full takeover), critical ratio 9; plus mu=4*tau and ratio 9.
    for n in (2, 3, 5, 10, 100):
        tau = tau_of_n(n)
        for mu in (tau, 4 * tau):
            r = hit_prob(n, mu, 9.0)
            rows.append(r)
            print(f"{r['n']:>5} {r['tau']:>4} {r['mu']:>5} {r['lambda']:>7} {r['ratio']:>5} "
                  f"{r['horizon']:>4} {r['p_hit']:>7.4f} {3*r['se']:>7.4f} "
                  f"{r['margin']:>+7.4f} {str(r['pass']):>5}")
    print("\n-- sensitivity at n=2, mu=tau (the hardest), varying ratio --")
    for ratio in (9.0, 10.0, 12.0, 16.0):
        r = hit_prob(2, tau_of_n(2), ratio)
        print(f"  ratio {ratio:>4}: p_hit={r['p_hit']:.4f} margin={r['margin']:+.4f} "
              f"pass={r['pass']}")
    worst = min(rows, key=lambda r: r["margin"])
    print(f"\nWORST margin: n={worst['n']} mu={worst['mu']} -> p_hit={worst['p_hit']:.4f} "
          f"(target {TARGET:.4f}, margin {worst['margin']:+.4f})")
    print("ALL PASS (3-sigma above 5/9):", all(r["pass"] for r in rows))


if __name__ == "__main__":
    main()
