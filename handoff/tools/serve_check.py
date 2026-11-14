"""Start uvicorn, call /api/v1/health, print the response, and shut down.

Usage: .venv\\Scripts\\python.exe handoff/tools/serve_check.py [--port PORT]

Exit code 0 if health returns HTTP 200; 1 otherwise.
"""

from __future__ import annotations

import argparse
import socket
import subprocess
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[2]
VENV_PYTHON = str(ROOT / ".venv" / "Scripts" / "python.exe")
DEFAULT_PORT = 18321  # unlikely to collide


def _port_open(port: int, host: str = "127.0.0.1", timeout: float = 0.3) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        return s.connect_ex((host, port)) == 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Start server, hit health, stop.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--timeout", type=int, default=15, help="Max seconds to wait for startup")
    args = parser.parse_args()

    port = args.port

    if _port_open(port):
        print(f"ERROR: port {port} already in use", file=sys.stderr)
        sys.exit(1)

    cmd = [
        VENV_PYTHON, "-m", "uvicorn",
        "--factory", "app.main:create_app",
        "--port", str(port),
        "--host", "127.0.0.1",
    ]

    proc = subprocess.Popen(
        cmd,
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    # Wait for server to start
    started = False
    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            out = proc.stdout.read() if proc.stdout else ""
            print(f"ERROR: server exited early (code {proc.returncode})\n{out}", file=sys.stderr)
            sys.exit(1)
        if _port_open(port):
            started = True
            break
        time.sleep(0.3)

    if not started:
        proc.terminate()
        proc.wait(timeout=5)
        print("ERROR: server did not start within timeout", file=sys.stderr)
        sys.exit(1)

    # Call health
    import urllib.request
    import json

    url = f"http://127.0.0.1:{port}/api/v1/health"
    ok = False
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            body = json.loads(resp.read())
            status_code = resp.status
            print(f"HTTP {status_code}")
            print(json.dumps(body, indent=2, ensure_ascii=False))
            ok = status_code == 200
    except Exception as exc:
        print(f"ERROR: health request failed: {exc}", file=sys.stderr)
    finally:
        proc.terminate()
        proc.wait(timeout=5)

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
