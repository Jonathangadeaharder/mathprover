<script lang="ts">
  import StatusPill from './StatusPill.svelte';
  import Icon from './Icon.svelte';
  import Meter from './Meter.svelte';
  import RunAgentButton from './RunAgentButton.svelte';
  import GitGraph from './GitGraph.svelte';
  import { app } from '$lib/stores.svelte';
  import { NODE_BY_ID, CHILDREN_BY_ID, DEF_BY_ID, foundationsForNode } from '$lib/data';
  import type { Foundation } from '$lib/types';
  import { highlightLean, statusKey } from '$lib/lean';

  type Tab = 'overview' | 'paper' | 'lean' | 'mapping' | 'attempts' | 'sorries';

  let node = $derived(app.selectedNodeId ? NODE_BY_ID[app.selectedNodeId] : null);
  let tab = $state<Tab>('overview');
  let mappingVariant = $state<'comment' | 'macro' | 'sidecar'>('comment');

  let paperSource = $state<string | null>(null);
  let leanSource = $state<string | null>(null);
  let statusMd = $state<string | null>(null);
  let sourceLoading = $state(false);

  async function loadNodeSource() {
    if (!node || !app.projectRoot) { paperSource = null; leanSource = null; statusMd = null; return; }
    sourceLoading = true;
    try {
      const folder = node.proof_folder || node.id;
      const params = new URLSearchParams({ project: app.projectRoot, node: node.id, folder });
      const res = await fetch(`/api/node-source?${params}`);
      if (res.ok) {
        const data = await res.json();
        paperSource = data.paper;
        leanSource = data.lean;
        statusMd = data.status;
      } else {
        paperSource = null;
        leanSource = null;
        statusMd = null;
      }
    } catch {
      paperSource = null;
      leanSource = null;
      statusMd = null;
    }
    sourceLoading = false;
  }

  $effect(() => {
    void app.selectedNodeId;
    tab = 'overview';
    loadNodeSource();
  });

  let sk = $derived(node ? statusKey(node.status) : 'UNEXPLORED');
  let depsResolved = $derived(node ? (node.depends_on || []).map((d) => NODE_BY_ID[d]).filter(Boolean) : []);
  let children = $derived(node ? (CHILDREN_BY_ID[node.id] || []).map((c) => NODE_BY_ID[c]).filter(Boolean) : []);
  let defsUsed = $derived(node ? (node.uses_defs || []).map((d) => DEF_BY_ID[d]).filter(Boolean) : []);
  let scopes = $derived(node ? foundationsForNode(node.id) : []);

  function scopeAccent(scope: Foundation) {
    if (scope.kind === 'paper') return { bg: 'var(--st-proven-bg)', fg: 'var(--st-proven)' };
    if (scope.kind === 'shared') return { bg: 'var(--st-sorries-bg)', fg: 'var(--st-sorries)' };
    return { bg: 'var(--bg-3)', fg: 'var(--fg-3)' };
  }

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
        <span class="pid">{node.paper_id}{node.paper_section ? ` · ${node.paper_section}` : ''}</span>
        {#if node.isCapstone}
          <span class="gn-flag capstone-flag">CAPSTONE</span>
        {/if}
        <button class="close" onclick={close} aria-label="close"><Icon name="close" size={14} /></button>
      </div>
      <h2>{node.paper_name}</h2>
      <div class="detail-lean-theorem mono-sm" style="margin-top: 2px;">
        {node.lean_theorem}
      </div>
      {#if scopes.length > 0}
        <div class="flex-gap-sm" style="margin-top: 10px; flex-wrap: wrap; align-items: center;">
          <span class="section-label" style="margin: 0;">Workstream</span>
          {#each scopes as scope (scope.id)}
            {@const tone = scopeAccent(scope)}
            <span class="kind-pill" style:background={tone.bg} style:color={tone.fg}>
              {scope.kind ?? 'foundation'} · {scope.name}
            </span>
          {/each}
        </div>
      {/if}

      <div class="flex-gap-sm" style="margin-top: 12px; flex-wrap: wrap;">
        {#if sk !== 'PROVEN' && sk !== 'IN_PROGRESS' && sk !== 'DISPROVEN' && sk !== 'REJECTED'}
          <RunAgentButton disabled={!allDepsProven && sk === 'BLOCKED'} status={sk} onrun={runAgent} />
        {/if}
        {#if sk === 'IN_PROGRESS'}
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
        { id: 'paper',    label: 'Paper source', count: undefined },
        { id: 'lean',     label: 'Lean code', count: undefined },
        { id: 'mapping',  label: 'Mapping',  count: undefined },
        { id: 'attempts', label: 'Attempts', count: (node.attemptsLog || []).length },
        { id: 'sorries',  label: 'Subgoals', count: (node.sorries || []).length },
      ] as t (t.id)}
        <button
          class="detail-tab"
          class:active={tab === t.id}
          onclick={() => (tab = t.id as Tab)}
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
              <span class="italic-fg3">No paper statement linked yet — add a <span class="kbd kbd-mono">% @lean:</span> decorator above the theorem in main.tex.</span>
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
              <span class="pct-label">{(node.importance * 100).toFixed(0)}%</span>
            </dd>
            <dt>Difficulty</dt><dd class="capitalize">{node.difficulty}</dd>
            {#if node.confidence !== null && node.confidence !== undefined}
              <dt>Confidence</dt><dd>
                <Meter
                  value={node.confidence}
                  color={node.confidence > 0.7 ? 'var(--st-proven)' : node.confidence > 0.4 ? 'var(--st-sorries)' : 'var(--st-stuck)'}
                />
                <span class="pct-label">{(node.confidence * 100).toFixed(0)}%</span>
              </dd>
            {/if}
            <dt>Tokens spent</dt><dd>{node.tokens_spent.toLocaleString()}</dd>
            <dt>Attempts</dt><dd>{node.attempts}</dd>
          </dl>
        </section>

        {#if scopes.length > 0}
          <section class="detail-section">
            <h3>Workstream rationale</h3>
            <div class="flex-gap-sm" style="flex-wrap: wrap;">
              {#each scopes as scope (scope.id)}
                {@const tone = scopeAccent(scope)}
                <span class="kind-pill" style:background={tone.bg} style:color={tone.fg}>
                  {scope.kind ?? 'foundation'} · {scope.name}
                </span>
              {/each}
            </div>
            <p class="meta-text" style="margin: 8px 0 0;">
              The first badge is the primary reading. Paper-facing work outranks shared work, and shared work outranks foundation work when a theorem sits in multiple streams.
            </p>
          </section>
        {/if}

        {#if defsUsed.length > 0}
          <section class="detail-section">
            <h3>Uses definitions ({defsUsed.length})</h3>
            <div class="dep-list">
              {#each defsUsed as def (def.id)}
                <button class="dep-row" type="button" onclick={() => openDef(def.id)}>
                  <Icon name="cog" size={12} />
                  <span class="kind-pill">{def.kind}</span>
                  <code class="mono-code">{def.lean_name}</code>
                  <span class="name name-sm-fg3">{def.name}</span>
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

        {#if sk !== 'PROVEN' && sk !== 'DISPROVEN' && sk !== 'REJECTED'}
          <section class="detail-section">
            <h3>Decompose into sub-lemmas</h3>
            <p class="split-desc">
              Split this node into smaller, independently provable sub-lemmas. Each sub-lemma becomes a child node in the graph.
            </p>
            <button class="btn sm" disabled title="Split decomposition requires agent integration">
              <Icon name="split" size={11} />Split into sub-lemmas
            </button>
          </section>
        {/if}

        {#if node.note}
          <section class="detail-section">
            <h3>Notes</h3>
            <div class="detail-note">{node.note}</div>
          </section>
        {/if}

      {:else if tab === 'paper'}
        <section class="detail-section">
          <h3>paper_source.md</h3>
          <div class="file-path-row">
            <Icon name="page" size={12} />
            <span>proofs/{node.proof_folder || node.id}/paper_source.md</span>
          </div>
          {#if sourceLoading}
            <div class="empty-state">Loading...</div>
          {:else if paperSource}
            <pre class="code-block paper-source">{paperSource}</pre>
          {:else}
            <div class="empty-state">
              No paper_source.md found for this node.
            </div>
          {/if}
        </section>

        {#if statusMd}
          <section class="detail-section">
            <h3>status.md</h3>
            <pre class="code-block status-source">{statusMd}</pre>
          </section>
        {/if}

      {:else if tab === 'lean'}
        <section class="detail-section">
          <h3>attempt.lean</h3>
          <div class="file-path-row">
            <Icon name="page" size={12} />
            <span>proofs/{node.proof_folder || node.id}/attempt.lean</span>
          </div>
          {#if sourceLoading}
            <div class="empty-state">Loading...</div>
          {:else if leanSource}
            <pre class="code-block">{@html highlightLean(leanSource)}</pre>
          {:else if node.lean_stmt}
            <pre class="code-block">{@html highlightLean(node.lean_stmt)}</pre>
          {:else}
            <div class="empty-state">
              No Lean source found for this node.
            </div>
          {/if}
        </section>

        {#if leanSource || node.lean_stmt}
          <div class="detail-section detail-section-mt">
            <h3>Axiom usage</h3>
            <div class="axiom-grid">
              <span class="axiom-ok">✓</span>
              <span class="axiom-text">propext, Classical.choice, Quot.sound</span>
              {#if leanSource && leanSource.includes('sorry')}
                <span class="axiom-warn">!</span>
                <span class="axiom-text">Contains open sorry placeholders</span>
              {:else if node.sorries && node.sorries.length > 0}
                <span class="axiom-warn">!</span>
                <span class="axiom-text">{node.sorries.length} open sorry placeholders</span>
              {:else}
                <span class="axiom-ok">✓</span>
                <span class="axiom-text">No sorry placeholders</span>
              {/if}
            </div>
          </div>
        {/if}

      {:else if tab === 'mapping'}
        <section class="detail-section">
          <h3>Mapping declaration style</h3>
          <div class="map-seg-bar">
            {#each [
              { id: 'comment', label: 'LaTeX % comment + Lean docstring' },
              { id: 'macro',   label: '\\leanref{} + @[paper] attr' },
              { id: 'sidecar', label: 'Sidecar mapping.yaml' },
            ] as v (v.id)}
              <button
                class="btn sm map-seg-btn"
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
          <div class="meta-text">
            The bidirectional mapping makes every paper claim a first-class object in the graph. When the LaTeX
            changes, MathProver re-runs the parser, flags stale Lean nodes, and surfaces them in the Frontier
            view marked <em>stale</em>. Without the decorator, the agent can still attack the Lean theorem but
            won't know which paper passage to cite for context.
          </div>
        </section>

      {:else if tab === 'attempts'}
        {#if !node.attemptsLog || node.attemptsLog.length === 0}
          <div class="empty-state">No attempts logged yet.</div>
        {:else}
          <div class="detail-section">
            <h3>Git-backed branch graph</h3>
            <p class="split-desc" style="font-size: 11.5px; margin: 0 0 4px;">
              Each attempt is a real branch under <span class="kbd kbd-mono">.mathprover/attempts/</span>.
              Failed approaches are dead ends; partial progress merges back to <span class="kbd kbd-mono">main</span>.
              Click any branch to <span class="accent-text">git checkout</span> its Lean workspace state.
            </p>
            <GitGraph {node} />
          </div>

          <div class="detail-section">
            <h3>{node.attemptsLog.length} attempt{node.attemptsLog.length > 1 ? 's' : ''} — newest first</h3>
            {#each [...node.attemptsLog].reverse() as a (a.id)}
              <div class="attempt">
                <div class="attempt-head">
                  <StatusPill status={a.result === 'PARTIAL' ? 'SORRIES' : a.result === 'PROGRESS' ? 'IN_PROGRESS' : a.result === 'FAILED' ? 'STUCK' : a.result} />
                  <span class="agent">{a.agent}</span>
                  <span class="time">{a.duration} · {a.started.slice(11)}</span>
                </div>
                <div class="strategy"><strong class="fg-0">Strategy:</strong> {a.strategy}</div>
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
          <div class="empty-state">
            {#if statusKey(node.status) === 'PROVEN'} Theorem is fully derived.{:else} Agent hasn't proposed any decomposition yet.{/if}
          </div>
        {:else}
          <div class="detail-section">
            <h3>Agent-proposed subgoals ({node.sorries.length})</h3>
            <p class="meta-text" style="margin-top: 0; margin-bottom: 12px;">
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
                <div class="flex-gap-sm" style="margin-top: 8px;">
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
