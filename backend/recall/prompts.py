"""The two recall passes. Plots are judged loosely, summaries strictly; the instruction outranks both.
Each pass states its limit; judge.py enforces it by keeping the first ids, so the order matters."""

SYSTEM = "你是长篇故事的记忆召回器。你不续写故事，只判断哪些记忆需要展开。没有需要展开的记忆时，返回空列表是正确的结果。"

SHARED_RULES = (
    "## 判断依据\n"
    "“回忆依据”是最近的完整回合和用户的最新输入，请根据它的全部内容判断。\n"
    "“临时指令”是用户对这一次写作的直接要求，优先级最高，范围也最广："
    "凡是指令提到、指向或需要依据的记忆，无条件选中，不受下面判断标准的限制，并排在结果最前面。\n"
    "没有被指令涉及的候选，按下面的标准判断。\n\n"
)

PASSES = {
    "episode": (
        "## 本次任务：判断哪些情节需要展开\n"
        "候选是过去的情节。选中后，它会展开为其下各回合的摘要。最多选择 {limit} 个情节。\n"
        "选出可能与接下来的剧情发展相关的情节：回忆依据提到或回到其中的事件，延续其中的约定、悬念或关系变化，"
        "再次用到其中的特定物件或人物过往。只要存在具体关联就可以选，漏选的情节这次无法再被展开。\n"
        "仅仅因为人物或地点相同不算关联，主要人物几乎出现在每段记忆里。\n\n"
        "## 示例\n"
        "- 输入“继续走吧”，场景平稳延续，没有回到过去：不选。\n"
        "- 某情节里甲乙同行，而当前甲乙在商量晚饭吃什么：不选，只是人物相同。\n"
        "- 输入“她摸了摸那枚戒指”，某情节写到甲赠戒：选。\n"
        "- 指令“让她想起第一次见面”，输入本身没提：选第一次见面所在的情节。\n\n"
    ),
    "summary": (
        "## 本次任务：判断哪些摘要需要展开\n"
        "候选是过去回合的摘要。选中后，它会展开为该回合的完整原文。最多选择 {limit} 个摘要。\n"
        "选出与接下来的剧情发展直接相关、并且写好下一段需要原文细节的摘要：原话、约定的确切内容、"
        "具体的外貌或物件描写、事件的具体经过。标准比情节严格得多。\n"
        "相关但摘要已经够用的不选。拿不准时不选。\n\n"
        "## 示例\n"
        "- 输入“她摸了摸那枚戒指”，摘要写了甲把银戒送给乙，下一段只需提到有这回事：不选。\n"
        "- 输入“她念出戒指内侧刻的字”，摘要没写刻了什么：选。\n"
        "- 输入“你当时到底是怎么说的？”，摘要只概括了那次对话：选。\n"
        "- 指令“让她复述第一次见面时的原话”，输入本身没提：选那个回合。\n\n"
    ),
}


def render_prompt(context, stage: str, candidates: list[str], limit: int) -> str:
    basis = "\n".join(context.basis_rounds)
    return (
        f"## 人物\n角色：{context.character_name}\n用户角色：{context.user_name}\n\n"
        f"## 回忆依据\n{basis + chr(10) if basis else ''}"
        f"最新输入：{context.user_input.strip() or '（空，表示顺着当前情节继续）'}\n\n"
        f"## 临时指令\n{context.instruction.strip() or '（无）'}\n\n"
        f"## 候选（从早到晚）\n" + "\n".join(candidates) + "\n\n"
        f"{SHARED_RULES}{PASSES[stage].format(limit=limit)}"
        "## 输出\n只输出一个 JSON 对象，先写简短理由，再写结论：\n"
        '{"reason": "不超过100字", "ids": ["候选编号"]}\n'
        f"ids 只能使用候选方括号里的编号，不带方括号，最多 {limit} 个，按重要性从高到低排列。超出上限的部分会被直接丢弃。"
    )
