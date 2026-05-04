from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Twilio
    TWILIO_ACCOUNT_SID: str
    TWILIO_AUTH_TOKEN: str
    TWILIO_WHATSAPP_NUMBER: str = "whatsapp:+14155238886"

    # Database
    DATABASE_URL: str

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # App
    SECRET_KEY: str = "changeme"
    ENVIRONMENT: str = "development"

    class Config:
        env_file = ".env"


settings = Settings()
