<script lang="ts">
  interface Props { value: number; color?: string; }
  let { value, color = 'var(--accent)' }: Props = $props();
</script>

<span class="meter-inline">
  <span class="meter-inline-fill" style="--meter-pct: {value * 100}%; --meter-color: {color};"></span>
</span>
