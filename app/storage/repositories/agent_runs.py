from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.storage.models import AgentRunModel


@dataclass
class StoredAgentRun:
    id: int
    request_id: str
    stage_name: str
    status: str
    payload: dict | None


class AgentRunRepository:
    def __init__(self, session_factory: sessionmaker) -> None:
        self.session_factory = session_factory

    def create(
        self,
        request_id: str,
        stage_name: str,
        status: str,
        payload: dict | None = None,
    ) -> StoredAgentRun:
        with self.session_factory() as session:
            model = AgentRunModel(
                request_id=request_id,
                stage_name=stage_name,
                status=status,
                payload=payload,
            )
            session.add(model)
            session.commit()
            session.refresh(model)
            return self._to_record(model)

    def list_for_request(self, request_id: str) -> list[StoredAgentRun]:
        with self.session_factory() as session:
            statement = (
                select(AgentRunModel)
                .where(AgentRunModel.request_id == request_id)
                .order_by(AgentRunModel.id.asc())
            )
            models = session.execute(statement).scalars().all()
            return [self._to_record(model) for model in models]

    @staticmethod
    def _to_record(model: AgentRunModel) -> StoredAgentRun:
        return StoredAgentRun(
            id=model.id,
            request_id=model.request_id,
            stage_name=model.stage_name,
            status=model.status,
            payload=model.payload,
        )
