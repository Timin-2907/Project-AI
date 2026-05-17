from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── PostgreSQL ──────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://admin:123456@db:5432/auth_system"

    # ── MongoDB ─────────────────────────────────────────────────────────────
    MONGO_URL: str = "mongodb://root:example@mongodb:27017"

    # ── Redis ───────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://redis:6379"

    # ── JWT ─────────────────────────────────────────────────────────────────
    JWT_SECRET: str = "your_super_secret_key_change_in_production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # ── Email ────────────────────────────────────────────────────────────────
    EMAIL_HOST: str = "smtp.gmail.com"
    EMAIL_PORT: int = 587
    EMAIL_USER: str = ""
    EMAIL_PASS: str = ""

    # ── Frontend ─────────────────────────────────────────────────────────────
    CLIENT_URL: str = "http://localhost:3000"

    class Config:
        env_file = ".env"
        extra = "ignore"    # <-- quan trọng: bỏ qua các biến thừa trong .env


settings = Settings()