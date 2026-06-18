import { json } from "@sveltejs/kit";
import type { RequestHandler } from "./$types";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { resolveRootFromRequest, ProjectRootError } from "$lib/server/dispatch";

export const GET: RequestHandler = async ({ url }) => {
  try {
    const root = resolveRootFromRequest(url);
    const nodeId = url.searchParams.get("node");
    if (!nodeId) {
      return json(
        { paper: null, lean: null, error: "Missing ?node=" },
        { status: 400 },
      );
    }

    const folder = url.searchParams.get("folder") || nodeId;
    const proofDir = resolve(root, "proofs", folder);

    let paper: string | null = null;
    let lean: string | null = null;
    let status: string | null = null;

    try {
      paper = await readFile(resolve(proofDir, "paper_source.md"), "utf-8");
    } catch {
      /* not found */
    }

    try {
      lean = await readFile(resolve(proofDir, "attempt.lean"), "utf-8");
    } catch {
      /* not found */
    }

    try {
      status = await readFile(resolve(proofDir, "status.md"), "utf-8");
    } catch {
      /* not found */
    }

    return json({ paper, lean, status, error: null });
  } catch (err) {
    if (err instanceof ProjectRootError) {
      return json(
        { paper: null, lean: null, error: err.message },
        { status: 400 },
      );
    }
    return json(
      { paper: null, lean: null, error: (err as Error).message },
      { status: 500 },
    );
  }
};
