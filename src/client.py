"""最小 stdio client：呼叫 greet，確認能連到 server。"""

import asyncio
from pathlib import Path

from fastmcp import Client


async def main() -> None:
    async with Client(Path(__file__).with_name("server.py")) as client:
        result = await client.call_tool("greet", {"name": "Guest"})
        print(result.data)


if __name__ == "__main__":
    asyncio.run(main())
