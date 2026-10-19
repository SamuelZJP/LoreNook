"""Opt-in, append-only model attempt journal; never persist authentication headers."""

from contextvars import ContextVar
from datetime import UTC, datetime
from functools import wraps
import inspect
import json
from pathlib import Path
import threading
import time


_scope = ContextVar("model_call_scope", default=None)
_lock = threading.RLock()


def _now():
    return datetime.now(UTC).isoformat()


def _json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


class CallJournal:
    def __init__(self, directory):
        self.root = Path(directory).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def begin(self, content, *, api_type, model):
        scope = _scope.get()
        context = scope[0] if scope else {}
        with _lock:
            records = [json.loads(p.read_text(encoding="utf-8"))
                       for p in self.root.glob("*/metadata.json")]
            number = 1
            while True:
                directory = self.root / f"{number:06d}"
                try:
                    directory.mkdir()
                    break
                except FileExistsError:
                    number += 1
            key = (context.get("chat_id"), context.get("round_id"), context.get("round_no"),
                   context.get("purpose", "direct"))
            attempt = 1 + sum((r.get("chat_id"), r.get("round_id"), r.get("round_no"),
                               r.get("purpose")) == key for r in records)
            metadata = {"call_id": directory.name, "chat_id": None, "round_id": None,
                        "round_no": None, "purpose": "direct", **context,
                        "attempt": attempt, "started_at": _now(), "api_type": api_type,
                        "model": model, "result": "started", "response_complete": False,
                        "request_file": f"{directory.name}/request.json",
                        "response_file": f"{directory.name}/response.raw",
                        "metadata_file": f"{directory.name}/metadata.json"}
            (directory / "request.json").write_bytes(content)
            (directory / "response.raw").write_bytes(b"")
            record = Attempt(self, directory, metadata)
            record.save()
            if scope:
                scope[1].append(record)
            return record


class Attempt:
    def __init__(self, journal, directory, metadata):
        self.journal, self.directory, self.metadata = journal, directory, metadata
        self.started = time.perf_counter()

    def save(self):
        with _lock:
            _json(self.directory / "metadata.json", self.metadata)
            # Events are append-only; the latest event for a call is its current status.
            with (self.journal.root / "index.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(self.metadata, ensure_ascii=False, allow_nan=False) + "\n")

    def chunk(self, chunk):
        with (self.directory / "response.raw").open("ab") as stream:
            stream.write(chunk)

    def finish(self, error=None):
        try:
            value = json.loads((self.directory / "response.raw").read_bytes())
            _json(self.directory / "response.json", value)
            self.metadata["response_json_file"] = f"{self.directory.name}/response.json"
        except (ValueError, UnicodeError, RecursionError):
            pass  # Exact bytes remain available even for malformed/non-JSON replies.
        self.metadata.update(finished_at=_now(), duration_ms=round((time.perf_counter() - self.started) * 1000, 3),
                             result=getattr(error, "kind", type(error).__name__) if error else "success")
        if error:
            # Exception strings can contain URLs and authentication. Store only safe classification.
            self.metadata["error_type"] = type(error).__name__
        self.save()


def recorded_workflow(purpose):
    """Associate transport records with a workflow, including parse/persistence failures."""
    def decorate(function):
        signature = inspect.signature(function)

        @wraps(function)
        def wrapped(*args, **kwargs):
            values = signature.bind(*args, **kwargs).arguments
            client = values["client"]
            if getattr(client, "journal", None) is None:
                return function(*args, **kwargs)
            chat_id, round_id = values.get("chat_id"), values.get("round_id")
            from backend.repository.queries import Repository
            from backend.repository.models import Round
            with values["database"].read() as session:
                repo = Repository(session)
                record = (repo.get_owned(Round, round_id, chat_id) if round_id else
                          repo.latest_round(chat_id) if chat_id else None)
                round_no = (record.round_no if round_id else (record.round_no + 1 if record else 1)) if chat_id else None
            calls = []
            token = _scope.set(({"chat_id": chat_id, "round_id": round_id,
                                 "round_no": round_no, "purpose": purpose}, calls))
            try:
                result = function(*args, **kwargs)
            except BaseException as error:
                for call in calls:
                    call.metadata.update(workflow_result="error", workflow_error_type=type(error).__name__)
                    call.save()
                raise
            else:
                for call in calls:
                    call.metadata["workflow_result"] = "success"
                    call.save()
                return result
            finally:
                _scope.reset(token)
        return wrapped
    return decorate
