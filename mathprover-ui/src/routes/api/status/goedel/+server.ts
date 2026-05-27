import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { goedelLockStatus, ProjectRootError, resolveRootFromRequest } from '$lib/server/dispatch';

export const GET: RequestHandler = async ({ url }) => {
  try {
    const root = resolveRootFromRequest(url);
    const lock = await goedelLockStatus(root);
    return json(lock);
  } catch (err) {
    if (err instanceof ProjectRootError) return json({ error: err.message }, { status: 400 });
    throw err;
  }
};
