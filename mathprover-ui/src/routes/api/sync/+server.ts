import { json } from "@sveltejs/kit";
import type { RequestHandler } from "./$types";
import { syncProject } from "$lib/server/project";
import { ProjectRootError, resolveRootFromRequest } from "$lib/server/dispatch";

export const POST: RequestHandler = async ({ url }) => {
  try {
    const root = resolveRootFromRequest(url);
    const result = await syncProject(root);
    return json(result);
  } catch (err) {
    if (err instanceof ProjectRootError) {
      return json({ error: err.message }, { status: 400 });
    }
    throw err;
  }
};
