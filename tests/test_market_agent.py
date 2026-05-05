from app.agents.market_agent import MarketAgent
from app.schemas.request import CompanyAnalysisRequest


def test_market_agent_builds_price_action_and_valuation_views() -> None:
    agent = MarketAgent()

    result = agent.run(
        {
            "request": CompanyAnalysisRequest(
                ticker="NVDA",
                user_goal="Assess market positioning",
            ),
            "market_snapshot": {
                "ticker": "NVDA",
                "price": 950.0,
                "price_change_1y": 0.82,
                "year_high": 1000.0,
                "year_low": 400.0,
                "pe_ttm": 45.0,
                "price_to_sales": 22.0,
                "price_bars": [
                    {"open": 910.0, "high": 920.0, "low": 900.0, "close": 915.0, "volume": 1000},
                    {"open": 920.0, "high": 935.0, "low": 915.0, "close": 930.0, "volume": 1100},
                    {"open": 932.0, "high": 950.0, "low": 928.0, "close": 945.0, "volume": 1200},
                    {"open": 946.0, "high": 970.0, "low": 940.0, "close": 965.0, "volume": 1300},
                    {"open": 966.0, "high": 980.0, "low": 960.0, "close": 975.0, "volume": 1400},
                    {"open": 976.0, "high": 990.0, "low": 970.0, "close": 985.0, "volume": 1500},
                    {"open": 986.0, "high": 1000.0, "low": 980.0, "close": 995.0, "volume": 1600},
                    {"open": 996.0, "high": 1010.0, "low": 990.0, "close": 1005.0, "volume": 1700},
                    {"open": 1006.0, "high": 1020.0, "low": 1000.0, "close": 1015.0, "volume": 1800},
                    {"open": 1016.0, "high": 1030.0, "low": 1010.0, "close": 1025.0, "volume": 1900},
                    {"open": 1026.0, "high": 1040.0, "low": 1020.0, "close": 1035.0, "volume": 2000},
                    {"open": 1036.0, "high": 1050.0, "low": 1030.0, "close": 1045.0, "volume": 2100},
                    {"open": 1046.0, "high": 1060.0, "low": 1040.0, "close": 1055.0, "volume": 2200},
                    {"open": 1056.0, "high": 1070.0, "low": 1050.0, "close": 1065.0, "volume": 2300},
                    {"open": 1066.0, "high": 1080.0, "low": 1060.0, "close": 1075.0, "volume": 2400},
                    {"open": 1076.0, "high": 1090.0, "low": 1070.0, "close": 1085.0, "volume": 2500},
                    {"open": 1086.0, "high": 1100.0, "low": 1080.0, "close": 1095.0, "volume": 2600},
                    {"open": 1096.0, "high": 1110.0, "low": 1090.0, "close": 1105.0, "volume": 2700},
                    {"open": 1106.0, "high": 1120.0, "low": 1100.0, "close": 1115.0, "volume": 2800},
                    {"open": 1116.0, "high": 1130.0, "low": 1110.0, "close": 1125.0, "volume": 2900},
                ],
                "source_uris": {
                    "quote": "https://financialmodelingprep.com/stable/quote?symbol=NVDA",
                    "ratios": "https://financialmodelingprep.com/stable/ratios?symbol=NVDA",
                },
            },
        }
    )

    assert result.price_action_summary
    assert any("82%" in item.statement or "82" in item.statement for item in result.price_action_summary)
    assert result.market_view
    assert result.valuation_view
    assert result.latest_price_analysis
    assert result.short_term_plan is not None
    assert result.mid_term_plan is not None
    assert result.short_term_plan.target_price is not None
    assert result.short_term_plan.stop_loss is not None
    assert result.short_term_plan.position_size_pct == 12.0
    assert result.mid_term_plan.position_size_pct == 20.0
    assert result.citations
