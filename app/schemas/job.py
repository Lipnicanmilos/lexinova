"""Pydantic schémy pre admin správu denných jobov."""
from typing import Optional

from pydantic import BaseModel, Field


class JobHourUpdate(BaseModel):
    """Prestavenie cieľovej hodiny jobu (UTC). None = návrat na default z kódu."""
    run_after_hour: Optional[int] = Field(None, ge=0, le=23)
