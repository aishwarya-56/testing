from datetime import datetime
from pydantic import BaseModel, Field


class AccidentRequest(BaseModel):
    claim_id: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    city: str
    province: str
    event_timestamp: datetime


class SurveyorAcceptance(BaseModel):
    surveyor_id: str