from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "dev"
    app_name: str = "stock-research-multiagent"
    database_url: str = "sqlite:///./stock_research.db"
    redis_url: str = "redis://localhost:6379/0"
    sec_user_agent: str = "stock-research-multiagent contact@example.com"
    market_data_providers: str = "fmp,polygon,finnhub"
    market_data_api_key: str = ""
    market_data_base_url: str = "https://financialmodelingprep.com/stable"
    polygon_api_key: str = ""
    polygon_base_url: str = "https://api.polygon.io"
    finnhub_api_key: str = ""
    finnhub_base_url: str = "https://finnhub.io/api/v1"
    alpaca_api_key: str = ""
    alpaca_api_secret: str = ""
    alpaca_news_base_url: str = "https://data.alpaca.markets/v1beta1/news"
    web_news_search_enabled: bool = True
    web_news_search_base_url: str = "https://www.bing.com/news/search"
    sec_rss_feed_url_template: str = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={ticker}&owner=exclude&count=20&output=atom"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    use_demo_data: bool = True
    llm_enabled: bool = False
    llm_provider: str = "openai"
    llm_model_supervisor: str = "gpt-4o-mini"
    llm_model_filings: str = "gpt-4o-mini"
    llm_model_thesis: str = "gpt-4o-mini"
    llm_model_validation: str = "gpt-4o-mini"
    llm_timeout_seconds: float = 30.0
    llm_max_retries: int = 1
    worker_poll_interval_seconds: float = 1.0
    worker_error_backoff_seconds: float = 5.0
    market_data_max_retries: int = 2
    market_data_retry_backoff_seconds: float = 1.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    def resolve_llm_model(self, agent_name: str) -> str:
        configured = getattr(self, f"llm_model_{agent_name}", "") or ""
        provider = (self.llm_provider or "").strip().lower()
        normalized = configured.strip()

        if provider == "deepseek" and (not normalized or normalized.startswith("gpt-")):
            return "deepseek-chat"
        if provider == "openai" and (not normalized or normalized.startswith("deepseek-")):
            return "gpt-4o-mini"
        return normalized


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
