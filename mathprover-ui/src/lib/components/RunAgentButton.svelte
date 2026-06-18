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

  let label = $derived(status === 'STUCK' || status === 'SORRIES' ? 'Retry with agent' : 'Run agent');
  let modelObj = $derived(DISPATCH_MODELS.find((m) => m.id === model) ?? DISPATCH_MODELS[0]);
</script>

<div bind:this={ref} class="split-btn-wrap">
  <div class="split-btn" style:opacity={disabled ? 0.5 : 1} style:pointer-events={disabled ? 'none' : 'auto'}>
    <button onclick={() => onrun(model)}>
      <Icon name="play" size={11} />
      {label} <span class="split-btn-label">· {modelObj.id === 'auto' ? 'auto' : modelObj.name.split('-')[0]}</span>
    </button>
    <button class="caret" onclick={() => (open = !open)} aria-label="select model">
      <svg width="9" height="9" viewBox="0 0 12 12" fill="none">
        <path d="M3 4l3 4 3-4" stroke="white" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
    </button>
  </div>
  {#if open}
    <div class="model-menu">
      <div class="route-to-label">Route to</div>
      {#each DISPATCH_MODELS as m (m.id)}
        <button class="opt" class:active={m.id === model} type="button" onclick={() => { model = m.id; open = false; }}>
          <span>
            {#if m.id === model}<Icon name="check" size={12} />{/if}
          </span>
          <div class="opt-text-left">
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
    width: 100%;
    box-sizing: border-box;
  }
</style>
