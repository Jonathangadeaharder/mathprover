import { existsSync, realpathSync } from 'node:fs';
import { readFile } from 'node:fs/promises';
import { homedir } from 'node:os';
import { isAbsolute, resolve, sep } from 'node:path';
import { spawn, type ChildProcess } from 'node:child_process';
import type { ProjectData } from '$lib/types';
import { EMPTY_PROJECT_DATA } from '$lib/data-empty';
import { isUnderRoot, mathproverHome } from './mathprover-home';

const PROJECT_MARKERS = ['lakefile.lean', 'mathprover.toml'];

export class ProjectRootError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ProjectRootError';
  }
}

export function expandHome(p: string): string {
  if (p.startsWith('~/')) return resolve(homedir(), p.slice(2));
  if (p === '~') return homedir();
  return p;
}

function realpathSafe(p: string): string {
  try {
    return realpathSync(p);
  } catch {
    return resolve(p);
  }
}

function defaultAllowedRoots(): string[] {
  const roots = new Set<string>();
  const add = (p: string) => roots.add(realpathSafe(expandHome(p)));

  add(process.cwd());
  add(resolve(process.cwd(), '..'));
  if (process.env.MATHPROVER_PROJECT_PATH) {
    add(process.env.MATHPROVER_PROJECT_PATH);
  }
  add('~/projects');
  add('~/Documents/projects');

  return [...roots];
}

function allowedRoots(): string[] {
  const env = process.env.MATHPROVER_ALLOWED_ROOTS;
  if (env) {
    return env
      .split(':')
      .map((entry) => entry.trim())
      .filter(Boolean)
      .map((entry) => realpathSafe(expandHome(entry)));
  }
  return defaultAllowedRoots();
}

function isUnderAllowedRoot(candidate: string, root: string): boolean {
  return isUnderRoot(candidate, root);
}

function hasProjectMarker(root: string): boolean {
  return PROJECT_MARKERS.some((marker) => existsSync(resolve(root, marker)));
}

export function resolveProjectRoot(raw?: string | null): string {
  const requested = (raw?.trim() || process.env.MATHPROVER_PROJECT_PATH || process.cwd()).trim();
  const normalized = requested.replace(/\\/g, '/');
  if (!requested || requested.includes('\0') || normalized.split('/').includes('..')) {
    throw new ProjectRootError('Invalid project path');
  }

  const resolved = isAbsolute(requested)
    ? resolve(requested)
    : resolve(process.cwd(), expandHome(requested));
  const canonical = realpathSafe(resolved);
  const permitted = allowedRoots();

  if (!permitted.some((root) => isUnderAllowedRoot(canonical, root))) {
    throw new ProjectRootError(`Project path is not under allowed roots: ${canonical}`);
  }
  if (!hasProjectMarker(canonical)) {
    throw new ProjectRootError(`Not a Lean/MathProver project (missing lakefile.lean): ${canonical}`);
  }

  return canonical;
}

export function graphPath(root: string): string {
  return resolve(root, '.mathprover/graph.json');
}

export async function loadGraph(root: string): Promise<ProjectData> {
  const raw = await readFile(graphPath(root), 'utf-8');
  const parsed = JSON.parse(raw) as Partial<ProjectData>;
  return { ...EMPTY_PROJECT_DATA, ...parsed } as ProjectData;
}

export async function enrichGraph(root: string): Promise<ProjectData> {
  const base = await loadGraph(root);
  const enriched = await runPythonJson<ProjectData>(
    root,
    ['scripts/index_runs.py', '--root', root, '--graph'],
  );
  if (!enriched) return base;
  return {
    ...base,
    ...enriched,
    project: { ...base.project, ...enriched.project },
    nodes: enriched.nodes?.length ? enriched.nodes : base.nodes,
    activeAgent: enriched.activeAgent ?? base.activeAgent,
  };
}

export function pythonBin(): string {
  return resolve(mathproverHome(), 'agents/.venv/bin/python');
}

function pythonEnv(projectRoot: string): NodeJS.ProcessEnv {
  return {
    ...process.env,
    MATHPROVER_HOME: mathproverHome(),
    MATHPROVER_PROJECT_PATH: projectRoot,
  };
}

function attachSpawnHandlers<T>(
  proc: ChildProcess,
  onClose: (code: number | null) => T,
  onFailure: (message: string) => T,
): Promise<T> {
  return new Promise((resolvePromise) => {
    proc.on('error', (err) => resolvePromise(onFailure(err.message)));
    proc.on('close', (code) => resolvePromise(onClose(code)));
  });
}

export function runPythonJson<T>(projectRoot: string, args: string[]): Promise<T | null> {
  const proc = spawn(pythonBin(), args, {
    cwd: mathproverHome(),
    env: pythonEnv(projectRoot),
  });
  let out = '';
  let err = '';
  proc.stdout.on('data', (d) => (out += d.toString()));
  proc.stderr.on('data', (d) => (err += d.toString()));

  return attachSpawnHandlers(
    proc,
    (code) => {
      if (code !== 0 || !out.trim()) {
        if (err) console.error('[python]', err.trim());
        return null;
      }
      try {
        return JSON.parse(out) as T;
      } catch {
        return null;
      }
    },
    (message) => {
      console.error('[python spawn]', message);
      return null;
    },
  );
}

export function runPythonText(
  projectRoot: string,
  args: string[],
): Promise<{ code: number; out: string; err: string }> {
  const proc = spawn(pythonBin(), args, {
    cwd: mathproverHome(),
    env: pythonEnv(projectRoot),
  });
  let out = '';
  let err = '';
  proc.stdout.on('data', (d) => (out += d.toString()));
  proc.stderr.on('data', (d) => (err += d.toString()));

  return attachSpawnHandlers(
    proc,
    (code) => ({ code: code ?? 1, out, err }),
    (message) => ({ code: 1, out: '', err: message }),
  );
}

export function utcRunId(): string {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, '0');
  return (
    d.getUTCFullYear() +
    pad(d.getUTCMonth() + 1) +
    pad(d.getUTCDate()) +
    'T' +
    pad(d.getUTCHours()) +
    pad(d.getUTCMinutes()) +
    pad(d.getUTCSeconds()) +
    'Z'
  );
}

export function projectQuery(url: URL): string {
  return url.searchParams.get('project') ?? '';
}

export function resolveRootFromRequest(url: URL): string {
  return resolveProjectRoot(url.searchParams.get('project'));
}
