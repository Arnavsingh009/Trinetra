from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field
from pydantic import BaseModel
from typing import Optional, List

class RestoreEdgeRequest(BaseModel):
    edge_id: str

class JobState(str, Enum):
    QUEUED = "QUEUED"
    DISCOVERING = "DISCOVERING"
    DOWNLOADING = "DOWNLOADING"
    PROCESSING = "PROCESSING"
    INFERENCE = "INFERENCE"
    NETWORK_ANALYSIS = "NETWORK_ANALYSIS"
    REPORTING = "REPORTING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class AOI(BaseModel):
    type: str = Field(default="Polygon")
    coordinates: list[list[list[float]]]


class AnalyzeRequest(BaseModel):
    aoi: AOI
    flood_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    config: str = "default"


class JobResponse(BaseModel):
    id: str
    state: JobState
    created_at: datetime
    flood_date: str
    message: str


class LayerResponse(BaseModel):
    name: str
    type: str
    data: dict[str, Any]
    status: str = "available"


class SummaryResponse(BaseModel):
    id: str
    state: JobState
    flood_date: str
    layers: list[str]
    message: str
