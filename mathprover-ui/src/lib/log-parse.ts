export type LogLine = { t: string; lvl: string; msg: string };

export type TimelineStep = {
  kind: 'info' | 'warn' | 'success' | 'fail';
  title: string;
  time: string;
  summary: string;
  tactic?: string;
};

const PATTERNS: { re: RegExp; lvl: string; title?: string }[] = [
  { re: /^\[heartbeat\]/, lvl: 'think', title: 'Generating tokens' },
  { re: /^\[generate\]/, lvl: 'info', title: 'Generation phase' },
  { re: /^\[compile\]/, lvl: 'info', title: 'Compiling candidate' },
  { re: /^loaded in/, lvl: 'ok', title: 'Model ready' },
  { re: /^=== sample (\d+)\/(\d+) ===/, lvl: 'think', title: 'Sample generation' },
  { re: /^--- correction round (\d+) ---/, lvl: 'warn', title: 'Self-correction' },
  { re: /^compile: ok/, lvl: 'ok', title: 'Lean compile succeeded' },
  { re: /^compile: failed/, lvl: 'err', title: 'Lean compile failed' },
  { re: /^extract: no lean4 block/, lvl: 'warn', title: 'No Lean block in output' },
  { re: /^extract: candidate still contains sorry/, lvl: 'warn', title: 'Proof still has sorry' },
  { re: /^pipeline exhausted/, lvl: 'err', title: 'All samples exhausted' },
  { re: /^--- lake build ---/, lvl: 'info', title: 'Verifying project build' },
  { re: /"success":\s*true/, lvl: 'ok', title: 'Prover reported success' },
  { re: /error:/i, lvl: 'err', title: 'Error' },
];

export function parseLogText(raw: string, startedAt?: string): LogLine[] {
  const lines: LogLine[] = [];
  const t0 = startedAt ? new Date(startedAt) : new Date();
  let i = 0;
  for (const line of raw.split('\n')) {
    const trimmed = line.trimEnd();
    if (!trimmed) continue;
    const matched = PATTERNS.find((p) => p.re.test(trimmed));
    const lvl = matched?.lvl ?? (trimmed.startsWith('warning:') ? 'warn' : 'info');
    const ts = formatOffset(t0, i * 3);
    lines.push({ t: ts, lvl, msg: trimmed.slice(0, 500) });
    i += 1;
  }
  return lines;
}

function formatOffset(base: Date, secs: number): string {
  const d = new Date(base.getTime() + secs * 1000);
  return d.toISOString().slice(11, 19);
}

export function logToTimeline(raw: string): TimelineStep[] {
  const steps: TimelineStep[] = [];
  for (const line of raw.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    for (const p of PATTERNS) {
      if (!p.re.test(trimmed)) continue;
      const kind =
        p.lvl === 'ok' ? 'success' : p.lvl === 'err' ? 'fail' : p.lvl === 'warn' ? 'warn' : 'info';
      steps.push({
        kind,
        title: p.title ?? trimmed.slice(0, 60),
        time: '—',
        summary: trimmed.length > 120 ? trimmed.slice(0, 120) + '…' : trimmed,
      });
      break;
    }
  }
  return steps;
}

export function formatDuration(started: string, ended?: string | null): string {
  const a = new Date(started).getTime();
  const b = ended ? new Date(ended).getTime() : Date.now();
  const secs = Math.max(0, Math.floor((b - a) / 1000));
  if (secs < 60) return `${secs}s`;
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return `${m}m ${s}s`;
}
