import { spawn, type ChildProcess } from "node:child_process";
import { isAbsolute, resolve, sep } from "node:path";
import type { RunRecord } from "$lib/types";
import { pythonBin, utcRunId } from "./project";
import { mathproverHome } from "./mathprover-home";

const activeProcesses = new Map<string, ChildProcess>();

function attachSpawnHandlers<T>(
  proc: ChildProcess,
  onClose: () => T,
  onFailure: () => T,
): Promise<T> {
  return new Promise((resolvePromise) => {
    proc.on("error", () => resolvePromise(onFailure()));
    proc.on("close", () => resolvePromise(onClose()));
  });
}

export async function previewRoute(
  root: string,
  nodeId: string,
  prover: string,
): Promise<{ folder: string; prover: string; reason: string } | null> {
  const proc = spawn(
    pythonBin(),
    ["agents/preview.py", "--root", root, nodeId, prover],
    {
      cwd: mathproverHome(),
      env: {
        ...process.env,
        MATHPROVER_HOME: mathproverHome(),
        MATHPROVER_PROJECT_PATH: root,
      },
    },
  );
  let out = "";
  proc.stdout.on("data", (d) => (out += d.toString()));

  return attachSpawnHandlers(
    proc,
    () => {
      try {
        return JSON.parse(out) as {
          folder: string;
          prover: string;
          reason: string;
        };
      } catch {
        return null;
      }
    },
    () => null,
  );
}

export function spawnDispatch(opts: {
  root: string;
  nodeId: string;
  prover: string;
  skipVerify?: boolean;
  runId?: string;
}): { runId: string; pid: number } {
  const runId = opts.runId ?? utcRunId();
  const args = [
    "agents/dispatch.py",
    "--root",
    opts.root,
    "--node",
    opts.nodeId,
    "--prover",
    opts.prover,
    "--run-id",
    runId,
  ];
  if (opts.skipVerify) args.push("--skip-verify");

  const proc = spawn(pythonBin(), args, {
    cwd: mathproverHome(),
    env: {
      ...process.env,
      MATHPROVER_HOME: mathproverHome(),
      MATHPROVER_PROJECT_PATH: opts.root,
    },
    detached: false,
    stdio: ["ignore", "pipe", "pipe"],
  });

  activeProcesses.set(runId, proc);
  proc.on("error", () => activeProcesses.delete(runId));
  proc.on("close", () => activeProcesses.delete(runId));

  return { runId, pid: proc.pid ?? 0 };
}

export function cancelRun(runId: string): boolean {
  const proc = activeProcesses.get(runId);
  if (!proc?.pid) return false;
  proc.kill("SIGTERM");
  activeProcesses.delete(runId);
  return true;
}

export async function readRuns(root: string): Promise<RunRecord[]> {
  const { readdir, readFile } = await import("node:fs/promises");
  const runsDir = resolve(root, ".mathprover/runs");
  try {
    const files = (await readdir(runsDir)).filter((f) => f.endsWith(".json"));
    const runs: RunRecord[] = [];
    for (const f of files) {
      try {
        runs.push(
          JSON.parse(await readFile(resolve(runsDir, f), "utf-8")) as RunRecord,
        );
      } catch {
        /* skip corrupt */
      }
    }
    return runs.sort((a, b) => b.started_at.localeCompare(a.started_at));
  } catch {
    return [];
  }
}

export function resolveLogPath(root: string, logPath: string): string {
  const normalized = logPath.replace(/\\/g, "/");
  if (isAbsolute(logPath) || normalized.split("/").includes("..")) {
    throw new Error("Invalid log path");
  }

  const rootReal = resolve(root);
  const full = resolve(rootReal, logPath);
  const attemptsRoot = resolve(rootReal, ".mathprover/attempts");
  if (!full.startsWith(attemptsRoot + sep) && full !== attemptsRoot) {
    throw new Error("Log path must stay under .mathprover/attempts");
  }
  return full;
}

export async function readLogTail(
  root: string,
  logPath: string,
  offset = 0,
): Promise<{ text: string; size: number }> {
  const { readFile, stat } = await import("node:fs/promises");
  const full = resolveLogPath(root, logPath);
  try {
    const st = await stat(full);
    const buf = await readFile(full);
    const text = buf.slice(Math.min(offset, buf.length)).toString("utf-8");
    return { text, size: st.size };
  } catch {
    return { text: "", size: 0 };
  }
}

function pidAlive(pid: number): boolean {
  if (!Number.isFinite(pid) || pid <= 0) return false;
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

export async function goedelLockStatus(
  root: string,
): Promise<{ locked: boolean; pid?: string }> {
  const { readFile, unlink } = await import("node:fs/promises");
  const lockPath = resolve(root, ".mathprover/locks/goedel.lock");
  try {
    const content = await readFile(lockPath, "utf-8");
    const m = content.match(/pid=(\d+)/);
    const pid = m ? Number(m[1]) : NaN;
    if (!pidAlive(pid)) {
      await unlink(lockPath).catch(() => {});
      return { locked: false };
    }
    return { locked: true, pid: String(pid) };
  } catch {
    return { locked: false };
  }
}

export { ProjectRootError, resolveRootFromRequest } from "./project";
