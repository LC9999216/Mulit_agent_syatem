from dataclasses import dataclass, field
from uuid import uuid4

from app.config import get_settings
from app.data_sources.market_data_client import MarketDataClient
from app.data_sources.news_client import NewsClient
from app.data_sources.sec_client import SecClient
from app.services.llm_client import build_llm_client


@dataclass
class RuntimeServices:
    settings: object = field(default_factory=get_settings)
    sec_client: object | None = None
    market_data_client: object | None = None
    news_client: object | None = None
    llm_client: object | None = None

    def __post_init__(self) -> None:
        if self.sec_client is None:
            self.sec_client = SecClient(
                user_agent=self.settings.sec_user_agent,
                use_demo_data=self.settings.use_demo_data,
            )
        if self.market_data_client is None:
            self.market_data_client = MarketDataClient(
                api_key=self.settings.market_data_api_key,
                use_demo_data=self.settings.use_demo_data,
                base_url=self.settings.market_data_base_url,
            )
        if self.news_client is None:
            self.news_client = NewsClient(use_demo_data=self.settings.use_demo_data)
        if self.llm_client is None:
            self.llm_client = build_llm_client(self.settings)

    def next_request_id(self) -> str:
        return f"req-{uuid4().hex[:12]}"
