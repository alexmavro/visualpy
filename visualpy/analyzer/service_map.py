"""Known library to service mapping — extensible detection of external services."""

from __future__ import annotations

from visualpy.models import Service

# Maps import prefixes to (human-readable name, icon hint).
# Longest prefix wins: "google.cloud.storage" beats "google".
SERVICE_MAP: dict[str, tuple[str, str | None]] = {
    # AI / ML
    "openai": ("OpenAI", "openai"),
    "anthropic": ("Anthropic", "anthropic"),
    "cohere": ("Cohere", "cohere"),
    "replicate": ("Replicate", "replicate"),
    "huggingface_hub": ("Hugging Face", "huggingface"),
    "transformers": ("Hugging Face Transformers", "huggingface"),
    "litellm": ("LiteLLM", "litellm"),
    "langchain": ("LangChain", "langchain"),
    # Google
    "gspread": ("Google Sheets", "google-sheets"),
    "google.oauth2": ("Google Auth", "google"),
    "google.cloud.storage": ("Google Cloud Storage", "gcs"),
    "google.cloud.bigquery": ("BigQuery", "bigquery"),
    "googleapiclient": ("Google API", "google"),
    "googlemaps": ("Google Maps", "google-maps"),
    # AWS
    "boto3": ("AWS", "aws"),
    "botocore": ("AWS", "aws"),
    # Databases
    "sqlalchemy": ("SQL Database", "database"),
    "pymongo": ("MongoDB", "mongodb"),
    "redis": ("Redis", "redis"),
    "psycopg2": ("PostgreSQL", "postgresql"),
    "sqlite3": ("SQLite", "sqlite"),
    "supabase": ("Supabase", "supabase"),
    # HTTP / APIs
    "requests": ("HTTP Client", "http"),
    "httpx": ("HTTP Client", "http"),
    "aiohttp": ("HTTP Client", "http"),
    "urllib3": ("HTTP Client", "http"),
    # Messaging / notifications
    "slack_sdk": ("Slack", "slack"),
    "twilio": ("Twilio", "twilio"),
    "sendgrid": ("SendGrid", "sendgrid"),
    "telegram": ("Telegram", "telegram"),
    "discord": ("Discord", "discord"),
    # Scraping / automation
    "selenium": ("Selenium", "selenium"),
    "playwright": ("Playwright", "playwright"),
    "scrapy": ("Scrapy", "scrapy"),
    "beautifulsoup4": ("BeautifulSoup", "bs4"),
    "bs4": ("BeautifulSoup", "bs4"),
    "apify_client": ("Apify", "apify"),
    # File / storage
    "dropbox": ("Dropbox", "dropbox"),
    "paramiko": ("SSH/SFTP", "ssh"),
    # Payments
    "stripe": ("Stripe", "stripe"),
    # Task / scheduling
    "celery": ("Celery", "celery"),
    "apscheduler": ("APScheduler", "scheduler"),
    "schedule": ("Schedule", "scheduler"),
    # Web frameworks (detected as services for visibility)
    "fastapi": ("FastAPI", "fastapi"),
    "flask": ("Flask", "flask"),
    "django": ("Django", "django"),
    # Modal (serverless)
    "modal": ("Modal", "modal"),
}


def detect_services(imports: list[str]) -> list[Service]:
    """Match a list of import names against SERVICE_MAP.

    Uses longest-prefix matching so 'google.cloud.storage' beats 'google'.
    Deduplicates by service name (multiple imports can map to same service).
    """
    seen: set[str] = set()
    services: list[Service] = []

    for imp in imports:
        best_key = ""
        for prefix in SERVICE_MAP:
            if (imp == prefix or imp.startswith(prefix + ".")) and len(prefix) > len(
                best_key
            ):
                best_key = prefix
        if best_key:
            name, icon = SERVICE_MAP[best_key]
            if name not in seen:
                seen.add(name)
                services.append(Service(name=name, library=best_key, icon=icon))

    return services
