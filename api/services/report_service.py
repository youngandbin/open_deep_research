import logging
import os
import sys
from typing import Optional
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from api.models.requests import GenerateReportRequest
from api.models.responses import ReportResponse
from api.core.settings import settings
from open_deep_research.deep_researcher import deep_researcher
from open_deep_research.configuration import Configuration

logger = logging.getLogger(__name__)


class ReportService:
    """Service for handling report generation"""

    # Mapping of depth levels to max_researcher_iterations
    DEPTH_MAPPING = {"shallow": 3, "medium": 6, "deep": 9}

    def __init__(self):
        self.logger = logger

    def validate_and_prepare_request(self, request: GenerateReportRequest) -> GenerateReportRequest:
        """
        Validate and prepare the request for report generation.

        Args:
            request: The incoming report generation request

        Returns:
            Validated and prepared request

        Raises:
            ValueError: If request validation fails
        """
        # Basic validation
        if not request.topic or not request.topic.strip():
            raise ValueError("Topic cannot be empty")

        # Validate depth parameter
        if request.depth and request.depth not in self.DEPTH_MAPPING:
            raise ValueError(
                f"Invalid depth value '{request.depth}'. Must be one of: {', '.join(self.DEPTH_MAPPING.keys())}"
            )

        # Set defaults if not provided
        if request.depth is None:
            request.depth = "medium"

        return request

    def _create_config(self, max_researcher_iterations: int) -> Configuration:
        """Create configuration for deep researcher with API keys from settings"""
        # Set environment variables for API keys
        if settings.openai_api_key:
            os.environ["OPENAI_API_KEY"] = settings.openai_api_key
        if settings.anthropic_api_key:
            os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key
        if settings.tavily_api_key:
            os.environ["TAVILY_API_KEY"] = settings.tavily_api_key

        return Configuration(
            research_model=settings.default_model,
            research_model_max_tokens=4000,
            compression_model=settings.default_model,
            compression_model_max_tokens=4000,
            final_report_model=settings.default_model,
            final_report_model_max_tokens=8000,
            max_researcher_iterations=max_researcher_iterations,
            max_concurrent_research_units=2,
            max_react_tool_calls=10,
            allow_clarification=True,
            max_structured_output_retries=3,
            mcp_prompt=""
        )

    def generate_report_sync(
        self,
        request: GenerateReportRequest,
        log_callback: Optional[callable] = None,
        progress_callback: Optional[callable] = None,
        is_cancelled: Optional[callable] = None,
    ) -> ReportResponse:
        """
        Generate a report based on the provided request (synchronous version).

        Args:
            request: The report generation request
            log_callback: Optional callback for logging progress

        Returns:
            ReportResponse containing the generated report
        """
        try:
            self.logger.info(f"Starting report generation for topic: {request.topic}")

            if log_callback:
                log_callback("Starting report generation...")

            # Convert depth to max_researcher_iterations
            max_researcher_iterations = self.DEPTH_MAPPING.get(request.depth, 6)  # default to medium

            # Create configuration for deep researcher
            config = self._create_config(max_researcher_iterations)

            if log_callback:
                log_callback("Initialized Deep Researcher")

            # Prepare the message for the pipeline
            message = request.topic
            if request.instructions:
                message = f"{request.topic}\n\nInstructions: {request.instructions}"

            if log_callback:
                log_callback("Starting report generation process")

            # Run the deep researcher (synchronous)
            result = deep_researcher.invoke({
                "messages": [{"role": "user", "content": message}]
            }, config={"configurable": config.model_dump()})

            if log_callback:
                log_callback("Report generation completed")

            self.logger.info(f"Report generation completed for topic: {request.topic}")

            # Extract the final report from the result
            final_report = None
            if "final_report" in result:
                final_report = result["final_report"]
            elif "messages" in result and result["messages"]:
                final_report = result["messages"][-1].content if hasattr(result["messages"][-1], 'content') else str(result["messages"][-1])

            return ReportResponse(success=True, report_content=final_report, title=request.topic, error=None)

        except Exception as e:
            error_msg = f"Failed to generate report: {str(e)}"
            self.logger.error(error_msg)

            if log_callback:
                log_callback(f"Error: {error_msg}")

            return ReportResponse(success=False, report_content=None, title=None, error=error_msg)

    async def generate_report(
        self,
        request: GenerateReportRequest,
        log_callback: Optional[callable] = None,
        progress_callback: Optional[callable] = None,
        is_cancelled: Optional[callable] = None,
    ) -> ReportResponse:
        """
        Generate a report based on the provided request (fully async).
        """
        try:
            self.logger.info(f"Starting report generation for topic: {request.topic}")
            if log_callback:
                log_callback("Starting report generation...")

            # Convert depth to max_researcher_iterations
            max_researcher_iterations = self.DEPTH_MAPPING.get(request.depth, 6)

            # Create configuration for deep researcher
            config = self._create_config(max_researcher_iterations)

            if log_callback:
                log_callback("Initialized Deep Researcher")

            # Prepare the message for the pipeline
            message = request.topic
            if request.instructions:
                message = f"{request.topic}\n\nInstructions: {request.instructions}"
            if log_callback:
                log_callback("Starting report generation process")

            # Run the deep researcher asynchronously
            result = await deep_researcher.ainvoke({
                "messages": [{"role": "user", "content": message}]
            }, config={"configurable": config.model_dump()})
            if log_callback:
                log_callback("Report generation completed")

            self.logger.info(f"Report generation completed for topic: {request.topic}")
            
            # Extract the final report from the result
            final_report = None
            if "final_report" in result:
                final_report = result["final_report"]
            elif "messages" in result and result["messages"]:
                final_report = result["messages"][-1].content if hasattr(result["messages"][-1], 'content') else str(result["messages"][-1])

            return ReportResponse(
                success=True,
                report_content=final_report,
                title=request.topic,
                error=None,
            )
        except Exception as e:
            error_msg = f"Failed to generate report: {str(e)}"
            self.logger.error(error_msg)
            if log_callback:
                log_callback(f"Error: {error_msg}")
            return ReportResponse(
                success=False,
                report_content=None,
                title=None,
                error=error_msg,
            )


# Global instance
report_service = ReportService()
