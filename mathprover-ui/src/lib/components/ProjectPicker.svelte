<script lang="ts">
  import Icon from './Icon.svelte';
  import { app } from '$lib/stores.svelte';
  import { RECENT_PROJECTS } from '$lib/data';
  import { goto } from '$app/navigation';

  let dragOver = $state(false);

  function open(path?: string) {
    if (path) {
      goto(`/workspace?project=${encodeURIComponent(path)}`);
      app.openedProject = true;
      app.route = 'graph';
    } else {
      app.openedProject = true;
      app.route = 'graph';
    }
  }
</script>

<div class="picker-stage">
  <div class="picker-card">
    <h1>Open a Lean+LaTeX research project</h1>
    <p class="lede">
      MathProver indexes paired LaTeX&nbsp;sources and Lean&nbsp;4 formalizations, builds a dependency graph
      of every theorem and lemma, and lets you dispatch a proof-search agent to any ready node.
    </p>

    <button
      type="button"
      class="dropzone"
      style:border-color={dragOver ? 'var(--accent)' : null}
      style:background={dragOver ? 'var(--accent-soft)' : null}
      ondragover={(e) => { e.preventDefault(); dragOver = true; }}
      ondragleave={() => (dragOver = false)}
      ondrop={(e) => { e.preventDefault(); dragOver = false; open(); }}
      onclick={() => open()}
    >
      <Icon name="folder" size={32} />
      <div class="ttl">Drop a project folder here, or click to browse</div>
      <div class="sub">Expects <span class="kbd">paper/</span>, <span class="kbd">lean/</span> and a <span class="kbd">mathprover.toml</span> manifest at the root</div>
    </button>

    <div class="recent-list">
      <h2>Recent projects</h2>
      {#each RECENT_PROJECTS as p, i (p.name)}
        <button class="recent-row" type="button" onclick={() => open(p.path)}>
          <Icon name="folder" size={14} />
          <div style="flex: 1; min-width: 0; text-align: left;">
            <div class="ttl">{p.name}</div>
            <div class="path">{p.path}</div>
          </div>
          <div class="meta">
            <span style="color: var(--st-proven)">{p.proven}</span>
            <span style="color: var(--fg-4)"> / </span>
            <span>{p.thms}</span> thms
          </div>
          <div class="meta" style="width: 60px; text-align: right;">{p.updated}</div>
        </button>
      {/each}
    </div>

    <div class="structure-block">
      <h3>Expected folder structure</h3>
      <div class="tree">
        <span>my_project/</span>{'\n'}
        ├── <span class="file">mathprover.toml</span>              <span class="note"># project manifest + capstone</span>{'\n'}
        ├── <span class="dir">paper/</span>{'\n'}
        │   ├── <span class="file">main.tex</span>                  <span class="note"># LaTeX with %@lean: decorators</span>{'\n'}
        │   ├── <span class="file">sections/*.tex</span>{'\n'}
        │   └── <span class="file">references.bib</span>{'\n'}
        ├── <span class="dir">lean/</span>{'\n'}
        │   ├── <span class="file">lakefile.toml</span>{'\n'}
        │   └── <span class="dir">Project/</span>{'\n'}
        │       ├── <span class="file">Theorems/*.lean</span>         <span class="note">{'# /-- @paper: Thm 5.4 -/'}</span>{'\n'}
        │       ├── <span class="file">Propositions/*.lean</span>{'\n'}
        │       └── <span class="file">Axioms/*.lean</span>            <span class="note"># axiom = open obligation</span>{'\n'}
        └── <span class="dir">.mathprover/</span>              <span class="note"># cache, attempts, agent runs</span>{'\n'}
            ├── <span class="file">graph.json</span>{'\n'}
            ├── <span class="file">attempts/</span>{'\n'}
            └── <span class="file">strategies.jsonl</span>
      </div>
    </div>

    <div style="display: flex; justify-content: flex-end; margin-top: 24px; gap: 8px;">
      <button class="btn ghost">Documentation</button>
      <button class="btn primary" onclick={() => open()}>
        Open sample project
        <Icon name="arrow_right" size={12} />
      </button>
    </div>
  </div>
</div>

<style>
  .dropzone {
    width: 100%;
    cursor: pointer;
    font: inherit;
  }
  .recent-row { width: 100%; }
</style>
