import threading
import uuid
from dataclasses import dataclass, field


class OperationCancelled(RuntimeError):
    pass


@dataclass
class OperationState:
    event: threading.Event = field(default_factory=threading.Event)
    stage: str = "uploading"
    progress: int = 0
    status: str = "running"
    error: str | None = None
    document_id: uuid.UUID | None = None


class CancellationRegistry:
    """Process-local cooperative cancellation for work executed by this API process."""

    def __init__(self) -> None:
        self._states: dict[uuid.UUID, OperationState] = {}
        self._lock = threading.Lock()

    def state(self, operation_id: uuid.UUID) -> OperationState:
        with self._lock:
            return self._states.setdefault(operation_id, OperationState())

    def token(self, operation_id: uuid.UUID) -> threading.Event:
        return self.state(operation_id).event

    def update(self, operation_id: uuid.UUID, stage: str, progress: int,
               status: str = "running", error: str | None = None) -> None:
        if stage == "completed":
            status = "completed"
        state = self.state(operation_id)
        state.stage, state.progress, state.status, state.error = stage, progress, status, error

    def cancel(self, operation_id: uuid.UUID) -> None:
        state = self.state(operation_id)
        state.event.set()
        state.stage, state.status = "cancelling", "cancelling"

    def finish(self, operation_id: uuid.UUID) -> None:
        with self._lock:
            self._states.pop(operation_id, None)

    def bind_document(self, operation_id: uuid.UUID, document_id: uuid.UUID) -> None:
        self.state(operation_id).document_id = document_id

    def cancel_document(self, document_id: uuid.UUID) -> None:
        with self._lock:
            matches = [(operation_id, state) for operation_id, state in self._states.items()
                       if state.document_id == document_id]
        for operation_id, state in matches:
            state.event.set()
            state.stage, state.status = "cancelling", "cancelling"
            with self._lock:
                self._states.pop(operation_id, None)

    def cancel_documents(self, document_ids: set[uuid.UUID]) -> int:
        """Cancel every in-flight operation bound to any of the given documents."""
        if not document_ids:
            return 0
        with self._lock:
            matches = [
                (operation_id, state)
                for operation_id, state in self._states.items()
                if state.document_id in document_ids
            ]
        for operation_id, state in matches:
            state.event.set()
            state.stage, state.status = "cancelling", "cancelling"
            with self._lock:
                self._states.pop(operation_id, None)
        return len(matches)


operations = CancellationRegistry()


def check_cancelled(token: threading.Event | None) -> None:
    if token is not None and token.is_set():
        raise OperationCancelled()
