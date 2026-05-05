from app.agents.base import BaseAgent
from app.schemas.common import Citation, ConfidenceLevel, StatementWithCitations
from app.schemas.financials import MetricPoint
from app.schemas.market import MarketOutput, TradePlan


class MarketAgent(BaseAgent):
    name = "market"

    def run(self, state: dict) -> MarketOutput:
        snapshot = state.get("market_snapshot", {})
        ticker = state["request"].ticker
        source_uris = snapshot.get("source_uris", {})

        quote_citation = Citation(
            source_type="market_data",
            source_uri=source_uris.get("quote", f"market://snapshot/{ticker}/quote"),
            label=f"{ticker} quote",
            support_type="market_data",
        )
        ratios_citation = Citation(
            source_type="market_data",
            source_uri=source_uris.get("ratios", f"market://snapshot/{ticker}/ratios"),
            label=f"{ticker} valuation metrics",
            support_type="market_data",
        )
        history_citation = Citation(
            source_type="market_data",
            source_uri=source_uris.get("history", source_uris.get("price_change", f"market://snapshot/{ticker}/history")),
            label=f"{ticker} price history",
            support_type="market_data",
        )

        price = self._safe_float(snapshot.get("price"))
        price_change_1y = self._safe_optional_float(snapshot.get("price_change_1y"))
        year_high = self._safe_optional_float(snapshot.get("year_high"))
        year_low = self._safe_optional_float(snapshot.get("year_low"))
        pe_ttm = self._safe_optional_float(snapshot.get("pe_ttm"))
        price_to_sales = self._safe_optional_float(snapshot.get("price_to_sales"))
        bars = snapshot.get("price_bars") or []

        key_metrics_table: dict[str, list[MetricPoint]] = {}
        latest_price_analysis: list[StatementWithCitations] = []
        price_action_summary: list[StatementWithCitations] = []
        market_view: list[StatementWithCitations] = []
        valuation_view: list[StatementWithCitations] = []

        closes = [self._safe_float(bar.get("close")) for bar in bars if bar.get("close") is not None]
        highs = [self._safe_float(bar.get("high")) for bar in bars if bar.get("high") is not None]
        lows = [self._safe_float(bar.get("low")) for bar in bars if bar.get("low") is not None]
        volumes = [self._safe_float(bar.get("volume")) for bar in bars if bar.get("volume") is not None]

        ma50 = self._moving_average(closes[-50:]) if closes else None
        ma200 = self._moving_average(closes[-200:]) if closes else None
        atr20 = self._compute_atr20(bars) if bars else None
        support_20 = min(closes[-20:]) if len(closes) >= 20 else (min(closes) if closes else None)
        resistance_20 = max(closes[-20:]) if len(closes) >= 20 else (max(closes) if closes else None)
        support_60 = min(closes[-60:]) if len(closes) >= 60 else (min(closes) if closes else None)
        resistance_60 = max(closes[-60:]) if len(closes) >= 60 else (max(closes) if closes else None)

        if price is not None:
            key_metrics_table["price"] = [MetricPoint(period="latest", value=float(price), source="market_snapshot")]
        if price_change_1y is not None:
            key_metrics_table["price_change_1y"] = [
                MetricPoint(period="trailing_1y", value=float(price_change_1y), source="market_snapshot")
            ]
            price_action_summary.append(
                StatementWithCitations(
                    statement=f"{ticker} shares are up {price_change_1y:.0%} over the trailing year.",
                    citations=[quote_citation],
                )
            )
        if price is not None and year_high is not None and year_low is not None and year_high != year_low:
            range_position = (float(price) - float(year_low)) / (float(year_high) - float(year_low))
            key_metrics_table["range_position_52w"] = [
                MetricPoint(period="trailing_52w", value=range_position, source="derived")
            ]
            price_action_summary.append(
                StatementWithCitations(
                    statement=f"{ticker} is trading at roughly {range_position:.0%} of its 52-week price range.",
                    citations=[quote_citation],
                )
            )
        if ma50 is not None:
            key_metrics_table["ma50"] = [MetricPoint(period="latest", value=ma50, source="derived")]
        if ma200 is not None:
            key_metrics_table["ma200"] = [MetricPoint(period="latest", value=ma200, source="derived")]
        if atr20 is not None:
            key_metrics_table["atr20"] = [MetricPoint(period="latest", value=atr20, source="derived")]

        trend_state = self._determine_trend(price=price, ma50=ma50, ma200=ma200)
        support_level = self._choose_support(price, support_20, ma50)
        medium_support = self._choose_support(price, support_60, ma200)
        resistance_level = resistance_20
        medium_resistance = resistance_60
        display_support = support_level if support_level is not None else (
            max((price or 0) - (1.2 * (atr20 or max((price or 0) * 0.04, 1.0))), year_low or 0.0) if price is not None else None
        )
        display_resistance = resistance_level if resistance_level is not None else (
            min((price or 0) + (2.0 * (atr20 or max((price or 0) * 0.04, 1.0))), year_high or ((price or 0) * 1.12)) if price is not None else None
        )

        if price is not None:
            latest_price_analysis.append(
                StatementWithCitations(
                    statement=f"{ticker} is trading around {price:.2f} and the trend currently reads as {trend_state.replace('_', ' ')}.",
                    citations=[quote_citation, history_citation],
                )
            )
        if year_high is not None and year_low is not None and year_high != year_low and price is not None:
            range_position = (float(price) - float(year_low)) / (float(year_high) - float(year_low))
            latest_price_analysis.append(
                StatementWithCitations(
                    statement=f"The stock is sitting around {range_position:.0%} of its 52-week range, which suggests the market is still pricing in a strong operating backdrop.",
                    citations=[quote_citation],
                )
            )
        if display_support is not None and display_resistance is not None:
            latest_price_analysis.append(
                StatementWithCitations(
                    statement=f"Nearest support sits near {display_support:.2f}, while near-term resistance sits near {display_resistance:.2f}.",
                    citations=[history_citation],
                )
            )
        if price_to_sales is not None:
            latest_price_analysis.append(
                StatementWithCitations(
                    statement=f"Valuation remains demanding at roughly {price_to_sales:.1f}x sales, so upside still depends on sustained high execution.",
                    citations=[ratios_citation],
                )
            )
        if trend_state == "uptrend":
            market_view.append(
                StatementWithCitations(
                    statement=f"{ticker} remains in an uptrend, but the setup should be treated as execution-sensitive after a large prior move.",
                    citations=[quote_citation, history_citation],
                )
            )
        elif trend_state == "downtrend":
            market_view.append(
                StatementWithCitations(
                    statement=f"{ticker} is in a weaker technical posture, so downside control matters more than upside projection right now.",
                    citations=[quote_citation, history_citation],
                )
            )
        else:
            market_view.append(
                StatementWithCitations(
                    statement=f"{ticker} is trading in a more mixed range-like setup, so entries should be staged rather than chased.",
                    citations=[quote_citation, history_citation],
                )
            )

        if pe_ttm is not None:
            key_metrics_table["pe_ttm"] = [MetricPoint(period="latest", value=float(pe_ttm), source="market_snapshot")]
            valuation_view.append(
                StatementWithCitations(
                    statement=f"{ticker} trades around {pe_ttm:.1f}x trailing earnings, which keeps valuation sensitive to any growth normalization.",
                    citations=[ratios_citation],
                )
            )
        if price_to_sales is not None:
            key_metrics_table["price_to_sales"] = [
                MetricPoint(period="latest", value=float(price_to_sales), source="market_snapshot")
            ]
            valuation_view.append(
                StatementWithCitations(
                    statement=f"Price-to-sales remains elevated near {price_to_sales:.1f}x, reinforcing how much future growth the market is already discounting.",
                    citations=[ratios_citation],
                )
            )

        short_term_plan = self._build_trade_plan(
            horizon="short_term",
            ticker=ticker,
            price=price,
            trend_state=trend_state,
            atr20=atr20,
            support=support_level,
            resistance=resistance_level,
            fallback_support=year_low,
            fallback_resistance=year_high,
            position_size_pct=12.0,
        )
        mid_term_plan = self._build_trade_plan(
            horizon="mid_term",
            ticker=ticker,
            price=price,
            trend_state=trend_state,
            atr20=atr20,
            support=medium_support or support_level,
            resistance=medium_resistance or resistance_level,
            fallback_support=year_low,
            fallback_resistance=year_high,
            position_size_pct=20.0,
        )

        return MarketOutput(
            key_metrics_table=key_metrics_table,
            latest_price_analysis=latest_price_analysis,
            price_action_summary=price_action_summary,
            valuation_view=valuation_view,
            market_view=market_view,
            short_term_plan=short_term_plan,
            mid_term_plan=mid_term_plan,
            citations=[quote_citation, ratios_citation, history_citation],
            confidence=ConfidenceLevel.MEDIUM,
        )

    @staticmethod
    def _safe_float(value: object) -> float | None:
        if value in (None, ""):
            return None
        return float(value)

    @staticmethod
    def _safe_optional_float(value: object) -> float | None:
        if value in (None, ""):
            return None
        return float(value)

    @staticmethod
    def _moving_average(values: list[float]) -> float | None:
        if not values:
            return None
        return sum(values) / len(values)

    @classmethod
    def _compute_atr20(cls, bars: list[dict]) -> float | None:
        if len(bars) < 2:
            return None
        true_ranges: list[float] = []
        previous_close = cls._safe_float(bars[0].get("close"))
        for bar in bars[1:]:
            high = cls._safe_float(bar.get("high"))
            low = cls._safe_float(bar.get("low"))
            close = cls._safe_float(bar.get("close"))
            if high is None or low is None or previous_close is None:
                previous_close = close
                continue
            true_range = max(high - low, abs(high - previous_close), abs(low - previous_close))
            true_ranges.append(true_range)
            previous_close = close
        if not true_ranges:
            return None
        window = true_ranges[-20:]
        return sum(window) / len(window)

    @staticmethod
    def _determine_trend(price: float | None, ma50: float | None, ma200: float | None) -> str:
        if price is None or ma50 is None or ma200 is None:
            return "range"
        if price > ma50 and ma50 > ma200:
            return "uptrend"
        if price < ma50 and ma50 < ma200:
            return "downtrend"
        return "range"

    @staticmethod
    def _choose_support(price: float | None, level_a: float | None, level_b: float | None) -> float | None:
        candidates = [level for level in (level_a, level_b) if level is not None]
        if not candidates:
            return None
        if price is None:
            return candidates[0]
        return min(candidates, key=lambda level: abs(price - level))

    def _build_trade_plan(
        self,
        *,
        horizon: str,
        ticker: str,
        price: float | None,
        trend_state: str,
        atr20: float | None,
        support: float | None,
        resistance: float | None,
        fallback_support: float | None,
        fallback_resistance: float | None,
        position_size_pct: float,
    ) -> TradePlan | None:
        if price is None:
            return None

        atr_value = atr20 or max(price * 0.04, 1.0)
        chosen_support = support if support is not None else max(price - (1.2 * atr_value), fallback_support or (price * 0.9))
        chosen_resistance = resistance if resistance is not None else min(price + (2.0 * atr_value), fallback_resistance or (price * 1.12))

        if horizon == "short_term":
            target_price = max(chosen_resistance, price + (2.0 * atr_value))
            stop_loss = min(chosen_support, price - (1.2 * atr_value))
            if trend_state == "uptrend":
                bias = "bullish"
                entry_context = "Prefer buying pullbacks into support or confirmed breakouts rather than chasing intraday spikes."
            elif trend_state == "range":
                bias = "neutral"
                entry_context = "Treat this as a range trade and wait for pullbacks toward support before adding risk."
            else:
                bias = "cautious"
                entry_context = "Avoid aggressive chasing while the short-term trend is weaker; only watch for reversal confirmation."
        else:
            target_price = max(chosen_resistance, price * (1 + max(0.12, (3.0 * atr_value / price))))
            stop_candidates = [value for value in (chosen_support, price * 0.88) if value is not None]
            stop_loss = max(stop_candidates) if stop_candidates else (price * 0.88)
            if trend_state == "downtrend":
                bias = "cautious"
                entry_context = "Use staged entries only if the intermediate trend begins to repair."
            else:
                bias = "bullish"
                entry_context = "Use staged entries while the primary trend remains intact and avoid oversized chasing after sharp extensions."

        return TradePlan(
            horizon=horizon,
            bias=bias,
            entry_context=entry_context,
            target_price=round(target_price, 2),
            stop_loss=round(stop_loss, 2),
            position_size_pct=position_size_pct,
            rationale=[
                f"{ticker} is currently in a {trend_state.replace('_', ' ')} technical setup.",
                f"Support is anchored near {chosen_support:.2f} and resistance is near {chosen_resistance:.2f}.",
            ],
            invalidators=[
                f"A decisive break below {round(stop_loss, 2):.2f} would invalidate the current {horizon.replace('_', ' ')} setup.",
            ],
        )
