import { existsSync, realpathSync } from "node:fs";
import { resolve, sep } from "node:path";

function realpathSafe(p: string): string {
  try {
    return realpathSync(p);
  } catch {
    return resolve(p);
  }
}

/** MathProver tooling root (agents/, scripts/). Not the Lean project under work. */
export function mathproverHome(): string {
  const env = process.env.MATHPROVER_HOME?.trim();
  if (env) return realpathSafe(env);

  const cwd = realpathSafe(process.cwd());
  const candidates = [cwd, resolve(cwd, ".."), resolve(cwd, "../..")];
  for (const candidate of candidates) {
    if (existsSync(resolve(candidate, "agents/dispatch.py"))) {
      return candidate;
    }
  }

  throw new Error(
    "MATHPROVER_HOME is not set and agents/dispatch.py was not found. " +
      "Set MATHPROVER_HOME to the MathProver repository root.",
  );
}

export function isUnderRoot(candidate: string, root: string): boolean {
  return candidate === root || candidate.startsWith(root + sep);
}
