from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ReportResponse(BaseModel):
    """Response model for report generation"""

    success: bool = Field(..., description="Whether the generation was successful")
    report_content: Optional[str] = Field(None, description="Generated report content in markdown format")
    title: Optional[str] = Field(None, description="Title of the generated report")
    error: Optional[str] = Field(None, description="Error message if generation failed")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "report_content": "# Market Analysis of AI in Healthcare\n\n## Executive Summary\n\n...",
                "title": "Market Analysis of AI in Healthcare",
                "error": None,
            }
        }
    )


class JobStatusResponse(BaseModel):
    """Response model for job status requests"""

    job_id: str = Field(..., description="Unique identifier for the job")
    logs: List[str] = Field(default_factory=list, description="List of progress logs for the job")
    created_at: str = Field(..., description="When the job was created")
    started_at: Optional[str] = Field(None, description="When the job started execution")
    completed_at: Optional[str] = Field(None, description="When the job completed")
    error: Optional[str] = Field(None, description="Error message if job failed")
    request: dict = Field(..., description="Original request parameters")
    status: str = Field(..., description="Status of the job")
    current_research_iteration: int = Field(0, description="Current research iteration number")
    max_research_iterations: int = Field(6, description="Maximum number of research iterations")
    current_phase: str = Field("initializing", description="Current research phase")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "logs": [
                    "Job submitted successfully",
                    "Starting research phase",
                    "Research iteration 1/6",
                    "Generating report content",
                ],
                "created_at": "2025-01-07T10:00:00Z",
                "started_at": "2025-01-07T10:00:02Z",
                "completed_at": None,
                "error": None,
                "request": {
                    "topic": "Market Analysis of AI in Healthcare",
                    "instructions": "Focus on market trends and growth opportunities",
                    "max_plan_iterations": 2,
                    "do_background_research": True,
                    "locale": "en-US",
                    "depth": "medium",
                },
                "status": "running",
                "current_research_iteration": 1,
                "max_research_iterations": 6,
                "current_phase": "research",
            }
        }
    )


class JobSubmissionResponse(BaseModel):
    """Response model for job submission"""

    success: bool = Field(..., description="Whether the job was successfully submitted")
    job_id: str = Field(..., description="Unique identifier for the submitted job")
    message: str = Field(..., description="Human-readable message about the submission")
    estimated_completion_time: Optional[int] = Field(None, description="Estimated completion time in seconds")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "message": "Report generation job submitted successfully",
                "estimated_completion_time": 180,
            }
        }
    )


class JobListResponse(BaseModel):
    """Response model for listing jobs"""

    jobs: List[JobStatusResponse] = Field(..., description="List of jobs")
    total: int = Field(..., description="Total number of jobs")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "jobs": [
                    {
                        "job_id": "550e8400-e29b-41d4-a716-446655440000",
                        "status": "completed",
                        "created_at": "2025-01-07T10:00:00Z",
                        "started_at": "2025-01-07T10:00:02Z",
                        "completed_at": "2025-01-07T10:02:15Z",
                        "error": None,
                        "request": {
                            "topic": "Market Analysis of AI in Healthcare",
                            "instructions": "Focus on market trends and growth opportunities",
                            "depth": "medium",
                        },
                        "logs": ["Job completed successfully"],
                    }
                ],
                "total": 1,
            }
        }
    )


class HealthCheckResponse(BaseModel):
    """Response model for health check endpoint"""
    
    status: str = Field(..., description="Service status")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Service version")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "service": "elice-deer-backend",
                "version": "0.1.0"
            }
        }
    )


class ModelInfoResponse(BaseModel):
    """Response model for model information endpoint"""
    
    default_model: str = Field(..., description="Default AI model used")
    output_formats: List[str] = Field(..., description="List of supported output formats")
    default_max_research_iterations: int = Field(..., description="Default maximum number of research iterations")
    features: Dict[str, bool] = Field(..., description="Available features and their status")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "default_model": "gpt-4o",
                "output_formats": ["markdown"],
                "default_max_research_iterations": 6,
                "features": {
                    "web_search": True,
                    "multi_agent_coordination": True,
                    "content_planning": True,
                    "markdown_export": True,
                }
            }
        }
    )


class CancelJobResponse(BaseModel):
    """Response model for job cancellation endpoint"""
    
    success: bool = Field(..., description="Whether the cancellation was successful")
    message: str = Field(..., description="Human-readable message about the cancellation")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Job cancelled successfully"
            }
        }
    )
