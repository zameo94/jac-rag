from sqlmodel import SQLModel

from app.schemas.workspace import AnswerMode


class WidgetSessionRead(SQLModel):
    visitor_token: str
    expires_in: int
    workspace_id: int


class WidgetConfigRead(SQLModel):
    workspace_name: str
    default_locale: str
    answer_mode: AnswerMode
    is_active: bool
