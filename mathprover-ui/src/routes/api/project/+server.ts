import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { enrichGraph } from '$lib/server/project';
import { ProjectRootError, resolveRootFromRequest } from '$lib/server/dispatch';

export const GET: RequestHandler = async ({ url }) => {
  try {
    const root = resolveRootFromRequest(url);
    const data = await enrichGraph(root);
    return json({ data, projectRoot: root, error: null });
  } catch (err) {
    if (err instanceof ProjectRootError) {
      return json({ data: null, projectRoot: '', error: err.message }, { status: 400 });
    }
    return json({ data: null, projectRoot: '', error: (err as Error).message }, { status: 500 });
  }
};
