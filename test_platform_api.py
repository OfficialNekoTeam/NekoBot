import asyncio
import aiohttp

async def test():
    async with aiohttp.ClientSession() as session:
        async with session.get('http://localhost:6285/api/platform/stats', headers={'Authorization': 'Bearer admin'}) as resp:
            print(f"Status: {resp.status}")
            text = await resp.text()
            print(f"Raw response: {text}")

asyncio.run(test())
