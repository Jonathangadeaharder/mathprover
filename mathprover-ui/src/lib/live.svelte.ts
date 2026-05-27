import { fetchGoedelStatus, fetchProject, subscribeRunStream } from './api';
import { setProjectData, app, project } from './stores.svelte';

let pollTimer: ReturnType<typeof setInterval> | null = null;
let streamCleanup: (() => void) | null = null;

export function setProjectRoot(root: string) {
  app.projectRoot = root;
}

export async function refreshProject() {
  if (!app.projectRoot) return;
  const data = await fetchProject(app.projectRoot);
  if (data) setProjectData(data);
}

export function startLivePolling() {
  stopLivePolling();
  const tick = async () => {
    await refreshProject();
    await checkGoedelLock();
    const active = project.data.activeAgent;
    if (active?.runId && active.runId !== app.activeRunId) {
      app.activeRunId = active.runId;
      attachRunStream(active.runId);
    }
  };
  tick();
  pollTimer = setInterval(tick, app.activeRunId ? 3000 : 10000);
}

export function stopLivePolling() {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = null;
  streamCleanup?.();
  streamCleanup = null;
}

export function attachRunStream(runId: string) {
  if (!app.projectRoot) return;
  streamCleanup?.();
  app.liveLogText = '';
  streamCleanup = subscribeRunStream(app.projectRoot, runId, {
    onLog: (chunk) => {
      app.liveLogText += chunk;
    },
    onDone: async () => {
      app.activeRunId = null;
      await refreshProject();
    },
    onError: () => {
      /* polling will pick up completion */
    },
  });
}

export async function checkGoedelLock() {
  if (!app.projectRoot) return;
  app.goedelLocked = (await fetchGoedelStatus(app.projectRoot)).locked;
}
