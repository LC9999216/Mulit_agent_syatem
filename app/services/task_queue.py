import json
from collections import deque
from typing import Protocol

import redis


class TaskQueue(Protocol):
    def enqueue(self, request_id: str) -> None: ...

    def dequeue(self) -> str | None: ...


class InMemoryTaskQueue:
    def __init__(self) -> None:
        self._items: deque[str] = deque()

    def enqueue(self, request_id: str) -> None:
        self._items.append(request_id)

    def dequeue(self) -> str | None:
        if not self._items:
            return None
        return self._items.popleft()


class RedisTaskQueue:
    def __init__(self, redis_url: str, queue_name: str = "analysis:jobs") -> None:
        self.client = redis.Redis.from_url(redis_url, decode_responses=True)
        self.queue_name = queue_name

    def enqueue(self, request_id: str) -> None:
        self.client.rpush(self.queue_name, request_id)

    def dequeue(self) -> str | None:
        item = self.client.lpop(self.queue_name)
        return str(item) if item is not None else None
