from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "+7 Pay YooKassa Payment Proposal"
    database_url: str = "sqlite:///./payments.sqlite3"
    yookassa_shop_id: str = Field(default="test_shop_id", repr=False)
    yookassa_secret_key: str = Field(default="test_secret_key", repr=False)
    yookassa_api_url: str = "https://api.yookassa.ru/v3"
    public_return_url: str = "https://example.com/payments/return"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


def get_settings() -> Settings:
    return Settings()

