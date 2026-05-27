// Project data is loaded at request time from .mathprover/graph.json by
// +layout.server.ts. These exports are live views into the reactive `project`
// store. No paper/Lean/foundation content is hardcoded here.

import type {
  Definition,
  Failure,
  Foundation,
  LeanBlock,
  LiveAgent,
  PaperBlock,
  Project,
  RecentProject,
  TermLookup,
  TheoremNode,
} from './types';
import { project } from './stores.svelte';

export { EMPTY_PROJECT_DATA } from './data-empty';

const d = () => project.data;

// --- live array proxies ------------------------------------------------------
function arrayProxy<T>(getter: () => T[]): T[] {
  return new Proxy([] as T[], {
    get(_t, p) {
      const arr = getter();
      const v = Reflect.get(arr, p);
      return typeof v === 'function' ? v.bind(arr) : v;
    },
    has(_t, p) { return Reflect.has(getter(), p); },
    ownKeys() { return Reflect.ownKeys(getter()); },
    getOwnPropertyDescriptor(_t, p) {
      return Object.getOwnPropertyDescriptor(getter(), p);
    },
  });
}

function recordProxy<V>(getter: () => Record<string, V>): Record<string, V> {
  return new Proxy({} as Record<string, V>, {
    get(_t, p) { return Reflect.get(getter(), p); },
    has(_t, p) { return Reflect.has(getter(), p); },
    ownKeys() { return Reflect.ownKeys(getter()); },
    getOwnPropertyDescriptor(_t, p) {
      const desc = Object.getOwnPropertyDescriptor(getter(), p);
      if (desc) desc.configurable = true;
      return desc;
    },
  });
}

export const NODES: TheoremNode[] = arrayProxy(() => d().nodes);
export const DEFINITIONS: Definition[] = arrayProxy(() => d().definitions);
export const FOUNDATIONS: Foundation[] = arrayProxy(() => d().foundations);
export const FAILURES: Failure[] = arrayProxy(() => d().failures);
export const RECENT_PROJECTS: RecentProject[] = arrayProxy(() => d().recents);
export const PAPER_BLOCKS: PaperBlock[] = arrayProxy(() => d().paperBlocks);
export const LEAN_BLOCKS: LeanBlock[] = arrayProxy(() => d().leanBlocks);

export const NODE_BY_ID: Record<string, TheoremNode> = recordProxy(() =>
  Object.fromEntries(d().nodes.map((n) => [n.id, n])),
);

export const DEF_BY_ID: Record<string, Definition> = recordProxy(() =>
  Object.fromEntries(d().definitions.map((def) => [def.id, def])),
);

// Live "theorems that use this definition" backlinks.
export const DEF_USED_BY: Record<string, string[]> = recordProxy(() => {
  const m: Record<string, string[]> = {};
  for (const def of d().definitions) m[def.id] = [];
  for (const n of d().nodes) {
    for (const did of n.uses_defs || []) m[did]?.push(n.id);
  }
  return m;
});

export const CHILDREN_BY_ID: Record<string, string[]> = recordProxy(() => {
  const c: Record<string, string[]> = {};
  for (const n of d().nodes) c[n.id] = [];
  for (const n of d().nodes) for (const dep of n.depends_on) c[dep]?.push(n.id);
  return c;
});

export const TERMS_BY_NAME: TermLookup = recordProxy(() => d().terms);

// Scalar getters — call as functions, components read with reactivity preserved
// because they touch project.data which is $state.
export const sampleProject = (): Project => d().project;
export const activeAgent = (): LiveAgent | null => d().activeAgent;

// Back-compat names used in older imports.
export const SAMPLE_PROJECT = new Proxy({} as Project, {
  get(_t, p) { return Reflect.get(d().project, p); },
  ownKeys() { return Reflect.ownKeys(d().project); },
  getOwnPropertyDescriptor(_t, p) {
    const desc = Object.getOwnPropertyDescriptor(d().project, p);
    if (desc) desc.configurable = true;
    return desc;
  },
});

export const ACTIVE_AGENT = new Proxy({} as LiveAgent, {
  get(_t, p) {
    const a = d().activeAgent;
    return a ? Reflect.get(a, p) : undefined;
  },
  ownKeys() { return d().activeAgent ? Reflect.ownKeys(d().activeAgent!) : []; },
  getOwnPropertyDescriptor(_t, p) {
    const a = d().activeAgent;
    if (!a) return undefined;
    const desc = Object.getOwnPropertyDescriptor(a, p);
    if (desc) desc.configurable = true;
    return desc;
  },
});
