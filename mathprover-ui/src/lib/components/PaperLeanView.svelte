<script lang="ts">
  import Icon from './Icon.svelte';
  import { app } from '$lib/stores.svelte';
  import { NODE_BY_ID, PAPER_BLOCKS, LEAN_BLOCKS } from '$lib/data';
  import { wrapTerms } from '$lib/lean';


  let leftEl: HTMLDivElement;
  let rightEl: HTMLDivElement;

  function scrollPaneTo(pane: HTMLElement, el: HTMLElement) {
    pane.scrollTo({ top: Math.max(0, el.offsetTop - 80), behavior: 'smooth' });
  }

  $effect(() => {
    const target = app.paperLeanNodeId;
    if (!target) return;
    setTimeout(() => {
      const l = leftEl?.querySelector<HTMLElement>(`[data-nid="${target}"]`);
      const r = rightEl?.querySelector<HTMLElement>(`[data-nid="${target}"]`);
      if (l && leftEl) scrollPaneTo(leftEl, l);
      if (r && rightEl) scrollPaneTo(rightEl, r);
    }, 30);
  });

  // line numbers: precompute
  type Rendered =
    | { type: 'comment'; lines: { ln: number; html: string }[] }
    | { type: 'code'; nodeId: string; lines: { ln: number; html: string }[] }
    | { type: 'gap'; ln: number };

  let renderedLean = $derived.by<Rendered[]>(() => {
    const out: Rendered[] = [];
    let lineNo = 0;
    LEAN_BLOCKS.forEach((b) => {
      if (b.kind === 'comment') {
        lineNo += 1;
        out.push({ type: 'comment', lines: [{ ln: lineNo, html: `<span class="cm">${b.text}</span>` }] });
        return;
      }
      const lines = b.lines.map((ln) => {
        lineNo += 1;
        return { ln: lineNo, html: wrapTerms(ln) };
      });
      out.push({ type: 'code', nodeId: b.nodeId, lines });
      lineNo += 1;
      out.push({ type: 'gap', ln: lineNo });
    });
    return out;
  });
</script>

<div class="pl-split">
  <div class="pl-pane left" bind:this={leftEl}>
    <div class="pl-pane-header">
      <Icon name="page" size={12} />
      <span class="filepath">paper/main.tex</span>
      <span style="font-size: 10.5px; color: var(--fg-3); margin-left: 8px;">§5</span>
      <span class="pl-lang">TeX</span>
    </div>
    <div class="paper-doc">
      {#each PAPER_BLOCKS as b, i (i)}
        {#if b.kind === 'heading'}
          <h2>{b.text}</h2>
        {:else if b.kind === 'para'}
          <p>{b.text}</p>
        {:else}
          <div
            class="thm-block"
            class:synced={app.paperLeanNodeId === b.nodeId}
            data-nid={b.nodeId}
            onclick={() => (app.paperLeanNodeId = b.nodeId)}
            onkeydown={(e) => { if (e.key === 'Enter') app.paperLeanNodeId = b.nodeId; }}
            role="button"
            tabindex="0"
          >
            <span class="anchor">@lean: {NODE_BY_ID[b.nodeId]?.lean_theorem}</span>
            <span class="label">{b.label}.</span>
            {b.text}
            {#if b.math}<div class="math">{b.math}</div>{/if}
            {#if b.after}<div style="margin-top: 6px;">{b.after}</div>{/if}
          </div>
        {/if}
      {/each}
    </div>
  </div>

  <div class="pl-pane" bind:this={rightEl}>
    <div class="pl-pane-header">
      <Icon name="page" size={12} />
      <span class="filepath">lean/Project/Theorems/BatchCoEA.lean</span>
      <span class="pl-lang">Lean 4</span>
    </div>
    <div class="lean-doc">
      {#each renderedLean as r, i (i)}
        {#if r.type === 'comment'}
          {#each r.lines as l (l.ln)}
            <div class="lean-line">
              <div class="ln">{l.ln}</div>
              <div class="ct">{@html l.html}</div>
            </div>
          {/each}
        {:else if r.type === 'code'}
          <div
            class="lean-block"
            class:synced={app.paperLeanNodeId === r.nodeId}
            data-nid={r.nodeId}
            onclick={() => (app.paperLeanNodeId = r.nodeId)}
            onkeydown={(e) => { if (e.key === 'Enter') app.paperLeanNodeId = r.nodeId; }}
            role="button"
            tabindex="0"
          >
            {#each r.lines as l (l.ln)}
              <div class="lean-line">
                <div class="ln">{l.ln}</div>
                <div class="ct">{@html l.html}</div>
              </div>
            {/each}
          </div>
        {:else}
          <div class="lean-line"><div class="ln">{r.ln}</div><div class="ct"></div></div>
        {/if}
      {/each}
    </div>
  </div>
</div>

<style>
  .thm-block, .lean-block { cursor: pointer; }
</style>
