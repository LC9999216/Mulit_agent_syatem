from enum import StrEnum


class AnalysisStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SupportType(StrEnum):
    FILING = "filing"
    MARKET_DATA = "market_data"
    DERIVED = "derived"
