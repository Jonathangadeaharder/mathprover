<script lang="ts">
  import { app } from '$lib/stores.svelte';
  import ProjectPicker from '$lib/components/ProjectPicker.svelte';
  import { goto } from '$app/navigation';
  import { onMount } from 'svelte';

  // If we already have a project loaded (e.g. via store rehydration), bounce to /workspace.
  onMount(() => {
    if (app.openedProject) goto('/workspace');
  });

  // Watch in case the picker sets a project — redirect to /workspace.
  $effect(() => {
    if (app.openedProject) goto('/workspace');
  });
</script>

<svelte:head>
  <title>MathProver</title>
</svelte:head>

<ProjectPicker />
