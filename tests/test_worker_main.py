from app.workers import worker_main


class StubWorker:
    def __init__(self, results: list[bool | Exception]) -> None:
        self.results = results
        self.calls = 0

    def run_once(self) -> bool:
        result = self.results[self.calls]
        self.calls += 1
        if isinstance(result, Exception):
            raise result
        return result


def test_run_worker_loop_retries_after_unhandled_error() -> None:
    worker = StubWorker([RuntimeError("boom"), False, True])
    sleep_calls: list[float] = []

    processed = worker_main.run_worker_loop(
        worker=worker,
        poll_interval=1.5,
        error_backoff=4.0,
        sleep_fn=sleep_calls.append,
        stop_after_iterations=3,
    )

    assert processed == 1
    assert worker.calls == 3
    assert sleep_calls == [4.0, 1.5]


def test_run_worker_loop_keeps_polling_until_work_arrives() -> None:
    worker = StubWorker([False, False, True])
    sleep_calls: list[float] = []

    processed = worker_main.run_worker_loop(
        worker=worker,
        poll_interval=2.0,
        error_backoff=5.0,
        sleep_fn=sleep_calls.append,
        stop_after_iterations=3,
    )

    assert processed == 1
    assert worker.calls == 3
    assert sleep_calls == [2.0, 2.0]
