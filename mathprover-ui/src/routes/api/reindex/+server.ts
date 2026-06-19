import { json } from "@sveltejs/kit";
import type { RequestHandler } from "./$types";
import { enrichGraph, reindexProjectGraph } from "$lib/server/project";
import { ProjectRootError, resolveRootFromRequest } from "$lib/server/dispatch";

export const POST: RequestHandler = async ({ url }) => {
  try {
    const root = resolveRootFromRequest(url);
    const build = await reindexProjectGraph(root);
    let data = null;
    let error: string | null = null;
    try {
      data = await enrichGraph(root);
    } catch (err) {
      error = (err as Error).message;
    }
    return json({
      ok: build.code === 0,
      build: build.out.trim() || build.err.trim(),
      data,
      error,
    });
  } catch (err) {
    if (err instanceof ProjectRootError)
      return json({ error: err.message }, { status: 400 });
    throw err;
  }
};
