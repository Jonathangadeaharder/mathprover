<script lang="ts">
  import StatusPill from './StatusPill.svelte';
  import Icon from './Icon.svelte';
  import { app, tweaks } from '$lib/stores.svelte';
  import { NODES, NODE_BY_ID, CHILDREN_BY_ID, activeAgent } from '$lib/data';
  import { statusKey } from '$lib/lean';
  import type { TheoremNode, EdgeSufficiency } from '$lib/types';

  const NODE_W = 200;
  const NODE_H = 96;
  const LAYER_H = 150;
  const NODE_GAP = 36;

  type Pos = { x: number; y: number };

  function computeLayout(nodes: TheoremNode[], layout: string) {
    const byId: Record<string, TheoremNode> = Object.fromEntries(nodes.map((n) => [n.id, n]));
    const layerOf: Record<string, number> = {};

    function layer(id: string, visiting?: Set<string>): number {
      if (layerOf[id] !== undefined) return layerOf[id];
      const n = byId[id];
      if (!n) return 0;
      if (visiting?.has(id)) return 0;
      const next = new Set(visiting);
      next.add(id);
      const deps = (n.depends_on || []).filter((d) => byId[d]);
      const l = deps.length === 0 ? 0 : 1 + Math.max(...deps.map((d) => layer(d, next)));
      layerOf[id] = l;
      return l;
    }
    for (const n of nodes) layer(n.id);

    const layers: Record<number, string[]> = {};
    for (const n of nodes) {
      const L = layerOf[n.id];
      layers[L] = layers[L] || [];
      layers[L].push(n.id);
    }

    const positions: Record<string, Pos> = {};

    if (layout === 'dag') {
      Object.keys(layers).sort((a, b) => +a - +b).forEach((L) => {
        const ids = layers[+L];
        ids.sort((a, b) => (byId[b].importance || 0) - (byId[a].importance || 0));
        const arr: string[] = [];
        for (let i = 0; i < ids.length; i++) {
          if (i % 2 === 0) arr.push(ids[i]);
          else arr.unshift(ids[i]);
        }
        const total = arr.length * (NODE_W + NODE_GAP) - NODE_GAP;
        arr.forEach((id, i) => {
          positions[id] = { x: 400 - total / 2 + i * (NODE_W + NODE_GAP), y: 80 + +L * LAYER_H };
        });
      });
    } else if (layout === 'radial') {
      const maxL = Math.max(...Object.values(layerOf));
      const cx = 600, cy = 400;
      Object.entries(layers).forEach(([L, ids]) => {
        const lvl = +L;
        const r = (maxL - lvl) * 200 + 80;
        if (lvl === maxL) {
          ids.forEach((id, i) => {
            positions[id] = { x: cx - NODE_W / 2 + (i - (ids.length - 1) / 2) * (NODE_W + 30), y: cy };
          });
        } else {
          ids.forEach((id, i) => {
            const ang = (i / Math.max(ids.length, 1)) * Math.PI - Math.PI / 2;
            positions[id] = {
              x: cx + Math.cos(ang) * r - NODE_W / 2,
              y: cy + Math.sin(ang) * r - NODE_H / 2 + (maxL - lvl) * 30,
            };
          });
        }
      });
    } else {
      Object.keys(layers).sort((a, b) => +a - +b).forEach((L) => {
        const ids = layers[+L];
        ids.forEach((id, i) => {
          positions[id] = {
            x: 200 + i * (NODE_W + 60) + Math.sin((+L + i) * 1.7) * 30,
            y: 60 + +L * LAYER_H + Math.cos(i * 0.9) * 20,
          };
        });
      });
    }

    return positions;
  }

  let visibleNodes = $derived(
    tweaks.show_proven ? NODES : NODES.filter((n) => statusKey(n.status) !== 'PROVEN')
  );
  let positions = $derived(computeLayout(visibleNodes, tweaks.graph_layout));

  let drag = $state({ x: 0, y: 0, scale: 0.85 });
  let panning = $state<{ x: number; y: number; dx: number; dy: number } | null>(null);
  let nodePos = $state<Record<string, Pos>>({});
  let nodeDrag = $state<{ id: string; startX: number; startY: number; baseX: number; baseY: number } | null>(null);
  let stageEl: HTMLDivElement;

  $effect(() => { void tweaks.graph_layout; void tweaks.show_proven; nodePos = {}; centerView(); });

  let related = $derived.by(() => {
    const focus = app.hoveredId || app.selectedNodeId;
    if (!focus) return null;
    const all = new Set<string>([focus]);
    function up(id: string) { (NODE_BY_ID[id]?.depends_on || []).forEach((d) => { if (!all.has(d)) { all.add(d); up(d); } }); }
    function dn(id: string) { (CHILDREN_BY_ID[id] || []).forEach((c) => { if (!all.has(c)) { all.add(c); dn(c); } }); }
    up(focus); dn(focus);
    return all;
  });

  function resolvePos(id: string): Pos {
    return nodePos[id] || positions[id] || { x: 0, y: 0 };
  }

  let edges = $derived.by(() => {
    const out: { key: string; path: string; isHi: boolean; isDim: boolean; suff: EdgeSufficiency }[] = [];
    visibleNodes.forEach((n) => {
      (n.depends_on || []).forEach((d) => {
        if (!positions[d] || !positions[n.id]) return;
        const from = resolvePos(d);
        const to = resolvePos(n.id);
        const x1 = from.x + NODE_W / 2;
        const y1 = from.y + NODE_H;
        const x2 = to.x + NODE_W / 2;
        const y2 = to.y;
        const mid = (y1 + y2) / 2;
        const path = `M ${x1} ${y1} C ${x1} ${mid}, ${x2} ${mid}, ${x2} ${y2}`;
        const isHi = related ? (related.has(d) && related.has(n.id)) : false;
        const isDim = related ? !isHi : false;
        const childSk = statusKey(NODE_BY_ID[d]?.status || '');
        const parentSk = statusKey(n.status);
        let suff: EdgeSufficiency = 'unknown';
        const override = n.sufficiencyOverride?.[d];
        if (override) {
          suff = override;
        } else if (childSk === 'PROVEN' && parentSk === 'PROVEN') {
          suff = 'sufficient';
        } else if (childSk === 'PROVEN' && ['SORRIES', 'STUCK', 'BLOCKED', 'IN_PROGRESS', 'DRAFT'].includes(parentSk)) {
          suff = 'insufficient';
        }
        out.push({ key: `${d}->${n.id}`, path, isHi, isDim, suff });
      });
    });
    return out;
  });

  function onWheel(e: WheelEvent) {
    e.preventDefault();
    const delta = -e.deltaY * 0.001;
    const newScale = Math.min(2.2, Math.max(0.2, drag.scale + delta));
    const rect = stageEl.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const k = newScale / drag.scale;
    drag = { scale: newScale, x: mx - (mx - drag.x) * k, y: my - (my - drag.y) * k };
  }

  function onMouseDown(e: MouseEvent) {
    const target = e.target as HTMLElement;
    if (target.closest('.gnode')) return;
    panning = { x: e.clientX, y: e.clientY, dx: drag.x, dy: drag.y };
  }

  function onMouseMove(e: MouseEvent) {
    if (nodeDrag) {
      const dx = (e.clientX - nodeDrag.startX) / drag.scale;
      const dy = (e.clientY - nodeDrag.startY) / drag.scale;
      nodePos = { ...nodePos, [nodeDrag.id]: { x: nodeDrag.baseX + dx, y: nodeDrag.baseY + dy } };
      return;
    }
    if (!panning) return;
    drag = { ...drag, x: panning.dx + e.clientX - panning.x, y: panning.dy + e.clientY - panning.y };
  }

  function endDrag() { panning = null; nodeDrag = null; }

  function nodeStartDrag(e: MouseEvent, id: string, base: Pos) {
    e.stopPropagation();
    nodeDrag = { id, startX: e.clientX, startY: e.clientY, baseX: base.x, baseY: base.y };
  }

  function zoom(by: number) {
    const rect = stageEl.getBoundingClientRect();
    const mx = rect.width / 2;
    const my = rect.height / 2;
    const ns = Math.min(2.2, Math.max(0.2, drag.scale * by));
    const k = ns / drag.scale;
    drag = { scale: ns, x: mx - (mx - drag.x) * k, y: my - (my - drag.y) * k };
  }

  function centerView(scale = 0.85) {
    if (!stageEl) return;
    const rect = stageEl.getBoundingClientRect();
    const ps = visibleNodes.map((n) => positions[n.id]).filter(Boolean);
    if (ps.length === 0) { drag = { x: 0, y: 0, scale }; return; }
    const xs = ps.map((p) => p.x);
    const ys = ps.map((p) => p.y);
    const cx = (Math.min(...xs) + Math.max(...xs) + NODE_W) / 2;
    const cy = (Math.min(...ys) + Math.max(...ys) + NODE_H) / 2;
    drag = { scale, x: rect.width / 2 - cx * scale, y: rect.height / 2 - cy * scale };
  }

  function fit() { centerView(); nodePos = {}; }

  const legend = ['PROVEN','DISPROVEN','SORRIES','IN_PROGRESS','STUCK','DRAFT','REJECTED','BLOCKED','READY','UNEXPLORED'];
  const activeRun = $derived(activeAgent());
</script>

<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<div
  class="graph-stage"
  bind:this={stageEl}
  onmousedown={onMouseDown}
  onmousemove={onMouseMove}
  onmouseup={endDrag}
  onmouseleave={endDrag}
  onwheel={onWheel}
  onkeydown={(e) => {
    if (e.key === 'Escape') { app.selectedNodeId = null; }
    else if (e.key === '=' || e.key === '+') { zoom(1.15); e.preventDefault(); }
    else if (e.key === '-') { zoom(0.85); e.preventDefault(); }
  }}
  role="application"
  aria-label="Theorem dependency graph"
  tabindex="0"
>
  <div class="graph-canvas" style:transform="translate({drag.x}px, {drag.y}px) scale({drag.scale})">
    <svg class="graph-svg" style="width: 2400px; height: 1600px; overflow: visible; position: absolute; pointer-events: none;">
      <defs>
        <marker id="arrow" viewBox="0 -3 6 6" refX="6" refY="0" markerWidth="6" markerHeight="6" orient="auto">
          <path d="M0,-3 L6,0 L0,3 Z" class="edge-arrow" />
        </marker>
        <marker id="arrow-hi" viewBox="0 -3 6 6" refX="6" refY="0" markerWidth="6" markerHeight="6" orient="auto">
          <path d="M0,-3 L6,0 L0,3 Z" class="edge-arrow highlighted" />
        </marker>
        <marker id="arrow-sufficient" viewBox="0 -3 6 6" refX="6" refY="0" markerWidth="6" markerHeight="6" orient="auto">
          <path d="M0,-3 L6,0 L0,3 Z" class="edge-arrow suff-sufficient" />
        </marker>
        <marker id="arrow-insufficient" viewBox="0 -3 6 6" refX="6" refY="0" markerWidth="6" markerHeight="6" orient="auto">
          <path d="M0,-3 L6,0 L0,3 Z" class="edge-arrow suff-insufficient" />
        </marker>
      </defs>
      {#each edges as e (e.key)}
        <path
          d={e.path}
          class="edge"
          class:highlighted={e.isHi}
          class:dimmed={e.isDim}
          class:suff-sufficient={e.suff === 'sufficient'}
          class:suff-insufficient={e.suff === 'insufficient'}
          marker-end={e.isHi ? 'url(#arrow-hi)' : e.suff !== 'unknown' ? `url(#arrow-${e.suff === 'sufficient' ? 'sufficient' : 'insufficient'})` : 'url(#arrow)'}
        />
      {/each}
    </svg>

    {#each visibleNodes as n (n.id)}
      {@const p = resolvePos(n.id)}
      {@const sk = statusKey(n.status)}
      {@const isDim = related ? !related.has(n.id) : false}
      {@const isSel = app.selectedNodeId === n.id}
      {@const isActiveRun = activeRun?.node === n.id || activeRun?.node === n.proof_folder}
      <div
        class="gnode"
        class:selected={isSel}
        class:dimmed={isDim}
        class:active-run={isActiveRun}
        data-status={sk}
        style:left="{p.x}px"
        style:top="{p.y}px"
        style:width="{NODE_W}px"
        onmousedown={(e) => nodeStartDrag(e, n.id, p)}
        onclick={(e) => { e.stopPropagation(); app.selectedNodeId = n.id; }}
        onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); e.stopPropagation(); app.selectedNodeId = n.id; } }}
        onmouseenter={() => (app.hoveredId = n.id)}
        onmouseleave={() => (app.hoveredId = null)}
        role="button"
        tabindex="0"
        title={isActiveRun ? `${activeRun?.agent} running since ${activeRun?.started}` : n.paper_name}
      >
        {#if isActiveRun}<span class="run-ring" aria-hidden="true"></span>{/if}
        <div class="gn-id">
          <span>{n.paper_id}</span>
          {#if n.isCapstone}<span class="gn-flag capstone">capstone</span>{/if}
          {#if isActiveRun}<span class="gn-flag running">{activeRun?.agent || 'running'}</span>{:else if sk === 'READY' && !n.isCapstone}<span class="gn-flag frontier">frontier</span>{/if}
        </div>
        <div class="gn-title">{n.paper_name}</div>
        {#if n.paper_section}
          <div class="gn-origin">{n.paper_section}</div>
        {/if}
        {#if n.lean_theorem && n.lean_theorem !== n.id && n.lean_theorem !== n.paper_id}
          <div class="gn-theorem" title={n.lean_theorem}>{n.lean_theorem}</div>
        {/if}
        <div class="gn-meta">
          <StatusPill status={n.status} />
          <span style="margin-left: auto;">
            {n.attempts > 0 ? `${n.attempts} attempt${n.attempts > 1 ? 's' : ''}` : '—'}
          </span>
        </div>
        {#if n.attemptsLog && n.attemptsLog.length > 0}
          {@const agentCounts = n.attemptsLog.reduce((acc, a) => { acc[a.agent] = (acc[a.agent] || 0) + 1; return acc; }, {} as Record<string, number>)}
          <div class="gn-agents">
            {#each Object.entries(agentCounts) as [agent, count] (agent)}
              <span class="agent-chip">{agent} {count}</span>
            {/each}
          </div>
        {/if}
        {#if n.confidence !== null && n.confidence !== undefined}
          <div class="gn-conf" title={`confidence ${((n.confidence) * 100).toFixed(0)}%`}>
            <div class="gn-conf-fill" style:width="{n.confidence * 100}%"></div>
          </div>
        {/if}
      </div>
    {/each}
  </div>

  <div class="graph-legend">
    {#each legend as s (s)}
      <div class="row">
        <span class="swatch" style:border-color="var(--st-{s.toLowerCase()})" style:background="var(--st-{s.toLowerCase()}-bg)"></span>
        <span style="font-family: var(--font-mono); font-size: 10.5px;">{s.toLowerCase()}</span>
      </div>
    {/each}
  </div>

  <div class="zoom-controls">
    <button onclick={() => zoom(0.85)} title="zoom out"><Icon name="minus" size={14} /></button>
    <div class="zoom-label">{Math.round(drag.scale * 100)}%</div>
    <button onclick={() => zoom(1.15)} title="zoom in"><Icon name="plus" size={14} /></button>
    <button onclick={fit} title="fit"><Icon name="maximize" size={14} /></button>
  </div>
</div>
