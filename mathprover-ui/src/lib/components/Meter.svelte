<script lang="ts">
  interface Props { value: number; color?: string; }
  let { value, color = 'var(--accent)' }: Props = $props();
</script>

<span style="display:inline-block;width:100px;height:4px;background:var(--bg-3);border-radius:2px;vertical-align:middle;overflow:hidden;">
  <span style:width="{value * 100}%" style:background={color} style="display:block;height:100%;border-radius:2px;"></span>
</span>
