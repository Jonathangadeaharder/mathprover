<script lang="ts">
  import { statusKey } from '$lib/lean';
  interface Props { status: string; }
  let { status }: Props = $props();
  let k = $derived(statusKey(status));
</script>

<span class="status-pill" data-status={k}>
  <span class="dot"></span>
  {k.toLowerCase()}
</span>
