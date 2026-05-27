<script lang="ts">
  import { app, project } from '$lib/stores.svelte';
  import { NODES, NODE_BY_ID } from '$lib/data';
  import { statusKey } from '$lib/lean';
  import { goto } from '$app/navigation';
  import { onMount } from 'svelte';
  import { postDispatch } from '$lib/api';
  import { attachRunStream, refreshProject } from '$lib/live.svelte';

  import Topbar from '$lib/components/Topbar.svelte';
  import Sidebar from '$lib/components/Sidebar.svelte';
  import GraphView from '$lib/components/GraphView.svelte';
  import NodeDetail from '$lib/components/NodeDetail.svelte';
  import FrontierView from '$lib/components/FrontierView.svelte';
  import PaperLeanView from '$lib/components/PaperLeanView.svelte';
  import AgentView from '$lib/components/AgentView.svelte';
  import FailuresView from '$lib/components/FailuresView.svelte';
  import FoundationsView from '$lib/components/FoundationsView.svelte';
  import DefinitionsView from '$lib/components/DefinitionsView.svelte';
  import PremisePicker from '$lib/components/PremisePicker.svelte';

  onMount(() => {
    if (!app.openedProject) goto('/');
  });
  $effect(() => {
    if (!app.openedProject) goto('/');
  });

  let provenCount = $derived(NODES.filter((n) => statusKey(n.status) === 'PROVEN').length);
  let projectName = $derived(project.data.project.name || 'MathProver');
  let dispatchError = $state<string | null>(null);
  let dispatching = $state(false);

  async function confirmDispatch() {
    if (!app.pendingDispatch || !app.projectRoot) return;
    const { nodeId, model } = app.pendingDispatch;
    app.pendingDispatch = null;
    dispatching = true;
    dispatchError = null;
    const node = NODE_BY_ID[nodeId];
    const target = node?.proof_folder ?? nodeId;
    const result = await postDispatch(app.projectRoot, target, model);
    dispatching = false;
    if (!result || result.error) {
      dispatchError = result?.error ?? 'Dispatch failed';
      return;
    }
    app.activeRunId = result.runId;
    app.agentNodeId = nodeId;
    app.route = 'agents';
    app.liveLogText = '';
    attachRunStream(result.runId);
    await refreshProject();
  }

  function cancelDispatch() {
    app.pendingDispatch = null;
    dispatchError = null;
  }
</script>

<svelte:head>
  <title>{projectName} · MathProver</title>
</svelte:head>

{#if app.openedProject}
  <div class="app-shell">
    <Topbar />
    <Sidebar />
    <main class="main">
      {#if app.route === 'graph'}
        <div class="pane-header">
          <h1>Graph</h1>
          <span class="subtle">{NODES.length} theorems · {provenCount} proven</span>
        </div>
        <div class="pane-body" style="position: relative;">
          <GraphView />
          <NodeDetail />
        </div>

      {:else if app.route === 'frontier'}
        <div class="pane-header">
          <h1>Frontier</h1>
          <span class="subtle">Ready-to-attempt nodes, ranked by importance × tractability</span>
        </div>
        <FrontierView />

      {:else if app.route === 'paper-lean'}
        <div class="pane-header">
          <h1>Paper ⇄ Lean</h1>
          <span class="subtle">Click a theorem on either side to sync</span>
          <select
            style="margin-left: auto; font-size: 11.5px; padding: 4px 8px;"
            value={app.paperLeanNodeId}
            onchange={(e) => (app.paperLeanNodeId = (e.currentTarget as HTMLSelectElement).value)}
          >
            {#each NODES.filter((n) => n.lean_stmt || n.paper_stmt) as n (n.id)}
              <option value={n.id}>{n.paper_id} · {n.paper_name}</option>
            {/each}
          </select>
        </div>
        <div class="pane-body">
          <PaperLeanView />
        </div>

      {:else if app.route === 'agents'}
        <div class="pane-header">
          <h1>Agent runs</h1>
          <span class="subtle">One run per attempt — live + historic</span>
        </div>
        <div class="pane-body">
          <AgentView />
        </div>

      {:else if app.route === 'failures'}
        <div class="pane-header">
          <h1>Failure shelf</h1>
          <span class="subtle">What didn't work, with counterexamples</span>
        </div>
        <FailuresView />

      {:else if app.route === 'foundations'}
        <div class="pane-header">
          <h1>Foundations</h1>
          <span class="subtle">External results this work depends on — mechanization progress</span>
        </div>
        <div class="pane-body">
          <FoundationsView />
        </div>

      {:else if app.route === 'definitions'}
        <div class="pane-header">
          <h1>Definitions</h1>
          <span class="subtle">Primitive notions — structures, defs, abstractions the theorems build on</span>
        </div>
        <div class="pane-body" style="padding: 0;">
          <DefinitionsView />
        </div>
      {/if}
    </main>
  </div>

  {#if app.pendingDispatch && NODE_BY_ID[app.pendingDispatch.nodeId]}
    <PremisePicker
      node={NODE_BY_ID[app.pendingDispatch.nodeId]}
      model={app.pendingDispatch.model}
      dispatching={dispatching}
      oncancel={cancelDispatch}
      onconfirm={confirmDispatch}
    />
  {/if}

  {#if dispatchError}
    <div style="position:fixed;bottom:16px;right:16px;z-index:9999;background:#5b2620;color:#ffd5cf;padding:10px 14px;border-radius:8px;font-size:12px;max-width:360px;">
      <strong>Dispatch failed</strong> — {dispatchError}
      <button class="btn sm" style="margin-left:8px;" onclick={() => (dispatchError = null)}>Dismiss</button>
    </div>
  {/if}
{/if}
