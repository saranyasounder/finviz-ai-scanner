from __future__ import annotations

from datetime import datetime
from typing import Optional

from loguru import logger

from config.settings import ChangeDetectionThresholds
from models.change_event import ChangeEvent, ChangeType
from models.stock_candidate import StockCandidate


class ChangeDetector:
    """Detects only meaningful changes between two scans - new tickers, threshold-crossing
    moves in score/relative volume/gap/price, and Top-N entries/exits. Everything else is ignored."""

    def __init__(self, thresholds: ChangeDetectionThresholds, top_n: int):
        self.thresholds = thresholds
        self.top_n = top_n

    def detect(
        self,
        current: list[StockCandidate],
        previous: Optional[list[StockCandidate]],
    ) -> list[ChangeEvent]:
        now = datetime.now()
        events: list[ChangeEvent] = []

        previous_by_ticker = {s.ticker: s for s in previous} if previous else {}
        previous_top_n = {s.ticker for s in (previous or [])[: self.top_n]}
        current_top_n = {s.ticker for s in current[: self.top_n]}

        for stock in current:
            prev = previous_by_ticker.get(stock.ticker)

            if prev is None:
                events.append(
                    ChangeEvent(
                        ticker=stock.ticker,
                        change_type=ChangeType.NEW,
                        old_value=None,
                        new_value=stock.score,
                        timestamp=now,
                        description=f"{stock.ticker} is a new candidate (score {stock.score:.1f}).",
                    )
                )
            else:
                events.extend(self._diff(stock, prev, now))

            if stock.ticker in current_top_n and stock.ticker not in previous_top_n:
                events.append(
                    ChangeEvent(
                        ticker=stock.ticker,
                        change_type=ChangeType.ENTERED_TOP_N,
                        old_value=None,
                        new_value=stock.score,
                        timestamp=now,
                        description=f"{stock.ticker} entered the Top {self.top_n}.",
                    )
                )

        for ticker in previous_top_n - current_top_n:
            events.append(
                ChangeEvent(
                    ticker=ticker,
                    change_type=ChangeType.LEFT_TOP_N,
                    old_value=previous_by_ticker[ticker].score,
                    new_value=None,
                    timestamp=now,
                    description=f"{ticker} left the Top {self.top_n}.",
                )
            )

        if events:
            logger.info(f"ChangeDetector found {len(events)} meaningful change(s).")
        else:
            logger.info("ChangeDetector found no meaningful changes.")

        return events

    def _diff(
        self, current: StockCandidate, previous: StockCandidate, now: datetime
    ) -> list[ChangeEvent]:
        events: list[ChangeEvent] = []

        score_delta = current.score - previous.score
        if abs(score_delta) >= self.thresholds.score_delta:
            events.append(
                ChangeEvent(
                    ticker=current.ticker,
                    change_type=ChangeType.SCORE_CHANGE,
                    old_value=previous.score,
                    new_value=current.score,
                    timestamp=now,
                    description=f"{current.ticker} score changed by {score_delta:+.1f}.",
                )
            )

        if current.relative_volume is not None and previous.relative_volume is not None:
            rvol_delta = current.relative_volume - previous.relative_volume
            if abs(rvol_delta) >= self.thresholds.relative_volume_delta:
                events.append(
                    ChangeEvent(
                        ticker=current.ticker,
                        change_type=ChangeType.RELATIVE_VOLUME_CHANGE,
                        old_value=previous.relative_volume,
                        new_value=current.relative_volume,
                        timestamp=now,
                        description=f"{current.ticker} relative volume changed by {rvol_delta:+.2f}.",
                    )
                )

        if current.gap is not None and previous.gap is not None:
            gap_delta = current.gap - previous.gap
            if abs(gap_delta) >= self.thresholds.gap_delta_pct:
                events.append(
                    ChangeEvent(
                        ticker=current.ticker,
                        change_type=ChangeType.GAP_CHANGE,
                        old_value=previous.gap,
                        new_value=current.gap,
                        timestamp=now,
                        description=f"{current.ticker} gap changed by {gap_delta:+.2f}%.",
                    )
                )

        if previous.price:
            price_delta_pct = ((current.price - previous.price) / previous.price) * 100
            if abs(price_delta_pct) >= self.thresholds.price_delta_pct:
                events.append(
                    ChangeEvent(
                        ticker=current.ticker,
                        change_type=ChangeType.PRICE_CHANGE,
                        old_value=previous.price,
                        new_value=current.price,
                        timestamp=now,
                        description=f"{current.ticker} price changed by {price_delta_pct:+.2f}%.",
                    )
                )

        return events
