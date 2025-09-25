from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database settings
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "fastapi_db"

    # MinIO settings
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_SECURE: bool = False
    MINIO_BUCKET_NAME: str = "fastapi-bucket"

    # Application settings
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # JIRA settings
    JIRA_URL: str = "https://your-domain.atlassian.net"
    JIRA_USER: str = "your-email@example.com"
    JIRA_TOKEN: str = "your-jira-token"

    # Confluence settings
    CONFLUENCE_URL: str = "https://your-domain.atlassian.net"
    CONFLUENCE_USER: str = "your-email@example.com"
    CONFLUENCE_TOKEN: str = "your-confluence-token"

    # google calendar settings
    GOOGLE_CALENDAR_API_KEY: str = "your-google-calendar-api-key"
    GOOGLE_CALENDAR_API_URL: str = (
        "https://www.googleapis.com/calendar/v3/calendars/primary/events"
    )

    AI_MEETING_SERVICE_END_POINT: str = "http://localhost:8000"
    EXTERNAL_SERVICE_URL: str = "https://fd3b0768cccc.ngrok-free.app"

    class Config:
        env_file = ".env"


settings = Settings()
