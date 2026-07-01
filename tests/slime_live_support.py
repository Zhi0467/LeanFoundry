"""Local deterministic generator for Slime live smoke tests."""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import threading
import time
import urllib.request
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LocalSlimeGenerator:
    host: str
    port: int
    checkpoint_path: Path
    server: ThreadingHTTPServer
    thread: threading.Thread

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


@dataclass(frozen=True)
class RealSGLangServer:
    host: str
    port: int
    checkpoint_path: Path
    process: subprocess.Popen
    log_path: Path

    def stop(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=10)


def start_local_slime_generator(tmp_path: Path) -> LocalSlimeGenerator:
    checkpoint_path = tmp_path / "tokenizer"
    _write_tokenizer(checkpoint_path)
    host = "127.0.0.1"
    port = _free_port(host)
    server = ThreadingHTTPServer((host, port), _GenerateHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return LocalSlimeGenerator(
        host=host,
        port=port,
        checkpoint_path=checkpoint_path,
        server=server,
        thread=thread,
    )


def start_real_sglang_server(
    tmp_path: Path,
    *,
    python_path: str,
    cuda_visible_devices: str,
) -> RealSGLangServer:
    """Start a tiny real SGLang `/generate` server for e2e tests."""

    checkpoint_path = tmp_path / "tiny-trivial-gpt2"
    write_tiny_trivial_gpt2(checkpoint_path)
    host = "127.0.0.1"
    port = _free_port(host)
    log_path = tmp_path / "sglang.log"
    log_file = log_path.open("w", encoding="utf-8")
    env = {**dict(os.environ), "CUDA_VISIBLE_DEVICES": cuda_visible_devices}
    process = subprocess.Popen(
        [
            python_path,
            "-m",
            "sglang.launch_server",
            "--model-path",
            str(checkpoint_path),
            "--host",
            host,
            "--port",
            str(port),
            "--context-length",
            "128",
            "--attention-backend",
            "torch_native",
            "--sampling-backend",
            "pytorch",
            "--mem-fraction-static",
            "0.05",
            "--max-running-requests",
            "2",
            "--skip-server-warmup",
            "--log-level",
            "warning",
        ],
        stdout=log_file,
        stderr=subprocess.STDOUT,
        env=env,
    )
    log_file.close()
    server = RealSGLangServer(
        host=host,
        port=port,
        checkpoint_path=checkpoint_path,
        process=process,
        log_path=log_path,
    )
    try:
        _wait_for_sglang_generate(server)
    except Exception:
        server.stop()
        raise
    return server


def write_tiny_trivial_gpt2(path: Path) -> None:
    """Write a tiny HF CausalLM checkpoint whose token 0 is `trivial`."""

    from tokenizers import Tokenizer
    from tokenizers.models import WordLevel
    from tokenizers.pre_tokenizers import Whitespace
    from transformers import GPT2Config, GPT2LMHeadModel
    from transformers import PreTrainedTokenizerFast, set_seed

    path.mkdir(parents=True, exist_ok=True)
    tokenizer = Tokenizer(
        WordLevel(
            {
                "trivial": 0,
                "[UNK]": 1,
                "[PAD]": 2,
                "[EOS]": 3,
            },
            unk_token="[UNK]",
        )
    )
    tokenizer.pre_tokenizer = Whitespace()
    fast_tokenizer = PreTrainedTokenizerFast(
        tokenizer_object=tokenizer,
        unk_token="[UNK]",
        pad_token="[PAD]",
        eos_token="[EOS]",
        bos_token="[EOS]",
    )
    fast_tokenizer.model_max_length = 128
    fast_tokenizer.save_pretrained(path)
    _patch_tokenizer_config(path)

    set_seed(1234)
    config = GPT2Config(
        vocab_size=4,
        n_positions=128,
        n_ctx=128,
        n_embd=32,
        n_layer=1,
        n_head=1,
        bos_token_id=3,
        eos_token_id=3,
        pad_token_id=2,
    )
    GPT2LMHeadModel(config).save_pretrained(path, safe_serialization=True)


class _GenerateHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        if self.path != "/generate":
            self.send_error(404)
            return
        content_length = int(self.headers.get("Content-Length", "0"))
        request = json.loads(self.rfile.read(content_length) or b"{}")
        prompt = str(request.get("text", ""))
        sampling_params = request.get("sampling_params") or {}
        n = int(sampling_params.get("n", 1))
        response = {"texts": [_response_for_prompt(prompt) for _ in range(n)]}
        encoded = json.dumps(response).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: Any) -> None:
        return


def _response_for_prompt(prompt: str) -> str:
    if "⊢ True" in prompt:
        return "trivial"
    theorem_name = _theorem_name(prompt)
    if theorem_name == "lf_slime_live_self_correct" and (
        "Previous verifier feedback:" not in prompt
    ):
        return _true_proof(theorem_name, "exact 0")
    return _true_proof(theorem_name, "trivial")


def _theorem_name(prompt: str) -> str:
    match = re.search(r"\btheorem\s+([A-Za-z_][A-Za-z0-9_]*)\s*:", prompt)
    if match is not None:
        return match.group(1)
    return "lf_slime_live_generated"


def _true_proof(theorem_name: str, tactic: str) -> str:
    return f"theorem {theorem_name} : True := by\n  {tactic}"


def _write_tokenizer(path: Path) -> None:
    from tokenizers import Tokenizer
    from tokenizers.models import WordLevel
    from tokenizers.pre_tokenizers import Whitespace
    from transformers import PreTrainedTokenizerFast

    path.mkdir(parents=True, exist_ok=True)
    tokenizer = Tokenizer(WordLevel({"[UNK]": 0}, unk_token="[UNK]"))
    tokenizer.pre_tokenizer = Whitespace()
    fast_tokenizer = PreTrainedTokenizerFast(
        tokenizer_object=tokenizer,
        unk_token="[UNK]",
    )
    fast_tokenizer.save_pretrained(path)


def _patch_tokenizer_config(path: Path) -> None:
    config_path = path / "tokenizer_config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["tokenizer_class"] = "PreTrainedTokenizerFast"
    config["model_max_length"] = 128
    config_path.write_text(
        json.dumps(config, sort_keys=True, indent=2),
        encoding="utf-8",
    )


def _wait_for_sglang_generate(server: RealSGLangServer) -> None:
    deadline = time.monotonic() + 180
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if server.process.poll() is not None:
            log_tail = _tail(server.log_path)
            raise RuntimeError(
                "SGLang exited before serving /generate:\n"
                f"{log_tail}"
            )
        try:
            response = _post_generate(server)
            if response.get("text") == "trivial":
                return
            last_error = RuntimeError(
                f"unexpected SGLang response: {response}"
            )
        except Exception as exc:  # pragma: no cover - e2e diagnostic path
            last_error = exc
        time.sleep(1)
    log_tail = _tail(server.log_path)
    raise TimeoutError(
        "SGLang did not produce the readiness completion. "
        f"Last error: {last_error}\n{log_tail}"
    )


def _post_generate(server: RealSGLangServer) -> dict[str, Any]:
    payload = {
        "text": "⊢ True",
        "sampling_params": {
            "n": 1,
            "max_new_tokens": 1,
            "temperature": 0,
            "logit_bias": {"0": 100.0},
        },
    }
    request = urllib.request.Request(
        f"http://{server.host}:{server.port}/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        body = response.read().decode("utf-8")
    decoded = json.loads(body)
    if not isinstance(decoded, dict):
        raise TypeError(f"unexpected SGLang response type: {decoded!r}")
    return decoded


def _tail(path: Path, *, lines: int = 80) -> str:
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return ""
    return "\n".join(content.splitlines()[-lines:])


def _free_port(host: str) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])
