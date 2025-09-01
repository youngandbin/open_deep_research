import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.core.settings import settings
from api.models.requests import GenerateReportRequest
from api.models.responses import (
    JobListResponse,
    JobStatusResponse,
    JobSubmissionResponse,
    ReportResponse,
)
from api.services.async_job_service import async_job_service
from api.services.report_service import report_service

# Configure logging
# Use current directory for log file
log_file_path = "app.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(log_file_path), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events"""
    logger.info("Starting Elice Deer Backend API")
    yield
    logger.info("Shutting down Elice Deer Backend API")


# Create FastAPI app
app = FastAPI(
    title="Elice Deer Backend API",
    description="API for generating research reports using the Deep Researcher pipeline",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Note: Removed generation_router to avoid duplication with direct endpoints below


# Root endpoint
@app.get("/")
async def root():
    return {"message": "Elice Deer Backend API", "version": "0.1.0", "docs": "/docs"}


# API Endpoints (async only)


@app.post("/generate/async", response_model=JobSubmissionResponse)
async def generate_report_async(request: GenerateReportRequest) -> JobSubmissionResponse:
    """
    Submit a report generation job to run in the background.

    This endpoint submits a job for background processing and returns immediately
    with a job ID that can be used to check the status and retrieve results.

    Args:
        request: GenerateReportRequest containing topic, instructions, and other preferences

    Returns:
        JobSubmissionResponse with job ID and submission details
    """
    try:
        logger.info(f"Submitting async report generation for topic: {request.topic}")

        # Validate and prepare the request
        try:
            request = report_service.validate_and_prepare_request(request)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # Submit the job
        job_id = async_job_service.create_job(request)

        return JobSubmissionResponse(
            success=True,
            job_id=job_id,
            message="Report generation job submitted successfully",
            estimated_completion_time=180,  # Estimate based on typical generation time
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting async job: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to submit job: {str(e)}")


@app.get("/jobs/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(job_id: str) -> JobStatusResponse:
    """
    Get the status of a background generation job.

    Args:
        job_id: The unique identifier of the job

    Returns:
        JobStatusResponse with current job status and progress
    """
    try:
        job_data = async_job_service.get_job_status(job_id)

        if not job_data:
            raise HTTPException(status_code=404, detail="Job not found")

        return JobStatusResponse(**job_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job status for {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get job status")


@app.get("/jobs/{job_id}/result", response_model=ReportResponse)
async def get_job_result(job_id: str) -> ReportResponse:
    """
    Get the result of a completed background generation job.

    Args:
        job_id: The unique identifier of the job

    Returns:
        ReportResponse with the generated report content
    """
    try:
        # First check if job exists and is completed
        job_data = async_job_service.get_job_status(job_id)

        if not job_data:
            raise HTTPException(status_code=404, detail="Job not found")

        if job_data["status"] == "pending":
            raise HTTPException(status_code=202, detail="Job is still pending")
        elif job_data["status"] == "running":
            raise HTTPException(status_code=202, detail="Job is still running")
        elif job_data["status"] == "failed":
            raise HTTPException(status_code=400, detail=f"Job failed: {job_data.get('error', 'Unknown error')}")
        elif job_data["status"] == "cancelled":
            raise HTTPException(status_code=400, detail="Job was cancelled")
        elif job_data["status"] != "completed":
            raise HTTPException(status_code=400, detail=f"Job is in unexpected state: {job_data['status']}")

        # Get the result
        result = async_job_service.get_job_result(job_id)

        if not result:
            raise HTTPException(status_code=404, detail="Job result not found")

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job result for {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get job result")


@app.delete("/jobs/{job_id}")
async def cancel_job(job_id: str) -> JSONResponse:
    """
    Cancel a running background generation job.

    Args:
        job_id: The unique identifier of the job

    Returns:
        JSONResponse with cancellation status
    """
    try:
        cancelled = async_job_service.cancel_job(job_id)

        if not cancelled:
            # Check if job exists
            job_data = async_job_service.get_job_status(job_id)
            if not job_data:
                raise HTTPException(status_code=404, detail="Job not found")
            else:
                return JSONResponse(
                    status_code=400,
                    content={
                        "success": False,
                        "message": f"Job cannot be cancelled (status: {job_data['status']})",
                    },
                )

        return JSONResponse(status_code=200, content={"success": True, "message": "Job cancelled successfully"})

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling job {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to cancel job")


@app.get("/jobs", response_model=JobListResponse)
async def list_jobs(limit: int = Query(50, ge=1, le=100)) -> JobListResponse:
    """
    List recent background generation jobs.

    Args:
        limit: Maximum number of jobs to return (1-100)

    Returns:
        JobListResponse with list of recent jobs
    """
    try:
        jobs_data = async_job_service.list_jobs(limit=limit)

        job_responses = []
        for job_data in jobs_data["jobs"]:
            job_responses.append(JobStatusResponse(**job_data))

        return JobListResponse(jobs=job_responses, total=jobs_data["total"])

    except Exception as e:
        logger.error(f"Error listing jobs: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list jobs")


@app.get("/health")
async def health_check() -> JSONResponse:
    """
    Health check endpoint to verify the API is running.

    Returns:
        JSONResponse with service status
    """
    return JSONResponse(
        status_code=200,
        content={"status": "healthy", "service": "elice-deer-backend", "version": "0.1.0"},
    )


@app.get("/models")
async def get_available_models() -> JSONResponse:
    """
    Get information about available AI models and capabilities.

    Returns:
        JSONResponse with model information
    """
    return JSONResponse(
        status_code=200,
        content={
            "default_model": "gpt-4o",
            "research_model": "openai:gpt-4.1",
            "compression_model": "openai:gpt-4.1",
            "final_report_model": "openai:gpt-4.1",
            "summarization_model": "openai:gpt-4.1-mini",
            "output_formats": ["markdown"],
            "default_max_research_iterations": 6,
            "max_research_iterations_range": {"min": 1, "max": 10},
            "max_concurrent_research_units": 2,
            "max_react_tool_calls": 10,
            "features": {
                "web_search": True,
                "multi_agent_coordination": True,
                "content_planning": True,
                "markdown_export": True,
                "structured_output": True,
                "clarification_questions": True,
            },
            "search_apis": ["tavily", "openai_native", "anthropic_native"],
            "model_configurations": {
                "research_model_max_tokens": 10000,
                "compression_model_max_tokens": 8192,
                "final_report_model_max_tokens": 10000,
                "summarization_model_max_tokens": 8192,
            }
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )
