import { existsSync, readdirSync, realpathSync, statSync } from "node:fs";
import { readdir, readFile } from "node:fs/promises";
import { homedir } from "node:os";
import { isAbsolute, resolve, sep } from "node:path";
import { spawn, type ChildProcess } from "node:child_process";
import type { ProjectData, RunRecord, TheoremNode } from "$lib/types";
import { EMPTY_PROJECT_DATA } from "$lib/data-empty";
import { isUnderRoot, mathproverHome } from "./mathprover-home";
import { log } from "$lib/telemetry";

const PROJECT_MARKERS = ["lakefile.lean", "mathprover.toml"];

export class ProjectRootError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ProjectRootError";
  }
}

export function expandHome(p: string): string {
  if (p.startsWith("~/")) return resolve(homedir(), p.slice(2));
  if (p === "~") return homedir();
  return p;
}

function realpathSafe(p: string): string {
  try {
    return realpathSync(p);
  } catch {
    return resolve(p);
  }
}

function defaultAllowedRoots(): string[] {
  const roots = new Set<string>();
  const add = (p: string) => roots.add(realpathSafe(expandHome(p)));

  add(process.cwd());
  add(resolve(process.cwd(), ".."));
  if (process.env.MATHPROVER_PROJECT_PATH) {
    add(process.env.MATHPROVER_PROJECT_PATH);
  }
  add("~/projects");
  add("~/Documents/projects");

  return [...roots];
}

function allowedRoots(): string[] {
  const env = process.env.MATHPROVER_ALLOWED_ROOTS;
  if (env) {
    return env
      .split(":")
      .map((entry) => entry.trim())
      .filter(Boolean)
      .map((entry) => realpathSafe(expandHome(entry)));
  }
  return defaultAllowedRoots();
}

function isUnderAllowedRoot(candidate: string, root: string): boolean {
  return isUnderRoot(candidate, root);
}

function hasProjectMarker(root: string): boolean {
  return PROJECT_MARKERS.some((marker) => existsSync(resolve(root, marker)));
}

export function resolveProjectRoot(raw?: string | null): string {
  const explicit = raw?.trim() || process.env.MATHPROVER_PROJECT_PATH;
  if (explicit) {
    const normalized = explicit.replace(/\\/g, "/");
    if (normalized.split("/").includes("..")) {
      throw new ProjectRootError("Invalid project path: contains ..");
    }
    const resolved = isAbsolute(explicit)
      ? resolve(explicit)
      : resolve(process.cwd(), expandHome(explicit));
    const canonical = realpathSafe(resolved);
    const permitted = allowedRoots();
    if (!permitted.some((root) => isUnderAllowedRoot(canonical, root))) {
      throw new ProjectRootError(`Project path is not under allowed roots: ${canonical}`);
    }
    if (!hasProjectMarker(canonical)) {
      throw new ProjectRootError(`Not a Lean/MathProver project (missing lakefile.lean): ${canonical}`);
    }
    return canonical;
  }

  const detected = autoDetectProject();
  if (detected) return detected;

  throw new ProjectRootError(
    "No project found. Set ?project=<path> or MATHPROVER_PROJECT_PATH, or place a project under ~/projects."
  );
}

function autoDetectProject(): string | null {
  const roots = allowedRoots();
  const candidates: string[] = [];

  for (const root of roots) {
    try {
      const entries = readdirSync(root);
      for (const entry of entries) {
        const full = resolve(root, entry);
        try {
          const st = statSync(full);
          if (!st.isDirectory()) continue;
        } catch { continue; }
        if (hasProjectMarker(full)) candidates.push(full);
      }
    } catch { /* root doesn't exist */ }
  }

  if (candidates.length === 0) return null;

  candidates.sort((a, b) => {
    const ga = existsSync(resolve(a, ".mathprover/graph.json")) ? 1 : 0;
    const gb = existsSync(resolve(b, ".mathprover/graph.json")) ? 1 : 0;
    if (ga !== gb) return gb - ga;
    return a.localeCompare(b);
  });

  return candidates[0];
}

export function graphPath(root: string): string {
  return resolve(root, ".mathprover/graph.json");
}

export async function loadGraph(root: string): Promise<ProjectData> {
  const raw = await readFile(graphPath(root), "utf-8");
  const parsed = JSON.parse(raw) as Partial<ProjectData>;
  return { ...EMPTY_PROJECT_DATA, ...parsed } as ProjectData;
}

export async function enrichGraph(root: string): Promise<ProjectData> {
  const base = await loadGraph(root);
  const enriched = await runPythonJson<ProjectData>(root, [
    "scripts/index_runs.py",
    "--root",
    root,
    "--graph",
  ]);
  if (!enriched) return enrichGraphWithLiveRuns(root, base);
  return enrichGraphWithLiveRuns(root, {
    ...base,
    ...enriched,
    project: { ...base.project, ...enriched.project },
    nodes: enriched.nodes?.length ? enriched.nodes : base.nodes,
    activeAgent: enriched.activeAgent ?? base.activeAgent,
  });
}

async function readRunRegistry(root: string): Promise<RunRecord[]> {
  const runsDir = resolve(root, ".mathprover/runs");
  try {
    const files = (await readdir(runsDir)).filter((f) => f.endsWith(".json"));
    const runs: RunRecord[] = [];
    for (const file of files) {
      try {
        runs.push(
          JSON.parse(await readFile(resolve(runsDir, file), "utf-8")) as RunRecord,
        );
      } catch {
        /* skip corrupt run records */
      }
    }
    return runs.sort((a, b) => b.started_at.localeCompare(a.started_at));
  } catch {
    return [];
  }
}

function runStatus(run: RunRecord): TheoremNode["status"] {
  if (isStaleRun(run)) return "BLOCKED";
  if (run.status === "pending" || run.status === "running") return "IN_PROGRESS";
  if (run.status === "ok") return "PROVEN";
  if (run.status === "failed" || run.status === "error") return "STUCK";
  return "UNEXPLORED";
}

function runSource(run: RunRecord): string {
  return `.mathprover/runs/${run.id}.json`;
}

function isStaleRun(run: RunRecord): boolean {
  if (run.status !== "pending" && run.status !== "running") return false;
  const twelveHours = 12 * 60 * 60 * 1000;
  if (run.heartbeat_at) {
    const heartbeat = Date.parse(run.heartbeat_at);
    if (Number.isFinite(heartbeat)) return Date.now() - heartbeat > twelveHours;
  }
  const started = Date.parse(run.started_at);
  if (!Number.isFinite(started)) return false;
  return Date.now() - started > twelveHours;
}

function isClosedWorkerState(state: string | undefined): boolean {
  if (!state) return false;
  const normalized = state.toLowerCase();
  return (
    normalized.includes("done") ||
    normalized.includes("solved") ||
    normalized.includes("complete") ||
    normalized.includes("real_proven")
  );
}

function shouldRunOverrideNode(node: TheoremNode, run: RunRecord): boolean {
  if (run.status === "pending" || run.status === "running") return !isStaleRun(run);
  if (node.status === "PROVEN" && (run.status === "failed" || run.status === "error")) {
    return false;
  }
  if (isClosedWorkerState(node.worker_state) && (run.status === "failed" || run.status === "error")) {
    return false;
  }
  return true;
}

function runNodeId(run: RunRecord): string {
  return run.node_id || run.proof_folder || run.id;
}

function parentGoalForRunNode(id: string): string | null {
  if (id.startsWith("CRN_R1_")) return "CRN_constant_ratio_runtime";
  if (id.startsWith("CRN_R2_")) return "CRN_constant_ratio_runtime";
  if (id.startsWith("CRN_R3_")) return "CRN_constant_ratio_runtime";
  if (id.startsWith("CRN_R4_")) return "CRN_constant_ratio_runtime";
  if (id === "A3a_core") return "CRN_constant_ratio_runtime";
  if (id === "A3a_constant_ratio_bridge") return "CRN_constant_ratio_runtime";
  return null;
}

function goalNote(id: string): string {
  const parent = parentGoalForRunNode(id);
  return parent ? `Goal: prerequisite for ${parent}. ` : "";
}

function humanizeId(id: string): string {
  return id
    .replaceAll("_", " ")
    .replace(/\bcrn\b/gi, "CRN")
    .replace(/\ba3a\b/gi, "A3a")
    .replace(/\blbt\b/gi, "LBT")
    .replace(/\s+/g, " ")
    .trim();
}

function activeAgentFromRun(run: RunRecord): ProjectData["activeAgent"] {
  return {
    node: runNodeId(run),
    agent: run.prover,
    started: run.started_at,
    step: 0,
    totalSteps: 4,
    runId: run.id,
    phase: run.phase ?? undefined,
    detail: run.detail ?? undefined,
    tokensGenerated: run.tokens_generated ?? undefined,
    tokensPerSec: run.tokens_per_sec ?? undefined,
    heartbeatAt: run.heartbeat_at ?? undefined,
    log: [],
  };
}

function syntheticNodeFromRun(run: RunRecord): TheoremNode {
  const id = runNodeId(run);
  const parent = parentGoalForRunNode(id);
  const label = friendlyWorkerLabel(id);
  const folderLabel = humanizeId(run.proof_folder || id);
  return {
    id,
    paper_id: label.short,
    paper_name: label.desc,
    lean_theorem: id,
    lean_file: `proofs/${run.proof_folder || id}/attempt.lean`,
    lean_line: null,
    paper_file: `proofs/${run.proof_folder || id}/paper_source.md`,
    paper_section: parent ? `Supports ${parent}` : `Discovered node: ${folderLabel}`,
    status: runStatus(run),
    depends_on: [],
    uses_defs: [],
    importance: 0.55,
    difficulty: "worker",
    confidence: null,
    tokens_spent: 0,
    attempts: 0,
    note: `${goalNote(id)}${run.prover} ${isStaleRun(run) ? "stale running" : run.status}; source ${runSource(run)}; folder ${run.proof_folder || id}`,
    proof_folder: run.proof_folder || id,
    worker_state: isStaleRun(run) ? "stale" : run.status,
    attemptsLog: [],
    sorries: [],
  };
}

function friendlyWorkerLabel(id: string): { short: string; desc: string } {
  if (id.startsWith("CRN_R1_")) return { short: "R1", desc: `CRN R1 bridge: kernel founder mass` };
  if (id.startsWith("CRN_R2_")) return { short: "R2", desc: `CRN R2 bridge: founder mass scaling` };
  if (id.startsWith("CRN_R3_")) return { short: "R3", desc: `CRN R3 bridge: positive founder survival` };
  if (id.startsWith("CRN_R4_")) return { short: "R4", desc: `CRN R4 bridge: robust-fill assembly` };
  if (id === "A3a_core") return { short: "A3a", desc: `A3a core survival bound` };
  if (id === "A3a_constant_ratio_bridge") return { short: "A3a-bridge", desc: `A3a constant-ratio bridge` };
  return { short: id.split("_").slice(0, 2).join("_"), desc: `Worker node: ${humanizeId(id)}` };
}

async function enrichGraphWithLiveRuns(
  root: string,
  graph: ProjectData,
): Promise<ProjectData> {
  const runs = await readRunRegistry(root);
  if (runs.length === 0) return graph;

  const nodes = graph.nodes.map((node) => ({ ...node }));
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const byFolder = new Map(
    nodes
      .filter((node) => node.proof_folder)
      .map((node) => [node.proof_folder as string, node]),
  );

  const latestByNode = new Map<string, RunRecord>();
  for (const run of runs) {
    const id = runNodeId(run);
    if (!latestByNode.has(id)) latestByNode.set(id, run);
  }

  for (const run of latestByNode.values()) {
    const id = runNodeId(run);
    const parentId = parentGoalForRunNode(id);
    let node = byId.get(id) || byFolder.get(run.proof_folder);
    if (!node && (run.status === "pending" || run.status === "running" || parentId)) {
      node = syntheticNodeFromRun(run);
      nodes.push(node);
      byId.set(node.id, node);
      if (node.proof_folder) byFolder.set(node.proof_folder, node);
    }
    if (!node) continue;

    if (parentId) {
      const parent = byId.get(parentId);
      if (parent && !parent.depends_on.includes(node.id)) {
        parent.depends_on = [...parent.depends_on, node.id];
      }
      node.paper_section ||= `Supports ${parentId}`;
    } else if (!node.paper_section && node.proof_folder) {
      node.paper_section = `Proof folder: ${humanizeId(node.proof_folder)}`;
    }

    node.proof_folder = node.proof_folder || run.proof_folder;
    if (!shouldRunOverrideNode(node, run)) {
      node.note = `${node.note || ""}${node.note ? " · " : ""}Ignored stale/failed run ${run.id} from ${runSource(run)} because node is already ${node.status}${node.worker_state ? `/${node.worker_state}` : ""}.`;
      continue;
    }

    node.worker_state = isStaleRun(run) ? "stale" : run.status;
    if (!node.note && node.proof_folder) {
      node.note = `Source folder: ${node.proof_folder}.`;
    }
    if ((run.status === "pending" || run.status === "running") && !isStaleRun(run)) {
      node.status = "IN_PROGRESS";
      node.note = `${goalNote(id)}${run.prover} ${run.status} since ${run.started_at}; source ${runSource(run)}; folder ${run.proof_folder}`;
    } else if (isStaleRun(run)) {
      node.status = "BLOCKED";
      node.note = `${goalNote(id)}${run.prover} stale running record from ${run.started_at}; source ${runSource(run)}; folder ${run.proof_folder}`;
    } else if (run.status === "ok") {
      node.status = "PROVEN";
      node.note = `${goalNote(id)}${run.prover} verified ok at ${run.started_at}; source ${runSource(run)}; folder ${run.proof_folder}`;
    } else if (run.status === "failed" || run.status === "error") {
      node.status = "STUCK";
      node.note = `${goalNote(id)}${run.prover} ${run.status} at ${run.started_at}; source ${runSource(run)}; folder ${run.proof_folder}${run.message ? `; ${run.message}` : ""}`;
    }
  }

  const active = runs.find(
    (run) => (run.status === "running" || run.status === "pending") && !isStaleRun(run),
  );
  return {
    ...graph,
    nodes,
    activeAgent: active ? activeAgentFromRun(active) : null,
  };
}

export function pythonBin(): string {
  return resolve(mathproverHome(), "agents/.venv/bin/python");
}

function pythonEnv(projectRoot: string): NodeJS.ProcessEnv {
  return {
    ...process.env,
    MATHPROVER_HOME: mathproverHome(),
    MATHPROVER_PROJECT_PATH: projectRoot,
  };
}

function attachSpawnHandlers<T>(
  proc: ChildProcess,
  onClose: (code: number | null) => T,
  onFailure: (message: string) => T,
): Promise<T> {
  return new Promise((resolvePromise) => {
    proc.on("error", (err) => resolvePromise(onFailure(err.message)));
    proc.on("close", (code) => resolvePromise(onClose(code)));
  });
}

export function runPythonJson<T>(
  projectRoot: string,
  args: string[],
): Promise<T | null> {
  const proc = spawn(pythonBin(), args, {
    cwd: mathproverHome(),
    env: pythonEnv(projectRoot),
  });
  let out = "";
  let err = "";
  proc.stdout.on("data", (d) => (out += d.toString()));
  proc.stderr.on("data", (d) => (err += d.toString()));

  return attachSpawnHandlers(
    proc,
    (code) => {
      if (code !== 0 || !out.trim()) {
        if (err) log.error({ err: err.trim() }, "python subprocess error");
        return null;
      }
      try {
        return JSON.parse(out) as T;
      } catch {
        return null;
      }
    },
    (message) => {
      log.error({ message }, "python spawn failed");
      return null;
    },
  );
}

export function runPythonText(
  projectRoot: string,
  args: string[],
): Promise<{ code: number; out: string; err: string }> {
  const proc = spawn(pythonBin(), args, {
    cwd: mathproverHome(),
    env: pythonEnv(projectRoot),
  });
  let out = "";
  let err = "";
  proc.stdout.on("data", (d) => (out += d.toString()));
  proc.stderr.on("data", (d) => (err += d.toString()));

  return attachSpawnHandlers(
    proc,
    (code) => ({ code: code ?? 1, out, err }),
    (message) => ({ code: 1, out: "", err: message }),
  );
}

export function utcRunId(): string {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    d.getUTCFullYear() +
    pad(d.getUTCMonth() + 1) +
    pad(d.getUTCDate()) +
    "T" +
    pad(d.getUTCHours()) +
    pad(d.getUTCMinutes()) +
    pad(d.getUTCSeconds()) +
    "Z"
  );
}

export function projectQuery(url: URL): string {
  return url.searchParams.get("project") ?? "";
}

export function resolveRootFromRequest(url: URL): string {
  return resolveProjectRoot(url.searchParams.get("project"));
}
