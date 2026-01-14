from sqlmodel import SQLModel, Field


class Scammer(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int
    username: str
    reason: str