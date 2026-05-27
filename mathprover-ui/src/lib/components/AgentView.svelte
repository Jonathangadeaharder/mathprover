<script lang="ts">
  import StatusPill from './StatusPill.svelte';
  import Icon from './Icon.svelte';
  import { app } from '$lib/stores.svelte';
  import { NODES, NODE_BY_ID, activeAgent } from '$lib/data';
  import { formatDuration, logToTimeline, parseLogText } from '$lib/log-parse';
  import type { AttemptResult } from '$lib/types';
  import { onMount } from 'svelte';
  import { fetchRuns } from '$lib/api';

  type Run = {
    id: string;
    nodeId: string;
    nodeName: string;
    nodePid: string;
    agent: string;
    started: string;
    ended?: string;
    duration: string;
    tokens: number;
    cost: number;
    strategy: string;
    result: AttemptResult | 'PROGRESS';
    why?: string;
    isLive?: boolean;
    logPath?: string;
  };

  let remoteRuns = $state<Run[]>([]);

  onMount(async () => {
    if (!app.projectRoot) return;
    const records = await fetchRuns(app.projectRoot);
    remoteRuns = records.map((r) => ({
      id: r.id,
      nodeId: r.node_id,
      nodeName: NODE_BY_ID[r.node_id]?.paper_name ?? r.proof_folder,
      nodePid: NODE_BY_ID[r.node_id]?.paper_id ?? r.proof_folder,
      agent: r.prover,
      started: r.started_at,
      ended: r.ended_at ?? undefined,
      duration: r.status === 'running' ? 'running' : formatDuration(r.started_at, r.ended_at),
      tokens: 0,
      cost: 0,
      strategy: r.route_reason,
      result: r.status === 'running' ? 'PROGRESS' : (r.result ?? (r.status === 'ok' ? 'PROVEN' : 'FAILED')),
      why: r.message ?? undefined,
      isLive: r.status === 'running' || r.status === 'pending',
      logPath: r.log_path,
    }));
  });

  let runs = $derived.by<Run[]>(() => {
    const all: Run[] = [];
    const seen = new Set<string>();

    NODES.forEach((n) => {
      (n.attemptsLog || []).forEach((a) => {
        if (seen.has(a.id)) return;
        seen.add(a.id);
        all.push({
          ...a,
          nodeId: n.id,
          nodeName: n.paper_name,
          nodePid: n.paper_id,
          logPath: a.logPath,
        });
      });
    });

    for (const r of remoteRuns) {
      if (seen.has(r.id)) continue;
      seen.add(r.id);
      all.push(r);
    }

    const live = activeAgent();
    if (live?.runId && NODE_BY_ID[live.node]) {
      const existing = all.find((r) => r.id === live.runId);
      if (!existing) {
        all.unshift({
          id: live.runId,
          nodeId: live.node,
          nodeName: NODE_BY_ID[live.node].paper_name,
          nodePid: NODE_BY_ID[live.node].paper_id,
          agent: live.agent,
          started: live.started,
          duration: 'running',
          tokens: 0,
          cost: 0,
          strategy: 'dispatch in progress',
          result: 'PROGRESS',
          isLive: true,
        });
      } else {
        existing.isLive = true;
      }
    }

    return all.sort((a, b) => {
      if (a.isLive && !b.isLive) return -1;
      if (!a.isLive && b.isLive) return 1;
      return b.started.localeCompare(a.started);
    });
  });

  let activeRunId = $state<string>('');
  let view = $state<'timeline' | 'log'>('log');
  let run = $derived(runs.find((r) => r.id === activeRunId) ?? runs[0]);

  $effect(() => {
    if (!activeRunId && runs.length) activeRunId = runs[0].id;
    if (app.activeRunId) activeRunId = app.activeRunId;
    if (app.agentNodeId) {
      const found = runs.find((r) => r.nodeId === app.agentNodeId);
      if (found) activeRunId = found.id;
    }
  });

  type Step = {
    kind: 'info' | 'warn' | 'success' | 'fail';
    title: string;
    time: string;
    summary: string;
  };

  let steps = $derived(logToTimeline(app.liveLogText || ''));

  let logLines = $derived(
    run?.isLive
      ? parseLogText(app.liveLogText || '(waiting for log output…)', run.started)
      : parseLogText(app.liveLogText || '', run?.started),
  );

  let logEl: HTMLDivElement;

  $effect(() => {
    if (!run || run.isLive || !run.logPath || !app.projectRoot) return;
    const url = `/api/runs/${run.id}/log?project=${encodeURIComponent(app.projectRoot)}`;
    fetch(url)
      .then((r) => r.json())
      .then((body) => {
        if (body.text) app.liveLogText = body.text;
      })
      .catch(() => {});
  });

  $effect(() => {
    void logLines.length;
    if (logEl) logEl.scrollTop = logEl.scrollHeight;
  });
</script>

<div class="agent-shell">
  <div class="agent-list">
    <div style="display: flex; align-items: center; padding: 4px 8px 10px; justify-content: space-between;">
      <span style="font-size: 10.5px; text-transform: uppercase; letter-spacing: 0.08em; color: var(--fg-3); font-weight: 600;">Agent runs</span>
      <span style="font-family: var(--font-mono); font-size: 10.5px; color: var(--fg-3);">{runs.length}</span>
    </div>
    {#each runs as r (r.id)}
      <button class="agent-list-row" class:active={activeRunId === r.id} type="button" onclick={() => (activeRunId = r.id)}>
        <div class="ttl">{r.nodeName}</div>
        <div class="row">
          <span class="agent-name">{r.agent}</span>
          <span style="margin-left: auto;">
            <StatusPill status={r.result === 'PARTIAL' ? 'SORRIES' : r.result} />
          </span>
        </div>
        <div class="row" style="margin-top: 4px; color: var(--fg-3);">
          <span style="font-family: var(--font-mono); font-size: 10.5px;">{r.nodePid}</span>
          <span class="dur">
            {#if r.isLive}<span style="color: var(--st-progress);">● live</span>{:else}{r.duration}{/if}
          </span>
        </div>
      </button>
    {/each}
  </div>

  <div class="agent-detail">
    {#if run}
    <div class="agent-detail-tabs">
      <button class="tab" class:active={view === 'timeline'} onclick={() => (view = 'timeline')}>Timeline</button>
      <button class="tab" class:active={view === 'log'} onclick={() => (view = 'log')}>Streaming log</button>
      <div class="spacer"></div>
      <div class="actions">
        <span style="font-family: var(--font-mono); font-size: 11px; color: var(--fg-3); margin-right: 12px;">
          {run.agent} · {run.duration}
        </span>
        {#if run.isLive}
          <span style="font-size: 11px; color: var(--st-progress);">● running</span>
          {#if activeAgent()?.detail}
            <span style="font-size: 11px; color: var(--fg-3); margin-left: 8px;">{activeAgent()?.detail}</span>
          {/if}
          {#if activeAgent()?.tokensGenerated}
            <span style="font-size: 11px; color: var(--fg-3); margin-left: 8px; font-family: var(--font-mono);">
              {activeAgent()?.tokensGenerated} tok
              {#if activeAgent()?.tokensPerSec} · {activeAgent()?.tokensPerSec?.toFixed(1)} tok/s{/if}
            </span>
          {/if}
        {/if}
      </div>
    </div>

    <div class="agent-body">
      {#if view === 'timeline'}
        <div class="timeline">
          <div style="margin-bottom: 24px;">
            <div style="display: flex; gap: 8px; align-items: center; margin-bottom: 6px;">
              <Icon name="target" size={14} />
              <span style="font-family: var(--font-mono); font-size: 11px; color: var(--fg-3);">Target</span>
              <span style="font-size: 13px; color: var(--fg-0); font-weight: 500;">{run.nodeName}</span>
              <span style="margin-left: auto;">
                <StatusPill status={run.result === 'PARTIAL' ? 'SORRIES' : run.result} />
              </span>
            </div>
            <div style="padding-left: 22px; font-size: 12px; color: var(--fg-2); font-style: italic;">{run.strategy}</div>
          </div>

          {#if steps.length === 0}
            <p style="color: var(--fg-3); font-size: 12px;">Waiting for pipeline events… switch to Streaming log for raw output.</p>
          {/if}
          {#each steps as s, i (i)}
            <div class="tl-step">
              <div class="dot {s.kind}">
                {s.kind === 'success' ? '✓' : s.kind === 'fail' ? '✗' : s.kind === 'warn' ? '!' : i + 1}
              </div>
              <div class="body">
                <div class="head">
                  <span class="label">{s.title}</span>
                  <span class="time">{s.time}</span>
                </div>
                <div class="summary">{s.summary}</div>
              </div>
            </div>
          {/each}
        </div>
      {:else}
        <div class="log" bind:this={logEl}>
          {#each logLines as l, i (i)}
            <div>
              <span class="ts">{l.t}</span>
              <span class="lvl-{l.lvl}">{('[' + l.lvl.toUpperCase() + ']').padEnd(8)}</span>
              {' '}{l.msg}
            </div>
          {/each}
          {#if run.isLive}
            <div><span class="ts">…</span><span class="lvl-think" style="animation: blink 1.4s infinite;">streaming</span></div>
          {/if}
        </div>
      {/if}
    </div>
    {:else}
      <div style="padding: 24px; color: var(--fg-3); font-size: 13px;">No agent runs yet. Dispatch from the graph or frontier.</div>
    {/if}
  </div>
</div>

<style>
  .agent-list-row, .tab { all: unset; cursor: pointer; display: block; }
</style>
