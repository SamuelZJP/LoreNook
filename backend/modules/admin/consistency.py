"""Cross-row rules for the final database state of an administrative batch."""

from backend.shared.errors import ConflictError


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ConflictError(message)


def check_consistency(tables: dict[str, list[dict]]) -> None:
    characters = {row["chat_id"]: row for row in tables["characters"] if row["chat_id"] is not None}
    identities = {row["chat_id"]: row for row in tables["user_identities"] if row["chat_id"] is not None}
    states = {row["round_id"]: row for row in tables["state_snapshots"] if row["round_id"] is not None}
    initial = {row["character_id"] for row in tables["state_snapshots"] if row["round_id"] is None}
    episodes_by_creator = {row["created_by_round_id"]: row for row in tables["episodes"]
                           if row["created_by_round_id"] is not None}
    for chat in tables["chats"]:
        cid = chat["id"]
        _require(cid in characters and cid in identities, "聊天必须保留角色和用户身份副本")
        _require(characters[cid]["id"] in initial, "聊天角色必须保留一份初始状态")
        rounds = sorted((row for row in tables["rounds"] if row["chat_id"] == cid), key=lambda row: row["round_no"])
        _require([row["round_no"] for row in rounds] == list(range(1, len(rounds) + 1)),
                 "聊天回合必须从 1 开始连续编号")
        by_id = {row["id"]: row for row in rounds}
        for index, record in enumerate(rounds):
            step = record["archive_step"]
            has_state = record["id"] in states
            has_summary = record["summary"] is not None
            has_decision = record["episode_required"] is not None
            has_episode = record["id"] in episodes_by_creator
            _require(index == len(rounds) - 1 or step == "complete", "只有最新回合可以尚未归档完成")
            _require(has_state == (step != "state_update"), "回合状态与归档步骤不一致")
            _require(has_summary == (step in ("episode_decision", "episode_summary", "complete")),
                     "回合摘要与归档步骤不一致")
            _require(has_decision == (step in ("episode_summary", "complete")), "情节判定与归档步骤不一致")
            _require(has_episode == (step == "complete" and record["episode_required"] is True),
                     "情节结果与产生回合的归档步骤不一致")

        def selected(start_id, end_id, creator=None):
            start, end = by_id.get(start_id), by_id.get(end_id)
            _require(start is not None and end is not None, "情节范围端点必须属于当前聊天")
            _require(start["round_no"] <= end["round_no"], "情节范围必须正向")
            if creator is not None:
                _require(end["round_no"] < creator["round_no"], "情节范围必须截止于产生回合之前")
            covered = [row for row in rounds if start["round_no"] <= row["round_no"] <= end["round_no"]]
            _require(all(row["archive_step"] == "complete" for row in covered), "情节只能覆盖已完成归档的回合")
            return start["round_no"], end["round_no"]

        episodes = sorted((row for row in tables["episodes"] if row["chat_id"] == cid),
                          key=lambda row: by_id[row["start_round_id"]]["round_no"])
        next_unrepresented = 1
        previous_creator_no = 0
        for episode in episodes:
            creator = by_id.get(episode["created_by_round_id"])
            if episode["created_by_round_id"] is not None:
                _require(creator is not None, "情节产生回合必须属于当前聊天")
                _require(creator["archive_step"] == "complete" and creator["episode_required"] is True,
                         "已保存情节必须对应已完成且需要情节的产生回合")
                _require((episode["start_round_id"], episode["end_round_id"]) ==
                         (creator["episode_start_round_id"], creator["episode_end_round_id"]),
                         "情节范围必须与产生回合保存的判定范围一致")
                _require(creator["round_no"] > previous_creator_no, "情节产生回合顺序必须与覆盖顺序一致")
                previous_creator_no = creator["round_no"]
            start_no, end_no = selected(episode["start_round_id"], episode["end_round_id"], creator)
            _require(start_no == next_unrepresented, "情节必须从最早未归纳回合开始，不得重复覆盖或跳过历史")
            next_unrepresented = end_no + 1
        if rounds and rounds[-1]["archive_step"] == "episode_summary":
            creator = rounds[-1]
            start_no, _ = selected(creator["episode_start_round_id"], creator["episode_end_round_id"], creator)
            _require(start_no == next_unrepresented, "待生成情节必须从最早未归纳回合开始")
