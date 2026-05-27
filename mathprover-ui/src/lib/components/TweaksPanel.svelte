<script lang="ts">
  import { tweaks, persistTweaks, ACCENT_PALETTES } from '$lib/stores.svelte';
  import Icon from './Icon.svelte';

  let open = $state(false);

  function set<K extends keyof typeof tweaks>(key: K, value: (typeof tweaks)[K]) {
    tweaks[key] = value;
    persistTweaks();
  }

  $effect(() => {
    document.documentElement.dataset.theme = tweaks.theme;
    document.documentElement.dataset.density = tweaks.density;
    const p = ACCENT_PALETTES[tweaks.accent] ?? ACCENT_PALETTES['#8b7cf6'];
    document.documentElement.style.setProperty('--accent', tweaks.accent);
    document.documentElement.style.setProperty('--accent-strong', p.strong);
    document.documentElement.style.setProperty('--accent-soft', p.soft);
    document.documentElement.style.setProperty('--accent-border', p.border);
  });

  const accentSwatches = Object.keys(ACCENT_PALETTES);
  const layouts: { id: 'dag' | 'radial' | 'force'; label: string }[] = [
    { id: 'dag', label: 'Layered DAG' },
    { id: 'radial', label: 'Radial' },
    { id: 'force', label: 'Force-organic' },
  ];
</script>

{#if !open}
  <button class="tweaks-fab" type="button" onclick={() => (open = true)} title="Tweaks">
    <Icon name="cog" size={14} />
  </button>
{:else}
  <div class="tweaks-panel">
    <div class="tw-header">
      <span>Tweaks</span>
      <button class="close" onclick={() => (open = false)} aria-label="close"><Icon name="close" size={12} /></button>
    </div>

    <div class="tw-section">
      <div class="tw-label">Appearance</div>

      <div class="tw-row">
        <span class="tw-name">Theme</span>
        <div class="seg">
          <button class:on={tweaks.theme === 'dark'} onclick={() => set('theme', 'dark')}>dark</button>
          <button class:on={tweaks.theme === 'light'} onclick={() => set('theme', 'light')}>light</button>
        </div>
      </div>

      <div class="tw-row">
        <span class="tw-name">Density</span>
        <div class="seg">
          <button class:on={tweaks.density === 'compact'} onclick={() => set('density', 'compact')}>compact</button>
          <button class:on={tweaks.density === 'comfortable'} onclick={() => set('density', 'comfortable')}>comfy</button>
        </div>
      </div>

      <div class="tw-row">
        <span class="tw-name">Accent</span>
        <div style="display: flex; gap: 6px;">
          {#each accentSwatches as c (c)}
            <button
              class="swatch-btn"
              class:on={tweaks.accent === c}
              style:background={c}
              onclick={() => set('accent', c)}
              aria-label="accent {c}"
            ></button>
          {/each}
        </div>
      </div>
    </div>

    <div class="tw-section">
      <div class="tw-label">Graph</div>

      <div class="tw-row">
        <span class="tw-name">Layout</span>
        <select value={tweaks.graph_layout} onchange={(e) => set('graph_layout', (e.currentTarget as HTMLSelectElement).value as any)}>
          {#each layouts as l (l.id)}<option value={l.id}>{l.label}</option>{/each}
        </select>
      </div>

      <div class="tw-row">
        <span class="tw-name">Show proven nodes</span>
        <button class="toggle" class:on={tweaks.show_proven} onclick={() => set('show_proven', !tweaks.show_proven)} aria-pressed={tweaks.show_proven}>
          <span class="thumb"></span>
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .tweaks-fab {
    position: fixed;
    bottom: 16px;
    right: 16px;
    width: 36px;
    height: 36px;
    border-radius: 50%;
    background: var(--bg-1);
    border: 1px solid var(--border);
    color: var(--fg-2);
    display: grid;
    place-items: center;
    box-shadow: var(--shadow-md);
    z-index: 50;
    cursor: pointer;
  }
  .tweaks-fab:hover { color: var(--fg-0); background: var(--bg-2); }

  .tweaks-panel {
    position: fixed;
    bottom: 16px;
    right: 16px;
    width: 280px;
    background: var(--bg-1);
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    padding: 6px;
    box-shadow: var(--shadow-lg);
    z-index: 50;
    font-size: 12px;
  }
  .tw-header {
    display: flex; align-items: center; padding: 6px 10px; font-weight: 600;
  }
  .tw-header .close {
    margin-left: auto; cursor: pointer; color: var(--fg-3); border: none; background: none;
    width: 20px; height: 20px; display: grid; place-items: center; border-radius: var(--r-sm);
  }
  .tw-header .close:hover { background: var(--bg-2); color: var(--fg-0); }

  .tw-section { padding: 4px 8px 8px; }
  .tw-label {
    font-size: 10px; text-transform: uppercase; letter-spacing: 0.06em;
    color: var(--fg-3); font-weight: 600; margin: 4px 0;
  }
  .tw-row {
    display: flex; align-items: center; justify-content: space-between;
    padding: 6px 0;
  }
  .tw-name { color: var(--fg-1); }

  .seg {
    display: inline-flex; background: var(--bg-2); border-radius: var(--r-sm); padding: 2px;
  }
  .seg button {
    all: unset; cursor: pointer; padding: 3px 9px; font-size: 11px;
    color: var(--fg-3); border-radius: 3px;
  }
  .seg button.on { background: var(--bg-1); color: var(--fg-0); }

  .swatch-btn {
    all: unset; cursor: pointer;
    width: 20px; height: 20px; border-radius: 50%;
    border: 2px solid transparent;
    box-shadow: inset 0 0 0 1px var(--border-soft);
  }
  .swatch-btn.on { border-color: var(--fg-1); }

  .toggle {
    all: unset; cursor: pointer;
    width: 30px; height: 16px;
    background: var(--bg-3); border-radius: 8px;
    position: relative; transition: background 0.15s;
  }
  .toggle .thumb {
    position: absolute; top: 2px; left: 2px;
    width: 12px; height: 12px; background: var(--fg-2); border-radius: 50%;
    transition: transform 0.15s, background 0.15s;
  }
  .toggle.on { background: var(--accent); }
  .toggle.on .thumb { transform: translateX(14px); background: white; }

  select { font-size: 11px; padding: 3px 6px; }
</style>
