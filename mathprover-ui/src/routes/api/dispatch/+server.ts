import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { goedelLockStatus, previewRoute, ProjectRootError, resolveRootFromRequest, spawnDispatch } from '$lib/server/dispatch';

export const GET: RequestHandler = async ({ url }) => {
  try {
    const root = resolveRootFromRequest(url);
    const nodeId = url.searchParams.get('nodeId');
    const prover = url.searchParams.get('prover') ?? 'auto';
    if (!nodeId) return json({ error: 'nodeId required' }, { status: 400 });
    const preview = await previewRoute(root, nodeId, prover);
    if (!preview) return json({ error: 'preview failed' }, { status: 500 });
    const lock = await goedelLockStatus(root);
    return json({ ...preview, goedelLocked: lock.locked, goedelPid: lock.pid });
  } catch (err) {
    if (err instanceof ProjectRootError) return json({ error: err.message }, { status: 400 });
    throw err;
  }
};

export const POST: RequestHandler = async ({ url, request }) => {
  try {
    const root = resolveRootFromRequest(url);
    const body = (await request.json()) as {
      nodeId: string;
      prover?: string;
      skipVerify?: boolean;
    };
    if (!body.nodeId) return json({ error: 'nodeId required' }, { status: 400 });

    const prover = body.prover ?? 'auto';
    if (prover === 'goedel') {
      const lock = await goedelLockStatus(root);
      if (lock.locked) {
        return json({ error: 'Goedel is busy (exclusive lock held)', locked: true }, { status: 409 });
      }
    }

    const preview = await previewRoute(root, body.nodeId, prover);
    if (!preview) return json({ error: 'could not resolve node' }, { status: 404 });

    const { runId, pid } = spawnDispatch({
      root,
      nodeId: body.nodeId,
      prover,
      skipVerify: body.skipVerify ?? false,
    });

    return json({
      runId,
      pid,
      folder: preview.folder,
      prover: preview.prover,
      reason: preview.reason,
    });
  } catch (err) {
    if (err instanceof ProjectRootError) return json({ error: err.message }, { status: 400 });
    throw err;
  }
};
