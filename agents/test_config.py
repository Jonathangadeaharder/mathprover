#!/usr/bin/env python3
"""Config compatibility tests for local OpenAI-compatible backends."""

from __future__ import annotations

import tempfile
import textwrap
import unittest
from pathlib import Path

from config import load_config


class ConfigTests(unittest.TestCase):
    def test_loads_legacy_lmstudio_and_new_local_openai(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "mathprover.toml").write_text(
                textwrap.dedent(
                    """
                    [provers.oprover]
                    type = "lmstudio"
                    base_url = "http://localhost:1234/v1"
                    model = "oprover-8b"

                    [provers.qwen]
                    type = "local_openai"
                    base_url = "http://127.0.0.1:8000/v1"
                    model = "Youssofal/Qwen3.6-27B-MTPLX-Optimized-Speed"

                    [provers.aristotle]
                    type = "cloud"
                    command = "aristotle"

                    [routing]
                    default_leaf = "oprover"
                    default_mid = "qwen"
                    default_capstone = "aristotle"
                    escalate_after_failures = 3
                    capstone_node = "capstone"
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            cfg = load_config(root)

        self.assertEqual("lmstudio", cfg.provers["oprover"].type)
        self.assertEqual("local_openai", cfg.provers["qwen"].type)
        self.assertEqual("http://127.0.0.1:8000/v1", cfg.provers["qwen"].base_url)
        self.assertEqual("Youssofal/Qwen3.6-27B-MTPLX-Optimized-Speed", cfg.provers["qwen"].model)


if __name__ == "__main__":
    unittest.main()
