import type { ProjectData, RunRecord } from './types';

function qs(projectRoot: string): string {
  return `?project=${encodeURIComponent(projectRoot)}`;
}

export async function fetchProject(projectRoot: string): Promise<ProjectData | null> {
  const res = await fetch(`/api/project${qs(projectRoot)}`);
  if (!res.ok) return null;
  const body = await res.json();
  return body.data as ProjectData;
}

export async function fetchDispatchPreview(
  projectRoot: string,
  nodeId: string,
  prover: string,
): Promise<{
  folder: string;
  prover: string;
  reason: string;
  goedelLocked?: boolean;
} | null> {
  const url = `/api/dispatch${qs(projectRoot)}&nodeId=${encodeURIComponent(nodeId)}&prover=${encodeURIComponent(prover)}`;
  const res = await fetch(url);
  if (!res.ok) return null;
  return res.json();
}

export async function postDispatch(
  projectRoot: string,
  nodeId: string,
  prover: string,
  skipVerify = false,
): Promise<{ runId: string; prover: string; reason: string; error?: string } | null> {
  const res = await fetch(`/api/dispatch${qs(projectRoot)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ nodeId, prover, skipVerify }),
  });
  const body = await res.json();
  if (!res.ok) return { runId: '', prover: '', reason: '', error: body.error ?? 'dispatch failed' };
  return body;
}

export async function fetchRuns(projectRoot: string): Promise<RunRecord[]> {
  const res = await fetch(`/api/runs${qs(projectRoot)}`);
  if (!res.ok) return [];
  const body = await res.json();
  return body.runs as RunRecord[];
}

export async function fetchGoedelStatus(projectRoot: string): Promise<{ locked: boolean; pid?: string }> {
  const res = await fetch(`/api/status/goedel${qs(projectRoot)}`);
  if (!res.ok) return { locked: false };
  return res.json();
}

export async function reindexProject(projectRoot: string): Promise<ProjectData | null> {
  const res = await fetch(`/api/reindex${qs(projectRoot)}`, { method: 'POST' });
  if (!res.ok) return null;
  const body = await res.json();
  return body.data as ProjectData | null;
}

export function subscribeRunStream(
  projectRoot: string,
  runId: string,
  handlers: {
    onLog?: (chunk: string) => void;
    onDone?: (run: RunRecord) => void;
    onError?: () => void;
  },
): () => void {
  const es = new EventSource(`/api/runs/${runId}/stream${qs(projectRoot)}`);
  es.addEventListener('log', (ev) => {
    const data = JSON.parse((ev as MessageEvent).data) as { chunk: string };
    handlers.onLog?.(data.chunk);
  });
  es.addEventListener('done', (ev) => {
    const data = JSON.parse((ev as MessageEvent).data) as RunRecord;
    handlers.onDone?.(data);
    es.close();
  });
  es.onerror = () => {
    handlers.onError?.();
    es.close();
  };
  return () => es.close();
}
