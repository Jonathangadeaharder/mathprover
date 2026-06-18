import { enrichGraph, resolveProjectRoot } from "$lib/server/project";
import { resolve } from "node:path";
import type { LayoutServerLoad } from "./$types";
import { EMPTY_PROJECT_DATA } from "$lib/data-empty";

export const load: LayoutServerLoad = async ({ url }) => {
  let root: string;
  try {
    root = resolveProjectRoot(url.searchParams.get("project"));
  } catch (err) {
    return {
      projectData: EMPTY_PROJECT_DATA,
      projectRoot: "",
      error: err instanceof Error ? err.message : "Invalid project path",
    };
  }

  const graphFile = resolve(root, ".mathprover/graph.json");

  try {
    const data = await enrichGraph(root);
    return {
      projectData: data,
      projectRoot: root,
      error: null as string | null,
    };
  } catch (err) {
    return {
      projectData: EMPTY_PROJECT_DATA,
      projectRoot: root,
      error: `Failed to load ${graphFile}: ${(err as Error).message}`,
    };
  }
};
