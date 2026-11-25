from backend.schemas.common import Contract


class CardSummary(Contract):
    """What an import would bring in, shown before the user confirms."""
    name: str
    scenes: int
    has_state_schema: bool
    has_state_script: bool
    # Feature sections this installation reads, and those it would skip.
    features: list[str]
    unknown_features: list[str]
