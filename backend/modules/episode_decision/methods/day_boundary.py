from backend.schemas.episode_decision import EpisodeDecisionContext
from backend.shared.errors import EpisodeDecisionError
from backend.modules.state.world import parse_date

MIN_PREVIOUS_ROUNDS = 5


def decide(context: EpisodeDecisionContext) -> str | None:
    """Dispatcher supplies sorted consecutive candidates, with the current round last."""
    if len(context.candidates) - 1 < MIN_PREVIOUS_ROUNDS:
        return None
    previous, current = context.candidates[-2:]
    dates = []
    for record in (previous, current):
        date = context.dates.get(record.id)
        try:
            dates.append(parse_date(date))
        except ValueError as error:
            raise EpisodeDecisionError(f"回合 {record.id}：{error}") from error
    return None if dates[0] == dates[1] else previous.id
