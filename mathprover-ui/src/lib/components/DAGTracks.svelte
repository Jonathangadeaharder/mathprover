<script lang="ts">
  import Icon from './Icon.svelte';
  import StatusPill from './StatusPill.svelte';
  import { app } from '$lib/stores.svelte';
  import { NODES, NODE_BY_ID, activeAgent, primaryFoundationForNode } from '$lib/data';
  import { statusKey } from '$lib/lean';
  import type { TheoremNode } from '$lib/types';

  type Lane = {
    key: string;
    depth: number;
    title: string;
    subtitle: string;
    nodes: TheoremNode[];
    proven: number;
    open: number;
  };

  const statusRank: Record<string, number> = {
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

  function depthOf(node: TheoremNode, memo: Record<string, number>, seen = new Set<string>()): number {
    if (memo[node.id] !== undefined) return memo[node.id];
    if (seen.has(node.id)) return 0;
    seen.add(node.id);
    const deps = (node.depends_on || []).map((id) => NODE_BY_ID[id]).filter(Boolean);
    const depth = deps.length === 0 ? 0 : 1 + Math.max(...deps.map((dep) => depthOf(dep, memo, seen)));
    memo[node.id] = depth;
    return depth;
  }

  function scopeOf(node: TheoremNode): string {
    const scope = primaryFoundationForNode(node.id);
    if (!scope) return 'unscoped';
    return `${scope.kind ?? 'foundation'}::${scope.name}`;
  }

  function scopeTitle(key: string): string {
    if (key === 'unscoped') return 'Unscoped work';
    const [, name] = key.split('::');
    return name || 'Unscoped work';
  }

  function scopeSubtitle(key: string): string {
    if (key === 'unscoped') return 'nodes without a top-level workstream tag';
    const [kind] = key.split('::');
    if (kind === 'paper') return 'paper-facing work';
    if (kind === 'shared') return 'shared between paper and foundation';
    return 'foundational work';
  }

  let lanes = $derived.by(() => {
    const memo: Record<string, number> = {};
    const groups: Record<string, TheoremNode[]> = {};
    for (const node of NODES) {
      const depth = depthOf(node, memo);
      const scope = scopeOf(node);
      const key = `${depth}::${scope}`;
      groups[key] ||= [];
      groups[key].push(node);
    }

    return Object.entries(groups)
      .map(([key, nodes]) => {
        const [depthRaw, scopeKey] = key.split('::', 2);
        const depth = Number(depthRaw);
        const sorted = [...nodes].sort((a, b) => {
          const sa = statusRank[statusKey(a.status)] ?? 9;
          const sb = statusRank[statusKey(b.status)] ?? 9;
          if (sa !== sb) return sa - sb;
          if ((b.importance || 0) !== (a.importance || 0)) return (b.importance || 0) - (a.importance || 0);
          return a.paper_id.localeCompare(b.paper_id);
        });
        const proven = sorted.filter((n) => statusKey(n.status) === 'PROVEN').length;
        return {
          key,
          depth,
          title: depth === 0
            ? `Leaves (${scopeTitle(scopeKey)})`
            : depth === 1
            ? `Assembly (${scopeTitle(scopeKey)})`
            : `Depth ${depth} (${scopeTitle(scopeKey)})`,
          subtitle: `${scopeSubtitle(scopeKey)} · depth ${depth}`,
          nodes: sorted,
          proven,
          open: sorted.length - proven,
        };
      })
      .sort((a, b) => {
        if (a.depth !== b.depth) return a.depth - b.depth;
        return a.title.localeCompare(b.title);
      });
  });

  let active = $derived(activeAgent());

  function pick(node: TheoremNode) {
    app.selectedNodeId = node.id;
    app.route = 'graph';
  }

  function start(node: TheoremNode, e: MouseEvent) {
    e.stopPropagation();
    app.selectedNodeId = node.id;
    app.pendingDispatch = { nodeId: node.id, model: 'auto' };
  }

  function onClipKey(node: TheoremNode, e: KeyboardEvent) {
    if (e.key !== 'Enter' && e.key !== ' ') return;
    e.preventDefault();
    pick(node);
  }
</script>

<div class="tracks-shell">
  <div class="tracks-timeline" aria-hidden="true">
    {#each lanes as lane (lane.key)}
      <span>{lane.depth}</span>
    {/each}
  </div>

  <div class="tracks-board">
    {#each lanes as lane (lane.key)}
      <section class="track-lane" aria-label={lane.title}>
        <div class="track-head">
          <div>
            <h2>{lane.title}</h2>
            <p>{lane.subtitle}</p>
          </div>
          <div class="track-meter" title={`${lane.proven} proved, ${lane.open} open`}>
            <span>{lane.proven}</span>
            <div><i style:width={`${lane.nodes.length ? (lane.proven / lane.nodes.length) * 100 : 0}%`}></i></div>
            <span>{lane.nodes.length}</span>
          </div>
        </div>

        <div class="track-clips">
          {#each lane.nodes as node (node.id)}
            {@const sk = statusKey(node.status)}
            {@const running = active?.node === node.id}
            <div
              class="track-clip"
              class:selected={app.selectedNodeId === node.id}
              class:running
              data-status={sk}
              onclick={() => pick(node)}
              onkeydown={(e) => onClipKey(node, e)}
              role="button"
              tabindex="0"
              title={`${node.paper_id}: ${node.paper_name}`}
            >
              <span class="clip-main">
                <span class="clip-id">{node.paper_id}</span>
                <span class="clip-title">{node.paper_name}</span>
              </span>
              <span class="clip-controls">
                <StatusPill status={node.status} />
                <span class="clip-attempts">{node.attempts || 0}</span>
                <button class="clip-play" onclick={(e) => start(node, e)} title="Dispatch proof attempt" type="button">
                  <Icon name="play" size={11} />
                </button>
              </span>
            </div>
          {/each}
        </div>
      </section>
    {/each}
  </div>
</div>
