<script lang="ts">
  import StatusPill from './StatusPill.svelte';
  import Icon from './Icon.svelte';
  import { app, tweaks } from '$lib/stores.svelte';
  import { ACTIVE_NODES, NODE_BY_ID, CHILDREN_BY_ID, activeAgent, primaryFoundationForNode } from '$lib/data';
  import { statusKey } from '$lib/lean';
  import type { TheoremNode, EdgeSufficiency } from '$lib/types';

  const NODE_W = 200;
  const NODE_H = 96;
  const GRID_X = NODE_W + 38;
  const GRID_Y = NODE_H + 24;
  const LANE_GAP = 76;
  const TOP_MARGIN = 96;
  const LEFT_MARGIN = 96;

  type Pos = { x: number; y: number };
  type Lane = {
    key: string;
    label: string;
    subtitle: string;
    kind: string;
    count: number;
    x: number;
    y: number;
    w: number;
    h: number;
  };

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

    function statusScore(id: string): number {
      const sk = statusKey(byId[id]?.status || '');
      const order: Record<string, number> = {
        PROVEN: 0,
        READY: 1,
        IN_PROGRESS: 2,
        SORRIES: 3,
        BLOCKED: 4,
        STUCK: 5,
        DRAFT: 6,
        REJECTED: 7,
        DISPROVEN: 8,
        UNEXPLORED: 9,
      };
      return order[sk] ?? 9;
    }

    function groupOrder(id: string): [number, string, number, string] {
      const scope = primaryFoundationForNode(id);
      const kindRank = scope?.kind === 'paper' ? 0 : scope?.kind === 'shared' ? 1 : 2;
      const name = scope?.name ?? 'unscoped';
      return [kindRank, name, statusScore(id), id];
    }

    if (layout === 'dag') {
      const groups = new Map<string, string[]>();
      for (const n of nodes) {
        const scope = primaryFoundationForNode(n.id);
        const key = scope ? `${scope.kind ?? 'foundation'}::${scope.name}` : 'zz::Needs workstream';
        groups.set(key, [...(groups.get(key) || []), n.id]);
      }

      function naturalRank(id: string): [number, number, number, string] {
        const n = byId[id];
        const text = `${n.paper_id} ${n.id}`;
        const c2 = text.match(/\bC2[_\s-]*M(\d+)/i);
        const crn = text.match(/\bCRN[_\s-]*R(\d+)/i);
        const m = text.match(/\bM(\d+)/i);
        if (n.isCapstone) return [0, 0, statusScore(id), id];
        if (c2) return [1, Number(c2[1]), statusScore(id), id];
        if (crn) return [2, Number(crn[1]), statusScore(id), id];
        if (m) return [3, Number(m[1]), statusScore(id), id];
        return [4, layerOf[id] ?? 0, statusScore(id), id];
      }

      const orderedGroups = [...groups.entries()]
        .map(([key, ids]) => ({
          key,
          ids: [...ids].sort((a, b) => {
            const ra = naturalRank(a);
            const rb = naturalRank(b);
            for (let i = 0; i < ra.length; i++) {
              if (ra[i] !== rb[i]) return typeof ra[i] === 'string'
                ? String(ra[i]).localeCompare(String(rb[i]))
                : Number(ra[i]) - Number(rb[i]);
            }
            return a.localeCompare(b);
          }),
          order: groupOrder(ids[0]),
        }))
        .sort((a, b) => {
          const [ka, na, sa, ia] = a.order;
          const [kb, nb, sb, ib] = b.order;
          if (ka !== kb) return ka - kb;
          if (na !== nb) return na.localeCompare(nb);
          if (sa !== sb) return sa - sb;
          return ia.localeCompare(ib);
        });

      function placeGroup(group: { ids: string[] }, x: number, y: number, columns: number): number {
        const rows = Math.ceil(group.ids.length / columns);
        group.ids.forEach((id, i) => {
          const col = i % columns;
          const row = Math.floor(i / columns);
          positions[id] = {
            x: x + col * GRID_X,
            y: y + row * GRID_Y,
          };
        });
        return rows * GRID_Y;
      }

      const [primary, ...secondary] = orderedGroups;
      let yCursor = TOP_MARGIN;
      if (primary) {
        const primaryColumns = primary.ids.length >= 16 ? 5 : Math.max(3, Math.min(5, Math.ceil(primary.ids.length / 3)));
        yCursor += placeGroup(primary, LEFT_MARGIN, yCursor, primaryColumns) + LANE_GAP;
      }

      const secondaryColumns = 2;
      const secondaryWidth = NODE_W + (secondaryColumns - 1) * GRID_X;
      const laneColumnGap = 72;
      const xColumns = [
        LEFT_MARGIN,
        LEFT_MARGIN + secondaryWidth + laneColumnGap,
        LEFT_MARGIN + (secondaryWidth + laneColumnGap) * 2,
      ];
      const yColumns = xColumns.map(() => yCursor);

      for (const group of secondary) {
        const colIndex = yColumns.reduce((best, y, i) => (y < yColumns[best] ? i : best), 0);
        const columns = Math.min(secondaryColumns, Math.max(1, group.ids.length));
        const usedHeight = placeGroup(group, xColumns[colIndex], yColumns[colIndex], columns);
        yColumns[colIndex] += usedHeight + LANE_GAP;
      }
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
            y: 60 + +L * 150 + Math.cos(i * 0.9) * 20,
          };
        });
      });
    }

    return positions;
  }

  let visibleNodes = $derived(
    tweaks.show_proven ? ACTIVE_NODES : ACTIVE_NODES.filter((n) => statusKey(n.status) !== 'PROVEN')
  );
  let positions = $derived(computeLayout(visibleNodes, tweaks.graph_layout));

  let drag = $state({ x: 0, y: 0, scale: 0.85 });
  let panning = $state<{ x: number; y: number; dx: number; dy: number } | null>(null);
  let nodePos = $state<Record<string, Pos>>({});
  let nodeDrag = $state<{ id: string; startX: number; startY: number; baseX: number; baseY: number } | null>(null);
  let stageEl: HTMLDivElement;

  $effect(() => {
    void tweaks.graph_layout;
    void tweaks.show_proven;
    void visibleNodes.length;
    void Object.keys(positions).length;
    nodePos = {};
    centerView();
  });

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
        const dx = to.x - from.x;
        const dy = to.y - from.y;
        let path: string;
        if (Math.abs(dx) > Math.abs(dy) * 0.7) {
          const leftToRight = dx >= 0;
          const x1 = leftToRight ? from.x + NODE_W : from.x;
          const y1 = from.y + NODE_H / 2;
          const x2 = leftToRight ? to.x : to.x + NODE_W;
          const y2 = to.y + NODE_H / 2;
          const mid = (x1 + x2) / 2;
          path = `M ${x1} ${y1} C ${mid} ${y1}, ${mid} ${y2}, ${x2} ${y2}`;
        } else {
          const topToBottom = dy >= 0;
          const x1 = from.x + NODE_W / 2;
          const y1 = topToBottom ? from.y + NODE_H : from.y;
          const x2 = to.x + NODE_W / 2;
          const y2 = topToBottom ? to.y : to.y + NODE_H;
          const mid = (y1 + y2) / 2;
          path = `M ${x1} ${y1} C ${x1} ${mid}, ${x2} ${mid}, ${x2} ${y2}`;
        }
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

  let lanes = $derived.by<Lane[]>(() => {
    const grouped = new Map<string, { label: string; subtitle: string; kind: string; ids: string[] }>();
    for (const n of visibleNodes) {
      const scope = primaryFoundationForNode(n.id);
      const key = scope ? `${scope.kind ?? 'foundation'}::${scope.name}` : 'zz::Needs workstream';
      const label = scope ? scope.name : 'Needs workstream';
      const subtitle = scope
        ? (scope.subgoals?.length
          ? scope.subgoals.map((s) => s.desc).slice(0, 2).join(' -> ')
          : scope.summary || scope.citation || '')
        : 'Unassigned artifacts that need a parent paper or library objective.';
      const kind = scope?.kind ?? 'unscoped';
      grouped.set(key, {
        label,
        subtitle,
        kind,
        ids: [...(grouped.get(key)?.ids || []), n.id],
      });
    }
    return [...grouped.entries()].map(([key, g]) => {
      const ps = g.ids.map((id) => resolvePos(id)).filter(Boolean);
      const minX = Math.min(...ps.map((p) => p.x));
      const minY = Math.min(...ps.map((p) => p.y));
      const maxX = Math.max(...ps.map((p) => p.x + NODE_W));
      const maxY = Math.max(...ps.map((p) => p.y + NODE_H));
      return {
        key,
        label: g.label,
        subtitle: g.subtitle,
        kind: g.kind,
        count: g.ids.length,
        x: minX - 18,
        y: minY - 54,
        w: maxX - minX + 36,
        h: maxY - minY + 72,
      };
    });
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

  function centerView(scale = 0.85, fit = false) {
    if (!stageEl) return;
    const rect = stageEl.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) {
      drag = { x: drag.x, y: drag.y, scale: drag.scale || scale };
      return;
    }
    const ps = visibleNodes.map((n) => positions[n.id]).filter(Boolean);
    if (ps.length === 0) { drag = { x: 0, y: 0, scale }; return; }
    const minX = Math.min(...ps.map((p) => p.x));
    const minY = Math.min(...ps.map((p) => p.y));
    const maxX = Math.max(...ps.map((p) => p.x + NODE_W));
    const maxY = Math.max(...ps.map((p) => p.y + NODE_H));
    const cx = (minX + maxX) / 2;
    const cy = (minY + maxY) / 2;

    let targetScale = scale;
    if (fit && !app.projectRoot.includes("test-project")) {
      const fitScale = Math.min(
        scale,
        (rect.width - 48) / Math.max(1, maxX - minX),
        (rect.height - 48) / Math.max(1, maxY - minY),
      );
      targetScale = Math.max(0.38, Math.min(scale, fitScale));
    }

    drag = {
      scale: targetScale,
      x: rect.width / 2 - cx * targetScale + 40,
      y: rect.height / 2 - cy * targetScale,
    };
  }

  function fit() { centerView(0.85, true); nodePos = {}; }

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
    {#each lanes as lane (lane.key)}
      <div
        class="graph-lane"
        data-kind={lane.kind}
        style:left="{lane.x}px"
        style:top="{lane.y}px"
        style:width="{lane.w}px"
        style:height="{lane.h}px"
      >
        <div class="graph-lane-title">
          <span>
            <strong>{lane.label}</strong>
            {#if lane.subtitle}<em>{lane.subtitle}</em>{/if}
          </span>
          <span>{lane.count}</span>
        </div>
      </div>
    {/each}

    <svg class="graph-svg graph-svg-base">
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
      {@const scope = primaryFoundationForNode(n.id)}
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
        {#if scope}
          <div class="gn-origin" title={scope.summary || scope.citation}>
            <span class="kind-pill">{scope.kind ?? 'foundation'}</span>
            <span>{scope.name}</span>
          </div>
        {/if}
        {#if n.paper_section}
          <div class="gn-origin">{n.paper_section}</div>
        {/if}
        {#if n.lean_theorem && n.lean_theorem !== n.id && n.lean_theorem !== n.paper_id}
          <div class="gn-theorem" title={n.lean_theorem}>{n.lean_theorem}</div>
        {/if}
        <div class="gn-meta">
          <StatusPill status={n.status} />
          <span class="ml-auto">
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
        <span class="graph-legend-label">{s.toLowerCase()}</span>
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
