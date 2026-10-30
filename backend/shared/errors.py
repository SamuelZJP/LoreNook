class NotFoundError(LookupError):
    """A requested record does not exist."""


class ConflictError(ValueError):
    """Stored data no longer permits the requested operation."""


class AdminDataError(ValueError):
    """Raw data management fields are invalid; never include submitted values."""


class ArchiveExecutionError(RuntimeError):
    """A persisted archive stopped; carry its progress alongside the original error."""

    def __init__(self, cause: Exception, progress):
        self.cause = cause
        self.progress = progress
        super().__init__("归档已停止，请读取保存进度")


class StateInitializationError(ValueError):
    """A character's schema cannot produce a valid initial state."""


class StateSchemaError(ValueError):
    """State schema compilation, validation or correction failed."""


class StateUpdateError(ValueError):
    """Current round content or model patch response is invalid."""


class RoundSummaryError(ValueError):
    """Current round content or generated summary text is invalid."""


class EpisodeDecisionError(ValueError):
    """A decision method or its required state variables are invalid."""


class EpisodeSummaryError(ValueError):
    """Episode source material or generated summary is invalid."""


class PresetExecutionError(ValueError):
    """A preset failed to execute or returned an invalid result."""

    def __init__(self, stage: str, message: str):
        self.stage = stage
        self.message = message
        super().__init__(f"Preset {stage}: {message}")


class ModelConfigurationError(ValueError):
    """An unsupported or incompatible model request; no network call was made."""


class ModelCallError(RuntimeError):
    """Sanitized transport/provider failure, without credentials or response bodies."""

    def __init__(self, kind: str, message: str, upstream_status: int | None = None):
        self.kind = kind
        self.message = message
        self.upstream_status = upstream_status
        super().__init__(message)


class DefinitionTemplateError(ValueError):
    """An individual definition failed to compile or render."""

    def __init__(self, definition_id: str, message: str, line: int | None = None):
        self.definition_id = definition_id
        self.message = message
        self.line = line
        super().__init__(f"Definition {definition_id}: {message}")


class IllustrationError(ValueError):
    """An image workflow, generated image prompt or image platform result is invalid."""
