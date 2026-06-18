<script lang="ts">
  import { app } from '$lib/stores.svelte';
  import ProjectPicker from '$lib/components/ProjectPicker.svelte';
  import { goto } from '$app/navigation';
  import { onMount } from 'svelte';

  onMount(() => {
    if (app.projectRoot) goto('/workspace');
  });

  $effect(() => {
    if (app.projectRoot) goto('/workspace');
  });
</script>

<svelte:head>
  <title>MathProver</title>
</svelte:head>

<ProjectPicker />
