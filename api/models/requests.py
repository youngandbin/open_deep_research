from typing import Optional, Literal

from pydantic import BaseModel, ConfigDict, Field


class GenerateReportRequest(BaseModel):
    """Request model for report generation"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "topic": "Market Analysis of AI in Healthcare",
                "instructions": "Focus on market trends, key players, and growth opportunities. Include data analysis and statistics.",
                "depth": "medium",
            }
        }
    )

    topic: str = Field(..., description="The topic for the report", min_length=1, max_length=500)
    instructions: Optional[str] = Field(
        None, description="Instructions for the report", min_length=1, max_length=2000
    )
    depth: Optional[Literal["shallow", "medium", "deep"]] = Field("medium", description="Research depth: shallow (3 steps), medium (6 steps), or deep (9 steps)")
