// Lean syntax highlighter + term lookup.
// Term metadata is loaded per-project from .mathprover/graph.json (`terms` field).

import type { TermInfo, TermLookup } from './types';
import { project } from './stores.svelte';

export type { TermInfo } from './types';

// Live view onto the project's term lookup table.
export const TERM_LOOKUP: TermLookup = new Proxy({} as TermLookup, {
  get(_t, p) { return Reflect.get(project.data.terms, p); },
  has(_t, p) { return Reflect.has(project.data.terms, p); },
  ownKeys() { return Reflect.ownKeys(project.data.terms); },
  getOwnPropertyDescriptor(_t, p) {
    const desc = Object.getOwnPropertyDescriptor(project.data.terms, p);
    if (desc) desc.configurable = true;
    return desc;
  },
});

const KEYWORDS = new Set([
  'theorem','lemma','def','by','have','exact','apply','rw','intro','obtain','sorry',
  'with','let','fun','match','do','if','then','else','return','axiom','structure',
  'inductive','namespace','open','import','variable','instance','where','linarith',
  'refine','unfold','simp','ring','positivity','induction','cases','rfl',
]);

const ESC: Record<string, string> = { '&': '&amp;', '<': '&lt;', '>': '&gt;' };
const esc = (s: string) => s.replace(/[&<>]/g, c => ESC[c]);

export function highlightLean(src: string): string {
  const lookup = project.data.terms;
  let s = esc(src);
  s = s.replace(/(\/--[\s\S]*?-\/)/g, '<span class="cm">$1</span>');
  s = s.replace(/(--[^\n]*)/g, '<span class="cm">$1</span>');
  s = s.replace(
    /\b(theorem|lemma|def|by|have|exact|apply|rw|intro|obtain|sorry|with|let|fun|match|do|if|then|else|return|axiom|structure|inductive|namespace|open|import|variable|instance|where|linarith|refine|unfold|simp|ring|positivity|induction|cases|rfl)\b/g,
    (m) => {
      if (m === 'sorry') return '<span class="so">sorry</span>';
      if (lookup[m]) return `<span class="kw lean-term" data-term="${m}">${m}</span>`;
      return `<span class="kw">${m}</span>`;
    }
  );
  s = s.replace(/\b([A-Z][A-Za-z0-9_]*)\b/g, (_m, name: string) => {
    if (lookup[name]) return `<span class="tp lean-term" data-term="${name}">${name}</span>`;
    return `<span class="tp">${name}</span>`;
  });
  for (const name of Object.keys(lookup)) {
    if (/^[a-z]/.test(name) && !KEYWORDS.has(name)) {
      const re = new RegExp('\\b(' + name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')\\b', 'g');
      s = s.replace(re, `<span class="fn lean-term" data-term="${name}">$1</span>`);
    }
  }
  s = s.replace(/(\b\d+(\.\d+)?\b)/g, '<span class="st">$1</span>');
  return s;
}

export function wrapTerms(html: string): string {
  const lookup = project.data.terms;
  return html.replace(
    /<span class="(fn|tp|kw)">([^<]+)<\/span>/g,
    (m, cls, name) => {
      if (lookup[name]) {
        return `<span class="lean-term ${cls}" data-term="${name}">${name}</span>`;
      }
      return m;
    }
  );
}

export function getTerm(name: string): TermInfo | undefined {
  return project.data.terms[name];
}

export function statusKey(status: string): string {
  if (status === 'PROVEN' || status === 'FULLY_PROVEN') return 'PROVEN';
  if (status === 'SORRIES' || status === 'PROVEN_WITH_SORRIES') return 'SORRIES';
  if (status === 'PROGRESS' || status === 'IN_PROGRESS') return 'PROGRESS';
  if (status === 'FAILED' || status === 'ATTEMPTED_FAILED') return 'FAILED';
  if (status === 'BLOCKED') return 'BLOCKED';
  if (status === 'READY') return 'READY';
  return 'UNEXPLORED';
}
