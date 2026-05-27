## 1. Backend

- [x] 1.1 `agents/run_registry.py` — run records + progress heartbeats
- [x] 1.2 `dispatch.py` — write/clear run records and activeAgent
- [x] 1.3 `scripts/index_runs.py` + `bootstrap_graph.py`

## 2. API

- [x] 2.1 POST /api/dispatch, GET /api/project, GET /api/runs
- [x] 2.2 SSE /api/runs/[id]/stream
- [x] 2.3 GET /api/status/goedel, POST /api/reindex

## 3. UI

- [x] 3.1 Wire confirmDispatch → postDispatch
- [x] 3.2 AgentView real logs (remove synthetic live injection)
- [x] 3.3 Router preview in PremisePicker
- [x] 3.4 Graph pulse on active node; Frontier dispatch button

## 4. Goedel observability

- [x] 4.1 stream_generate in run_pipeline.py
- [x] 4.2 Heartbeat lines every 15s during generation
- [x] 4.3 Pass --run-id from goedel.py

## 5. Archive

- [ ] 5.1 `/opsx:archive mathprover-gui-harmonization`
