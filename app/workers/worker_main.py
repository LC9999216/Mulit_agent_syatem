import time
import logging

from app.logging import configure_logging
from app.services.analysis_service import AnalysisService
from app.workers.tasks_analysis import AnalysisWorker


logger = logging.getLogger(__name__)


def run_worker_loop(
    worker: AnalysisWorker,
    poll_interval: float,
    error_backoff: float,
    sleep_fn=time.sleep,
    stop_after_iterations: int | None = None,
) -> int:
    processed_total = 0
    iterations = 0
    while True:
        if stop_after_iterations is not None and iterations >= stop_after_iterations:
            return processed_total
        iterations += 1
        try:
            processed = worker.run_once()
        except Exception:
            logger.exception("Worker iteration failed; backing off before retry")
            sleep_fn(error_backoff)
            continue

        if processed:
            processed_total += 1
            continue

        sleep_fn(poll_interval)


def main() -> None:
    configure_logging()
    service = AnalysisService()
    worker = AnalysisWorker(service.runtime_services, service.repository, service.queue)
    worker.agent_run_repository = service.agent_run_repository
    poll_interval = service.runtime_services.settings.worker_poll_interval_seconds
    error_backoff = service.runtime_services.settings.worker_error_backoff_seconds
    logger.info(
        "Starting analysis worker loop with poll_interval=%s error_backoff=%s",
        poll_interval,
        error_backoff,
    )
    try:
        run_worker_loop(
            worker=worker,
            poll_interval=poll_interval,
            error_backoff=error_backoff,
        )
    except KeyboardInterrupt:
        logger.info("Analysis worker stopped by operator")


if __name__ == "__main__":
    main()
