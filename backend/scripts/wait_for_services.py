import asyncio
import os
import sys

import httpx


async def main() -> None:
    urls = sys.argv[1:] or [os.getenv("FUSEKI_BASE_URL", "http://fuseki:3030/$/ping"), os.getenv("OLLAMA_BASE_URL", "http://ollama:11434") + "/api/tags"]
    for attempt in range(30):
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                if all((await client.get(url)).status_code < 500 for url in urls): return
        except Exception:
            pass
        await asyncio.sleep(min(1 + attempt / 5, 5))
    raise SystemExit("Services did not become available after bounded retries")


if __name__ == "__main__": asyncio.run(main())

