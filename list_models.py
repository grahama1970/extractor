
import aiohttp
import asyncio

async def list_models():
    url = "http://localhost:8791/v1/models"
    headers = {"Authorization": "Bearer sk-placeholder"}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            print(f"Status: {resp.status}")
            data = await resp.json()
            print(f"Data: {data}")

if __name__ == "__main__":
    asyncio.run(list_models())
