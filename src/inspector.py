"""用 uv 啟動 MCP Inspector，連到本專案的 stdio server。"""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    npx = shutil.which("npx")
    if npx is None:
        raise SystemExit("找不到 npx，請先安裝 Node.js。")

    env = os.environ.copy()
    env.setdefault("CLIENT_PORT", "6294")
    env.setdefault("MCP_SANDBOX_PORT", "6295")
    env.setdefault("MCP_APP_ORIGIN_PORT", "6298")
    command = [
        npx,
        "--yes",
        "@modelcontextprotocol/inspector@2.9.0",
        "--protocol-era",
        "modern",
        sys.executable,
        str(Path(__file__).with_name("server.py")),
    ]
    try:
        return subprocess.call(command, env=env)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
