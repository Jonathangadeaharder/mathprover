<script lang="ts">
  import StatusPill from './StatusPill.svelte';
  import Icon from './Icon.svelte';
  import Meter from './Meter.svelte';
  import RunAgentButton from './RunAgentButton.svelte';
  import GitGraph from './GitGraph.svelte';
  import { app } from '$lib/stores.svelte';
  import { NODE_BY_ID, CHILDREN_BY_ID, DEF_BY_ID } from '$lib/data';
  import { highlightLean, statusKey } from '$lib/lean';

  let node = $derived(app.selectedNodeId ? NODE_BY_ID[app.selectedNodeId] : null);
  let tab = $state<'overview' | 'mapping' | 'lean' | 'attempts' | 'sorries'>('overview');
  let mappingVariant = $state<'comment' | 'macro' | 'sidecar'>('comment');

  $effect(() => {
    void app.selectedNodeId;
    tab = 'overview';
  });

  let sk = $derived(node ? statusKey(node.status) : 'UNEXPLORED');
  let depsResolved = $derived(node ? (node.depends_on || []).map((d) => NODE_BY_ID[d]).filter(Boolean) : []);
  let children = $derived(node ? (CHILDREN_BY_ID[node.id] || []).map((c) => NODE_BY_ID[c]).filter(Boolean) : []);
  let defsUsed = $derived(node ? (node.uses_defs || []).map((d) => DEF_BY_ID[d]).filter(Boolean) : []);

  function openDef(id: string) {
    app.selectedDefId = id;
    app.selectedNodeId = null;
    app.route = 'definitions';
  }
  let allDepsProven = $derived(depsResolved.every((d) => statusKey(d.status) === 'PROVEN'));

  function close() { app.selectedNodeId = null; }
  function runAgent(model: string) {
    if (!node) return;
    app.pendingDispatch = { nodeId: node.id, model };
  }
  function openPaperLean() {
    if (!node) return;
    app.paperLeanNodeId = node.id;
    app.route = 'paper-lean';
  }
</script>

<div class="detail-overlay" class:hidden={!app.selectedNodeId}>
  {#if node}
    <div class="detail-header">
      <div class="row">
        <StatusPill status={node.status} />
        <span class="pid">{node.paper_section} · {node.paper_id}</span>
        {#if node.isCapstone}
          <span class="gn-flag capstone" style="font-size: 9.5px; padding: 1px 5px; border-radius: 3px;">CAPSTONE</span>
        {/if}
        <button class="close" onclick={close} aria-label="close"><Icon name="close" size={14} /></button>
      </div>
      <h2>{node.paper_name}</h2>
      <div style="display: flex; gap: 6px; margin-top: 12px; flex-wrap: wrap;">
        {#if sk !== 'PROVEN' && sk !== 'PROGRESS'}
          <RunAgentButton disabled={!allDepsProven && sk === 'BLOCKED'} status={sk} onrun={runAgent} />
        {/if}
        {#if sk === 'PROGRESS'}
          <button class="btn" onclick={() => (app.route = 'agents')}>
            <Icon name="activity" size={12} />View live run
          </button>
        {/if}
        <button class="btn" onclick={openPaperLean}>
          <Icon name="page" size={12} />Paper ⇄ Lean
        </button>
      </div>
    </div>

    <div class="detail-tabs">
      {#each [
        { id: 'overview', label: 'Overview', count: undefined },
        { id: 'mapping',  label: 'Mapping',  count: undefined },
        { id: 'lean',     label: 'Lean source', count: undefined },
        { id: 'attempts', label: 'Attempts', count: (node.attemptsLog || []).length },
        { id: 'sorries',  label: 'Subgoals', count: (node.sorries || []).length },
      ] as t (t.id)}
        <button
          class="detail-tab"
          class:active={tab === t.id}
          onclick={() => (tab = t.id as typeof tab)}
        >
          {t.label}
          {#if t.count !== undefined && t.count > 0}
            <span class="count">{t.count}</span>
          {/if}
        </button>
      {/each}
    </div>

    <div class="detail-body">
      {#if tab === 'overview'}
        <section class="detail-section">
          <h3>Statement (paper)</h3>
          <div class="paper-block">
            {#if node.paper_stmt}
              {node.paper_stmt}
            {:else}
              <span style="color: var(--fg-3); font-style: italic;">No paper statement linked yet — add a <span class="kbd" style="font-family: inherit;">% @lean:</span> decorator above the theorem in main.tex.</span>
            {/if}
          </div>
        </section>

        <section class="detail-section">
          <h3>Metadata</h3>
          <dl class="meta-grid">
            <dt>Paper file</dt><dd>{node.paper_file}{node.paper_section ? ` · ${node.paper_section}` : ''}</dd>
            <dt>Lean theorem</dt><dd>{node.lean_theorem}</dd>
            <dt>Lean file</dt><dd>{node.lean_file}{node.lean_line ? `:${node.lean_line}` : ''}</dd>
            <dt>Importance</dt><dd>
              <Meter value={node.importance} color="var(--accent)" />
              <span style="margin-left: 8px;">{(node.importance * 100).toFixed(0)}%</span>
            </dd>
            <dt>Difficulty</dt><dd style="text-transform: capitalize;">{node.difficulty}</dd>
            {#if node.confidence !== null && node.confidence !== undefined}
              <dt>Confidence</dt><dd>
                <Meter
                  value={node.confidence}
                  color={node.confidence > 0.7 ? 'var(--st-proven)' : node.confidence > 0.4 ? 'var(--st-sorries)' : 'var(--st-failed)'}
                />
                <span style="margin-left: 8px;">{(node.confidence * 100).toFixed(0)}%</span>
              </dd>
            {/if}
            <dt>Tokens spent</dt><dd>{node.tokens_spent.toLocaleString()}</dd>
            <dt>Attempts</dt><dd>{node.attempts}</dd>
          </dl>
        </section>

        {#if defsUsed.length > 0}
          <section class="detail-section">
            <h3>Uses definitions ({defsUsed.length})</h3>
            <div class="dep-list">
              {#each defsUsed as def (def.id)}
                <button class="dep-row" type="button" onclick={() => openDef(def.id)}>
                  <Icon name="cog" size={12} />
                  <span style="font-size: 10px; padding: 1px 6px; border-radius: 999px; background: var(--bg-3); color: var(--fg-3); text-transform: lowercase;">{def.kind}</span>
                  <code style="font-family: var(--font-mono); font-size: 11.5px; color: var(--fg-1);">{def.lean_name}</code>
                  <span class="name" style="font-size: 11px; color: var(--fg-3);">{def.name}</span>
                </button>
              {/each}
            </div>
          </section>
        {/if}

        {#if depsResolved.length > 0}
          <section class="detail-section">
            <h3>Depends on ({depsResolved.length})</h3>
            <div class="dep-list">
              {#each depsResolved as d (d.id)}
                <button class="dep-row" type="button" onclick={() => (app.selectedNodeId = d.id)}>
                  <Icon name="arrow_left" size={12} />
                  <StatusPill status={d.status} />
                  <span class="name">{d.paper_name}</span>
                  <span class="pid">{d.paper_id}</span>
                </button>
              {/each}
            </div>
          </section>
        {/if}

        {#if children.length > 0}
          <section class="detail-section">
            <h3>Used by ({children.length})</h3>
            <div class="dep-list">
              {#each children as d (d.id)}
                <button class="dep-row" type="button" onclick={() => (app.selectedNodeId = d.id)}>
                  <Icon name="arrow_right" size={12} />
                  <StatusPill status={d.status} />
                  <span class="name">{d.paper_name}</span>
                  <span class="pid">{d.paper_id}</span>
                </button>
              {/each}
            </div>
          </section>
        {/if}

        {#if node.note}
          <section class="detail-section">
            <h3>Notes</h3>
            <div style="font-size: 12px; color: var(--fg-2); line-height: 1.6;">{node.note}</div>
          </section>
        {/if}

      {:else if tab === 'mapping'}
        <section class="detail-section">
          <h3>Mapping declaration style</h3>
          <div style="display: flex; gap: 4px; margin-bottom: 12px; background: var(--bg-2); padding: 3px; border-radius: var(--r);">
            {#each [
              { id: 'comment', label: 'LaTeX % comment + Lean docstring' },
              { id: 'macro',   label: '\\leanref{} + @[paper] attr' },
              { id: 'sidecar', label: 'Sidecar mapping.yaml' },
            ] as v (v.id)}
              <button
                class="btn sm"
                style="flex: 1;"
                style:background={mappingVariant === v.id ? 'var(--bg-1)' : 'transparent'}
                style:border-color={mappingVariant === v.id ? 'var(--border)' : 'transparent'}
                onclick={() => (mappingVariant = v.id as typeof mappingVariant)}
              >{v.label}</button>
            {/each}
          </div>
        </section>

        <section class="detail-section">
          <h3>In LaTeX</h3>
          <pre class="code-block">{#if mappingVariant === 'comment'}% @lean: {node.lean_theorem}
% @file: {node.lean_file}
% @status: {node.status.toLowerCase()}
\begin{'{'}theorem{'}'}[{node.paper_id}]
\label{'{'}thm:{node.lean_theorem}{'}'}
{node.paper_stmt ? node.paper_stmt.slice(0, 140) + '...' : ''}
\end{'{'}theorem{'}'}{:else if mappingVariant === 'macro'}\begin{'{'}theorem{'}'}[{node.paper_id}]\leanref{'{'}{node.lean_theorem}{'}'}
\label{'{'}thm:{node.lean_theorem}{'}'}
{node.paper_stmt ? node.paper_stmt.slice(0, 140) + '...' : ''}
\end{'{'}theorem{'}'}{:else}# mathprover.yaml (sidecar)
- paper_id:   {node.paper_id}
  paper_loc:  {node.paper_file}#{node.paper_section}
  lean:       {node.lean_theorem}
  lean_file:  {node.lean_file}{node.lean_line ? `:${node.lean_line}` : ''}
  status:     {node.status.toLowerCase()}{/if}</pre>
        </section>

        <section class="detail-section">
          <h3>In Lean</h3>
          <pre class="code-block">{#if mappingVariant === 'comment'}{'/-- @paper: ' + node.paper_id}
    @section: {node.paper_section}
    "{node.paper_name}"
{'-/'}
theorem {node.lean_theorem} ...{:else if mappingVariant === 'macro'}@[paper "{node.paper_id}", section "{node.paper_section}"]
theorem {node.lean_theorem} ...{:else}-- referenced by mathprover.yaml; no inline decorator
theorem {node.lean_theorem} ...{/if}</pre>
        </section>

        <section class="detail-section">
          <h3>Why this matters</h3>
          <div style="font-size: 12px; color: var(--fg-2); line-height: 1.55;">
            The bidirectional mapping makes every paper claim a first-class object in the graph. When the LaTeX
            changes, MathProver re-runs the parser, flags stale Lean nodes, and surfaces them in the Frontier
            view marked <em>stale</em>. Without the decorator, the agent can still attack the Lean theorem but
            won't know which paper passage to cite for context.
          </div>
        </section>

      {:else if tab === 'lean'}
        {#if node.lean_stmt}
          <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px; font-family: var(--font-mono); font-size: 11px; color: var(--fg-3);">
            <Icon name="page" size={12} />
            <span>{node.lean_file}{node.lean_line ? `:${node.lean_line}` : ''}</span>
            <button class="btn ghost sm" style="margin-left: auto;">Open in VS Code</button>
          </div>
          <pre class="code-block">{@html highlightLean(node.lean_stmt)}</pre>
          <div class="detail-section" style="margin-top: 18px;">
            <h3>Axiom usage</h3>
            <div style="display: grid; grid-template-columns: auto 1fr; gap: 4px 14px; font-size: 12px; font-family: var(--font-mono);">
              <span style="color: var(--st-proven);">✓</span>
              <span style="color: var(--fg-1);">propext, Classical.choice, Quot.sound</span>
              <span style="color: var(--st-sorries);">!</span>
              <span style="color: var(--fg-1);">{(node.sorries && node.sorries.length) || 0} open sorry placeholders</span>
            </div>
          </div>
        {:else}
          <div style="color: var(--fg-3); text-align: center; padding: 40px; font-size: 12px;">
            No Lean source linked.<br />Run the agent to scaffold a theorem stub.
          </div>
        {/if}

      {:else if tab === 'attempts'}
        {#if !node.attemptsLog || node.attemptsLog.length === 0}
          <div style="color: var(--fg-3); text-align: center; padding: 40px; font-size: 12px;">No attempts logged yet.</div>
        {:else}
          <div class="detail-section">
            <h3>Git-backed branch graph</h3>
            <p style="font-size: 11.5px; color: var(--fg-3); margin: 0 0 4px; line-height: 1.55;">
              Each attempt is a real branch under <span class="kbd" style="font-family: var(--font-mono);">.mathprover/attempts/</span>.
              Failed approaches are dead ends; partial progress merges back to <span class="kbd" style="font-family: var(--font-mono);">main</span>.
              Click any branch to <span style="color: var(--accent);">git checkout</span> its Lean workspace state.
            </p>
            <GitGraph {node} />
          </div>

          <div class="detail-section">
            <h3>{node.attemptsLog.length} attempt{node.attemptsLog.length > 1 ? 's' : ''} — newest first</h3>
            {#each [...node.attemptsLog].reverse() as a (a.id)}
              <div class="attempt">
                <div class="attempt-head">
                  <StatusPill status={a.result === 'PARTIAL' ? 'SORRIES' : a.result === 'PROGRESS' ? 'PROGRESS' : a.result} />
                  <span class="agent">{a.agent}</span>
                  <span class="time">{a.duration} · {a.started.slice(11)}</span>
                </div>
                <div class="strategy"><strong style="color: var(--fg-0);">Strategy:</strong> {a.strategy}</div>
                <div class="cost">
                  <span>{a.tokens.toLocaleString()} tok</span>
                  <span>${a.cost.toFixed(2)}</span>
                  <span>{a.duration}</span>
                </div>
                <div class="why">{a.why}</div>
              </div>
            {/each}
          </div>
        {/if}

      {:else if tab === 'sorries'}
        {#if !node.sorries || node.sorries.length === 0}
          <div style="color: var(--fg-3); text-align: center; padding: 40px; font-size: 12px;">
            No open subgoals.
            {#if statusKey(node.status) === 'PROVEN'} Theorem is fully derived.{:else} Agent hasn't proposed any decomposition yet.{/if}
          </div>
        {:else}
          <div class="detail-section">
            <h3>Agent-proposed subgoals ({node.sorries.length})</h3>
            <p style="font-size: 12px; color: var(--fg-2); margin-top: 0; margin-bottom: 12px; line-height: 1.5;">
              If all subgoals are proven, the parent theorem is closed. Subgoals shared across multiple parents get
              <span class="promoted" style="margin-left: 4px;">promoted</span> to first-class nodes in the graph.
            </p>
            {#each node.sorries as s (s.name)}
              <div class="sorry-card">
                <div class="ttl">
                  {s.name}
                  {#if s.promoted}<span class="promoted">promoted ({s.sharedBy}× parents)</span>{/if}
                </div>
                <div class="desc">{s.desc}</div>
                <div class="imp">{s.implies}</div>
                <div style="display: flex; gap: 6px; margin-top: 8px;">
                  <button class="btn sm primary"><Icon name="play" size={10} />Dispatch agent</button>
                  <button class="btn sm">Edit subgoal</button>
                </div>
              </div>
            {/each}
          </div>
        {/if}
      {/if}
    </div>
  {/if}
</div>

<style>
  .dep-row, .detail-tab, .close { all: unset; cursor: pointer; }
</style>
