#!/usr/bin/env python3
"""PydanticAI model layer — the single place agents get their local OpenAI-compatible models.

Each role owns a model id and endpoint. `oprover`/`gemma` can stay on the legacy LM Studio
endpoint, while `qwen` defaults to MTPLX's OpenAI-compatible server. `run_sync` ENFORCES
turn-based single residency before every managed local call.

Also owns the bare `openai.OpenAI` client + `chat_sync`/`embed`/`prompt_tokens` for callers that
need raw chat (prove_leaf, autoformalize) or embedding — replaces the hand-rolled urllib in pipeline.py.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import openai
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings

LOG = logging.getLogger("mathprover.models")

AGENTS = Path(__file__).resolve().parent
sys.path.insert(0, str(AGENTS))
import residency  # noqa: E402  (turn-based single-model guard)
import telemetry  # noqa: E402

LOCAL_BASE_URL = os.environ.get("MATHPROVER_LOCAL_BASE_URL", "http://localhost:1234/v1")
MTPLX_BASE_URL = os.environ.get("MATHPROVER_MTPLX_BASE_URL", "http://127.0.0.1:8000/v1")
BASE_URL = LOCAL_BASE_URL

# role -> model id (residency keys off these exact names when the model is LM-Studio managed)
NAMES = {
    "gemma": "google/gemma-4-26b-a4b-qat",   # context engine / synthesizer (262k)
    "qwen": os.environ.get(
        "MATHPROVER_QWEN_MODEL",
        "Youssofal/Qwen3.6-27B-MTPLX-Optimized-Speed",
    ),                                        # orchestrator / researcher (tools, structured output)
    "oprover": "oprover-8b",                  # prover (plain completion)
}

EMBED_MODEL = "text-embedding-nomic-embed-text-v1.5"

ROLE_BASE_URLS = {
    "gemma": os.environ.get("MATHPROVER_GEMMA_BASE_URL", LOCAL_BASE_URL),
    "qwen": os.environ.get("MATHPROVER_QWEN_BASE_URL", MTPLX_BASE_URL),
    "oprover": os.environ.get("MATHPROVER_OPROVER_BASE_URL", LOCAL_BASE_URL),
}

ROLE_API_KEYS = {
    "gemma": os.environ.get("MATHPROVER_GEMMA_API_KEY", "lm-studio"),
    "qwen": os.environ.get("MATHPROVER_QWEN_API_KEY", "mtplx"),
    "oprover": os.environ.get("MATHPROVER_OPROVER_API_KEY", "lm-studio"),
}

INPUT_LIMIT = 8000
SOLVE_RESERVE = 32000

CONTEXT_MODEL = NAMES["gemma"]
PLANNER_MODEL = NAMES["qwen"]
PROVER_MODEL = NAMES["oprover"]


def ensure_mtplx() -> None:
    """If qwen is configured for MTPLX, verify the daemon is reachable; start it if not."""
    qwen_url = ROLE_BASE_URLS.get("qwen", "")
    if "8000" not in qwen_url:
        return
    try:
        _oai_qwen = openai.OpenAI(base_url=qwen_url, api_key=ROLE_API_KEYS.get("qwen", "mtplx"))
        _oai_qwen.models.list()
        LOG.info("MTPLX daemon already running at %s", qwen_url)
        return
    except Exception:
        pass
    mtplx = shutil.which("mtplx")
    if not mtplx:
        LOG.warning("mtplx CLI not found on PATH; qwen calls will fail until MTPLX is started manually")
        return
    LOG.info("Starting MTPLX daemon via `mtplx quickstart --port 8000` …")
    proc = subprocess.Popen(
        [mtplx, "quickstart", "--port", "8000"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    deadline = time.time() + 120
    while time.time() < deadline:
        time.sleep(3)
        try:
            _oai_qwen = openai.OpenAI(base_url=qwen_url, api_key=ROLE_API_KEYS.get("qwen", "mtplx"))
            _oai_qwen.models.list()
            LOG.info("MTPLX daemon ready at %s (pid %d)", qwen_url, proc.pid)
            return
        except Exception:
            continue
    LOG.warning("MTPLX daemon not ready after 120s (pid %d); proceeding anyway", proc.pid)

_providers: dict[tuple[str, str], OpenAIProvider] = {}
_clients: dict[tuple[str, str], openai.OpenAI] = {}


def _provider_for(base_url: str, api_key: str) -> OpenAIProvider:
    key = (base_url, api_key)
    if key not in _providers:
        _providers[key] = OpenAIProvider(base_url=base_url, api_key=api_key)
    return _providers[key]


def _client_for(base_url: str, api_key: str) -> openai.OpenAI:
    key = (base_url, api_key)
    if key not in _clients:
        _clients[key] = openai.OpenAI(base_url=base_url, api_key=api_key)
    return _clients[key]


def base_url_for_role(role: str) -> str:
    return ROLE_BASE_URLS[role]


def api_key_for_role(role: str) -> str:
    return ROLE_API_KEYS[role]


def role_for_model(model: str) -> str | None:
    for role, name in NAMES.items():
        if name == model:
            return role
    return None


def base_url_for_model(model: str) -> str:
    role = role_for_model(model)
    return ROLE_BASE_URLS[role] if role else LOCAL_BASE_URL


def api_key_for_model(model: str) -> str:
    role = role_for_model(model)
    return ROLE_API_KEYS[role] if role else "lm-studio"


_models: dict[str, OpenAIChatModel] = {
    role: OpenAIChatModel(
        name,
        provider=_provider_for(base_url_for_role(role), api_key_for_role(role)),
    )
    for role, name in NAMES.items()
}


def model(role: str) -> OpenAIChatModel:
    return _models[role]


def agent(role: str, **kwargs) -> Agent:
    """Construct an Agent bound to a role's model. Pass output_type=<BaseModel>, system_prompt=…,
    tools=…, deps_type=…, retries=… as usual."""
    return Agent(_models[role], **kwargs)


def run_sync(ag: Agent, role: str, prompt, *, message_history=None, max_tokens: int | None = None,
             temperature: float | None = None, **kwargs):
    """Run an agent synchronously with turn-based residency enforced first (no-op if role resident)."""
    residency.use(NAMES[role])
    settings = None
    if max_tokens is not None or temperature is not None:
        settings = ModelSettings(max_tokens=max_tokens or 4096, temperature=temperature or 0.2)
    t0 = time.time()
    try:
        result = ag.run_sync(prompt, message_history=message_history, model_settings=settings, **kwargs)
    except Exception as exc:
        telemetry.record(
            "model_call",
            phase=f"pydantic:{role}",
            role=role,
            model=NAMES[role],
            base_url=base_url_for_role(role),
            max_tokens=max_tokens,
            temperature=temperature,
            latency_s=round(time.time() - t0, 3),
            success=False,
            error=type(exc).__name__,
        )
        raise
    telemetry.record(
        "model_call",
        phase=f"pydantic:{role}",
        role=role,
        model=NAMES[role],
        base_url=base_url_for_role(role),
        max_tokens=max_tokens,
        temperature=temperature,
        latency_s=round(time.time() - t0, 3),
        success=True,
    )
    return result


def chat_sync(model: str, messages: list[dict], *, max_tokens: int = 4096,
              temperature: float = 0.2, base_url: str | None = None,
              api_key: str | None = None, phase: str = "chat") -> str:
    """Raw chat via OpenAI-compatible SDK with turn-based residency + retry/400-shrink.

    Mirrors the old urllib retry logic: 3 attempts with max_tokens shrink [N, N//2, N//4],
    waits [0, 3, 6]s on 400 errors.
    """
    base_url = base_url or base_url_for_model(model)
    api_key = api_key or api_key_for_model(model)
    client = _client_for(base_url, api_key)
    residency.use(model)
    attempts = [(max_tokens, 0.0), (max(2048, max_tokens // 2), 3.0), (max(1024, max_tokens // 4), 6.0)]
    last_exc: Exception | None = None
    for mt, wait in attempts:
        if wait:
            time.sleep(wait)
        t0 = time.time()
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,  # type: ignore[arg-type]
                max_tokens=mt,
                temperature=temperature,
                timeout=900.0,
            )
        except Exception as e:
            LOG.warning("chat_sync[%s] failed (max_tokens=%d): %s — retrying", model, mt, str(e)[:400])
            telemetry.record(
                "model_call",
                phase=phase,
                model=model,
                base_url=base_url,
                max_tokens=mt,
                temperature=temperature,
                latency_s=round(time.time() - t0, 3),
                success=False,
                error=type(e).__name__,
            )
            last_exc = e
            continue
        u = resp.usage
        latency = time.time() - t0
        LOG.debug("chat_sync[%s] %.1fs prompt_tok=%s gen_tok=%s resp_head=%r",
                  model, latency, u.prompt_tokens if u else "?",
                  u.completion_tokens if u else "?",
                  (resp.choices[0].message.content or "")[:160] if resp.choices else "")
        telemetry.record(
            "model_call",
            phase=phase,
            model=model,
            base_url=base_url,
            max_tokens=mt,
            temperature=temperature,
            latency_s=round(latency, 3),
            prompt_tokens=u.prompt_tokens if u else None,
            completion_tokens=u.completion_tokens if u else None,
            success=True,
        )
        return resp.choices[0].message.content or ""
    raise last_exc if last_exc else RuntimeError("chat_sync failed with no exception captured")


def embed(texts: list[str]) -> list[list[float]]:
    """Embedding via openai SDK with turn-based residency (replaces pipeline.embed)."""
    residency.use(EMBED_MODEL)
    resp = _client_for(LOCAL_BASE_URL, "lm-studio").embeddings.create(model=EMBED_MODEL, input=texts, timeout=300.0)
    return [d.embedding for d in resp.data]


def prompt_tokens(text: str, model: str = NAMES["oprover"], *, base_url: str | None = None) -> int:
    """EXACT prompt-token count from the served model's tokenizer; 400 => over budget.
    Replaces pipeline.prompt_tokens."""
    base_url = base_url or base_url_for_model(model)
    client = _client_for(base_url, api_key_for_model(model))
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": text}],
            max_tokens=1,
            temperature=0,
            timeout=120.0,
        )
        return resp.usage.prompt_tokens if resp.usage else 0
    except openai.BadRequestError:
        return INPUT_LIMIT + SOLVE_RESERVE + 1
