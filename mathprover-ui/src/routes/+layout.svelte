<script lang="ts">
  import '../app.css';
  import HoverLayer from '$lib/components/HoverLayer.svelte';
  import TweaksPanel from '$lib/components/TweaksPanel.svelte';
  import { setProjectData } from '$lib/stores.svelte';
  import { setProjectRoot, startLivePolling, refreshProject, checkGoedelLock } from '$lib/live.svelte';
  import { onMount } from 'svelte';
  import type { Snippet } from 'svelte';

  interface Props { data: { projectData: any; projectRoot: string; error: string | null }; children?: Snippet; }
  let { data, children }: Props = $props();

  $effect.pre(() => {
    setProjectData(data.projectData);
    setProjectRoot(data.projectRoot);
  });

  onMount(() => {
    refreshProject();
    startLivePolling();
    checkGoedelLock();
    return () => {
      import('$lib/live.svelte').then((m) => m.stopLivePolling());
    };
  });
</script>

{#if data.error}
  <div style="position:fixed;top:8px;left:8px;right:8px;z-index:9999;background:#5b2620;color:#ffd5cf;padding:8px 12px;border-radius:6px;font-family:ui-monospace,monospace;font-size:12px;">
    <strong>Project load error</strong> — {data.error}
    <div style="opacity:.8;margin-top:4px;">Falling back to empty project. Set <code>?project=&lt;path&gt;</code> or env <code>MATHPROVER_PROJECT_PATH</code>.</div>
  </div>
{/if}

{@render children?.()}

<HoverLayer />
<TweaksPanel />
