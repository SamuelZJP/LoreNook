"""Round memory prompt: explicit scene header and concise factual narration."""

import yaml

SYSTEM = "你是一个记忆管理助手。请根据提供的内容生成简洁、准确、可复用的摘要。"


def render_prompt(context, content: str) -> str:
    return (
        f"## 上下文\n角色：{context.character_name}\n"
        f"主角、\"我\"、用户角色的名称为{context.user_name}。\n\n"
        f"## 当前状态（本回合更新后的状态，YAML）\n"
        f"{yaml.safe_dump(context.state, allow_unicode=True, sort_keys=False)}\n"
        f"## 最近回合摘要（仅理解衔接，不重复概括）\n{chr(10).join(context.summaries) or '（无）'}\n\n"
        f"## 待摘要内容\n用户输入：{context.user_input}\nAI回复：{content}\n\n"
        "## 任务\n请生成一段摘要，保留关键情节、人物互动、状态变化和重要事实，避免冗余。\n"
        "若当前状态给出了日期、时间、地点，请在摘要中以指定格式表现这些信息；缺失的信息不得编造。\n"
        "区分已经发生的事实与计划、愿望、台词中的猜测，不把后者写成既成事实。\n\n"
        "## 摘要格式\n年月日—时分—地点\n"
        "用约150字概括本回合的具体事件，忠实记录关键对白片段、情报、行为和情感变化。"
        "以第三人称直接呈现，不加以解读，不添加评价、推测、预演或结尾总结。\n"
        "原文较短时据实简写，不为凑字添加事实；正文有效字数（文字和数字，不计标点、空白和独立时间地点头）"
        "至少达到待摘要用户输入与AI正文有效字数的20%（向上取整），该下限最多75字。\n"
        "只输出上述摘要文本，不输出思考过程、工具调用、标签、JSON或Markdown代码围栏。"
        "摘要去除首尾空白后必须以至少两位ASCII数字（0-9）开头，以日期起笔，不添加介绍语。"
    )
