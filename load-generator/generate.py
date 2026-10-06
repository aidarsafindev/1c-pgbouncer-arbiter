"""
Генератор нагрузки для демонстрации TCP-арбитра подключений.

Подключается к TCP-арбитру, передаёт application_name в startup-пакете.
Арбитр размечает и направляет в нужный пул PgBouncer.

Имитирует три типа пользователей:
- VIP: лёгкие запросы, application_name = vip_*
- NORMAL: средние запросы, application_name = manager_*
- LOW: тяжёлые агрегации, application_name = background_*
"""

import asyncio
import os
import random
import time

import asyncpg


ARBITER_HOST = os.getenv("ARBITER_HOST", "arbiter")
ARBITER_PORT = int(os.getenv("ARBITER_PORT", "5432"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "demo_pgbouncer")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")

CONCURRENT_VIP = int(os.getenv("CONCURRENT_VIP", "10"))
CONCURRENT_NORMAL = int(os.getenv("CONCURRENT_NORMAL", "50"))
CONCURRENT_LOW = int(os.getenv("CONCURRENT_LOW", "20"))
DURATION_SECONDS = int(os.getenv("DURATION_SECONDS", "120"))


async def make_request(app_name: str, heavy: bool = False):
    """Подключается к арбитру, выполняет запрос, закрывает соединение."""
    conn = None
    try:
        conn = await asyncpg.connect(
            host=ARBITER_HOST,
            port=ARBITER_PORT,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            database=POSTGRES_DB,
            server_settings={"application_name": app_name},
            timeout=30,
        )

        if heavy:
            await conn.execute("SELECT pg_sleep(5)")
        else:
            await conn.execute("SELECT 1")

        return 0, "ok"

    except Exception as e:
        return 0, str(e)

    finally:
        if conn:
            await conn.close()


async def vip_worker(end_time: float):
    """VIP-пользователь: лёгкие read-only запросы."""
    username = f"vip_{random.randint(1, 5)}"
    while time.monotonic() < end_time:
        await make_request(username, heavy=False)
        await asyncio.sleep(random.uniform(0.2, 0.5))


async def normal_worker(end_time: float):
    """Обычный пользователь: средние запросы."""
    username = f"manager_{random.randint(1, 20)}"
    while time.monotonic() < end_time:
        heavy = random.random() < 0.3
        await make_request(username, heavy=heavy)
        await asyncio.sleep(random.uniform(0.5, 1.5))


async def low_worker(end_time: float):
    """Фоновый процесс: тяжёлые агрегации."""
    username = f"background_{random.randint(1, 5)}"
    while time.monotonic() < end_time:
        await make_request(username, heavy=True)
        await asyncio.sleep(random.uniform(3.0, 8.0))


async def main():
    print(f"Load generator: arbiter={ARBITER_HOST}:{ARBITER_PORT}")
    print(f"  VIP: {CONCURRENT_VIP}, NORMAL: {CONCURRENT_NORMAL}, LOW: {CONCURRENT_LOW}")
    print(f"  Duration: {DURATION_SECONDS}s")

    end_time = time.monotonic() + DURATION_SECONDS

    tasks = []
    for _ in range(CONCURRENT_VIP):
        tasks.append(asyncio.create_task(vip_worker(end_time)))
    for _ in range(CONCURRENT_NORMAL):
        tasks.append(asyncio.create_task(normal_worker(end_time)))
    for _ in range(CONCURRENT_LOW):
        tasks.append(asyncio.create_task(low_worker(end_time)))

    await asyncio.gather(*tasks)
    print("Load test completed.")


if __name__ == "__main__":
    asyncio.run(main())
