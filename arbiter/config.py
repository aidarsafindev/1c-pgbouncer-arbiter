import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Конфигурация TCP-арбитра."""

    # PgBouncer endpoints
    PGB_HIGH_HOST: str = os.getenv("PGB_HIGH_HOST", "pgbouncer-high")
    PGB_HIGH_PORT: int = int(os.getenv("PGB_HIGH_PORT", "5432"))
    PGB_NORMAL_HOST: str = os.getenv("PGB_NORMAL_HOST", "pgbouncer-normal")
    PGB_NORMAL_PORT: int = int(os.getenv("PGB_NORMAL_PORT", "5432"))
    PGB_LOW_HOST: str = os.getenv("PGB_LOW_HOST", "pgbouncer-low")
    PGB_LOW_PORT: int = int(os.getenv("PGB_LOW_PORT", "5432"))

    # PostgreSQL (для отмены запросов)
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "host.docker.internal")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "demo_pgbouncer")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "postgres")

    # Приоритезация
    VIP_USERS: list[str] = os.getenv("VIP_USERS", "vip,director,ceo").split(",")
    PREEMPTION_ENABLED: bool = (
        os.getenv("PREEMPTION_ENABLED", "true").lower() == "true"
    )

    # Сервер
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "5432"))
    METRICS_PORT: int = int(os.getenv("METRICS_PORT", "9090"))

    @property
    def postgres_dsn(self) -> str:
        return (
            f"dbname={self.POSTGRES_DB} "
            f"user={self.POSTGRES_USER} "
            f"password={self.POSTGRES_PASSWORD} "
            f"host={self.POSTGRES_HOST} "
            f"port={self.POSTGRES_PORT}"
        )

    def get_pool_addr(self, priority: str) -> tuple[str, int]:
        """Возвращает адрес пула для указанного приоритета."""
        pools = {
            "high": (self.PGB_HIGH_HOST, self.PGB_HIGH_PORT),
            "normal": (self.PGB_NORMAL_HOST, self.PGB_NORMAL_PORT),
            "low": (self.PGB_LOW_HOST, self.PGB_LOW_PORT),
        }
        return pools.get(priority, pools["normal"])
