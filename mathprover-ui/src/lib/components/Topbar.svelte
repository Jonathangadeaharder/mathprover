<script lang="ts">
  import Icon from './Icon.svelte';
  import { app, project, tweaks, persistTweaks } from '$lib/stores.svelte';
  import { reindexProject } from '$lib/api';
  import { refreshProject } from '$lib/live.svelte';

  let reindexing = $state(false);

  function toggleTheme() {
    tweaks.theme = tweaks.theme === 'dark' ? 'light' : 'dark';
    persistTweaks();
  }

  function closeProject() {
    app.openedProject = false;
  }

  async function reindex() {
    if (!app.projectRoot || reindexing) return;
    reindexing = true;
    const data = await reindexProject(app.projectRoot);
    if (data) {
      const { setProjectData } = await import('$lib/stores.svelte');
      setProjectData(data);
    }
    await refreshProject();
    reindexing = false;
  }
</script>

<div class="topbar">
  <div class="logo">
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
      <path d="M4 4l16 16M20 4L4 20" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" />
      <circle cx="4" cy="4" r="2" fill="currentColor" />
      <circle cx="20" cy="20" r="2" fill="currentColor" />
      <circle cx="20" cy="4" r="2" fill="currentColor" />
      <circle cx="4" cy="20" r="2" fill="currentColor" />
      <circle cx="12" cy="12" r="2.5" fill="currentColor" />
    </svg>
    MathProver
  </div>

  {#if app.openedProject}
    <button class="project-chip" onclick={closeProject} title="Switch project">
      <Icon name="folder" size={12} />
      <strong>{project.data.project.name}</strong>
      <span style="color: var(--fg-4)">·</span>
      <span style="font-family: var(--font-mono); font-size: 11px;">{project.data.project.path}</span>
    </button>
    <span style="font-size: 11px; color: var(--fg-3); font-family: var(--font-mono);">
      {#if app.goedelLocked}
        <span style="color: var(--st-progress);">Goedel running</span>
        <span style="color: var(--fg-4);"> · </span>
      {/if}
      last lake build: {project.data.project.lastVerified || '—'}
    </span>
  {/if}

  <div class="topbar-spacer"></div>
  <div class="actions">
    {#if app.openedProject}
      <button onclick={reindex} title="Reindex graph from Lean sources" disabled={reindexing}>
        <Icon name="refresh" size={13} />
      </button>
    {/if}
    <button onclick={toggleTheme} title="toggle theme">
      <Icon name={tweaks.theme === 'dark' ? 'sun' : 'moon'} size={13} />
    </button>
    <button title="search"><Icon name="search" size={13} /></button>
    <button title="settings"><Icon name="cog" size={13} /></button>
  </div>
</div>

<style>
  .project-chip {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: var(--fg-2);
    padding: 3px 8px;
    background: var(--bg-2);
    border: 1px solid var(--border-soft);
    border-radius: var(--r);
    cursor: pointer;
  }
  .project-chip:hover { border-color: var(--border); }
  .project-chip strong { color: var(--fg-0); font-weight: 500; }
</style>
