from pathlib import Path
from uuid import uuid4

import pytest

from app.config import get_settings
from app.data_sources.market_data_client import MarketDataClient
from app.data_sources.sec_client import SecClient
from app.services.analysis_service import AnalysisService
from app.services.runtime import RuntimeServices


@pytest.fixture
def isolated_service() -> AnalysisService:
    get_settings.cache_clear()
    database_path = Path.cwd() / f".test-{uuid4().hex}.db"
    runtime_services = RuntimeServices()
    runtime_services.settings.database_url = f"sqlite:///{database_path.as_posix()}"
    runtime_services.settings.use_demo_data = True
    runtime_services.sec_client = SecClient(use_demo_data=True)
    runtime_services.market_data_client = MarketDataClient(use_demo_data=True)
    yield AnalysisService(runtime_services=runtime_services)
