<script lang="ts">
  import Icon from './Icon.svelte';
  import { DISPATCH_MODELS, app } from '$lib/stores.svelte';
  import { NODE_BY_ID } from '$lib/data';
  import { fetchDispatchPreview } from '$lib/api';
  import type { TheoremNode } from '$lib/types';

  interface Props {
    node: TheoremNode;
    model: string;
    dispatching?: boolean;
    oncancel: () => void;
    onconfirm: () => void;
  }
  let { node, model, dispatching = false, oncancel, onconfirm }: Props = $props();

  type Premise = { name: string; src: string; score: number; kind: 'dep' | 'mathlib' | 'paper'; auto?: boolean };

  function generatePremises(n: TheoremNode): Premise[] {
    const out: Premise[] = [];
    (n.depends_on || []).forEach((d) => {
      const dep = NODE_BY_ID[d];
      if (!dep) return;
      out.push({ name: dep.lean_theorem, src: dep.lean_file, score: 1.0, kind: 'dep', auto: true });
    });
    const mathlibBank: Premise[] = [
      { name: 'additive_drift_bound', src: 'Mathlib.Probability.AdditiveDrift', score: 0.94, kind: 'mathlib' },
      { name: 'markov_geometric_restart', src: 'Mathlib.Probability.GeometricRestart', score: 0.91, kind: 'mathlib' },
      { name: 'Real.exp_neg_le_one_sub_of_nonneg', src: 'Mathlib.Analysis.SpecialFunctions.Exp', score: 0.78, kind: 'mathlib' },
      { name: 'Finset.sum_le_sum_of_subset', src: 'Mathlib.Algebra.BigOperators.Basic', score: 0.62, kind: 'mathlib' },
      { name: 'Measure.tprod_eq_prod', src: 'Mathlib.MeasureTheory.Product', score: 0.86, kind: 'mathlib' },
      { name: 'MeasureTheory.UniformIntegrable.of_bounded', src: 'Mathlib.MeasureTheory.UniformIntegrable', score: 0.71, kind: 'mathlib' },
      { name: 'Nat.log_le_log', src: 'Mathlib.Data.Nat.Log', score: 0.55, kind: 'mathlib' },
      { name: 'one_sub_inv_pow_lower_bound', src: 'Mathlib.Analysis.Asymptotics', score: 0.49, kind: 'mathlib' },
    ];
    (n.id === 'thm_5_4' ? mathlibBank.slice(0, 6) : mathlibBank.slice(0, 4)).forEach((p) => out.push(p));
    out.push({ name: '@paper:' + n.paper_section, src: 'paper/main.tex', score: 1.0, kind: 'paper', auto: true });
    return out;
  }

  let premises = $derived(generatePremises(node));
  let enabled = $state<boolean[]>([]);
  $effect(() => {
    enabled = premises.map((p) => p.score >= 0.6 || !!p.auto);
  });
  let enabledCount = $derived(enabled.filter(Boolean).length);
  let totalTokens = $derived(
    premises.reduce((acc, p, i) => acc + (enabled[i] ? Math.round(p.name.length * 30 + 400) : 0), 0)
  );
  let modelObj = $derived(DISPATCH_MODELS.find((m) => m.id === model) ?? DISPATCH_MODELS[0]);

  let routePreview = $state<{ prover: string; reason: string; goedelLocked?: boolean } | null>(null);

  $effect(() => {
    if (!app.projectRoot) return;
    const target = node.proof_folder ?? node.id;
    fetchDispatchPreview(app.projectRoot, target, model).then((p) => {
      if (p) routePreview = { prover: p.prover, reason: p.reason, goedelLocked: p.goedelLocked };
    });
  });

  function toggle(i: number) {
    if (premises[i].auto) return;
    enabled = enabled.map((v, j) => (j === i ? !v : v));
  }
</script>

<div class="modal-backdrop" onclick={oncancel} role="presentation">
  <div class="modal" onclick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
    <div class="modal-header">
      <h2>Confirm dispatch · {node.paper_id}</h2>
      <p class="lede">
        The agent will load <strong style="color: var(--fg-0)">{enabledCount}</strong> premises into its context
        (<span style="font-family: var(--font-mono)">~{(totalTokens / 1000).toFixed(1)}k</span> tokens).
        Uncheck retrievals you think are noise; required dependencies and the paper passage are pinned.
      </p>
    </div>
    <div class="modal-body">
      <div class="sec-label">Dependencies (required)</div>
      <div class="premise-list" style="margin-bottom: 16px;">
        {#each premises as p, i (p.name)}
          {#if p.kind === 'dep'}
            <button class="premise-row on" type="button" onclick={() => toggle(i)}>
              <div class="check"><Icon name="check" size={10} /></div>
              <div>
                <span class="name">{p.name}</span>
                <span class="badge-d">dep</span>
                <div class="src" style="margin-top: 2px;">{p.src}</div>
              </div>
              <div class="score">pinned</div>
            </button>
          {/if}
        {/each}
      </div>

      <div class="sec-label">
        Mathlib retrieval (semantic search)
        <span style="margin-left: 8px; font-size: 10px; color: var(--fg-4); text-transform: none; letter-spacing: 0;">
          relevance ≥ 0.6 enabled by default
        </span>
      </div>
      <div class="premise-list" style="margin-bottom: 16px;">
        {#each premises as p, i (p.name + i)}
          {#if p.kind === 'mathlib'}
            <button class="premise-row" class:on={enabled[i]} class:off={!enabled[i]} type="button" onclick={() => toggle(i)}>
              <div class="check">{#if enabled[i]}<Icon name="check" size={10} />{/if}</div>
              <div>
                <span class="name">{p.name}</span>
                <span class="badge-m">mathlib</span>
                <div class="src" style="margin-top: 2px;">{p.src}</div>
              </div>
              <div class="score">{p.score.toFixed(2)}</div>
            </button>
          {/if}
        {/each}
      </div>

      <div class="sec-label">Paper context</div>
      <div class="premise-list">
        {#each premises as p, i (p.name + i)}
          {#if p.kind === 'paper'}
            <button class="premise-row on" type="button" onclick={() => toggle(i)}>
              <div class="check"><Icon name="check" size={10} /></div>
              <div>
                <span class="name">{p.name}</span>
                <span class="badge-d" style="background: var(--st-progress-bg); color: var(--st-progress);">paper</span>
                <div class="src" style="margin-top: 2px;">{p.src}</div>
              </div>
              <div class="score">pinned</div>
            </button>
          {/if}
        {/each}
      </div>
    </div>
    <div class="modal-footer">
      <div style="font-size: 11px; color: var(--fg-3);">
        {#if routePreview}
          Routing to <strong style="color: var(--fg-0)">{routePreview.prover}</strong>
          — {routePreview.reason}
          {#if routePreview.goedelLocked && routePreview.prover === 'goedel'}
            <span style="color: var(--st-sorries);"> · Goedel busy</span>
          {/if}
        {:else}
          Routing to <strong style="color: var(--fg-0)">{modelObj.name}</strong>
        {/if}
      </div>
      <div style="margin-left: auto; display: flex; gap: 6px;">
        <button class="btn" onclick={oncancel} disabled={dispatching}>Cancel</button>
        <button class="btn primary" onclick={onconfirm} disabled={dispatching || (routePreview?.goedelLocked && routePreview?.prover === 'goedel')}>
          <Icon name="play" size={11} />{dispatching ? 'Dispatching…' : 'Dispatch'}
        </button>
      </div>
    </div>
  </div>
</div>

<style>
  .premise-row { all: unset; cursor: pointer; }
  .sec-label {
    font-size: 10.5px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--fg-3);
    font-weight: 600;
    margin-bottom: 8px;
  }
</style>
