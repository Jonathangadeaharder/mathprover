// Global reactive state via Svelte 5 runes.
// `project.data` is populated from `.mathprover/graph.json` by +layout.server.ts.

import type {
  PendingDispatch,
  ProjectData,
  Route,
  Tweaks,
} from './types';
import { EMPTY_PROJECT_DATA } from './data-empty';

interface AppState {
  openedProject: boolean;
  projectRoot: string;
  route: Route;
  selectedNodeId: string | null;
  selectedDefId: string | null;
  paperLeanNodeId: string;
  agentNodeId: string | null;
  activeRunId: string | null;
  liveLogText: string;
  goedelLocked: boolean;
  hoveredId: string | null;
  pendingDispatch: PendingDispatch | null;
}

function loadTweaks(): Tweaks {
  if (typeof localStorage === 'undefined') return defaults();
  try {
    const raw = localStorage.getItem('mathprover.tweaks');
    if (!raw) return defaults();
    return { ...defaults(), ...JSON.parse(raw) };
  } catch {
    return defaults();
  }
}

function defaults(): Tweaks {
  return {
    theme: 'dark',
    graph_layout: 'dag',
    density: 'compact',
    accent: '#8b7cf6',
    show_proven: true,
  };
}

export const app = $state<AppState>({
  openedProject: false,
  projectRoot: '',
  route: 'graph',
  selectedNodeId: null,
  selectedDefId: null,
  paperLeanNodeId: '',
  agentNodeId: null,
  activeRunId: null,
  liveLogText: '',
  goedelLocked: false,
  hoveredId: null,
  pendingDispatch: null,
});

export const project = $state<{ data: ProjectData }>({ data: EMPTY_PROJECT_DATA });

export function setProjectData(data: ProjectData) {
  project.data = data;
  if (!app.paperLeanNodeId && data.nodes.length > 0) {
    const capstone = data.nodes.find((n) => n.id === data.project.capstone);
    app.paperLeanNodeId = capstone?.id ?? data.nodes[0].id;
  }
}

export const tweaks = $state<Tweaks>(loadTweaks());

export function persistTweaks() {
  if (typeof localStorage === 'undefined') return;
  localStorage.setItem('mathprover.tweaks', JSON.stringify(tweaks));
}

export const ACCENT_PALETTES: Record<string, { strong: string; soft: string; border: string }> = {
  '#8b7cf6': { strong: '#a594ff', soft: '#8b7cf61f', border: '#8b7cf640' },
  '#34d399': { strong: '#6ee7b7', soft: '#34d3991f', border: '#34d39940' },
  '#fb7185': { strong: '#fda4af', soft: '#fb71851f', border: '#fb718540' },
  '#fbbf24': { strong: '#fcd34d', soft: '#fbbf2433', border: '#fbbf2440' },
};

export const MODELS = [
  { id: 'auto',      name: 'auto-router',                    desc: 'Apply mathprover.toml rules (Goedel leaves, Aristotle capstone)', lat: 'mixed', available: true },
  { id: 'goedel',    name: 'goedel-prover-v2-32b (local MLX)', desc: 'Frontier leaves — first pass, local 8-bit MLX',               lat: '~30m', available: true },
  { id: 'aristotle', name: 'aristotle (cloud)',              desc: 'Capstone L1012 and escalation after local failures',          lat: '~10m', available: true },
] as const;

/** Models shown in the dispatch picker (implemented backends only). */
export const DISPATCH_MODELS = MODELS.filter((m) => m.available);
