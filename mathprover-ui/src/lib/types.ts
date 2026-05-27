export type NodeStatus =
  | 'PROVEN'
  | 'SORRIES'
  | 'PROGRESS'
  | 'FAILED'
  | 'BLOCKED'
  | 'READY'
  | 'UNEXPLORED';

export type AttemptResult = 'PROVEN' | 'PARTIAL' | 'PROGRESS' | 'FAILED';

export interface Attempt {
  id: string;
  agent: string;
  started: string;
  ended: string;
  duration: string;
  tokens: number;
  cost: number;
  strategy: string;
  result: AttemptResult;
  why: string;
  logPath?: string;
}

export interface Sorry {
  name: string;
  desc: string;
  implies: string;
  promoted?: boolean;
  sharedBy?: number;
}

export interface TheoremNode {
  id: string;
  paper_id: string;
  paper_name: string;
  lean_theorem: string;
  lean_file: string;
  lean_line: number | null;
  paper_file: string;
  paper_section: string;
  status: NodeStatus;
  depends_on: string[];
  uses_defs?: string[];
  importance: number;
  difficulty: string;
  confidence: number | null;
  tokens_spent: number;
  attempts: number;
  paper_stmt?: string;
  lean_stmt?: string;
  note?: string;
  isCapstone?: boolean;
  sorries?: Sorry[];
  attemptsLog?: Attempt[];
  proof_folder?: string;
  worker_state?: 'todo' | 'in_progress' | 'done' | string;
}

export type DefinitionKind = 'structure' | 'def' | 'inductive' | 'abbrev' | 'instance' | 'class' | 'notation';

export interface Definition {
  id: string;
  name: string;
  kind: DefinitionKind;
  paper_label?: string;
  paper_section?: string;
  paper_file?: string;
  lean_name: string;
  lean_file: string;
  lean_line?: number | null;
  signature?: string;
  description: string;
  depends_on?: string[];
  used_in?: string[];
}

export interface Failure {
  id: string;
  target: string;
  targetName: string;
  approach: string;
  agent: string;
  date: string;
  why: string;
  counter: string;
  cost: { tokens: number; time: string; usd: number };
}

export interface Project {
  name: string;
  path: string;
  paper: string;
  authors: string;
  venue: string;
  capstone: string;
  lastVerified: string;
}

export interface RecentProject {
  name: string;
  path: string;
  thms: number;
  proven: number;
  updated: string;
}

export interface LiveAgent {
  node: string;
  agent: string;
  started: string;
  step: number;
  totalSteps: number;
  runId?: string;
  phase?: string;
  detail?: string;
  tokensGenerated?: number;
  tokensPerSec?: number;
  heartbeatAt?: string;
  log: { t: string; lvl: string; msg: string }[];
}

export interface RunRecord {
  id: string;
  node_id: string;
  proof_folder: string;
  prover: string;
  route_reason: string;
  status: 'pending' | 'running' | 'ok' | 'failed' | 'error';
  started_at: string;
  ended_at?: string | null;
  log_path: string;
  result?: AttemptResult | null;
  verify_ok?: boolean | null;
  message?: string | null;
  phase?: string | null;
  detail?: string | null;
  tokens_generated?: number | null;
  tokens_per_sec?: number | null;
  heartbeat_at?: string | null;
}

export type FoundationStatus = 'AXIOM' | 'PARTIAL' | 'MECHANIZED' | 'PLANNED';

export interface FoundationSubgoal {
  id: string;
  desc: string;
  status: 'todo' | 'in_progress' | 'done';
  lean_name?: string;
  effort?: string;
}

export interface Foundation {
  id: string;
  name: string;
  citation: string;
  venue?: string;
  doi?: string;
  status: FoundationStatus;
  lean_name?: string;
  lean_file?: string;
  lean_line?: number | null;
  used_in: string[];
  progress_pct: number;
  description: string;
  subgoals: FoundationSubgoal[];
  notes?: string;
}

export type PaperBlock =
  | { kind: 'heading'; text: string }
  | { kind: 'para'; text: string }
  | { kind: 'thm'; label: string; nodeId: string; text: string; math?: string; after?: string };

export type LeanBlock =
  | { kind: 'comment'; text: string }
  | { kind: 'code'; nodeId: string; lines: string[] };

export interface TermInfo {
  type: string;
  desc: string;
  src: string;
  nodeId?: string;
}

export type TermLookup = Record<string, TermInfo>;

export interface ProjectData {
  project: Project;
  recents: RecentProject[];
  nodes: TheoremNode[];
  definitions: Definition[];
  foundations: Foundation[];
  paperBlocks: PaperBlock[];
  leanBlocks: LeanBlock[];
  terms: TermLookup;
  failures: Failure[];
  activeAgent: LiveAgent | null;
}

export type Route =
  | 'graph'
  | 'frontier'
  | 'paper-lean'
  | 'agents'
  | 'failures'
  | 'foundations'
  | 'definitions';

export interface Tweaks {
  theme: 'dark' | 'light';
  graph_layout: 'dag' | 'radial' | 'force';
  density: 'compact' | 'comfortable';
  accent: string;
  show_proven: boolean;
}

export interface PendingDispatch {
  nodeId: string;
  model: string;
}
