<script lang="ts">
  import Icon from './Icon.svelte';
  import { DISPATCH_MODELS, app } from '$lib/stores.svelte';
  import { NODE_BY_ID, DEFINITIONS } from '$lib/data';
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
    for (const d of n.depends_on || []) {
      const dep = NODE_BY_ID[d];
      if (!dep) continue;
      out.push({ name: dep.lean_theorem, src: dep.lean_file, score: 1.0, kind: 'dep', auto: true });
    }
    const usedDefIds = new Set(n.uses_defs || []);
    for (const def of DEFINITIONS) {
      if (usedDefIds.has(def.id)) {
        out.push({ name: def.lean_name, src: def.lean_file, score: 0.85, kind: 'mathlib', auto: true });
      }
    }
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
  <div class="modal" onclick={(e) => e.stopPropagation()} onkeydown={(e) => { if (e.key === 'Escape') oncancel(); e.stopPropagation(); }} role="dialog" aria-modal="true" tabindex="-1">
    <div class="modal-header">
      <h2>Confirm dispatch · {node.paper_id}</h2>
      <p class="lede">
        The agent will load <strong class="fg-0">{enabledCount}</strong> premises into its context
        (<span class="mono-sm">~{(totalTokens / 1000).toFixed(1)}k</span> tokens).
        Uncheck retrievals you think are noise; required dependencies and the paper passage are pinned.
      </p>
    </div>
    <div class="modal-body">
      <div class="sec-label">Dependencies (required)</div>
      <div class="premise-list premise-list-mb">
        {#each premises as p, i (p.name)}
          {#if p.kind === 'dep'}
            <button class="premise-row on" type="button" onclick={() => toggle(i)}>
              <div class="check"><Icon name="check" size={10} /></div>
              <div>
                <span class="name">{p.name}</span>
                <span class="badge-d">dep</span>
                <div class="src src-mt">{p.src}</div>
              </div>
              <div class="score">pinned</div>
            </button>
          {/if}
        {/each}
      </div>

      <div class="sec-label">
        Mathlib retrieval (semantic search)
        <span class="sec-label-hint">
          relevance ≥ 0.6 enabled by default
        </span>
      </div>
      <div class="premise-list premise-list-mb">
        {#each premises as p, i (p.name + i)}
          {#if p.kind === 'mathlib'}
            <button class="premise-row" class:on={enabled[i]} class:off={!enabled[i]} type="button" onclick={() => toggle(i)}>
              <div class="check">{#if enabled[i]}<Icon name="check" size={10} />{/if}</div>
              <div>
                <span class="name">{p.name}</span>
                <span class="badge-m">mathlib</span>
                <div class="src src-mt">{p.src}</div>
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
                <span class="badge-d badge-paper">paper</span>
                <div class="src src-mt">{p.src}</div>
              </div>
              <div class="score">pinned</div>
            </button>
          {/if}
        {/each}
      </div>
    </div>
    <div class="modal-footer">
      <div class="mono-sm-11">
        {#if routePreview}
          Routing to <strong class="fg-0">{routePreview.prover}</strong>
          — {routePreview.reason}
          {#if routePreview.goedelLocked && routePreview.prover === 'goedel'}
            <span class="axiom-warn"> · Goedel busy</span>
          {/if}
        {:else}
          Routing to <strong class="fg-0">{modelObj.name}</strong>
        {/if}
      </div>
      <div class="ml-auto flex-gap-sm">
        <button class="btn" onclick={oncancel} disabled={dispatching}>Cancel</button>
        <button class="btn primary" onclick={onconfirm} disabled={dispatching || (routePreview?.goedelLocked && routePreview?.prover === 'goedel')}>
          <Icon name="play" size={11} />{dispatching ? 'Dispatching…' : 'Dispatch'}
        </button>
      </div>
    </div>
  </div>
</div>

<style>
  .sec-label {
    font-size: 10.5px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--fg-3);
    font-weight: 600;
    margin-bottom: 8px;
  }
</style>
