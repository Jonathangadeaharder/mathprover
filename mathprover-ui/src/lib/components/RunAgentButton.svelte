<script lang="ts">
  import Icon from './Icon.svelte';
  import { DISPATCH_MODELS } from '$lib/stores.svelte';

  interface Props {
    disabled?: boolean;
    status: string;
    onrun: (model: string) => void;
  }
  let { disabled = false, status, onrun }: Props = $props();

  let model = $state('auto');
  let open = $state(false);
  let ref: HTMLDivElement;

  $effect(() => {
    if (!open) return;
    function onClick(e: MouseEvent) {
      if (ref && !ref.contains(e.target as Node)) open = false;
    }
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  });

  let label = $derived(status === 'FAILED' || status === 'SORRIES' ? 'Retry with agent' : 'Run agent');
  let modelObj = $derived(DISPATCH_MODELS.find((m) => m.id === model) ?? DISPATCH_MODELS[0]);
</script>

<div bind:this={ref} style="position: relative; display: inline-flex;">
  <div class="split-btn" style:opacity={disabled ? 0.5 : 1} style:pointer-events={disabled ? 'none' : 'auto'}>
    <button onclick={() => onrun(model)}>
      <Icon name="play" size={11} />
      {label} <span style="opacity: 0.7; font-size: 11px; margin-left: 2px;">· {modelObj.id === 'auto' ? 'auto' : modelObj.name.split('-')[0]}</span>
    </button>
    <button class="caret" onclick={() => (open = !open)} aria-label="select model">
      <svg width="9" height="9" viewBox="0 0 12 12" fill="none">
        <path d="M3 4l3 4 3-4" stroke="white" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
    </button>
  </div>
  {#if open}
    <div class="model-menu">
      <div style="padding: 6px 10px; font-size: 10px; text-transform: uppercase; letter-spacing: 0.06em; color: var(--fg-3); font-weight: 600;">Route to</div>
      {#each DISPATCH_MODELS as m (m.id)}
        <button class="opt" class:active={m.id === model} type="button" onclick={() => { model = m.id; open = false; }}>
          <span>
            {#if m.id === model}<Icon name="check" size={12} />{/if}
          </span>
          <div style="text-align: left;">
            <div class="name">{m.name}</div>
            <div class="desc">{m.desc}</div>
          </div>
          <div class="lat">{m.lat}</div>
        </button>
      {/each}
    </div>
  {/if}
</div>

<style>
  .model-menu button.opt {
    all: unset;
    display: grid;
    grid-template-columns: 14px 1fr auto;
    gap: 8px;
    align-items: center;
    padding: 8px 10px;
    border-radius: var(--r-sm);
    cursor: pointer;
    font-size: 12px;
    width: 100%;
    box-sizing: border-box;
  }
</style>
