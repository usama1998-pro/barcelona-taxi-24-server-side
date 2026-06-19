import os
from dataclasses import dataclass
from urllib.parse import quote_plus

from dotenv import load_dotenv

load_dotenv()


def _truthy(value: str | None, default: bool = False) -> bool:
    if value is None or not value.strip():
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_optional_bool(value: str | None) -> bool | None:
    if value is None or not value.strip():
        return None
    lowered = value.strip().lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    return None


def _parse_max_files(value: str | None) -> int:
    raw = (value or "").strip()
    if raw.isdigit():
        return max(1, int(raw))
    return 5


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_env: str
    app_url: str
    host: str
    port: int
    jwt_secret: str
    jwt_expires_in: str
    database_host: str
    database_port: int
    database_user: str
    database_password: str
    database_name: str
    database_pool_connection_limit: int
    database_ssl: bool
    database_ssl_reject_unauthorized: bool
    database_connect_timeout_ms: int | None
    google_maps_api_key: str | None
    stripe_secret_key: str | None
    stripe_webhook_secret: str | None
    paypal_client_id: str | None
    paypal_client_secret: str | None
    paypal_mode: str
    viator_imap_host: str | None
    viator_imap_port: int
    viator_imap_user: str | None
    viator_imap_password: str | None
    viator_imap_tls: bool
    log_file_path: str | None
    log_file: str | None
    log_file_enabled: bool
    log_console: bool | None
    log_file_max_files: int
    log_file_max_size: str | None
    log_level: str

    @classmethod
    def from_env(cls) -> "Settings":
        port = int(os.getenv("PORT", "8000"))
        pool_limit = os.getenv("DATABASE_POOL_CONNECTION_LIMIT", "5")
        connect_timeout = os.getenv("DATABASE_CONNECT_TIMEOUT_MS", "").strip()

        jwt_secret = (os.getenv("JWT_SECRET") or "").strip()
        if not jwt_secret:
            if os.getenv("APP_ENV", "development") == "production":
                raise RuntimeError("JWT_SECRET must be set in production")
            jwt_secret = "dev-only-change-in-production"

        return cls(
            app_name=os.getenv("APP_NAME", "Taxi Booking API"),
            app_env=os.getenv("APP_ENV", "development"),
            app_url=os.getenv("APP_URL", f"http://localhost:{port}"),
            host=os.getenv("HOST", "0.0.0.0"),
            port=port,
            jwt_secret=jwt_secret,
            jwt_expires_in=os.getenv("JWT_EXPIRES_IN", "100y").strip() or "100y",
            database_host=os.getenv("DATABASE_HOST", "127.0.0.1"),
            database_port=int(os.getenv("DATABASE_PORT", "3306")),
            database_user=os.getenv("DATABASE_USER", "taxi"),
            database_password=os.getenv("DATABASE_PASSWORD", "taxi"),
            database_name=os.getenv("DATABASE_NAME", "taxi_booking"),
            database_pool_connection_limit=max(1, int(pool_limit)),
            database_ssl=_truthy(os.getenv("DATABASE_SSL")),
            database_ssl_reject_unauthorized=_truthy(
                os.getenv("DATABASE_SSL_REJECT_UNAUTHORIZED", "1"),
                default=True,
            ),
            database_connect_timeout_ms=int(connect_timeout)
            if connect_timeout
            else None,
            google_maps_api_key=(os.getenv("GOOGLE_MAPS_API_KEY") or "").strip() or None,
            stripe_secret_key=(os.getenv("STRIPE_SECRET_KEY") or "").strip() or None,
            stripe_webhook_secret=(os.getenv("STRIPE_WEBHOOK_SECRET") or "").strip() or None,
            paypal_client_id=(os.getenv("PAYPAL_CLIENT_ID") or "").strip() or None,
            paypal_client_secret=(os.getenv("PAYPAL_CLIENT_SECRET") or "").strip() or None,
            paypal_mode=os.getenv("PAYPAL_MODE", "sandbox").strip() or "sandbox",
            viator_imap_host=(os.getenv("VIATOR_IMAP_HOST") or "").strip() or None,
            viator_imap_port=int(os.getenv("VIATOR_IMAP_PORT", "993")),
            viator_imap_user=(os.getenv("VIATOR_IMAP_USER") or "").strip() or None,
            viator_imap_password=(os.getenv("VIATOR_IMAP_PASSWORD") or "").strip() or None,
            viator_imap_tls=_truthy(os.getenv("VIATOR_IMAP_TLS", "1")),
            log_file_path=(os.getenv("LOG_FILE_PATH") or "").strip() or None,
            log_file=(os.getenv("LOG_FILE") or "").strip() or None,
            log_file_enabled=_truthy(os.getenv("LOG_FILE_ENABLED"), True),
            log_console=_parse_optional_bool(os.getenv("LOG_CONSOLE")),
            log_file_max_files=_parse_max_files(os.getenv("LOG_FILE_MAX_FILES")),
            log_file_max_size=(os.getenv("LOG_FILE_MAX_SIZE") or "").strip() or None,
            log_level=(os.getenv("LOG_LEVEL") or "info").strip().lower() or "info",
        )

    def database_url(self) -> str:
        user = quote_plus(self.database_user)
        password = quote_plus(self.database_password)
        return (
            f"mysql+pymysql://{user}:{password}"
            f"@{self.database_host}:{self.database_port}/{self.database_name}"
        )


settings = Settings.from_env()
