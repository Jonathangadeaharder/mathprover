import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { ProjectRootError, readRuns, resolveRootFromRequest } from '$lib/server/dispatch';

export const GET: RequestHandler = async ({ url }) => {
  try {
    const root = resolveRootFromRequest(url);
    const runs = await readRuns(root);
    return json({ runs });
  } catch (err) {
    if (err instanceof ProjectRootError) return json({ error: err.message }, { status: 400 });
    throw err;
  }
};
