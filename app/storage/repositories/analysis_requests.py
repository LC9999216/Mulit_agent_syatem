from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.storage.models import AnalysisRequestModel


@dataclass
class StoredAnalysisRequest:
    request_id: str
    ticker: str
    status: str
    request_payload: dict
    report_payload: dict | None
    error_message: str | None


class AnalysisRequestRepository:
    def __init__(self, session_factory: sessionmaker) -> None:
        self.session_factory = session_factory

    def create(self, request_id: str, ticker: str, status: str, request_payload: dict) -> StoredAnalysisRequest:
        with self.session_factory() as session:
            model = AnalysisRequestModel(
                request_id=request_id,
                ticker=ticker,
                status=status,
                request_payload=request_payload,
            )
            session.add(model)
            session.commit()
            return self._to_record(model)

    def get(self, request_id: str) -> StoredAnalysisRequest | None:
        with self.session_factory() as session:
            model = session.get(AnalysisRequestModel, request_id)
            return self._to_record(model) if model else None

    def update_status(self, request_id: str, status: str, error_message: str | None = None) -> StoredAnalysisRequest:
        with self.session_factory() as session:
            model = session.get(AnalysisRequestModel, request_id)
            if model is None:
                raise KeyError(request_id)
            model.status = status
            model.error_message = error_message
            session.commit()
            session.refresh(model)
            return self._to_record(model)

    def get_oldest_by_status(self, status: str) -> StoredAnalysisRequest | None:
        with self.session_factory() as session:
            statement = (
                select(AnalysisRequestModel)
                .where(AnalysisRequestModel.status == status)
                .order_by(AnalysisRequestModel.created_at.asc())
            )
            model = session.execute(statement).scalars().first()
            return self._to_record(model) if model else None

    def save_report(self, request_id: str, status: str, report_payload: dict) -> StoredAnalysisRequest:
        with self.session_factory() as session:
            model = session.get(AnalysisRequestModel, request_id)
            if model is None:
                raise KeyError(request_id)
            model.status = status
            model.report_payload = report_payload
            model.error_message = None
            session.commit()
            session.refresh(model)
            return self._to_record(model)

    @staticmethod
    def _to_record(model: AnalysisRequestModel) -> StoredAnalysisRequest:
        return StoredAnalysisRequest(
            request_id=model.request_id,
            ticker=model.ticker,
            status=model.status,
            request_payload=model.request_payload,
            report_payload=model.report_payload,
            error_message=model.error_message,
        )
