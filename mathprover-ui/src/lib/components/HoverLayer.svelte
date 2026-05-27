<script lang="ts">
  import { TERM_LOOKUP } from '$lib/lean';
  import TermPopover from './TermPopover.svelte';
  import { onMount } from 'svelte';

  let pop = $state<{ term: string; x: number; y: number } | null>(null);

  onMount(() => {
    function onOver(e: MouseEvent) {
      const t = e.target as HTMLElement | null;
      if (!t) return;
      const el = t.closest('.lean-term') as HTMLElement | null;
      if (!el) return;
      const term = el.dataset.term ?? '';
      if (TERM_LOOKUP[term]) pop = { term, x: e.clientX, y: e.clientY };
    }
    function onMove(e: MouseEvent) {
      if (pop) pop = { ...pop, x: e.clientX, y: e.clientY };
    }
    function onOut(e: MouseEvent) {
      const rel = e.relatedTarget as HTMLElement | null;
      if (!rel || !rel.closest || !rel.closest('.lean-term')) pop = null;
    }
    document.addEventListener('mouseover', onOver);
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseout', onOut);
    return () => {
      document.removeEventListener('mouseover', onOver);
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseout', onOut);
    };
  });
</script>

{#if pop}
  <TermPopover term={pop.term} x={pop.x} y={pop.y} />
{/if}
