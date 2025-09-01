import logging
import os

import bentoml

# Configure logging
# Use current directory for log file
log_file_path = "service.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(log_file_path), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# Import the FastAPI app
from app import app as fastapi_app

# Create the BentoML service by mounting the FastAPI app directly
svc = bentoml.Service("open-deep-research", config={"workers": 1})

# Mount the FastAPI app to the BentoML service
svc.mount_asgi_app(fastapi_app, path="/v1")


def test_service():
    """Test that the BentoML service and FastAPI app are working."""
    logger.info("Testing BentoML service...")

    try:
        # Test that we can access the FastAPI app
        if fastapi_app is not None:
            logger.info("FastAPI app is accessible")
            logger.info(f"FastAPI app title: {fastapi_app.title}")
            logger.info(f"FastAPI app version: {fastapi_app.version}")
            logger.info(f"BentoML service name: {svc.name}")
            logger.info("FastAPI app successfully mounted to BentoML service")

            # List all routes
            logger.info("Available routes:")
            for route in fastapi_app.routes:
                if hasattr(route, "path") and hasattr(route, "methods"):
                    logger.info(f"  {route.methods} {route.path}")
        else:
            logger.error("FastAPI app is not properly imported")

    except Exception as e:
        logger.error(f"Failed to test service: {e}")


def test_generate_report_async():
    """Test async report generation and save result to markdown file."""
    import time
    import json
    import os
    from datetime import datetime
    from fastapi.testclient import TestClient

    logger.info("Testing async report generation...")

    try:
        # Create test client for the FastAPI app
        with TestClient(fastapi_app) as client:
            # Create sample report request (updated to match new API structure)
            sample_request = {
                "topic": "대규모 언어 모델(LLM)의 활용 현황과 미래 전망",
                "instructions": "대규모 언어 모델이 다양한 분야에서 어떻게 활용되고 있는지에 대한 종합적인 보고서를 작성해 주세요. 예를 들어 검색, 고객 서비스, 교육, 금융, 소프트웨어 개발 등에서의 LLM 적용 사례와 효과를 구체적으로 설명하고, 현재 기술적 한계와 향후 발전 방향에 대해 분석해 주세요. 최신 연구 동향과 산업 적용 사례도 포함해 주세요.",
                "depth": "shallow",
            }

            logger.info(f"Submitting async report generation for topic: {sample_request['topic']}")

            # Submit async job
            response = client.post("/generate/async", json=sample_request)

            if response.status_code != 200:
                logger.error(f"Failed to submit async job: {response.status_code} - {response.text}")
                return

            job_data = response.json()
            if not job_data.get("success", False):
                logger.error(f"Job submission failed: {job_data.get('message', 'Unknown error')}")
                return

            job_id = job_data["job_id"]
            logger.info(f"Async job submitted successfully with ID: {job_id}")

            # Poll for completion
            max_wait_time = 1200  # 20 minutes
            poll_interval = 5  # 5 seconds
            elapsed_time = 0
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            while elapsed_time < max_wait_time:
                # Check job status
                status_response = client.get(f"/jobs/{job_id}/status")

                if status_response.status_code != 200:
                    logger.error(f"Failed to get job status: {status_response.status_code}")
                    break

                status_data = status_response.json()
                current_status = status_data.get("status", "unknown")

                logger.info(f"Job status: {current_status}")

                if current_status == "completed":
                    logger.info("Job completed! Getting result...")

                    # Get result
                    result_response = client.get(f"/jobs/{job_id}/result")

                    if result_response.status_code != 200:
                        logger.error(f"Failed to get job result: {result_response.status_code}")
                        break

                    result_data = result_response.json()

                    if result_data.get("success", False) and result_data.get("report_content"):
                        # Save to markdown file
                        filename = f"async_report_{timestamp}.md"
                        with open(filename, "w", encoding="utf-8") as f:
                            f.write(result_data["report_content"])

                        logger.info(f"✅ Async report saved successfully to: {filename}")

                        # Log some stats
                        content_length = len(result_data["report_content"])
                        logger.info(f"📊 Report statistics:")
                        logger.info(f"   - Content length: {content_length:,} characters")
                        logger.info(f"   - Topic: {sample_request['topic']}")
                        logger.info(f"   - Job ID: {job_id}")
                        logger.info(f"   - Total time: {elapsed_time + poll_interval} seconds")

                    else:
                        logger.error(f"Job completed but no valid content: {result_data.get('error', 'Unknown error')}")
                    break

                elif current_status in ["failed", "cancelled"]:
                    error_msg = status_data.get("error", "Unknown error")
                    logger.error(f"Job {current_status}: {error_msg}")
                    break

                elif current_status == "running":
                    # Show progress if available (updated for new API structure)
                    current_research_iteration = status_data.get("current_research_iteration", 0)
                    max_research_iterations = status_data.get("max_research_iterations", 6)
                    current_phase = status_data.get("current_phase", "unknown")

                    logger.info(
                        f"   Progress: Phase {current_phase}, Research Iteration {current_research_iteration}/{max_research_iterations}"
                    )

                # Wait before next poll
                time.sleep(poll_interval)
                elapsed_time += poll_interval

            if elapsed_time >= max_wait_time:
                logger.warning(f"⏰ Job timed out after {max_wait_time} seconds")
                # Try to cancel the job
                cancel_response = client.delete(f"/jobs/{job_id}")
                if cancel_response.status_code == 200:
                    logger.info("Job cancelled due to timeout")

    except Exception as e:
        logger.error(f"Failed to test async report generation: {e}")


def test_concurrent_report_generation():
    """Test concurrent async report generation with two simultaneous requests."""
    import time
    import json
    import os
    import threading
    from datetime import datetime
    from fastapi.testclient import TestClient

    logger.info("Testing concurrent async report generation...")

    def generate_report(topic, instructions, report_id):
        """Generate a single report in a separate thread."""
        try:
            with TestClient(fastapi_app) as client:
                # Create report request (updated to match new API structure)
                request_data = {
                    "topic": topic,
                    "instructions": instructions,
                    "depth": "shallow",
                }

                logger.info(f"[Report {report_id}] Submitting request for topic: {topic}")

                # Submit async job
                response = client.post("/generate/async", json=request_data)

                if response.status_code != 200:
                    logger.error(f"[Report {report_id}] Failed to submit: {response.status_code}")
                    return None

                job_data = response.json()
                if not job_data.get("success", False):
                    logger.error(f"[Report {report_id}] Job submission failed: {job_data.get('message')}")
                    return None

                job_id = job_data["job_id"]
                logger.info(f"[Report {report_id}] Job submitted with ID: {job_id}")

                # Poll for completion
                max_wait_time = 1200  # 20 minutes
                poll_interval = 5  # 5 seconds
                elapsed_time = 0
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

                while elapsed_time < max_wait_time:
                    # Check job status
                    status_response = client.get(f"/jobs/{job_id}/status")

                    if status_response.status_code != 200:
                        logger.error(f"[Report {report_id}] Failed to get status: {status_response.status_code}")
                        break

                    status_data = status_response.json()
                    current_status = status_data.get("status", "unknown")

                    if current_status == "completed":
                        logger.info(f"[Report {report_id}] ✅ Job completed! Getting result...")

                        # Get result
                        result_response = client.get(f"/jobs/{job_id}/result")

                        if result_response.status_code != 200:
                            logger.error(f"[Report {report_id}] Failed to get result: {result_response.status_code}")
                            break

                        result_data = result_response.json()

                        if result_data.get("success", False) and result_data.get("report_content"):
                            # Save to markdown file
                            filename = f"concurrent_report_{report_id}_{timestamp}.md"
                            with open(filename, "w", encoding="utf-8") as f:
                                f.write(result_data["report_content"])

                            logger.info(f"[Report {report_id}] 📄 Report saved to: {filename}")

                            # Log stats
                            content_length = len(result_data["report_content"])
                            logger.info(
                                f"[Report {report_id}] 📊 Stats: {content_length:,} chars, {elapsed_time + poll_interval}s"
                            )

                            return {
                                "report_id": report_id,
                                "job_id": job_id,
                                "filename": filename,
                                "content_length": content_length,
                                "total_time": elapsed_time + poll_interval,
                                "topic": topic,
                            }
                        else:
                            logger.error(f"[Report {report_id}] No valid content: {result_data.get('error')}")
                        break

                    elif current_status in ["failed", "cancelled"]:
                        error_msg = status_data.get("error", "Unknown error")
                        logger.error(f"[Report {report_id}] Job {current_status}: {error_msg}")
                        break

                    elif current_status == "running":
                        # Show progress (updated for new API structure)
                        current_research_iteration = status_data.get("current_research_iteration", 0)
                        max_research_iterations = status_data.get("max_research_iterations", 6)
                        current_phase = status_data.get("current_phase", "unknown")
                        logger.info(f"[Report {report_id}] 🔄 Running: Phase {current_phase}, Research Iteration {current_research_iteration}/{max_research_iterations}")

                    # Wait before next poll
                    time.sleep(poll_interval)
                    elapsed_time += poll_interval

                if elapsed_time >= max_wait_time:
                    logger.warning(f"[Report {report_id}] ⏰ Timed out after {max_wait_time}s")
                    # Try to cancel
                    client.delete(f"/jobs/{job_id}")

        except Exception as e:
            logger.error(f"[Report {report_id}] Error: {e}")

        return None

    try:
        # Define two different reports to generate concurrently
        report_configs = [
            {
                "topic": "AI 기반 스마트 시티 구축 현황과 발전 방향",
                "instructions": "인공지능을 활용한 스마트 시티 구축이 도시 관리와 시민 생활에 미치는 영향에 대한 종합 보고서를 작성해 주세요. 교통 관리, 에너지 효율화, 환경 모니터링, 공공 안전 등 다양한 분야에서의 AI 활용 사례와 효과를 구체적인 데이터와 함께 분석해 주세요.",
                "report_id": "A",
            },
            {
                "topic": "AI와 로봇 기술의 제조업 혁신 사례",
                "instructions": "AI와 로봇 기술이 제조업에서 어떻게 생산성과 효율성을 향상시키고 있는지에 대한 상세한 분석 보고서를 작성해 주세요. 자동화, 예측 유지보수, 품질 관리, 공급망 최적화 등의 영역에서의 성공 사례와 도입 과정에서의 도전 과제들을 포함해 주세요.",
                "report_id": "B",
            },
        ]

        logger.info("🚀 Starting concurrent report generation...")
        logger.info(f"Report A: {report_configs[0]['topic']}")
        logger.info(f"Report B: {report_configs[1]['topic']}")

        # Record start time
        start_time = time.time()

        # Create threads for concurrent execution
        threads = []
        results = {}

        def thread_wrapper(config):
            result = generate_report(config["topic"], config["instructions"], config["report_id"])
            results[config["report_id"]] = result

        # Start both threads
        for config in report_configs:
            thread = threading.Thread(target=thread_wrapper, args=(config,))
            thread.start()
            threads.append(thread)

        # Wait for both threads to complete
        for thread in threads:
            thread.join()

        # Calculate total time
        total_time = time.time() - start_time

        # Summary
        logger.info("=" * 60)
        logger.info("🏁 CONCURRENT REPORT GENERATION SUMMARY")
        logger.info("=" * 60)

        successful_reports = 0
        for report_id, result in results.items():
            if result:
                successful_reports += 1
                logger.info(f"✅ Report {report_id}: SUCCESS")
                logger.info(f"   Topic: {result['topic']}")
                logger.info(f"   File: {result['filename']}")
                logger.info(f"   Size: {result['content_length']:,} characters")
                logger.info(f"   Time: {result['total_time']} seconds")
            else:
                logger.error(f"❌ Report {report_id}: FAILED")

        logger.info(f"📈 Overall Results:")
        logger.info(f"   Successful: {successful_reports}/2 reports")
        logger.info(f"   Total wall time: {total_time:.1f} seconds")
        logger.info(f"   Concurrency test: {'PASSED' if successful_reports == 2 else 'FAILED'}")

        if successful_reports == 2:
            logger.info("🎉 Both reports generated successfully in parallel!")
        else:
            logger.warning("⚠️  Some reports failed to generate")

    except Exception as e:
        logger.error(f"Failed to test concurrent report generation: {e}")


def test_models_endpoint():
    """Test the models endpoint to verify available models and capabilities."""
    from fastapi.testclient import TestClient

    logger.info("Testing models endpoint...")

    try:
        with TestClient(fastapi_app) as client:
            response = client.get("/models")

            if response.status_code != 200:
                logger.error(f"Failed to get models info: {response.status_code} - {response.text}")
                return

            models_data = response.json()
            logger.info("✅ Models endpoint working correctly")
            logger.info(f"📋 Available models and capabilities:")
            logger.info(f"   - Default model: {models_data.get('default_model', 'N/A')}")
            logger.info(f"   - Research model: {models_data.get('research_model', 'N/A')}")
            logger.info(f"   - Compression model: {models_data.get('compression_model', 'N/A')}")
            logger.info(f"   - Final report model: {models_data.get('final_report_model', 'N/A')}")
            logger.info(f"   - Max research iterations: {models_data.get('default_max_research_iterations', 'N/A')}")
            logger.info(f"   - Search APIs: {models_data.get('search_apis', [])}")
            logger.info(f"   - Features: {list(models_data.get('features', {}).keys())}")

    except Exception as e:
        logger.error(f"Failed to test models endpoint: {e}")


if __name__ == "__main__":
    logger.info("Starting Open Deep Research BentoML Service")
    test_service()
    logger.info("=" * 60)
    test_models_endpoint()
    logger.info("=" * 60)
    
    test_generate_report_async()  #  single test
    # test_concurrent_report_generation()  # concurrent test
