"""Episode memory prompt: bounded source material, bridge, title and summary."""

import yaml

from backend.shared.content import extract_content

SYSTEM = "你是一个记忆管理助手。请为指定连续回合生成事件标题和摘要。"


def render_prompt(context) -> str:
    sections = [
        "你是一个专业的剧情摘要生成器。现在请以第三人称的旁观者视角为下一组对话回合生成一个事件摘要。",
        f'请注意，自机主角为{context.user_name}，因此剧情文本中提到的"我"均为{context.user_name}。',
        f"## 上下文\n角色：{context.character_name}\n用户身份：{context.user_name}\n"
        "最新参考状态为本次范围最后一回合结束时的状态，不将其倒用于较早事件：\n"
        + yaml.safe_dump(context.rounds[-1].state, allow_unicode=True, sort_keys=False),
        f"## 选定范围\n第 {context.rounds[0].round_no}—{context.rounds[-1].round_no} 回合（包含两端）",
    ]
    if context.bridge is not None:
        bridge = context.bridge
        sections.append(
            "## 已归档的最后一个对话回合（跨事件边界的桥接上下文）\n"
            f"[回合{bridge.round_no}摘要] {bridge.summary}\n"
            f"[回合{bridge.round_no}用户] {bridge.user_input}\n"
            f"[回合{bridge.round_no}AI] {extract_content(bridge.ai_output)}\n"
            "这个回合位于上一事件的结尾。只将其中与当前事件直接相关的衔接信息当作参考，"
            "不要重复概括上一事件，也不要扩张本次覆盖范围。"
        )
    sections.append("## 事件包含的对话回合")
    if context.first_message:
        first = extract_content(context.first_message) if "<content>" in context.first_message else context.first_message
        sections.append(f"[首条消息]\n{first}")
    for record in context.rounds:
        sections.append(
            f"<回合{record.round_no}>\n[回合{record.round_no}摘要]\n{record.summary}\n"
            f"[回合{record.round_no}用户]\n{record.user_input}\n"
            f"[回合{record.round_no}AI]\n{extract_content(record.ai_output)}\n"
            f"[回合{record.round_no}结束状态（YAML）]\n"
            f"{yaml.safe_dump(record.state, allow_unicode=True, sort_keys=False)}</回合{record.round_no}>"
        )
    sections.append(
        "## 任务\n1. 为这组回合生成一个简短的事件标题（不超过20字），体现事件最关键的情节或冲突。\n"
        "2. 生成详略得当的事件摘要，包含关键情节，可保留重要细节。\n\n"
        "额外要求：\n- 仅概括选定范围的事件；边界附近属于下一事件的开头不写入当前事件摘要。"
        "桥接回合仅作衔接参考，不重复归纳其属于上一事件的内容。\n"
        "- 保留关键对白、情报、行为、人物互动与结果，区分计划、猜测和已经发生的事实。\n"
        "- 日期、时间和地点依据各回合对应状态；状态缺失的信息不编造，不把较晚状态倒用于较早事件。\n"
        "- 以第三人称旁观者视角描述，不在末尾添加评价、推测、预演或总结。\n\n"
        "## 事件摘要格式\n起始时间(yyyy/mm/dd)-终止时间(yyyy/mm/dd)—地点\n"
        "用约200~300字的一段话概括上述对话回合；地点变化时记录关键地点。\n\n"
        '## 输出格式\n仅输出一个JSON对象：\n{"title": "事件标题", "summary": "事件摘要内容"}\n'
        "不输出思考过程、工具调用或Markdown代码围栏。"
    )
    return "\n\n".join(sections)
