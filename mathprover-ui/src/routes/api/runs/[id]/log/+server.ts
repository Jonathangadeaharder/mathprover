import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { ProjectRootError, readLogTail, readRuns, resolveRootFromRequest } from '$lib/server/dispatch';

export const GET: RequestHandler = async ({ url, params }) => {
  try {
    const root = resolveRootFromRequest(url);
    const offset = Number(url.searchParams.get('offset') ?? '0');
    const runs = await readRuns(root);
    const run = runs.find((r) => r.id === params.id);
    if (!run?.log_path) return json({ error: 'run not found' }, { status: 404 });

    const { text, size } = await readLogTail(root, run.log_path, offset);
    return json({ id: params.id, text, size, offset });
  } catch (err) {
    if (err instanceof ProjectRootError) return json({ error: err.message }, { status: 400 });
    if (err instanceof Error && err.message.includes('log path')) {
      return json({ error: err.message }, { status: 400 });
    }
    throw err;
  }
};
