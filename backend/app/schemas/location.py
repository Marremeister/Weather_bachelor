from datetime import datetime

from pydantic import BaseModel


class LocationResponse(BaseModel):
    id: int
    name: str
    latitude: float
    longitude: float
    timezone: str
    created_at: datetime

    model_config = {"from_attributes": True}
