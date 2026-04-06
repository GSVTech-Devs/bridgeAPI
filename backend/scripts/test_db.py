import asyncio
import asyncpg


async def test():
    conn = await asyncpg.connect("postgresql://bridge:bridge@localhost:5433/bridgeapi")
    result = await conn.fetchval("SELECT 1")
    print("Conexão OK:", result)
    await conn.close()


asyncio.run(test())
