from sqlmodel import SQLModel

from app.schemas.tenant import AnswerMode


class WidgetSessionRead(SQLModel):
    visitor_token: str
    expires_in: int
    tenant_id: int


class WidgetConfigRead(SQLModel):
    tenant_name: str
    default_locale: str
    answer_mode: AnswerMode
