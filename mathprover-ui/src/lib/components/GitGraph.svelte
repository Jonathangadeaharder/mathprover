<script lang="ts">
  import StatusPill from './StatusPill.svelte';
  import Icon from './Icon.svelte';
  import { statusKey } from '$lib/lean';
  import type { TheoremNode } from '$lib/types';

  interface Props { node: TheoremNode; }
  let { node }: Props = $props();

  function hashStr(s: string): number {
    let h = 0;
    for (let i = 0; i < s.length; i++) h = ((h << 5) - h + s.charCodeAt(i)) | 0;
    return h;
  }

  type Row =
    | { kind: 'main'; branch: string; hash: string; msg: string; when: string }
    | { kind: 'branch'; branch: string; hash: string; msg: string; when: string; result: string; duration: string; tokens: number; cost: number; agent: string; index: number }
    | { kind: 'merge'; branch: string; hash: string; msg: string; when: string; result: string };

  let rows = $derived.by<Row[]>(() => {
    const attempts = node.attemptsLog || [];
    if (attempts.length === 0) return [];
    const out: Row[] = [];
    out.push({
      kind: 'main',
      branch: 'main',
      hash: 'a1b2c3d',
      msg: `Initial: scaffold for ${node.lean_theorem}`,
      when: 'baseline',
    });
    attempts.forEach((a, i) => {
      out.push({
        kind: 'branch',
        branch: (`trial/${a.id}-${a.strategy.split(' ')[0].toLowerCase()}`).replace(/[^a-z0-9-/]/g, ''),
        hash: (`${a.id}${(Math.abs(hashStr(a.id)) % 1000000).toString(16)}`).slice(0, 7),
        msg: a.strategy,
        when: a.started.slice(11),
        result: a.result === 'PARTIAL' ? 'SORRIES' : a.result === 'PROGRESS' ? 'PROGRESS' : a.result,
        duration: a.duration,
        tokens: a.tokens,
        cost: a.cost,
        agent: a.agent,
        index: i,
      });
    });
    const final = attempts.find((a) => a.result === 'PARTIAL' || a.result === 'PROGRESS');
    if (final) {
      out.push({
        kind: 'merge',
        branch: 'main',
        hash: 'f9e8d7c',
        msg: `Merge: ${final.strategy} (HEAD)`,
        when: final.ended.slice(11),
        result: statusKey(node.status),
      });
    }
    return out;
  });

  const ROW_H = 78;
  const mainX = 22;
  const branchSpread = 18;
  function rowX(r: Row, i: number) {
    if (r.kind === 'main' || r.kind === 'merge') return mainX;
    return mainX + branchSpread + (i % 3) * 14;
  }
  let total = $derived(rows.length * ROW_H);
</script>

{#if rows.length > 0}
  <div class="git-graph">
    <div style="position: absolute; inset: 12px 0 12px 0; width: 140px; pointer-events: none;">
      <svg width="140" height={total} style="overflow: visible;">
        <line x1={mainX} y1={ROW_H / 2} x2={mainX} y2={total - ROW_H / 2} stroke="var(--fg-3)" stroke-width="1.5" />
        {#each rows as r, i (r.hash + '-' + i)}
          {#if r.kind === 'branch'}
            {@const cy = i * ROW_H + ROW_H / 2}
            {@const x = rowX(r, i)}
            {@const prevY = (i - 1) * ROW_H + ROW_H / 2}
            {@const nextY = (i + 1) * ROW_H + ROW_H / 2}
            {@const color = r.result === 'FAILED' ? 'var(--st-failed)' : r.result === 'SORRIES' ? 'var(--st-sorries)' : r.result === 'PROGRESS' ? 'var(--st-progress)' : 'var(--st-proven)'}
            <path d={`M ${mainX} ${prevY} C ${mainX} ${prevY + 12}, ${x} ${cy - 12}, ${x} ${cy}`} stroke={color} fill="none" stroke-width="1.5" />
            {#if r.result === 'FAILED'}
              <line x1={x - 6} y1={cy + 8} x2={x + 6} y2={cy + 8} stroke="var(--st-failed)" stroke-width="1.5" />
            {:else}
              <path d={`M ${x} ${cy} C ${x} ${cy + 12}, ${mainX} ${nextY - 12}, ${mainX} ${nextY}`} stroke={color} fill="none" stroke-width="1.5" />
            {/if}
          {/if}
        {/each}
      </svg>
    </div>

    {#each rows as r, i (r.hash + '-' + i)}
      {@const x = rowX(r, i)}
      {@const status = r.kind === 'main' ? 'MAIN' : r.result}
      <div class="git-row" style:height="{ROW_H}px">
        <div class="git-canvas">
          <div class="git-node" data-r={status} style:left="{x}px" style:top="{ROW_H / 2}px"></div>
        </div>
        <div class="git-info">
          <div class="branch-name">
            <span style:color={r.kind === 'branch' ? 'var(--accent-strong)' : 'var(--fg-2)'}>{r.branch}</span>
            <span style="font-size: 10px; color: var(--fg-4);">·</span>
            <span style="color: var(--fg-3);">{r.hash}</span>
            {#if r.kind === 'branch'}<StatusPill status={r.result} />{/if}
            {#if r.kind === 'merge'}
              <span style="font-size: 9.5px; padding: 1px 5px; border-radius: 3px; background: var(--accent-soft); color: var(--accent-strong); font-family: var(--font-mono);">HEAD</span>
            {/if}
          </div>
          <div class="branch-msg">{r.msg}</div>
          <div class="branch-meta">
            {#if r.kind === 'branch'}
              <span>{r.agent}</span>
            {/if}
            <span>{r.when}</span>
            {#if r.kind === 'branch'}
              <span>{r.duration}</span>
              <span>{r.tokens.toLocaleString()} tok</span>
              <span>${r.cost.toFixed(2)}</span>
              <span class="git-checkout" style="margin-left: auto; cursor: pointer;">
                <Icon name="refresh" size={10} />git checkout
              </span>
            {/if}
          </div>
        </div>
      </div>
    {/each}
  </div>
{/if}
