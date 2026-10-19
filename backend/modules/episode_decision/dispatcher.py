from backend.modules.episode_decision.methods import day_boundary
from backend.schemas.episode_decision import EpisodeDecision, EpisodeDecisionContext
from backend.shared.errors import ConflictError, EpisodeDecisionError

DEFAULT_METHOD = "day_boundary"
METHODS = {"day_boundary": day_boundary.decide}


def decide_episode(context: EpisodeDecisionContext, *, method: str | None = None) -> EpisodeDecision:
    selected = METHODS.get(method if method is not None else DEFAULT_METHOD)
    if selected is None:
        raise EpisodeDecisionError("未知的情节判定方法")
    candidates = sorted(context.candidates, key=lambda record: record.round_no)
    if (not candidates or candidates[-1].id != context.current_round_id
            or len({r.id for r in candidates}) != len(candidates)
            or any(right.round_no != left.round_no + 1 for left, right in zip(candidates, candidates[1:]))):
        raise ConflictError("情节候选必须连续且不重复，并包含最新回合")
    ordered = context.model_copy(deep=True)
    ordered.candidates.sort(key=lambda record: record.round_no)
    end_id = selected(ordered)
    if end_id is None:
        return EpisodeDecision(episode_required=False)
    end = next((record for record in candidates[:-1] if record.id == end_id), None)
    if end is None:
        raise EpisodeDecisionError("判定截止回合必须属于最新回合之前的候选范围")
    return EpisodeDecision(episode_required=True, start_round_id=candidates[0].id,
                           end_round_id=end.id, start_round_no=candidates[0].round_no, end_round_no=end.round_no)
