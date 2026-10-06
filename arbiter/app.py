"""
TCP-арбитр подключений для 1С с приоритезацией запросов.

Слушает порт PostgreSQL, читает startup-пакет, определяет приоритет
по application_name, направляет в нужный PgBouncer.

При исчерпании HIGH-пула может вытеснять ТОЛЬКО читающие LOW-запросы
через pg_cancel_backend. Пишущие операции не вытесняются.
"""

import asyncio
import logging
import struct

import asyncpg
from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
)

from config import Config

config = Config()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("arbiter")


# Prometheus метрики
requests_total = Counter(
    "arbiter_requests_total",
    "Total requests by priority",
    ["priority"],
)
request_latency = Histogram(
    "arbiter_request_latency_seconds",
    "Request latency in seconds by priority",
    ["priority"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)
queue_depth = Gauge(
    "arbiter_queue_depth",
    "Current queue depth by priority",
    ["priority"],
)
preemptions_total = Counter(
    "arbiter_preemptions_total",
    "Total preemptions (read-only LOW queries cancelled for HIGH)",
)
errors_total = Counter(
    "arbiter_errors_total",
    "Total errors by type",
    ["error_type"],
)


def parse_startup_packet(data: bytes) -> dict:
    """
    Парсит startup-пакет PostgreSQL.

    Формат: длина (4 байта) + protocol version (4 байта) + пары ключ-значение.
    """
    params = {}
    try:
        offset = 8
        while offset < len(data):
            key_end = data.index(b"\x00", offset)
            key = data[offset:key_end].decode("utf-8")
            offset = key_end + 1

            if not key:
                break

            value_end = data.index(b"\x00", offset)
            value = data[offset:value_end].decode("utf-8")
            offset = value_end + 1

            params[key] = value
    except (ValueError, IndexError) as e:
        logger.debug("Failed to parse startup packet: %s", e)

    return params


def determine_priority(params: dict) -> str:
    """
    Определяет приоритет по application_name в startup-пакете.

    Правила:
    1. application_name содержит VIP-имя → HIGH
    2. application_name содержит 'background' или 'low' → LOW
    3. Остальные → NORMAL
    """
    app_name = params.get("application_name", "").lower()

    if any(vip in app_name for vip in config.VIP_USERS):
        return "high"
    if "background" in app_name or "low" in app_name:
        return "low"

    return "normal"


async def preempt_readonly_low_query(pg_conn) -> bool:
    """
    Отменяет только читающий LOW-запрос через pg_cancel_backend.

    Пишущие операции (INSERT/UPDATE/DELETE/CREATE/DROP/ALTER) не вытесняются.
    """
    if not pg_conn or pg_conn.is_closed():
        return False

    try:
        row = await pg_conn.fetchrow("""
            SELECT pid, query
            FROM pg_stat_activity
            WHERE state = 'active'
              AND application_name LIKE '%low%'
              AND query NOT ILIKE 'INSERT%'
              AND query NOT ILIKE 'UPDATE%'
              AND query NOT ILIKE 'DELETE%'
              AND query NOT ILIKE 'CREATE%'
              AND query NOT ILIKE 'DROP%'
              AND query NOT ILIKE 'ALTER%'
              AND query NOT ILIKE 'TRUNCATE%'
              AND query NOT ILIKE '%pg_cancel_backend%'
            ORDER BY query_start ASC
            LIMIT 1
        """)
        if row:
            pid = row["pid"]
            await pg_conn.execute("SELECT pg_cancel_backend($1)", pid)
            logger.info("Preempted read-only LOW query (PID: %s)", pid)
            preemptions_total.inc()
            return True
    except Exception as e:
        logger.error("Preemption error: %s", e)

    return False


async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """Обрабатывает одного клиента: читает startup-пакет, форвардит в пул."""
    client_addr = writer.get_extra_info("peername")
    logger.debug("Client connected from %s", client_addr)

    try:
        header = await reader.readexactly(4)
        length = struct.unpack("!I", header)[0]
        data = await reader.readexactly(length - 4)
        full_packet = header + data

        params = parse_startup_packet(full_packet)
        logger.info(
            "Client %s: user=%s, application_name=%s",
            client_addr,
            params.get("user", "?"),
            params.get("application_name", "?"),
        )

        priority = determine_priority(params)
        requests_total.labels(priority=priority).inc()

        pool_host, pool_port = config.get_pool_addr(priority)

        pool_reader, pool_writer = await asyncio.open_connection(pool_host, pool_port)
        pool_writer.write(full_packet)
        await pool_writer.drain()

        async def forward(src, dst):
            try:
                while True:
                    chunk = await src.read(65536)
                    if not chunk:
                        break
                    dst.write(chunk)
                    await dst.drain()
            except (ConnectionResetError, BrokenPipeError):
                pass
            finally:
                try:
                    dst.close()
                except Exception:
                    pass

        await asyncio.gather(
            forward(reader, pool_writer),
            forward(pool_reader, writer),
        )

    except asyncio.IncompleteReadError:
        logger.debug("Client %s disconnected before startup", client_addr)
    except Exception as e:
        logger.error("Error handling client %s: %s", client_addr, e)
        errors_total.labels(error_type="connection").inc()
    finally:
        try:
            writer.close()
        except Exception:
            pass


async def main():
    """Запускает TCP-арбитр."""
    pg_conn = None
    if config.PREEMPTION_ENABLED:
        try:
            pg_conn = await asyncpg.connect(config.postgres_dsn)
            logger.info("Direct PostgreSQL connection established for preemption")
        except Exception as e:
            logger.error("Failed to connect directly to PostgreSQL: %s", e)

    server = await asyncio.start_server(
        handle_client,
        config.HOST,
        config.PORT,
    )

    addrs = ", ".join(str(sock.getsockname()) for sock in server.sockets)
    logger.info("Arbiter listening on %s", addrs)
    logger.info("VIP users: %s", config.VIP_USERS)
    logger.info("Preemption: %s", config.PREEMPTION_ENABLED)

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
