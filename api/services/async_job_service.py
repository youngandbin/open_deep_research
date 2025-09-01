import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, Optional

from api.models.requests import GenerateReportRequest
from api.models.responses import ReportResponse
from api.services.report_service import report_service

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AsyncJob:
    def __init__(self, job_id: str, request: GenerateReportRequest):
        self.job_id = job_id
        self.request = request
        self.status = JobStatus.PENDING
        self.created_at = datetime.now()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.result: Optional[ReportResponse] = None
        self.error: Optional[str] = None
        self.task: Optional[asyncio.Task] = None
        self.logs: list[str] = []
        # Progress tracking for deep researcher
        self.current_research_iteration: int = 0
        self.max_research_iterations: int = self._get_max_research_iterations(request)
        self.current_phase: str = "initializing"

    def _get_max_research_iterations(self, request: GenerateReportRequest) -> int:
        """Convert depth to max_researcher_iterations"""
        depth_mapping = {"shallow": 3, "medium": 6, "deep": 9}
        return depth_mapping.get(request.depth or "medium", 6)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
            "request": self.request.model_dump(),
            "logs": self.logs,
            "current_research_iteration": self.current_research_iteration,
            "max_research_iterations": self.max_research_iterations,
            "current_phase": self.current_phase,
        }

    def add_log(self, message: str):
        """Add a log message to the job (no timestamp in stored logs).

        Slight improvements:
        - Remove timestamps from the stored job logs for cleaner UI.
        - De-duplicate consecutive identical messages to reduce noise.
        """
        # De-duplicate consecutive identical messages
        if self.logs and self.logs[-1] == message:
            return
        self.logs.append(message)
        # Keep standard logging (timestamps controlled by logging config)
        logger.info(f"Job {self.job_id}: {message}")

    def update_research_progress(self, current_iteration: int):
        """Update the current research iteration progress"""
        self.current_research_iteration = current_iteration
        self.add_log(f"Research iteration {current_iteration}/{self.max_research_iterations}")

    def update_phase(self, phase: str):
        """Update the current research phase"""
        self.current_phase = phase
        self.add_log(f"Phase: {phase}")


class AsyncJobService:
    def __init__(self, max_workers: int = 2):
        self.jobs: Dict[str, AsyncJob] = {}
        # No thread pool; jobs run as asyncio Tasks on the event loop
        self._shutdown = False
        logger.info(f"AsyncJobService initialized (async mode)")

    def create_job(self, request: GenerateReportRequest) -> str:
        """Create a new async job"""
        job_id = str(uuid.uuid4())
        job = AsyncJob(job_id, request)
        self.jobs[job_id] = job

        # More informative creation log (no timestamp in stored logs)
        job.add_log(
            "Created: "
            f"topic='{request.topic}', "
            f"depth={request.depth or 'medium'}, "
            f"maxResearchIterations={job.max_research_iterations}"
        )
        # Schedule the job on the current event loop as an asyncio Task
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # If called from a sync context without a running loop, create one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        job.task = loop.create_task(self._run_job_async(job))

        logger.info(f"Created async job {job_id} for topic: {request.topic}")
        return job_id

    async def _run_job_async(self, job: AsyncJob):
        """Async job runner scheduled on the event loop"""
        try:
            job.status = JobStatus.RUNNING
            job.started_at = datetime.now()
            job.add_log("Started report generation")

            # Callbacks captured by closure
            def log_callback(message: str):
                job.add_log(message)

            def progress_callback(phase: str = None, research_iteration: int = None):
                if phase is not None:
                    job.update_phase(phase)
                if research_iteration is not None:
                    job.update_research_progress(research_iteration)

            def is_cancelled() -> bool:
                return job.status == JobStatus.CANCELLED

            # Run the report generation asynchronously
            result = await report_service.generate_report(
                job.request,
                log_callback=log_callback,
                progress_callback=progress_callback,
                is_cancelled=is_cancelled,
            )

            # Only update status if not already cancelled
            if job.status != JobStatus.CANCELLED:
                job.result = result
                job.status = JobStatus.COMPLETED if result.success else JobStatus.FAILED
                job.completed_at = datetime.now()

                # Compose completion/collapse summary
                elapsed = None
                if job.started_at and job.completed_at:
                    elapsed = (job.completed_at - job.started_at).total_seconds()

                if result.success:
                    summary = "Completed successfully"
                    if elapsed is not None:
                        summary += f" in {elapsed:.1f}s"
                    summary += (
                        f" (research iterations {job.current_research_iteration}/{job.max_research_iterations})"
                    )
                    job.add_log(summary)
                else:
                    job.error = result.error
                    summary = "Failed"
                    if elapsed is not None:
                        summary += f" after {elapsed:.1f}s"
                    if result.error:
                        summary += f": {result.error}"
                    job.add_log(summary)

        except asyncio.CancelledError:
            # Task was cancelled
            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.now()
            elapsed = None
            if job.started_at and job.completed_at:
                elapsed = (job.completed_at - job.started_at).total_seconds()
            summary = "Cancelled"
            if elapsed is not None:
                summary += f" after {elapsed:.1f}s"
            summary += (
                f" at research iteration {job.current_research_iteration}/{job.max_research_iterations}"
            )
            job.add_log(summary)
        except Exception as e:
            if job.status != JobStatus.CANCELLED:
                job.status = JobStatus.FAILED
                job.error = str(e)
                job.completed_at = datetime.now()
                elapsed = None
                if job.started_at and job.completed_at:
                    elapsed = (job.completed_at - job.started_at).total_seconds()
                summary = "Failed with exception"
                if elapsed is not None:
                    summary += f" after {elapsed:.1f}s"
                if e:
                    summary += f": {str(e)}"
                job.add_log(summary)
                logger.error(f"Job {job.job_id} failed: {str(e)}")

    # Legacy sync path retained if needed by other callers
    def _run_report_generation_sync(
        self,
        request: GenerateReportRequest,
        log_callback: callable,
        progress_callback: callable = None,
        is_cancelled: callable = None,
    ) -> ReportResponse:
        return report_service.generate_report_sync(request, log_callback, progress_callback, is_cancelled)

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a job"""
        job = self.jobs.get(job_id)
        return job.to_dict() if job else None

    def get_job_result(self, job_id: str) -> Optional[ReportResponse]:
        """Get the result of a completed job"""
        job = self.jobs.get(job_id)
        if not job or job.status != JobStatus.COMPLETED:
            return None
        return job.result

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job"""
        job = self.jobs.get(job_id)
        if not job:
            return False

        if job.status in [JobStatus.PENDING, JobStatus.RUNNING]:
            # Mark job as cancelled first to prevent race conditions
            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.now()
            elapsed = None
            if job.started_at:
                elapsed = (datetime.now() - job.started_at).total_seconds()
            summary = "Cancelled"
            if elapsed is not None:
                summary += f" after {elapsed:.1f}s"
            summary += (
                f" at research iteration {job.current_research_iteration}/{job.max_research_iterations}"
            )
            job.add_log(summary)

            # Try to cancel the asyncio task if it exists and is not done
            if job.task and not job.task.done():
                try:
                    job.task.cancel()
                except Exception as e:
                    logger.warning(f"Error cancelling task for job {job_id}: {str(e)}")

            logger.info(f"Cancelled job {job_id}")
            return True

        return False

    def list_jobs(self, limit: int = 50) -> Dict[str, Any]:
        """List recent jobs"""
        jobs_list = list(self.jobs.values())
        # Sort by creation time (newest first)
        jobs_list.sort(key=lambda x: x.created_at, reverse=True)

        # Apply limit
        jobs_list = jobs_list[:limit]

        return {"jobs": [job.to_dict() for job in jobs_list], "total": len(self.jobs)}

    def cleanup_old_jobs(self, max_age_hours: int = 24):
        """Clean up old jobs to prevent memory leaks"""
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        jobs_to_remove = []

        for job_id, job in self.jobs.items():
            if job.completed_at and job.completed_at < cutoff_time:
                jobs_to_remove.append(job_id)

        for job_id in jobs_to_remove:
            del self.jobs[job_id]

        if jobs_to_remove:
            logger.info(f"Cleaned up {len(jobs_to_remove)} old jobs")

    def shutdown(self, wait: bool = True):
        """Shutdown the service and cleanup resources"""
        if self._shutdown:
            return

        logger.info("Shutting down AsyncJobService...")
        self._shutdown = True

        # Cancel all pending/running jobs
        for job in self.jobs.values():
            if job.status in [JobStatus.PENDING, JobStatus.RUNNING]:
                self.cancel_job(job.job_id)

    logger.info("AsyncJobService shutdown completed")

    def __del__(self):
        """Cleanup on deletion"""
        try:
            self.shutdown(wait=False)
        except:
            pass  # Ignore errors during cleanup


# Global instance
async_job_service = AsyncJobService()
