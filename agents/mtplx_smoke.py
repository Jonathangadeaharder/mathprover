#!/usr/bin/env python3
"""Smoke-test the MTPLX OpenAI-compatible qwen endpoint."""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request

DEFAULT_BASE_URL = "http://127.0.0.1:8000/v1"
DEFAULT_MODEL = "Youssofal/Qwen3.6-27B-MTPLX-Optimized-Speed"


def _request(base_url: str, path: str, payload: dict | None = None) -> tuple[float, dict]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        base_url.rstrip("/") + path,
        data=data,
        headers={"Content-Type": "application/json", "Authorization": "Bearer mtplx"},
        method="GET" if payload is None else "POST",
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return time.time() - t0, body


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Smoke-test MTPLX /v1/models and chat completions."
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--chat", action="store_true", help="Also run a minimal chat completion.")
    args = parser.parse_args()

    try:
        dt, models = _request(args.base_url, "/models")
    except urllib.error.URLError as exc:
        raise SystemExit(f"MTPLX /models failed at {args.base_url}: {exc}") from exc
    print(json.dumps({"check": "models", "latency_s": round(dt, 3), "ok": True}, indent=2))
    names = [
        m["id"]
        for m in models.get("data", [])
        if isinstance(m, dict) and isinstance(m.get("id"), str)
    ]
    if names:
        print("models:", ", ".join(names[:8]))

    if args.chat:
        payload = {
            "model": args.model,
            "messages": [{"role": "user", "content": "Reply with exactly: ok"}],
            "max_tokens": 8,
            "temperature": 0,
        }
        try:
            dt, out = _request(args.base_url, "/chat/completions", payload)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            raise SystemExit(
                f"MTPLX chat failed for model {args.model!r} at {args.base_url}: "
                f"HTTP {exc.code} {exc.reason}; {body[:500]}"
            ) from exc
        usage = out.get("usage") or {}
        completion = ((out.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        completion_tokens = usage.get("completion_tokens")
        print(
            json.dumps(
                {
                    "check": "chat",
                    "latency_s": round(dt, 3),
                    "completion_tokens": completion_tokens,
                    "tokens_per_s": round(completion_tokens / dt, 3)
                    if completion_tokens and dt > 0
                    else None,
                    "content": completion,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
