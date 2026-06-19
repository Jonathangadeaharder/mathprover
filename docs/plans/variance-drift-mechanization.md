# Mechanization Plan: Concentration Tail-Bound Analysis of Coevolutionary and Bandit Learning Algorithms

## Source

Paper: "Concentration Tail-Bound Analysis of Coevolutionary and Bandit Learning Algorithms" by Lehre & Lin (2024), University of Birmingham.
File: `/Users/jonathangadeaharder/Downloads/ea_papers_md/2405.04480v2.md` (1458 lines)

Lean library: `/Users/jonathangadeaharder/projects/lean-runtime-analysis/`
Mathlib: `v4.28.0` at `/Users/jonathangadeaharder/.cache/lean-runtime-analysis/lake/packages/mathlib/`

## Status

Design-only. No Lean files modified. Produces the implementation plan for mechanizing Theorems 1-5 (core drift theorems with exponential tail bounds) and Theorems 6-10 (applications: 2-SAT, Recolour, BILINEAR/RLS-PD, RWAB regret).

---

## Part 0: Paper Architecture

The paper's recurrent method for all five core theorems (1-5):

1. Define k-th hitting time `T_k = inf{t >= k | X_t in A}` (target set A depends on theorem)
2. Build variance-transformed process `Y_t` (polynomial in `X_t`, not exponential)
3. Build auxiliary super/sub-martingale `Z_t = Y_t +/- delta*t`
4. Show `E_t(Z_t - Z_{t+1}) >= 0` using the drift condition -> `Z_t` is (super/sub)martingale
5. Show `E(T) < infinity` via additive drift on `Y_t` (finiteness for OST)
6. Apply Lemma 1 (geometric integral) to discharge OST condition (4): bounded conditional increments
7. Apply Extended Optional Stopping Time Theorem (Theorem 12) to `Z_t` at stopping time `T_k`:
   `E_k(Z_k - Z_{T_k}) >= 0` (supermartingale) or `E_k(Z_{T_k} - Z_k) >= 0` (submartingale)
8. Rearrange to get `E_k(Y_k - Y_{T_k}) >= delta * E_k(T_k - k)`
9. Bound `E_k(Y_{T_k})` using the target-set condition + Jensen's inequality
10. Set `theta_k = E_k(Y_k - Y_{T_k}) / delta` in `[0, b^2/delta]` (or `n/epsilon` for Thm 5)
11. Take `theta = e*b^2/delta` (or `e*n/epsilon`), apply Markov: `Pr(T_k - k > theta | F_k) <= 1/e`
12. Intersection-decomposition recurrence: `{T_0 > (k+1)*theta} = {T_0 > k*theta} cap {T_{k*theta} - k*theta > theta}`
13. Tower property + conditional bound -> `Pr(T_0 > (k+1)*theta) <= Pr(T_0 > k*theta) * e^{-1}`
14. By induction: `Pr(T_0 >= tau) <= e^{-tau/theta}`

Steps 1-11 are per-theorem (different `Y_t`, different drift conditions). Steps 12-14 are identical across all theorems (the recurrence engine). This motivates factoring the recurrence into a reusable lemma.

---

## Part 1: Dependency Graph

```
Lemma 1 (geometric integral)
  |
  v
Theorem 1 (variance overcomes negative drift) -- core engine
  |
  +-> Theorem 2 (standard variance drift, Y_t = n - X_t)
  |     |
  |     +-> Corollary 3 (fixed step size, C1 replaces C1*)
  |           |
  |           +-> Theorem 6 (Random 2-SAT)
  |
  +-> Theorem 4 (zero drift, Y_t = X_t*(n - X_t))
  |     |
  |     +-> Theorem 7 (Recolouring)
  |
  +-> Theorem 5 (additive drift, Y_t = X_t, submartingale)
        |
        +-> Theorem 8 (RLS-PD on BILINEAR, phase 1)
        +-> Theorem 10 (RWAB regret, R_1..R_4 components)

Theorem 1 (direct application)
  |
  +-> Theorem 8 (RLS-PD on BILINEAR, phase 2)
  +-> Theorem 9 (RLS-PD forgets NE)

Theorem 5 + MultiplicativeChernoff + Lemma 3 (geometric domination)
  |
  +-> Theorem 10 (RWAB regret)
```

Implementation order follows the graph top-down.

---

## Part 2: Existing Infrastructure (Reuse Analysis)

### 2.1 Files and their exports

| File | Key declarations | Reuse for |
|---|---|---|
| `DriftTheorems/AdditiveDrift.lean` (197 lines) | `telescoping_sum`, `min_eq_sum_indicator`, `measurableSet_F_tau_gt`, `integrable_stopped_diff`, `additive_drift_theorem` | Steps 1-5 (stopping time helpers, finiteness of E[T] via additive drift). The `additive_drift_theorem` itself proves `E[tau] <= X0/delta` which is needed to show `E(T) < infinity` before applying OST. |
| `DriftTheorems/NegativeDrift.lean` (595 lines) | `exp_secant_bound`, `cosh_sub_r_sinh_le_one`, `negative_drift_theorem`, `negative_drift_tail_bound`, `negative_drift_expected_hitting_time`, `measurableSet_min_tau_eq`, `integrable_exp_stopped` | Proof skeleton template (OST + telescoping + indicator/Markov). `measurableSet_min_tau_eq` and the stopped-value integrability pattern are reusable. `exp_secant_bound` is NOT reusable (exponential-specific). |
| `DriftTheorems/MultiplicativeDrift.lean` (148 lines) | `multiplicative_drift_theorem` | Pattern for potential-function transform + `condExp_stronglyMeasurable_mul_of_bound` pullout. Not directly reused but validates the transform approach. |
| `DriftTheorems/ArtificialFitnessLevels.lean` (388 lines) | `FitnessLevel`, `ElitistLevelChain`, `hitTime_le_sum`, `oneMax` | Application wrappers for Theorems 6, 7 (fitness-level structure for 2-SAT agreement count, Recolour matching colour count). |
| `Hoeffding.lean` | `hoeffding_inequality_iid_bounded`, `hoeffding_batch_bound` | Theorem 10 (RWAB Chernoff step). |
| `HoeffdingBridge.lean` | `hoeffding_per_offspring_bound`, `hoeffding_two_sided_bound_fin` | Theorem 10 auxiliary. |
| `MultiplicativeChernoff.lean` | `chernoff_lower_tail_explicit`, `m9pre_binomial_lower_tail`, `m9pre_finset_markov_exp`, `boolToReal` helpers | Theorem 10 (Binomial concentration of #CHALLENGE `Z ~ Bin(T, L/T)`). `m9pre_finset_markov_exp` provides Markov-inequality engine. |
| `CoEALevelBased.lean` (399 lines) | `ZeroSumGame`, `MixedStrategy`, `is_nash_equilibrium`, `CoEAState`, `CoEALevelPartition`, `negative_drift_theorem` (local) | Theorems 8, 9 (CoEA domain). Needs extension: pairwise dominance, BILINEAR, Manhattan distance, RLS-PD kernel. |
| `CoevolutionDeepBounds.lean` (179 lines) | `hoeffding_batch_sample_complexity`, `psi_expansion`, `discrete_drift_cancellation_gap`, `sbm_transition_prob` | Theorems 8, 9 algebra (variance-transformed drift cancellation). |

### 2.2 Idiom (from `AdditiveDrift.lean`)

All DriftTheorems files use this setup:
```lean
variable {Ω : Type*} [m0 : MeasureSpace Ω]
variable {F : Filtration ℕ m0.toMeasurableSpace}
-- Probability measure added per-theorem:
-- [IsProbabilityMeasure (ℙ : Measure Ω)]

-- Stopping times are ℕ-valued:
-- τ : Ω → ℕ
-- h_stop : ∀ n, MeasurableSet[F n] {ω | τ ω ≤ n}

-- Conditional expectation:
-- (ℙ[fun ω' => X t ω' - X (t + 1) ω' | ↑(F t)]) ω

-- Adaptedness:
-- Adapted F X  (i.e., ∀ t, Measurable[F t] (X t))
```

This is a CUSTOM idiom, NOT Mathlib's `IsStoppingTime` / `Submartingale` / `stoppedValue` API (which uses `ℕ∞`-valued stopping times). All new code MUST follow the existing custom idiom for consistency and to reuse the helper lemmas.

### 2.3 Key reusable helper lemmas (exact signatures)

From `AdditiveDrift.lean`:
```lean
lemma telescoping_sum (X : ℕ → Ω → ℝ) (τ : Ω → ℕ) (N : ℕ) (ω : Ω) :
    ∑ t ∈ Finset.range N,
      Set.indicator {ω' | t < τ ω'} (fun ω' => X t ω' - X (t + 1) ω') ω =
      X 0 ω - X (min N (τ ω)) ω

lemma min_eq_sum_indicator (τ : Ω → ℕ) (N : ℕ) (ω : Ω) :
    (↑(min N (τ ω)) : ℝ) = ∑ t ∈ Finset.range N,
      Set.indicator {ω' | t < τ ω'} (fun _ => (1 : ℝ)) ω

lemma measurableSet_F_tau_gt (τ : Ω → ℕ) (t : ℕ)
    (h_stop : ∀ n, MeasurableSet[F n] {ω | τ ω ≤ n}) :
    MeasurableSet[F t] {ω : Ω | t < τ ω}

lemma integrable_stopped_diff (X : ℕ → Ω → ℝ) (τ : Ω → ℕ) (N : ℕ)
    (h_stop : ∀ n, MeasurableSet[F n] {ω | τ ω ≤ n})
    (h_integrable : ∀ t, Integrable (X t) ℙ) :
    Integrable (fun ω => X 0 ω - X (min N (τ ω)) ω) ℙ

theorem additive_drift_theorem
    [IsProbabilityMeasure (ℙ : Measure Ω)]
    (X : ℕ → Ω → ℝ) (τ : Ω → ℕ)
    (_h_adapted : Adapted F X)
    (h_stop : ∀ n, MeasurableSet[F n] {ω | τ ω ≤ n})
    (δ : ℝ) (h_delta : δ > 0)
    (X0 : ℝ) (hX0 : ∀ ω, X 0 ω = X0)
    (h_positive : ∀ t ω, 0 ≤ X t ω)
    (h_integrable_all : ∀ t, Integrable (X t) ℙ)
    (h_tau_integrable : Integrable (fun ω => (τ ω : ℝ)) ℙ)
    (h_drift : ∀ t, ∀ᵐ ω ∂(ℙ : Measure Ω), τ ω > t →
      (ℙ[fun ω' => X t ω' - X (t + 1) ω' | ↑(F t)]) ω ≥ δ) :
    ∫ ω, (τ ω : ℝ) ∂(ℙ : Measure Ω) ≤ X0 / δ
```

From `NegativeDrift.lean`:
```lean
lemma measurableSet_min_tau_eq (τ : Ω → ℕ) (N t : ℕ)
    (h_stop : ∀ n, MeasurableSet[F n] {ω | τ ω ≤ n}) :
    MeasurableSet {ω : Ω | min N (τ ω) = t}

-- condExp algebra used heavily in NegativeDrift:
-- condExp_mono, condExp_add, condExp_sub, condExp_smul,
-- condExp_of_stronglyMeasurable, condExp_stronglyMeasurable_mul_of_bound,
-- setIntegral_condExp, setIntegral_mono_on_ae
```

### 2.4 Mathlib OptionalStopping API (available but NOT used by existing code)

Mathlib's `Mathlib.Probability.Martingale.OptionalStopping` provides:
```lean
theorem Submartingale.expected_stoppedValue_mono
    (hf : Submartingale f 𝒢 μ) (hτ : IsStoppingTime 𝒢 τ) (hπ : IsStoppingTime 𝒢 π)
    (hle : τ ≤ π) {N : ℕ} (hbdd : ∀ ω, π ω ≤ N) :
    μ[stoppedValue f τ] ≤ μ[stoppedValue f π]
```

This uses `ℕ∞`-valued stopping times and requires boundedness. The existing code avoids this API entirely, using the telescoping-sum + condExp approach instead. The new code should follow the existing idiom.

The paper's Extended OST (Theorem 12) has four conditions; Mathlib's `expected_stoppedValue_mono` only covers condition (1) (bounded T). Conditions (2)-(4) are not in Mathlib. The existing `AdditiveDrift.lean` works around this by proving the expectation bound directly via telescoping + condExp monotonicity, which is equivalent to OST for the additive drift case. The same approach extends to the variance drift case.

---

## Part 3: New Files and Import Graph

### 3.1 New files

| File | Contents | Imports |
|---|---|---|
| `DriftTheorems/VarianceDrift.lean` | Lemma 1, Theorem 1, recurrence engine lemma | `DriftTheorems.AdditiveDrift`, `Mathlib.Analysis.SpecialFunctions.Exp`, `Mathlib.Analysis.Calculus.MeanValue` |
| `DriftTheorems/VarianceDriftCorollaries.lean` | Theorems 2, 3, 4, 5 | `DriftTheorems.VarianceDrift`, `DriftTheorems.AdditiveDrift` |
| `DriftTheorems/VarianceDriftApplications.lean` | Theorems 6, 7 (2-SAT, Recolour) | `DriftTheorems.VarianceDriftCorollaries`, `DriftTheorems.ArtificialFitnessLevels` |
| `CoEABilinear.lean` | Theorems 8, 9 (BILINEAR, RLS-PD) | `CoEALevelBased`, `DriftTheorems.VarianceDrift`, `DriftTheorems.VarianceDriftCorollaries`, `CoevolutionDeepBounds` |
| `RWABRegret.lean` | Theorem 10 + Lemma 3 (geometric domination) | `DriftTheorems.VarianceDriftCorollaries`, `MultiplicativeChernoff`, `Hoeffding` |

### 3.2 Lakefile update

Add to `roots := #[...]` in `lakefile.lean` (line 16):
```
`DriftTheorems.VarianceDrift,
`DriftTheorems.VarianceDriftCorollaries,
`DriftTheorems.VarianceDriftApplications,
`CoEABilinear,
`RWABRegret,
```

### 3.3 Import graph (no cycles)

```
AdditiveDrift (existing)
  |
  v
VarianceDrift (new) --- imports AdditiveDrift only
  |
  v
VarianceDriftCorollaries (new) --- imports VarianceDrift + AdditiveDrift
  |
  v
VarianceDriftApplications (new) --- imports VarianceDriftCorollaries + ArtificialFitnessLevels

CoEALevelBased (existing)
  |
  v
CoEABilinear (new) --- imports CoEALevelBased + VarianceDrift + VarianceDriftCorollaries + CoevolutionDeepBounds

MultiplicativeChernoff (existing)
  |
  v
RWABRegret (new) --- imports VarianceDriftCorollaries + MultiplicativeChernoff + Hoeffding
```

No reverse edges. No cycles.

---

## Part 4: Exact Lean Signatures and Proof Skeletons

### 4.1 Lemma 1: Bounded conditional increments from geometric tail

**Paper statement:** If `E[1_{T>t} * 1_{|X_t - X_{t+1}| >= j} | F_t] <= r / (1+eta)^j` for all `j >= 0`, then `E[|X_{t+1} - X_t| * 1_{T>t} | F_t] <= c` where `c = r / log(1+eta)`.

**Proof:** `E[|X_{t+1} - X_t| | F_t] = integral_0^infty Pr(|X_{t+1} - X_t| >= j | F_t) dj <= integral_0^infty r/(1+eta)^j dj = r / log(1+eta)`.

**Lean signature:**
```lean
/-- Lemma 1: Geometric step-size tail implies bounded conditional expected increments.
    If the conditional tail of the step size decays geometrically, then the
    conditional expectation of the step size (on {T > t}) is bounded by r / log(1+eta). -/
lemma bounded_conditional_increments
    [IsProbabilityMeasure (ℙ : Measure Ω)]
    (X : ℕ → Ω → ℝ) (τ : Ω → ℕ)
    (h_stop : ∀ n, MeasurableSet[F n] {ω | τ ω ≤ n})
    (r η : ℝ) (h_r : 0 < r) (h_η : 0 < η)
    (h_tail : ∀ t j, 0 ≤ j →
      ∀ᵐ ω ∂(ℙ : Measure Ω), τ ω > t →
        (ℙ[fun ω' => Set.indicator {ω' | |X (t+1) ω' - X t ω'| ≥ j}
          (fun _ => (1:ℝ)) ω' | ↑(F t)]) ω ≤ r / (1 + η)^j) :
    ∃ c : ℝ, 0 < c ∧
      ∀ t, ∀ᵐ ω ∂(ℙ : Measure Ω), τ ω > t →
        (ℙ[fun ω' => |X (t+1) ω' - X t ω'| | ↑(F t)]) ω ≤ c :=
  sorry
```

**Proof skeleton:**
1. Set `c = r / Real.log (1 + η)`.
2. Key integral identity: `E[|ΔX| | F_t] = ∫₀^∞ Pr(|ΔX| ≥ j | F_t) dj` (layer-cake / tail-sum formula for conditional expectation). This needs a Mathlib lemma — check `MeasureTheory.integral_eq_integral_measure_lintegral_le` or similar. May need to prove a conditional version.
3. Upper bound the integrand: `Pr(|ΔX| ≥ j | F_t) ≤ r / (1+η)^j` from `h_tail`.
4. Integrate: `∫₀^∞ r/(1+η)^j dj = r * [-1/log(1+η) * (1+η)^{-j}]₀^∞ = r / log(1+η)`.
5. The integral `∫₀^∞ (1+η)^{-j} dj = 1/log(1+η)` is a standard real integral. Use `Real.exp` substitution: `(1+η)^j = Real.exp(j * Real.log(1+η))`, so `∫₀^∞ Real.exp(-j * log(1+η)) dj = 1/log(1+η)`.

**Difficulty:** Medium. The main challenge is the conditional layer-cake formula. Mathlib has `MeasureTheory.lintegral_eq_lintegral_measure` but for the conditional version we may need to derive it from `condExp` properties. Alternative: avoid the integral entirely by using a discrete sum approximation — sum the tail probabilities over integer j, getting a geometric series `Σ_{j=0}^∞ r/(1+η)^j = r * (1+η)/η`. This gives a weaker constant `c = r*(1+η)/η` but avoids the continuous integral. The paper uses the continuous integral, but the discrete bound suffices for OST condition (4).

**Discrete alternative (simpler, recommended):**
```lean
/-- Lemma 1 (discrete version): Geometric tail implies bounded conditional increments
    via discrete sum over integer thresholds. Gives c = r * (1+η) / η. -/
lemma bounded_conditional_increments_discrete
    [IsProbabilityMeasure (ℙ : Measure Ω)]
    (X : ℕ → Ω → ℝ) (τ : Ω → ℕ)
    (h_stop : ∀ n, MeasurableSet[F n] {ω | τ ω ≤ n})
    (r η : ℝ) (h_r : 0 < r) (h_η : 0 < η)
    (h_tail : ∀ t j : ℕ, 0 < j →
      ∀ᵐ ω ∂(ℙ : Measure Ω), τ ω > t →
        (ℙ[fun ω' => Set.indicator {ω' | (j : ℝ) ≤ |X (t+1) ω' - X t ω'|}
          (fun _ => (1:ℝ)) ω' | ↑(F t)]) ω ≤ r / (1 + η)^j) :
    ∃ c : ℝ, 0 < c ∧
      ∀ t, ∀ᵐ ω ∂(ℙ : Measure Ω), τ ω > t →
        (ℙ[fun ω' => |X (t+1) ω' - X t ω'| | ↑(F t)]) ω ≤ c :=
  sorry
```

Proof: `E[|ΔX| | F_t] ≤ Σ_{j=0}^∞ Pr(|ΔX| ≥ j | F_t) ≤ Σ_{j=0}^∞ r/(1+η)^j = r * (1+η)/η`. The last equality is the geometric series sum `1/(1 - 1/(1+η)) = (1+η)/η`.

---

### 4.2 Theorem 1: Variance overcomes negative drift (main engine)

**Paper statement:** Given (A1) `E_t[(ΔX)^2 - 2*ΔX*(b - X_t)] >= delta`, (A2) `0 <= X_t <= b`, and geometric step-size tail, then `Pr(T > τ) <= exp(-τ * delta / (e * b^2))` where `T = inf{t >= 0 | X_t <= 0}`.

**Lean signature:**
```lean
/-- Theorem 1: Variance overcomes negative drift with exponential tail bound.
    Under conditions (A1), (A2), and geometric step-size tail,
    Pr(T > τ) ≤ exp(-τ * δ / (e * b²)). -/
theorem variance_drift_tail_bound
    [IsProbabilityMeasure (ℙ : Measure Ω)]
    (X : ℕ → Ω → ℝ) (τ : Ω → ℕ)
    (h_adapted : Adapted F X)
    (h_stop : ∀ n, MeasurableSet[F n] {ω | τ ω ≤ n})
    (b δ : ℝ) (h_delta : 0 < δ) (h_b : 0 < b)
    (h_bounded : ∀ t ω, τ ω > t → 0 ≤ X t ω ∧ X t ω ≤ b)
    (h_integrable_all : ∀ t, Integrable (X t) ℙ)
    (h_a1 : ∀ t, ∀ᵐ ω ∂(ℙ : Measure Ω), τ ω > t →
      (ℙ[fun ω' =>
        (X (t+1) ω' - X t ω')^2 - 2 * (X (t+1) ω' - X t ω') * (b - X t ω')
        | ↑(F t)]) ω ≥ δ)
    (r η : ℝ) (h_r : 0 < r) (h_η : 0 < η)
    (h_step_tail : ∀ t j : ℕ, 0 < j →
      ∀ᵐ ω ∂(ℙ : Measure Ω), τ ω > t →
        (ℙ[fun ω' => Set.indicator {ω' | (j : ℝ) ≤ |X (t+1) ω' - X t ω'|}
          (fun _ => (1:ℝ)) ω' | ↑(F t)]) ω ≤ r / (1 + η)^j) :
    ∀ time : ℕ, (ℙ {ω | τ ω > time}).toReal ≤
      Real.exp (-(time : ℝ) * δ / (Real.e * b^2)) :=
  sorry
```

**Proof skeleton (14 steps mapping to paper):**

**Step 1: Define the variance-transformed process Y_t.**
```lean
let Y := fun (t : ℕ) (ω : Ω) => b^2 - (b - X t ω)^2
```
Show `Y_t` is adapted: `Measurable[F t] (Y t)` via `h_adapted t` + ring operations.
Show `Y_t >= 0` on `{tau > t}`: from `(A2)`, `0 <= b - X_t <= b`, so `(b - X_t)^2 <= b^2`, so `Y_t = b^2 - (b - X_t)^2 >= 0`.
Show `Y_t <= b^2`: since `(b - X_t)^2 >= 0`.

**Step 2: Derive the key drift inequality E_t(Y_t - Y_{t+1}) >= delta.**

This is the core mathematical step. Expand:
```
Y_t - Y_{t+1} = (b^2 - (b - X_t)^2) - (b^2 - (b - X_{t+1})^2)
             = (b - X_{t+1})^2 - (b - X_t)^2
             = [(b - X_t) - (X_{t+1} - X_t)]^2 - (b - X_t)^2
             = (X_{t+1} - X_t)^2 - 2*(X_{t+1} - X_t)*(b - X_t)
```

So `Y_t - Y_{t+1} = (ΔX)^2 - 2*ΔX*(b - X_t)`, and condition (A1) says `E_t[(ΔX)^2 - 2*ΔX*(b - X_t)] >= delta`, which is exactly `E_t[Y_t - Y_{t+1}] >= delta`.

In Lean, prove the pointwise identity `Y t ω - Y (t+1) ω = (X (t+1) ω - X t ω)^2 - 2 * (X (t+1) ω - X t ω) * (b - X t ω)` by `ring`, then transfer to conditional expectation via `condExp_congr` (ae equality preservation).

**Step 3: Define the supermartingale Z_t = Y_t + delta*t.**
```lean
let Z := fun (t : ℕ) (ω : Ω) => Y t ω + δ * t
```
Show `E_t(Z_t - Z_{t+1}) = E_t(Y_t - Y_{t+1} - delta) >= delta - delta = 0` using Step 2.
So `Z_t` is a supermartingale: `E_t[Z_{t+1} | F_t] <= Z_t`.

In Lean: `condExp_sub` + `condExp_const` + the drift from Step 2.

**Step 4: Show E(T) < infinity via additive drift on Y_t.**

`Y_t >= 0` (from Step 1) and `E_t(Y_t - Y_{t+1}) >= delta` (from Step 2). By `additive_drift_theorem` applied to `Y_t` with stopping time `tau_Y = inf{t | Y_t <= 0}` (equivalent to `tau` since `Y_t <= 0 iff X_t <= 0`), we get `E[tau_Y] <= Y_0 / delta < infinity`.

In Lean: apply `additive_drift_theorem` to `Y` with `X0 = b^2 - (b - X_0)^2`. Need `h_positive : forall t omega, 0 <= Y t omega` — holds on all of Omega since `(b - X_t)^2 <= b^2` when `0 <= X_t <= b`, but we only know this on `{tau > t}`. Need to handle the post-stopping region. The existing `additive_drift_theorem` requires `forall t omega, 0 <= X t omega` unconditionally. We may need to extend `Y_t` to be 0 after the stopping time, or prove a version that only requires nonnegativity on `{tau > t}`.

**Risk:** The unconditional nonnegativity requirement in `additive_drift_theorem` is a potential blocker. Mitigation: define `Y'_t = Y_{min t tau}` (stopped process) which is nonneg everywhere, apply additive drift to `Y'`.

**Step 5: Apply Lemma 1 to get bounded conditional increments.**

From `h_step_tail` and `bounded_conditional_increments_discrete`, get `∃ c, E_t[|ΔX| * 1_{tau > t} | F_t] <= c`. This discharges OST condition (4).

**Step 6: Apply Extended OST to Z_t at T_k.**

The paper applies Theorem 12 (Extended OST) to get `E_k(Z_k - Z_{T_k}) >= 0`. In the existing idiom, this is proved directly via telescoping + condExp, as in `AdditiveDrift.lean` lines 99-154 and `NegativeDrift.lean` lines 232-328.

The pattern: `E[Z_0 - Z_{min N tau}] = sum_t E[1_{t < tau} * (Z_t - Z_{t+1})] = sum_t integral over {t < tau} of condExp[Z_t - Z_{t+1} | F_t] >= 0` since each summand is nonneg (supermartingale property on `{tau > t}`).

For the conditional version (conditioned on `F_k`), we need the stopped-at-k version: define `T_k = inf{t >= k | X_t <= 0}` and work with the process starting from time k.

**Step 7: Rearrange to E_k(Y_k - Y_{T_k}) >= delta * E_k(T_k - k).**

From `E_k(Z_k - Z_{T_k}) >= 0`:
```
E_k(Y_k + delta*k - Y_{T_k} - delta*T_k) >= 0
E_k(Y_k - Y_{T_k}) >= delta * E_k(T_k - k)
```

**Step 8: Bound E_k(Y_{T_k}) using Jensen.**

`0 <= E_k(Y_{T_k}) = E_k(b^2 - (b - X_{T_k})^2) = b^2 - E_k((b - X_{T_k})^2)`
`<= b^2 - (E_k(b - X_{T_k}))^2` (Jensen: `E[f^2] >= (E[f])^2` for convex `x -> x^2`)
`<= b^2 - (b - X_k)^2` (from OST on the submartingale `X_t`... or directly from the supermartingale property)

The paper says "Using Optional Stopping Time Theorem (Theorem 12) on stopping time T_k gives <= b^2 - (b - X_k)^2". This is the OST applied to get `E_k(X_{T_k}) >= X_k` (wait, that doesn't make sense for a process with negative drift). Actually, looking more carefully, the paper uses `Y_t` which is a supermartingale, so `E_k(Y_{T_k}) <= Y_k = b^2 - (b - X_k)^2`. Combined with `E_k(Y_{T_k}) >= 0` (from `Y_{T_k} >= 0` on the boundary), we get `E_k(Y_{T_k}) in [0, b^2 - (b - X_k)^2]`.

In Lean: Jensen's inequality `E[f^2] >= (E[f])^2` is in Mathlib as `MeasureTheory.variance_nonneg` or can be derived from `convexOn` + Jensen. The specific form: `∫ (b - X_{T_k})^2 >= (∫ (b - X_{T_k}))^2` when the measure is a probability measure. Check `MeasureTheory.integral_sq_le_integral_sq` or ` JenningsConvex`.

**Step 9: Set theta_k and derive E_k(T_k - k | F_k) <= theta_k.**

`theta_k = E_k(Y_k - Y_{T_k}) / delta in [0, b^2/delta]`
`E_k(T_k - k | F_k) <= theta_k` (from Step 7 rearranged)

**Step 10: Markov inequality -> Pr(T_k - k > theta | F_k) <= 1/e.**

Set `theta = e * b^2 / delta`. Then `theta_k <= b^2/delta <= theta/e`. Markov:
`Pr(T_k - k > theta | F_k) <= E_k(T_k - k | F_k) / theta <= theta_k / theta <= (b^2/delta) / (e*b^2/delta) = 1/e`

In Lean: `Real.e` is available. The Markov inequality `Pr(X > a) <= E[X]/a` for nonneg X: use `MeasureTheory.markov_inequality` or the pattern from `NegativeDrift.lean` lines 485-493.

**Step 11: Intersection-decomposition recurrence.**

This is the KEY novel step. Define:
```lean
-- T_k as a function of k: the k-th hitting time
-- In Lean, parameterize by k : ℕ
-- T_k ω = inf{t >= k | X t ω <= 0}
```

The recurrence: for `theta_n = Real.ceil (Real.e * b^2 / delta)` (natural number approximation of theta):
```
{T_0 > (k+1)*theta_n} = {T_0 > k*theta_n} ∩ {T_{k*theta_n} - k*theta_n > theta_n}
```

Proof of set equality: `T_0 > (k+1)*theta_n` means the process hasn't hit 0 by time `(k+1)*theta_n`. This is equivalent to: (hasn't hit 0 by time `k*theta_n`) AND (starting from time `k*theta_n`, hasn't hit 0 within `theta_n` more steps).

In Lean, this requires careful handling of the k-th hitting time definition. Define:
```lean
noncomputable def kthHitTime (X : ℕ → Ω → ℝ) (k : ℕ) (ω : Ω) : ℕ :=
  Nat.find (fun t => k ≤ t ∧ X t ω ≤ 0)  -- or Inf version
```

Need to prove `{T_0 > (k+1)*n} = {T_0 > k*n} ∩ {T_{k*n} - k*n > n}` as sets.

**Step 12: Tower property + conditional bound.**
```
Pr(T_0 > (k+1)*theta_n) = E[1_{T_0 > k*theta_n} * 1_{T_{k*theta_n} - k*theta_n > theta_n}]
= E[1_{T_0 > k*theta_n} * E[1_{T_{k*theta_n} - k*theta_n > theta_n} | F_{k*theta_n}]]
<= E[1_{T_0 > k*theta_n} * (1/e)]
= Pr(T_0 > k*theta_n) / e
```

In Lean: the tower property `E[E[X | G]] = E[X]` and the "taking out what is known" property `E[1_A * E[X | G]] = E[1_A * X]` when `A in G`. These are `condExp_condExpProd` and `condExp_stronglyMeasurable_mul` / `setIntegral_condExp` in the existing codebase.

Key: `{T_0 > k*theta_n} in F_{k*theta_n}` (since T_0 is a stopping time, the event `{T_0 > n}` is `F_n`-measurable — this is `measurableSet_F_tau_gt` from `AdditiveDrift.lean`).

**Step 13: Induction.**
By induction on k: `Pr(T_0 > k*theta_n) <= (1/e)^k = e^{-k}`.

**Step 14: Conclude for general tau.**
For `tau : ℕ`, let `k = tau / theta_n` (integer division). Then `k * theta_n <= tau < (k+1) * theta_n`, so `{tau < T_0} subseteq {k*theta_n < T_0}` (approximately — need to check the direction). Then `Pr(tau < T_0) <= Pr(k*theta_n < T_0) <= e^{-k}`. And `e^{-k} <= e^{-(tau/theta_n - 1)} = e * e^{-tau/theta_n} <= e * e^{-tau*delta/(e*b^2)}`.

The exact form `Pr(T > tau) <= exp(-tau * delta / (e * b^2))` requires `theta_n = Real.ceil(e * b^2 / delta)` and careful rounding. The paper is slightly loose here; the Lean version should state either:
- (a) `Pr(T > k * theta_n) <= exp(-k)` for all `k : ℕ` with `theta_n = ceil(e*b^2/delta)`, or
- (b) `Pr(T > tau) <= exp(-(tau : ℝ) * delta / (e * b^2))` with an appropriate rounding argument.

Option (a) is cleaner and more faithful to the proof structure. Option (b) requires an extra rounding step. Recommend (a) as the main statement, with (b) as a corollary.

---

### 4.3 Theorem 2: Standard variance drift

**Paper:** (C1*) geometric step tail, (C2) `E_t(ΔX) >= 0`, (C3) `E_t((ΔX)^2) >= delta`. `T = inf{t | X_t >= b}`. Then `E(T) <= (b^2 - X_0^2)/delta` and `Pr(T >= tau) <= exp(-tau*delta/(e*b^2))`.

**Proof:** Substitute `Y_t = b - X_t` (note: paper says `Y_t = n - X_t` but in the general theorem `b` plays the role of `n`). Then `Y_t in [0, b]`, and:
- `E_t(Y_t - Y_{t+1}) = E_t(X_{t+1} - X_t) >= 0` from (C2)
- `E_t((Y_t - Y_{t+1})^2) = E_t((ΔX)^2) >= delta` from (C3)
- `E_t((ΔY)^2 - 2*ΔY*(b - Y_t)) = E_t((ΔX)^2 + 2*ΔX*X_t) >= E_t((ΔX)^2) - 2*b*|E_t(ΔX)|`

Wait, let me re-derive. `Y_t = b - X_t`, so `ΔY = Y_{t+1} - Y_t = -(ΔX)`. Then:
```
Y_t - Y_{t+1} = ΔX
(Y_t - Y_{t+1})^2 = (ΔX)^2
b - Y_t = b - (b - X_t) = X_t
```
So the (A1) condition for Y_t becomes:
```
E_t[(ΔY)^2 - 2*ΔY*(b - Y_t)] = E_t[(ΔX)^2 - 2*(-ΔX)*X_t] = E_t[(ΔX)^2 + 2*ΔX*X_t]
```

Hmm, this doesn't directly simplify to (C2)+(C3). Let me re-read the paper.

The paper says (lines 866-874):
```
Y_t = n - X_t, T = {t | X_t >= n} = {t | Y_t <= 0}
E_t(Y_t - Y_{t+1}) = E_t(X_{t+1} - X_t) >= 0  [from C2]
E_t((Y_t - Y_{t+1})^2) = E_t((X_{t+1} - X_t)^2) >= delta  [from C3]
```
And then says "This implies that Y_t satisfies (A1) in Theorem 1."

The connection: (A1) is `E_t[(ΔX)^2 - 2*ΔX*(b - X_t)] >= delta`. For `Y_t = b - X_t`:
```
ΔY = -(ΔX), b - Y_t = X_t
(A1) for Y: E_t[(ΔY)^2 - 2*ΔY*(b - Y_t)] = E_t[(ΔX)^2 + 2*ΔX*X_t]
```

Now, `(ΔX)^2 + 2*ΔX*X_t = (ΔX)^2 + 2*X_t*E_t[ΔX] + 2*ΔX*X_t - 2*X_t*E_t[ΔX]`

Actually, let me think differently. The paper says `E_t(Y_t - Y_{t+1}) >= 0` and `E_t((Y_t - Y_{t+1})^2) >= delta` imply (A1). Let's verify:

(A1) for Y: `E_t[(Y_t - Y_{t+1})^2 - 2*(Y_t - Y_{t+1})*(b - Y_t)] >= delta`

Note `Y_t - Y_{t+1} = ΔX` (positive drift). So:
```
E_t[(ΔX)^2 - 2*ΔX*(b - Y_t)] = E_t[(ΔX)^2] - 2*E_t[ΔX*(b - Y_t)]
```

Hmm, but `b - Y_t = X_t`, so `E_t[ΔX * X_t]` doesn't simplify directly from (C2) and (C3).

Wait, I think the key insight is different. Let me re-read more carefully. The paper says at line 870-874:
```
E_t(Y_t - Y_{t+1}) >= 0
E_t((Y_t - Y_{t+1})^2) >= delta
```
And "This implies that Y_t satisfies (A1) in Theorem 1."

The (A1) condition is: `E_t[(X_{t+1} - X_t)^2 - 2*(X_{t+1} - X_t)*(b - X_t)] >= delta`.

For Y_t with `b = n` (the bound on Y_t), (A1) becomes:
```
E_t[(Y_{t+1} - Y_t)^2 - 2*(Y_{t+1} - Y_t)*(n - Y_t)] >= delta
```

Now `Y_{t+1} - Y_t = -(X_{t+1} - X_t) = -ΔX`, so `(Y_{t+1} - Y_t)^2 = (ΔX)^2`.
And `n - Y_t = n - (n - X_t) = X_t`.
So (A1) for Y becomes: `E_t[(ΔX)^2 - 2*(-ΔX)*X_t] = E_t[(ΔX)^2 + 2*ΔX*X_t]`.

For this to be `>= delta`, we need `E_t[(ΔX)^2 + 2*ΔX*X_t] >= delta`.

Now, `E_t[(ΔX)^2] >= delta` (C3) and `E_t[ΔX] >= 0` (C2). But `E_t[ΔX*X_t]` is not directly bounded.

Actually wait. Let me re-read the paper's proof of Theorem 2 more carefully. Lines 866-879:

"Let us define Y_t = n - X_t and T = {t >= 0 | X_t >= n} = {t >= 0 | Y_t <= 0}. So from (C2), (C3) we have

E_t(Y_t - Y_{t+1}) >= 0
E_t((Y_t - Y_{t+1})^2) >= delta

This implies that Y_t satisfies (A1) in Theorem 1."

Hmm, but (A1) is a specific condition, not just these two separately. Let me think about why these two imply (A1).

Actually, I think the argument is:
```
E_t[(ΔY)^2 - 2*ΔY*(b - Y_t)]
```
where `ΔY = Y_{t+1} - Y_t = -ΔX`. And `Y_t - Y_{t+1} = ΔX`. So the paper is using `Y_t - Y_{t+1}` (not `Y_{t+1} - Y_t`) in the drift.

Let me re-derive with `Y_t - Y_{t+1} = ΔX`:
```
(A1): E_t[(Y_t - Y_{t+1})^2 - 2*(Y_t - Y_{t+1})*(b - Y_t)] >= delta
= E_t[(ΔX)^2 - 2*ΔX*X_t]
```

For this to hold from (C2)+(C3), we need: `E_t[(ΔX)^2 - 2*ΔX*X_t] >= delta`.

We know `E_t[(ΔX)^2] >= delta` and `E_t[ΔX] >= 0`. But `E_t[ΔX*X_t]` involves the product of the increment and the current state.

Hmm, I think the paper might be making an implicit assumption or using a different formulation of (A1). Let me re-read the paper's definition of (A1) more carefully.

Looking at line 765-769:
```
(A1) there exist δ > 0 such that for all t < T,
     E_t[(X_{t+1} - X_t)^2 - 2(X_{t+1} - X_t)(b - X_t)] >= δ
```

And in the proof of Theorem 2, `Y_t = n - X_t`, `b` in Theorem 1 is set to `n`, and the process is `Y_t`.

(A1) for `Y_t` with bound `b = n`:
```
E_t[(Y_{t+1} - Y_t)^2 - 2*(Y_{t+1} - Y_t)*(n - Y_t)] >= δ
```

`Y_{t+1} - Y_t = -(ΔX)`, `n - Y_t = X_t`:
```
= E_t[(ΔX)^2 + 2*ΔX*X_t] >= δ
```

But this doesn't follow from just (C2) and (C3)! Unless there's an additional argument.

Wait — I think the key is that in Theorem 2, `X_t in [0, n]` (or `X_t in [0, b]`), and `E_t[ΔX] >= 0`. So:
```
E_t[(ΔX)^2 + 2*ΔX*X_t] = E_t[(ΔX)^2] + 2*E_t[ΔX*X_t]
```

If `X_t >= 0` and `E_t[ΔX] >= 0`, and if `ΔX` and `X_t` are... no, we can't determine the sign of `E_t[ΔX*X_t]` without more info.

Actually, I think I'm overcomplicating this. Let me look at the proof structure differently. The paper says at lines 866-878:

```
E_t(Y_t - Y_{t+1}) >= 0  [this is E_t(ΔX) >= 0, from C2]
E_t((Y_t - Y_{t+1})^2) >= delta  [this is E_t((ΔX)^2) >= delta, from C3]
This implies Y_t satisfies (A1)
```

I think what the paper means is that (A1) with the specific form for Y_t decomposes as:
```
E_t[(Y_t - Y_{t+1})^2 - 2*(Y_t - Y_{t+1})*(b - Y_t)]
```
where `Y_t - Y_{t+1} = ΔX` and `b - Y_t = X_t`.

But actually, looking at it differently: maybe the paper is using a WEAKER version of (A1) that just requires the two separate conditions `E_t(ΔY) >= 0` and `E_t((ΔY)^2) >= delta`, and the combined (A1) follows from:

```
E_t[(ΔY)^2 - 2*ΔY*(b - Y_t)] = E_t[(ΔY)^2] - 2*E_t[ΔY*(b - Y_t)]
```

Now, `0 <= Y_t <= b` so `0 <= b - Y_t <= b`. And `E_t[ΔY] >= 0` (from the first condition). But `ΔY` could be negative, so `E_t[ΔY*(b-Y_t)]` could be anything.

Hmm. Let me look at this from a different angle. In the proof of Theorem 1 itself, the key inequality is:

```
E_t(Y_t - Y_{t+1}) >= δ  where Y_t = b² - (b - X_t)²
```

This is proved from (A1). But in Theorem 2, the paper directly states `E_t(Y_t - Y_{t+1}) >= 0` and `E_t((Y_t - Y_{t+1})^2) >= δ` for `Y_t = n - X_t`, and claims this implies (A1).

I think the actual argument is: in Theorem 1, the variance transform is `Y_t = b² - (b - X_t)²`, and the drift `E_t(Y_t - Y_{t+1}) >= δ` comes from (A1). In Theorem 2, the process is already set up so that `Y_t = b - X_t` and the drift is `E_t(Y_t - Y_{t+1}) = E_t(ΔX) >= 0` with second moment `E_t((ΔY)^2) >= δ`. The paper then says "this satisfies (A1)" meaning that the CONCLUSIONS of Theorem 1 still hold because the key ingredients (nonneg drift + second moment bound) are present.

Actually, I think there may be a subtlety I'm missing. Let me re-examine the proof of Theorem 1. In the proof of Theorem 1, after defining `Y_t = b² - (b - X_t)²`, the paper shows:

1. `E_t(Y_t - Y_{t+1}) >= δ` (from A1, line 752-753)
2. `E_t(Z_t - Z_{t+1}) >= 0` where `Z_t = Y_t + δt` (line 762-769)

Then the supermartingale property of `Z_t` gives the OST bound.

For Theorem 2, the paper substitutes `Y_t = n - X_t` (a different Y_t!) and shows:
1. `E_t(Y_t - Y_{t+1}) >= 0` (from C2)
2. `E_t((Y_t - Y_{t+1})^2) >= δ` (from C3)

And then "This implies Y_t satisfies (A1)." I think what the paper means is: the conditions needed to run the proof of Theorem 1 are:
- `Y_t in [0, b]` (boundedness)
- `E_t(Y_t - Y_{t+1}) >= 0` (nonneg drift — weaker than `>= δ`)
- Something about the second moment

And then the `δ` in the exponential bound comes from the second moment, not from the drift of Y_t.

Actually, I think I need to look at this more carefully. In the proof of Theorem 1, the `δ` comes from condition (A1), which is the drift of the VARIANCE-TRANSFORMED process `Y_t = b² - (b - X_t)²`. The second moment of `Y_t - Y_{t+1}` is NOT directly used in Theorem 1 — it's (A1) that provides the `δ`.

But in Theorem 2, the paper replaces `Y_t = b - X_t` (linear, not quadratic), and the `δ` comes from the second moment condition (C3). The argument is:

The variance-transformed `Y_t = b² - (b - X_t)²` from Theorem 1 applied to the process `X_t' = b - X_t` (i.e., Y_t from Theorem 2) gives:
```
Y'_t = b² - (b - (b - X_t))² = b² - X_t²
```
And `E_t(Y'_t - Y'_{t+1}) = E_t(X_{t+1}² - X_t²) = E_t((ΔX)² + 2*X_t*ΔX) = E_t((ΔX)²) + 2*E_t[X_t*ΔX]`.

With `E_t[ΔX] >= 0` and `X_t >= 0`, and if `X_t` is `F_t`-measurable, then `E_t[X_t*ΔX] = X_t * E_t[ΔX] >= 0` (pulling out `X_t` which is `F_t`-measurable). So:
```
E_t(Y'_t - Y'_{t+1}) >= E_t((ΔX)²) >= δ
```

So the actual argument is: Theorem 2 applies Theorem 1 to the process `X'_t = b - X_t` (the "Y_t" in Theorem 2's notation), and the variance transform in Theorem 1 applied to `X'_t` gives `Y'_t = b² - (b - X'_t)² = b² - X_t²`, and the (A1) condition for `X'_t` is satisfied because:
```
E_t[(ΔX')² - 2*ΔX'*(b - X'_t)] = E_t[(ΔX)² + 2*ΔX*X_t] = E_t[(ΔX)²] + 2*X_t*E_t[ΔX] >= δ + 0 = δ
```

The key step is `E_t[X_t * ΔX] = X_t * E_t[ΔX]` because `X_t` is `F_t`-measurable (pullout property). This is exactly `condExp_stronglyMeasurable_mul_of_bound` or `condExp_of_stronglyMeasurable` in the existing code.

So the Lean proof of Theorem 2 is:
1. Define `X' = fun t omega => b - X t omega`
2. Show X' is adapted and bounded in [0, b]
3. Show (A1) for X': `E_t[(ΔX')² - 2*ΔX'*(b - X'_t)] >= δ` using pullout of `X_t` from condExp + (C2) + (C3)
4. Apply `variance_drift_tail_bound` to X'

**Lean signature:**
```lean
/-- Theorem 2: Standard variance drift with exponential tail bound.
    Under (C1*), (C2), (C3), Pr(T >= τ) ≤ exp(-τ*δ/(e*b²)). -/
theorem standard_variance_drift_tail
    [IsProbabilityMeasure (ℙ : Measure Ω)]
    (X : ℕ → Ω → ℝ) (τ : Ω → ℕ)
    (h_adapted : Adapted F X)
    (h_stop : ∀ n, MeasurableSet[F n] {ω | τ ω ≤ n})
    (b δ : ℝ) (h_delta : 0 < δ) (h_b : 0 < b)
    (h_bounded : ∀ t ω, τ ω > t → 0 ≤ X t ω ∧ X t ω ≤ b)
    (h_integrable_all : ∀ t, Integrable (X t) ℙ)
    (h_c2 : ∀ t, ∀ᵐ ω ∂(ℙ : Measure Ω), τ ω > t →
      (ℙ[fun ω' => X (t+1) ω' - X t ω' | ↑(F t)]) ω ≥ 0)
    (h_c3 : ∀ t, ∀ᵐ ω ∂(ℙ : Measure Ω), τ ω > t →
      (ℙ[fun ω' => (X (t+1) ω' - X t ω')^2 | ↑(F t)]) ω ≥ δ)
    (r η : ℝ) (h_r : 0 < r) (h_η : 0 < η)
    (h_c1star : ∀ t j : ℕ, 0 < j →
      ∀ᵐ ω ∂(ℙ : Measure Ω), τ ω > t →
        (ℙ[fun ω' => Set.indicator {ω' | (j : ℝ) ≤ |X (t+1) ω' - X t ω'|}
          (fun _ => (1:ℝ)) ω' | ↑(F t)]) ω ≤ r / (1 + η)^j) :
    ∀ time : ℕ, (ℙ {ω | τ ω > time}).toReal ≤
      Real.exp (-(time : ℝ) * δ / (Real.e * b^2)) :=
  sorry
```

**Proof:** Apply `variance_drift_tail_bound` to `X' = b - X`. The (A1) condition for X' is derived from (C2) + (C3) + the pullout of `X_t` from the conditional expectation.

---

### 4.4 Corollary 3: Fixed step size

Same as Theorem 2 but (C1) replaces (C1*): `|X_{t+1} - X_t| < c_step` (bounded step size, not geometric tail). In Lean, replace `h_c1star` + `h_step_tail` with `h_c1 : forall t omega, |X (t+1) omega - X t omega| <= c_step`. Lemma 1 is not needed (bounded step size directly gives bounded conditional increments).

**Proof:** Direct corollary of Theorem 2. The geometric tail condition is automatically satisfied: set `r = 1`, `eta` large enough, and `h_step_tail` follows from the bounded step size (the indicator is 0 for `j > c_step`).

---

### 4.5 Theorem 4: Zero drift, two absorbing states

**Paper:** (C1*), (C3), `E_t(ΔX) = 0`. `T = inf{t | X_t in {0, b}}`. Then `E(T) <= X_0*(b - X_0)/delta` and `Pr(T >= tau) <= exp(-2*tau*delta/(e*b^2))`. Note the factor 2.

**Proof:** Replace `Y_t = X_t*(b - X_t)` (not `b^2 - (b - X_t)^2`). Then:
```
E_t(Y_t - Y_{t+1}) = E_t(X_t*(b - X_t) - X_{t+1}*(b - X_{t+1}))
= b*E_t(ΔX) - E_t(X_{t+1}^2 - X_t^2)
= b*E_t(ΔX) - E_t((ΔX)^2 + 2*X_t*ΔX)
= 0 - E_t((ΔX)^2) - 2*X_t*E_t(ΔX)  [using E_t(ΔX) = 0 and pullout]
= -E_t((ΔX)^2)
<= -delta  [from C3]
```

So `E_t(Y_t - Y_{t+1}) <= -delta`, i.e., `E_t(Y_{t+1} - Y_t) >= delta`. Then `Z_t = Y_t + delta*t` is a submartingale (wait, the paper says supermartingale). Let me re-check.

Actually, `E_t(Y_t - Y_{t+1}) <= -delta` means `E_t(Y_{t+1} - Y_t) >= delta`. So `Z_t = Y_t + delta*t` gives `E_t(Z_{t+1} - Z_t) = E_t(Y_{t+1} - Y_t) + delta >= 2*delta >= 0`. Hmm, that gives a submartingale.

Wait, I need to be more careful. The paper says at line 881-892:
```
E_t(Y_t - Y_{t+1}) = n*E_t(X_t - X_{t+1}) + E_t(X_{t+1}^2 - X_t^2)
```

Hmm, that's a different expansion. Let me redo:
```
Y_t = X_t * (n - X_t) = n*X_t - X_t^2
Y_{t+1} = n*X_{t+1} - X_{t+1}^2
Y_t - Y_{t+1} = n*(X_t - X_{t+1}) - (X_t^2 - X_{t+1}^2)
            = n*(X_t - X_{t+1}) + (X_{t+1}^2 - X_t^2)
            = -n*ΔX + (X_{t+1}^2 - X_t^2)
            = -n*ΔX + (ΔX)^2 + 2*X_t*ΔX
            = (ΔX)^2 + (2*X_t - n)*ΔX
```

Taking conditional expectation:
```
E_t(Y_t - Y_{t+1}) = E_t[(ΔX)^2] + (2*X_t - n)*E_t[ΔX]  [pullout of X_t]
                   = E_t[(ΔX)^2] + 0  [from E_t[ΔX] = 0, condition]
                   >= delta  [from C3]
```

So `E_t(Y_t - Y_{t+1}) >= delta`. Then `Z_t = Y_t + delta*t` gives:
```
E_t(Z_t - Z_{t+1}) = E_t(Y_t - Y_{t+1}) - delta >= delta - delta = 0
```
So Z_t is a supermartingale. Same structure as Theorem 1.

The factor 2 in the exponent comes from the bound on `E_k(Y_{T_k})`:
```
0 <= E_k(Y_{T_k}) = E_k(X_{T_k}*(n - X_{T_k}))
```
Since `X_{T_k} in {0, n}`, we have `Y_{T_k} = X_{T_k}*(n - X_{T_k}) = 0` (either `0*n = 0` or `n*0 = 0`). So `E_k(Y_{T_k}) = 0`, and:
```
E_k(Y_k - Y_{T_k}) = Y_k - 0 = X_k*(n - X_k)
```

Wait, but the paper uses Jensen here too (lines 915-928). Actually, in the paper's proof (line 916-928):
```
0 <= E_k(Y_{T_k}) = E_k(n*(n - X_{T_k})) -- wait, this seems wrong
```

Actually looking more carefully at lines 915-928:
```
0 ≤ E_k(Y_{T_k}) = E_k(n(n - X_{T_k}))
                 = n² - n*E_k(X_{T_k})
Using Jensen... ≤ n² - (E_k(X_{T_k}))²  -- hmm, this is n² - n*E_k, not n² - (E_k)²
```

Wait, I think there's a typo or OCR error. Let me re-read. The paper at line 916 says:
```
0 ≤ E_k(Y_{T_k}) = E_k(n (n − X_{T_k}))
```

But `Y_t = X_t(n - X_t)`, so `Y_{T_k} = X_{T_k}(n - X_{T_k})`. This is NOT `n(n - X_{T_k})`. I think this is an OCR/parsing error in the markdown. The actual expression should be `E_k(X_{T_k}(n - X_{T_k}))`.

But then the paper at line 918 says `= n² - n*E_k(X_{T_k})` which would be `E_k(n*X_{T_k} - X_{T_k}²) = n*E_k(X_{T_k}) - E_k(X_{T_k}²)`. Hmm, that's `n*E_k(X_{T_k}) - E_k(X_{T_k}²)`, not `n² - n*E_k(X_{T_k})`.

I think there's a confusion in the OCR. Let me work with the math directly.

For Theorem 4, `Y_t = X_t*(b - X_t)`, `T_k = inf{t >= k | X_t in {0, b}}`. On the boundary, `Y_{T_k} = 0` (since `X_{T_k} = 0` or `b`). So:
```
E_k(Y_{T_k}) = 0
E_k(Y_k - Y_{T_k}) = E_k(Y_k) = E_k(X_k*(b - X_k)) = X_k*(b - X_k)  [since X_k is F_k-measurable]
```

Wait, but `E_k(Y_k) = Y_k` since `Y_k` is `F_k`-measurable. So `E_k(Y_k - Y_{T_k}) = Y_k - 0 = X_k*(b - X_k)`.

Then `theta_k = E_k(Y_k - Y_{T_k}) / delta = X_k*(b - X_k) / delta <= b²/(4*delta)` (max of `x*(b-x)` is `b²/4` at `x = b/2`).

Hmm, but the paper says `theta = e*n²/(2*delta)` (line 921) giving the factor 2 in the exponent. Let me check: `theta_k <= b²/(4*delta)`, and `theta = e * b²/(2*delta)`. Then `theta_k / theta <= (b²/(4*delta)) / (e*b²/(2*delta)) = 1/(2*e)`. That gives `Pr(T_k - k > theta | F_k) <= 1/(2*e)`, not `1/e`.

Actually, let me re-read the paper. Line 920-921: `theta = en²/(2δ)`. And line 940: `theta := en²/(2δ)`. Wait no, looking at line 940 again: it says `Taking θ := en²/2δ`. But then in the proof of Theorem 1, `theta = eb²/δ` (line 815).

So for Theorem 4, `theta = e*n²/(2*delta)` and the bound is `Pr(T >= tau) <= exp(-tau/theta) = exp(-2*tau*delta/(e*n²))`. The factor 2 comes from the tighter bound on `theta_k <= n²/(4*delta)` vs `n²/delta` in Theorem 1 (because `Y_t = X_t*(b - X_t)` has max `b²/4` vs `Y_t = b² - (b - X_t)²` which has max `b²`).

Actually wait, the paper says at line 932-934: `theta_k = E_k(Y_k - Y_{T_k}) / delta in [0, n²/(2*delta)]`. And then `theta = e*n²/(2*delta)`. So `theta_k/theta <= (n²/(2*delta)) / (e*n²/(2*delta)) = 1/e`. OK so the bound on `theta_k` is `n²/(2*delta)`, not `n²/(4*delta)`.

Where does `n²/(2*delta)` come from? The paper at line 928 says: `n² - n*X_k >= E_k(Y_k - Y_{T_k}) >= 0`. And `Y_k = X_k*(n - X_k)`, so `E_k(Y_k - Y_{T_k}) = X_k*(n - X_k)`. The max of `X_k*(n - X_k)` is `n²/4`. But the paper bounds it by `n²/2`. 

Hmm, I think the paper might be using a looser bound. Actually, looking at line 916-928 more carefully:

```
0 ≤ E_k(Y_{T_k}) = E_k(n² - (n - X_{T_k})²)  -- wait, this is the Theorem 1 form, not Theorem 4
```

I think there's a mixing of Theorem 1 and Theorem 4 notation in the OCR. In Theorem 4, the paper says "We follow the analysis of Theorem 1 by replacing Y_t = X_t(n - X_t)". But then the bound on `E_k(Y_{T_k})` uses Jensen on the Theorem 1 form.

Actually, I think the proof of Theorem 4 in the paper has an error or the OCR is mangled. Let me just work out the correct math:

For Theorem 4: `Y_t = X_t*(b - X_t)`, `Y_{T_k} = 0` (boundary).
- `E_k(Y_k - Y_{T_k}) = Y_k = X_k*(b - X_k) <= b²/4`
- `theta_k = X_k*(b - X_k) / delta <= b²/(4*delta)`
- `theta = e * b²/(4*delta)` would give `theta_k/theta <= 1/e`
- But the paper says `theta = e*b²/(2*delta)`, giving `theta_k/theta <= 1/(2*e)`

I think the paper is using a suboptimal bound `X_k*(b - X_k) <= b²/2` (which is weaker than the true max `b²/4`). This would give `theta_k <= b²/(2*delta)` and `theta = e*b²/(2*delta)`.

Either way, the Lean proof should use the tight bound `b²/4` (or `b²/2` to match the paper) and the result `Pr(T >= tau) <= exp(-tau/theta)` with `theta = e*b²/(2*delta)` (matching the paper) or the stronger `theta = e*b²/(4*delta)`.

Actually, looking at the paper's stated result (line 853): `Pr(T >= tau) <= exp(-2*tau*delta/(e*b²))`. This corresponds to `theta = e*b²/(2*delta)`, i.e., `1/theta = 2*delta/(e*b²)`. With `theta_k <= b²/(2*delta)`, `theta = e*b²/(2*delta)`, `theta_k/theta <= 1/e`, and `Pr(T >= tau) <= exp(-tau/theta) = exp(-2*tau*delta/(e*b²))`. So the paper uses `theta_k <= b²/(2*delta)` which comes from `X_k*(b - X_k) <= b²/2` (a valid but not tight bound — the max is b²/4).

For the Lean formalization, we can use either bound. Using `b²/4` gives a STRONGER result `exp(-4*tau*delta/(e*b²))`, but to match the paper exactly, use `b²/2`.

**Lean signature:**
```lean
/-- Theorem 4: Zero drift with two absorbing states.
    Under (C1*), (C3), and E_t(ΔX) = 0,
    Pr(T >= τ) ≤ exp(-2*τ*δ/(e*b²)). -/
theorem zero_drift_tail_bound
    [IsProbabilityMeasure (ℙ : Measure Ω)]
    (X : ℕ → Ω → ℝ) (τ : Ω → ℕ)
    (h_adapted : Adapted F X)
    (h_stop : ∀ n, MeasurableSet[F n] {ω | τ ω ≤ n})
    (b δ : ℝ) (h_delta : 0 < δ) (h_b : 0 < b)
    (h_bounded : ∀ t ω, τ ω > t → 0 ≤ X t ω ∧ X t ω ≤ b)
    (h_integrable_all : ∀ t, Integrable (X t) ℙ)
    (h_zero_drift : ∀ t, ∀ᵐ ω ∂(ℙ : Measure Ω), τ ω > t →
      (ℙ[fun ω' => X (t+1) ω' - X t ω' | ↑(F t)]) ω = 0)
    (h_c3 : ∀ t, ∀ᵐ ω ∂(ℙ : Measure Ω), τ ω > t →
      (ℙ[fun ω' => (X (t+1) ω' - X t ω')^2 | ↑(F t)]) ω ≥ δ)
    (r η : ℝ) (h_r : 0 < r) (h_η : 0 < η)
    (h_c1star : ∀ t j : ℕ, 0 < j →
      ∀ᵐ ω ∂(ℙ : Measure Ω), τ ω > t →
        (ℙ[fun ω' => Set.indicator {ω' | (j : ℝ) ≤ |X (t+1) ω' - X t ω'|}
          (fun _ => (1:ℝ)) ω' | ↑(F t)]) ω ≤ r / (1 + η)^j) :
    ∀ time : ℕ, (ℙ {ω | τ ω > time}).toReal ≤
      Real.exp (-2 * (time : ℝ) * δ / (Real.e * b^2)) :=
  sorry
```

**Proof:** Define `Y_t = X_t*(b - X_t)`, `Z_t = Y_t + delta*t`. Show `E_t(Y_t - Y_{t+1}) >= delta` from zero drift + (C3) + pullout. The rest follows the Theorem 1 recurrence engine, with `theta_k <= b²/(2*delta)` and `theta = e*b²/(2*delta)`.

---

### 4.6 Theorem 5: Additive drift, positive constant drift

**Paper:** (C1*), `E_t(ΔX) >= epsilon > 0`. `T = inf{t | X_t >= b}`. Then `E(T) <= (b - X_0)/epsilon` and `Pr(T >= tau) <= exp(-tau*epsilon/(e*b))`.

**Proof:** `Y_t = X_t`, `Z_t = Y_t - epsilon*t` (note the sign: submartingale, not supermartingale). `E_t(Z_{t+1} - Z_t) = E_t(ΔX) - epsilon >= 0`. OST gives `E_k(X_{T_k} - X_k) >= epsilon*E_k(T_k - k)`. `E_k(X_{T_k}) in [X_k, b]`, so `E_k(X_{T_k} - X_k) <= b - X_k`. `theta_k = (b - X_k)/epsilon <= b/epsilon`. `theta = e*b/epsilon`.

This is structurally simpler — no variance transform needed. The submartingale `Z_t = X_t - epsilon*t` and the OST bound directly.

**Lean signature:**
```lean
/-- Theorem 5: Additive drift with positive constant drift and exponential tail.
    Under (C1*) and E_t(ΔX) ≥ ε > 0,
    Pr(T >= τ) ≤ exp(-τ*ε/(e*b)). -/
theorem additive_drift_tail_bound
    [IsProbabilityMeasure (ℙ : Measure Ω)]
    (X : ℕ → Ω → ℝ) (τ : Ω → ℕ)
    (h_adapted : Adapted F X)
    (h_stop : ∀ n, MeasurableSet[F n] {ω | τ ω ≤ n})
    (b ε : ℝ) (h_eps : 0 < ε) (h_b : 0 < b)
    (h_bounded : ∀ t ω, τ ω > t → 0 ≤ X t ω ∧ X t ω ≤ b)
    (h_integrable_all : ∀ t, Integrable (X t) ℙ)
    (h_drift : ∀ t, ∀ᵐ ω ∂(ℙ : Measure Ω), τ ω > t →
      (ℙ[fun ω' => X (t+1) ω' - X t ω' | ↑(F t)]) ω ≥ ε)
    (r η : ℝ) (h_r : 0 < r) (h_η : 0 < η)
    (h_c1star : ∀ t j : ℕ, 0 < j →
      ∀ᵐ ω ∂(ℙ : Measure Ω), τ ω > t →
        (ℙ[fun ω' => Set.indicator {ω' | (j : ℝ) ≤ |X (t+1) ω' - X t ω'|}
          (fun _ => (1:ℝ)) ω' | ↑(F t)]) ω ≤ r / (1 + η)^j) :
    ∀ time : ℕ, (ℙ {ω | τ ω > time}).toReal ≤
      Real.exp (-(time : ℝ) * ε / (Real.e * b)) :=
  sorry
```

**Proof:** No variance transform. `Z_t = X_t - epsilon*t` is a submartingale. OST gives `E_k(X_{T_k} - X_k) >= epsilon*E_k(T_k - k)`. Bound `E_k(X_{T_k} - X_k) <= b - X_k <= b`. Set `theta = e*b/epsilon`. Apply the recurrence engine.

---

### 4.7 Recurrence Engine Lemma (shared by Theorems 1, 2, 3, 4, 5)

All five theorems share steps 11-14 (Markov + recurrence + induction). Factor into a reusable lemma:

```lean
/-- Recurrence engine: if the conditional tail bound Pr(T_k - k > θ | F_k) ≤ 1/e
    holds for all k, then Pr(T_0 > n*θ) ≤ e^{-n} for all n. -/
lemma recurrence_tail_bound
    [IsProbabilityMeasure (ℙ : Measure Ω)]
    (X : ℕ → Ω → ℝ) (T : ℕ → Ω → ℕ)
    -- T k is the k-th hitting time: T k ω = inf{t >= k | X t ω in target}
    (h_T_stop : ∀ k n, MeasurableSet[F n] {ω | T k ω ≤ n})
    (h_T_mono : ∀ k ω, T k ω ≤ T (k+1) ω)
    (θ : ℕ) (h_θ : 0 < θ)
    -- Conditional Markov bound: Pr(T_k - k > θ | F_k) ≤ 1/e a.s. on {T_0 > k}
    (h_cond_bound : ∀ k, ∀ᵐ ω ∂(ℙ : Measure Ω),
      T 0 ω > k * θ →
        (ℙ[fun ω' => Set.indicator {ω' | θ < T (k * θ) ω' - (k * θ)}
          (fun _ => (1:ℝ)) ω' | ↑(F (k * θ))]) ω ≤ Real.exp (-1)) :
    ∀ n : ℕ, (ℙ {ω | T 0 ω > n * θ}).toReal ≤ Real.exp (-(n : ℝ)) :=
  sorry
```

**Proof:**
1. Base case `n = 0`: `Pr(T_0 > 0) <= 1 = e^0`. (Need `T 0 > 0` a.s. or handle separately.)
2. Inductive step: `{T_0 > (k+1)*θ} = {T_0 > k*θ} ∩ {T_{k*θ} - k*θ > θ}`.
3. `Pr(T_0 > (k+1)*θ) = E[1_{T_0 > k*θ} * 1_{T_{k*θ} - k*θ > θ}]`
4. Tower: `= E[1_{T_0 > k*θ} * E[1_{T_{k*θ} - k*θ > θ} | F_{k*θ}]]`
5. `<= E[1_{T_0 > k*θ} * e^{-1}]` (from `h_cond_bound`)
6. `= Pr(T_0 > k*θ) * e^{-1}`
7. `<= e^{-k} * e^{-1} = e^{-(k+1)}` (induction hypothesis)

**Key Lean tools:**
- `measurableSet_F_tau_gt` for `{T_0 > k*θ} in F_{k*θ}`
- `condExp_condExpProd` or `setIntegral_condExp` for tower property
- `integral_indicator` for indicator integrals
- `integral_mul` / `integral_mul_const` for factoring out constants

**Risk:** The set equality in step 2 requires careful proof. The k-th hitting time `T_k` and the decomposition `{T_0 > (k+1)*θ} = {T_0 > k*θ} ∩ {T_{k*θ} - k*θ > θ}` need to be verified. This is the most delicate part.

---

### 4.8 Theorem 6: Random 2-SAT

**Paper:** `Pr(runtime <= r*n^4) >= 1 - exp(-r/e)`. Apply Theorem 2 with `X_t = #agreements`, variance bound 1, `b = n`, `theta = e*n^2`. Then `Pr(T >= r*n^2) <= exp(-r/e)`. Multiply by `O(n^2)` inner loop steps.

**Lean approach:** Define `X_t = number of agreeing variables`, show (C2) `E_t(ΔX) >= 0` and (C3) `E_t((ΔX)^2) >= 1` from the 2-SAT flip mechanics, apply `standard_variance_drift_tail` with `b = n`, `delta = 1`. The inner-loop multiplication `O(n^2)` is a separate counting argument.

**Placement:** `DriftTheorems/VarianceDriftApplications.lean`

---

### 4.9 Theorem 7: Recolouring

**Paper:** `Pr(runtime <= r*n^4) >= 1 - exp(-4r/(3e))`. Apply Theorem 4 with `X_t = #correctly coloured vertices`, zero drift, variance bound `3/4`. `theta = e*n^2/(2*(3/4)) = 2*e*n^2/3`. `Pr(T >= r*n^2) <= exp(-3r/(2e))`. Multiply by `O(n^2)`.

**Placement:** `DriftTheorems/VarianceDriftApplications.lean`

---

### 4.10 Theorem 8: RLS-PD on BILINEAR

**Paper:** Two phases. Phase 1: additive drift (Theorem 5) on `X_t = h_max - h(M_t)` with `delta_1 = 1/(2*sqrt(n))`. Phase 2: variance drift (Theorem 1) on `Y_t = (A+B)*sqrt(n) - M_t` with negative drift, `b = 2*(A+B)*sqrt(n) + 1`. Union bound: `Pr(T >= 2*r*n^{1.5}) <= 2*exp(-Omega(r))`.

**Lean approach:**
1. Define `BILINEAR_{alpha,beta}(x,y)`, `OPT`, `M_t` (Manhattan distance), `h(M_t)` (piecewise potential), `delta(M_t)` (piecewise drift) in `CoEABilinear.lean`
2. Phase 1: apply `additive_drift_tail_bound` to `X_t = h_max - h(M_t)`
3. Phase 2: apply `variance_drift_tail_bound` to `Y_t = (A+B)*sqrt(n) - M_t`
4. Union bound: `Pr(T >= T1 + T2) <= Pr(T1 >= r*n^{1.5}) + Pr(T2 >= r*n^{1.5})`

**New definitions needed:**
- `bilinear` function (Definition 6)
- `pairwise_dominance` (Definition 5)
- `manhattan_distance` (Definition 9)
- `piecewise_potential h` and `piecewise_drift delta` from Lemma 2 ([Hevia Fajardo et al. 2023])
- RLS-PD transition kernel

**Placement:** `CoEABilinear.lean`

---

### 4.11 Theorem 9: RLS-PD forgets NE

**Paper:** `Pr(runtime <= r*n) >= 1 - exp(-Omega(r))`. Apply Theorem 1 to `Y_t = (A+B)*sqrt(n) - M_t` with negative drift `E_t(M_t - M_{t+1} - (M_t - (A+B)*sqrt(n))/(2n)) >= 0`, `delta_2 > 0`, `b = (A+B)*sqrt(n)`.

**Placement:** `CoEABilinear.lean`

---

### 4.12 Theorem 10: RWAB regret

**Paper:** `regret <= 480*epsilon*(L + sqrt(L*T))` with probability `>= 1 - 2*exp(-sqrt(epsilon)/e)`. Splits into R_1..R_4.

**Lean approach:**
1. Define era, sub-era, swap, mistake (Definitions 11-13)
2. Prove Lemma 3 (geometric stochastic domination)
3. Bound R_1 via Theorem 5 (additive drift on `S_t`)
4. Bound R_2 via Chernoff (Binomial concentration of #CHALLENGE)
5. Bound R_3 via Lemma 3 (geometric domination for #sub-era-ending steps)
6. Bound R_4 via Theorem 5
7. Union bound for the four cases

**New definitions needed:**
- `Era`, `SubEra`, `Swap`, `Mistake` (Definitions 11-13)
- `CHALLENGE` random walk `S_t`
- Regret classes `R_1`, `R_2`, `R_3`, `R_4`

**Placement:** `RWABRegret.lean`

**Dependency:** `MultiplicativeChernoff.lean` for Binomial concentration, `Hoeffding.lean` for bounded-difference, `VarianceDriftCorollaries.lean` for Theorem 5.

---

## Part 5: Implementation Order with Checkpoints

### Phase 1: Core Engine (VarianceDrift.lean)

| Step | Content | Lines (est.) | Checkpoint |
|---|---|---|---|
| 1.1 | File setup, imports, namespace, variables | 15 | `lake build` passes (empty file) |
| 1.2 | `bounded_conditional_increments_discrete` (Lemma 1) | 40 | `#print axioms` clean |
| 1.3 | k-th hitting time definition + stopping time proof | 30 | Compiles |
| 1.4 | Variance transform `Y_t = b^2 - (b - X_t)^2` + adaptedness + bounds | 25 | Compiles |
| 1.5 | Key drift inequality: pointwise identity + condExp transfer | 30 | `by ring` closes identity |
| 1.6 | Supermartingale `Z_t = Y_t + delta*t` + `E_t(Z_t - Z_{t+1}) >= 0` | 35 | Compiles |
| 1.7 | Finiteness `E(T) < inf` via `additive_drift_theorem` on stopped Y | 40 | Compiles |
| 1.8 | OST application: `E_k(Y_k - Y_{T_k}) >= delta * E_k(T_k - k)` | 50 | Compiles |
| 1.9 | Jensen bound on `E_k(Y_{T_k})` | 30 | Compiles |
| 1.10 | Markov + theta bound: `Pr(T_k - k > theta | F_k) <= 1/e` | 25 | Compiles |
| 1.11 | `recurrence_tail_bound` lemma (shared engine) | 60 | Compiles |
| 1.12 | `variance_drift_tail_bound` theorem (assemble 1.2-1.11) | 20 | `#print axioms` clean |
| **Total** | | **~400** | |

### Phase 2: Corollaries (VarianceDriftCorollaries.lean)

| Step | Content | Lines (est.) | Checkpoint |
|---|---|---|---|
| 2.1 | `standard_variance_drift_tail` (Theorem 2) | 50 | Compiles |
| 2.2 | `fixed_step_variance_drift_tail` (Corollary 3) | 30 | Compiles |
| 2.3 | `zero_drift_tail_bound` (Theorem 4) | 60 | Compiles |
| 2.4 | `additive_drift_tail_bound` (Theorem 5) | 50 | Compiles |
| **Total** | | **~190** | |

### Phase 3: Simple Applications (VarianceDriftApplications.lean)

| Step | Content | Lines (est.) | Checkpoint |
|---|---|---|---|
| 3.1 | Theorem 6 (2-SAT): define agreement process, show (C2)+(C3), apply Thm 2 | 60 | Compiles |
| 3.2 | Theorem 7 (Recolour): define colour process, show zero drift + (C3), apply Thm 4 | 60 | Compiles |
| **Total** | | **~120** | |

### Phase 4: CoEA Applications (CoEABilinear.lean)

| Step | Content | Lines (est.) | Checkpoint |
|---|---|---|---|
| 4.1 | BILINEAR definition, OPT, pairwise dominance, Manhattan distance | 60 | Compiles |
| 4.2 | Piecewise potential `h(M_t)` and drift `delta(M_t)` (Lemma 2) | 50 | Compiles |
| 4.3 | RLS-PD transition kernel | 40 | Compiles |
| 4.4 | Phase 1: apply `additive_drift_tail_bound` | 40 | Compiles |
| 4.5 | Phase 2: apply `variance_drift_tail_bound` | 50 | Compiles |
| 4.6 | Union bound + Theorem 8 statement | 30 | `#print axioms` clean |
| 4.7 | Theorem 9 (forget NE): apply `variance_drift_tail_bound` directly | 40 | `#print axioms` clean |
| **Total** | | **~310** | |

### Phase 5: RWAB Regret (RWABRegret.lean)

| Step | Content | Lines (est.) | Checkpoint |
|---|---|---|---|
| 5.1 | Definitions: era, sub-era, swap, mistake, CHALLENGE walk | 60 | Compiles |
| 5.2 | Lemma 3: geometric stochastic domination | 40 | Compiles |
| 5.3 | R_1 bound via Theorem 5 | 40 | Compiles |
| 5.4 | R_2 bound via Chernoff | 50 | Compiles |
| 5.5 | R_3 bound via Lemma 3 + Theorem 5 | 50 | Compiles |
| 5.6 | R_4 bound via Theorem 5 | 30 | Compiles |
| 5.7 | Union bound + Theorem 10 statement | 30 | `#print axioms` clean |
| **Total** | | **~300** | |

### Phase 6: Integration

| Step | Content | Checkpoint |
|---|---|---|
| 6.1 | Update `lakefile.lean` with new roots | `lake build` passes |
| 6.2 | `#print axioms` on all new theorems | No axioms beyond standard |
| 6.3 | Verify no `sorry` in any new file | `rg "sorry"` returns 0 hits |

---

## Part 6: Risk Assessment

### High risk

1. **Recurrence engine set equality (Step 11 of Theorem 1):** The decomposition `{T_0 > (k+1)*theta} = {T_0 > k*theta} cap {T_{k*theta} - k*theta > theta}` requires a careful proof of the relationship between `T_0`, `T_{k*theta}`, and the process. The k-th hitting time `T_k = inf{t >= k | X_t <= 0}` has the property that `T_0 > n` iff the process never hits 0 in `[0, n]`, which equals `T_{k*theta} > (k+1)*theta` when `T_0 > k*theta`. **Mitigation:** Define `T_k` carefully and prove the set equality by extensionality, using the definition of `inf`.

2. **Conditional Markov inequality:** The paper applies Markov's inequality to the conditional expectation `E_k(T_k - k | F_k)`. Mathlib's Markov inequality is for unconditional expectations. Need to derive the conditional version: `Pr(T_k - k > theta | F_k) <= E_k(T_k - k | F_k) / theta` a.s. **Mitigation:** Prove via `condExp_mono` + indicator representation, similar to `negative_drift_tail_bound` lines 472-493.

3. **Jensen's inequality for conditional expectation:** The paper uses `E_k[(b - X_{T_k})^2] >= (E_k[b - X_{T_k}])^2`. Need the conditional Jensen inequality. **Mitigation:** Mathlib has `MeasureTheory.convexOn_integral_mem` / `Jensen`. Check if a conditional version exists; if not, derive from the unconditional version by disintegration or by working on the conditional probability space.

4. **Unconditional nonnegativity for `additive_drift_theorem`:** The existing `additive_drift_theorem` requires `forall t omega, 0 <= X t omega` unconditionally, but we only have `0 <= X_t <= b` on `{tau > t}`. **Mitigation:** Use the stopped process `Y'_t = Y_{min t tau}` which is nonneg everywhere. Prove `additive_drift_theorem` applies to `Y'`.

### Medium risk

5. **Tower property in the recurrence:** The step `E[1_A * E[1_B | G]] = E[1_A * 1_B]` when `A in G` needs the "taking out what is known" property. Available as `condExp_condExpProd` or `setIntegral_condExp` in the existing code. Verify the exact Mathlib API.

6. **Real-valued theta vs natural-valued times:** The paper's `theta = e*b^2/delta` is real, but stopping times are `Omega -> ℕ`. Use `theta_n = Nat.ceil (Real.e * b^2 / delta)` for the recurrence, and derive the real-valued bound from the discrete one. **Mitigation:** Prove `Pr(T > k * theta_n) <= exp(-k)` and then `Pr(T > tau) <= exp(-(tau / theta_n))` for general `tau` using `tau / theta_n >= k` when `tau >= k * theta_n`.

7. **Lemma 1 integral vs discrete sum:** The paper uses a continuous integral `int_0^infty r/(1+eta)^j dj = r/log(1+eta)`. The discrete version `sum_{j=0}^infty r/(1+eta)^j = r*(1+eta)/eta` is simpler to prove in Lean (geometric series). **Mitigation:** Use the discrete version. The constant `c = r*(1+eta)/eta` is larger but sufficient for OST condition (4).

### Low risk

8. **BILINEAR domain (Theorems 8, 9):** The CoEA structures (`ZeroSumGame`, `MixedStrategy`, `is_nash_equilibrium`) already exist in `CoEALevelBased.lean`. The new definitions (BILINEAR, Manhattan distance, RLS-PD kernel) are concrete and don't require deep Mathlib API. The proof is a direct application of the core theorems.

9. **RWAB domain (Theorem 10):** The regret split R_1..R_4 is combinatorial and uses existing `MultiplicativeChernoff` and `Hoeffding` infrastructure. Lemma 3 (geometric domination) is a simple stochastic-order result.

---

## Part 7: Verification Strategy

1. **Per-file incremental builds:** After each step in Part 5, run `lake build DriftTheorems.VarianceDrift` (or the relevant target). Fix errors before proceeding.

2. **Axiom check:** After each theorem is complete, run:
   ```bash
   lake env lean --print-axioms <file.lean> | grep -v "axiom"
   ```
   Target: no axioms beyond `Classical.choice`, `Quot.sound`, `propext`.

3. **Sorry check:** After each phase, run:
   ```bash
   rg "sorry" DriftTheorems/VarianceDrift.lean DriftTheorems/VarianceDriftCorollaries.lean ...
   ```
   Target: 0 hits.

4. **Full build:** After Phase 6, run `lake build` with no errors.

5. **Import graph verification:** Ensure no circular imports:
   ```bash
   lake env lean --imports DriftTheorems/VarianceDrift.lean
   ```

---

## Part 8: Summary

| Metric | Value |
|---|---|
| New files | 5 |
| New lines (estimated) | ~1320 |
| New theorems | 12 (Theorems 1-10 + Lemma 1 + recurrence engine) |
| Reused existing lemmas | 7+ (telescoping_sum, min_eq_sum_indicator, measurableSet_F_tau_gt, integrable_stopped_diff, additive_drift_theorem, measurableSet_min_tau_eq, condExp algebra) |
| High-risk steps | 4 |
| Implementation phases | 6 |
| Mathlib version | v4.28.0 |

The core novelty (variance transform + intersection-decomposition recurrence) is in `VarianceDrift.lean`. Everything else is either a corollary (different Y_t substitution) or an application (domain-specific setup + direct theorem application). The recurrence engine lemma factors out the shared proof structure across all five core theorems.
