<script lang="ts">
  import { TERM_LOOKUP } from '$lib/lean';
  import Icon from './Icon.svelte';

  interface Props {
    term: string;
    x: number;
    y: number;
  }
  let { term, x, y }: Props = $props();
  let info = $derived(TERM_LOOKUP[term]);

  let left = $derived(Math.min(x + 8, (typeof window !== 'undefined' ? window.innerWidth : 1200) - 380));
  let top = $derived(y + 16);
</script>

{#if info}
  <div class="popover" style:left="{left}px" style:top="{top}px">
    <div class="pop-name">{term}</div>
    <div class="pop-type">{info.type}</div>
    <div class="pop-desc">{info.desc}</div>
    <div class="pop-src">
      <Icon name="page" size={10} />
      {info.src}
      {#if info.nodeId}
        <span style="margin-left: auto; color: var(--accent)">→ open node</span>
      {/if}
    </div>
  </div>
{/if}
