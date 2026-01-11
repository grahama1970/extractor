
import aiohttp
import asyncio

async def list_models():
    paths = [
        "http://localhost:8791/models",
        "http://localhost:8791/v1/models",
        "http://localhost:8791/api/v1/models",
        "http://localhost:8791/available_models",
    ]
    headers = {"Authorization": "Bearer sk-placeholder"}
    async with aiohttp.ClientSession() as session:
        for url in paths:
            try:
                async with session.get(url, headers=headers) as resp:
                    print(f"URL: {url} -> Status: {resp.status}")
                    if resp.status == 200:
                        print(f"Data: {await resp.text()}")
            except Exception as e:
                print(f"URL: {url} -> Error: {e}")

if __name__ == "__main__":
    asyncio.run(list_models())
