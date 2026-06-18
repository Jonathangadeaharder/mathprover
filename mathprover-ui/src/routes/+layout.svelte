<script lang="ts">
  import '../app.css';
  import HoverLayer from '$lib/components/HoverLayer.svelte';
  import TweaksPanel from '$lib/components/TweaksPanel.svelte';
  import { setProjectData } from '$lib/stores.svelte';
  import { setProjectRoot, startLivePolling, refreshProject, checkGoedelLock } from '$lib/live.svelte';
  import { onMount } from 'svelte';
  import type { Snippet } from 'svelte';
  import type { ProjectData } from '$lib/types';

  interface Props { data: { projectData: ProjectData; projectRoot: string; error: string | null }; children?: Snippet; }
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
  <div class="error-banner">
    <strong>Project load error</strong> — {data.error}
    <div class="error-banner-hint">Falling back to empty project. Set <code>?project=&lt;path&gt;</code> or env <code>MATHPROVER_PROJECT_PATH</code>.</div>
  </div>
{/if}

{@render children?.()}

<HoverLayer />
<TweaksPanel />
