from pydantic import BaseModel, Field, model_validator
from typing import List, Optional


class SettlementTriageRecord(BaseModel):
    id: str
    name: str
    place: str = "settlement"
    road_status: str
    foot_status: str
    cutoff_probability: float = Field(ge=0.0, le=1.0)
    critical_bottleneck: Optional[str] = None
    logistics_recommendation: str


class SituationReportData(BaseModel):
    report_id: str
    generated_at: str
    flood_date: str
    osm_snapshot: str
    total_settlements: int
    settlements_cut_off: int
    foot_cut_off: int
    pedestrian_accessible_only: int
    damaged_road_segments: int
    total_buildings: int
    hospitals_monitored: int
    triage_records: List[SettlementTriageRecord]

    @model_validator(mode="after")
    def verify_numbers(self):
        """Automated number verification to guarantee consistency across deliverables."""
        # Settlements cut off cannot exceed total settlements
        if self.settlements_cut_off > self.total_settlements:
            raise ValueError("settlements_cut_off cannot exceed total_settlements")

        # Completely isolated cannot exceed road cut off
        if self.foot_cut_off > self.settlements_cut_off:
            raise ValueError("foot_cut_off cannot exceed settlements_cut_off")

        return self