import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { enrichGraph, runPythonText } from '$lib/server/project';
import { ProjectRootError, resolveRootFromRequest } from '$lib/server/dispatch';

export const POST: RequestHandler = async ({ url }) => {
  try {
    const root = resolveRootFromRequest(url);
    const backfill = await runPythonText(root, [
      'scripts/index_runs.py',
      '--root',
      root,
      '--backfill',
    ]);
    const build = await runPythonText(root, ['scripts/build_graph.py', '--root', root]);
    let data = null;
    let error: string | null = null;
    try {
      data = await enrichGraph(root);
    } catch (err) {
      error = (err as Error).message;
    }
    return json({
      ok: build.code === 0,
      backfill: backfill.out.trim(),
      build: build.out.trim() || build.err.trim(),
      data,
      error,
    });
  } catch (err) {
    if (err instanceof ProjectRootError) return json({ error: err.message }, { status: 400 });
    throw err;
  }
};
