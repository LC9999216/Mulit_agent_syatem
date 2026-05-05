from app.agents.filings_agent import FilingsAgent
from app.agents.financials_agent import FinancialsAgent
from app.agents.market_agent import MarketAgent
from app.agents.news_agent import NewsAgent
from app.agents.supervisor_agent import SupervisorAgent
from app.agents.thesis_agent import ThesisAgent
from app.agents.validation_agent import ValidationAgent


def build_agent_registry(runtime_services=None, llm_event_recorder=None) -> dict[str, object]:
    llm_client = getattr(runtime_services, "llm_client", None)
    settings = getattr(runtime_services, "settings", None)
    return {
        "supervisor": SupervisorAgent(
            llm_client=llm_client,
            llm_event_recorder=llm_event_recorder,
            settings=settings,
        ),
        "filings": FilingsAgent(
            llm_client=llm_client,
            llm_event_recorder=llm_event_recorder,
            settings=settings,
        ),
        "financials": FinancialsAgent(),
        "market": MarketAgent(),
        "news": NewsAgent(),
        "thesis": ThesisAgent(
            llm_client=llm_client,
            llm_event_recorder=llm_event_recorder,
            settings=settings,
        ),
        "validation": ValidationAgent(
            llm_client=llm_client,
            llm_event_recorder=llm_event_recorder,
            settings=settings,
        ),
    }
