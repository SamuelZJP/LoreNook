"""Image-prompt request: the round as source material, the workflow's instructions as the style guide."""

import yaml

from backend.schemas.definitions import ResolvedDefinitions
from backend.schemas.illustrations import IllustrationContext

SYSTEM = ("你是插图提示词助手。根据角色扮演的当前回合，选出最适合作为插图的一个画面，"
          "按图像工作流的要求写出提示词。只输出一个 JSON 对象。")


def _definitions(items) -> str:
    return "\n\n".join(item.content for item in items) or "（无）"


def render_prompt(context: IllustrationContext, content: str, definitions: ResolvedDefinitions,
                  instructions: str) -> str:
    fields = "、".join(f'"{name}"' for name in context.fields)
    return (
        f"## 图像工作流要求\n{instructions.strip() or '（无额外要求）'}\n\n"
        f"## 输出格式\n只输出一个 JSON 对象，恰好包含这些字符串字段：{fields}。"
        "字段含义以上面的工作流要求为准；没有说明的字段按字段名理解。"
        "不输出解释、Markdown 代码围栏或其他文字。\n\n"
        f"## 人物\n角色：{context.character_name}\n用户角色（\"我\"）：{context.user_name}\n\n"
        f"## 角色设定\n{_definitions(definitions.character_definitions)}\n\n"
        f"## 用户角色设定\n{_definitions(definitions.user_definitions)}\n\n"
        f"## 当前状态（本回合结束时，YAML）\n"
        f"{yaml.safe_dump(context.state, allow_unicode=True, sort_keys=False)}\n"
        f"## 本回合摘要\n{context.summary or '（无）'}\n\n"
        f"## 本回合内容\n用户输入：{context.user_input}\nAI正文：{content}\n\n"
        "## 任务\n选取本回合中最具代表性、最适合入画的一个瞬间，描述其中人物的外貌、衣着、姿态、表情，"
        "以及场景、时间、光线和氛围。外貌以设定和状态为准，不确定的细节不要编造。"
    )
