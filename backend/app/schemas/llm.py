from typing import Optional

from sqlmodel import Field, SQLModel


class ProviderInfo(SQLModel):
    id: str
    enabled: bool
    models: list[str]


class LLMConfigRead(SQLModel):
    providers: list[ProviderInfo]
    allowed_providers: list[str]
    selected_provider: Optional[str] = None
    default_provider: str


class ProviderSelection(SQLModel):
    provider_id: str = Field(min_length=1, max_length=50)


class LLMSettingsRead(SQLModel):
    allowed_providers: list[str]
    default_provider: Optional[str] = None
    model: Optional[str] = None
    external_configured: bool
    external_base_url: Optional[str] = None
    external_model: Optional[str] = None


class LLMSettingsUpdate(SQLModel):
    allowed_providers: Optional[list[str]] = None
    default_provider: Optional[str] = None
    model: Optional[str] = None
    external_base_url: Optional[str] = None
    external_model: Optional[str] = None
    external_api_key: Optional[str] = None
