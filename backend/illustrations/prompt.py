"""What a workflow receives from LoreNook: reference images and the prompt text that describes the round.

Turning this into an image prompt is the workflow's job, so the text only states facts.
"""

import yaml

from backend.illustrations.errors import IllustrationError
from backend.illustrations.schemas import IllustrationContext, Subject
from backend.shared.content import extract_content
from backend.shared.errors import StateUpdateError

MAX_IMAGES = 8
AUTO_FOCUS = "（未指定。请根据剧情内容自行判断本画面的中心人物。）"


def reference_images(people: list[Subject]) -> list[str]:
    """Distinct media names in the given order, so main characters survive the limit."""
    return list(dict.fromkeys(person.reference_image for person in people if person.reference_image))[:MAX_IMAGES]


def _person(person: Subject, images: list[str]) -> str | None:
    lines = []
    if person.reference_image in images:
        lines.append(f"参考图：图 {images.index(person.reference_image) + 1}")
    if person.appearance.strip():
        lines.append(person.appearance.strip())
    return "\n".join([f"<{person.name}>", *lines, f"</{person.name}>"]) if lines else None


def render_prompt(context: IllustrationContext, images: list[str]) -> str:
    try:
        content = extract_content(context.ai_output)
    except StateUpdateError as error:
        raise IllustrationError(str(error)) from error
    people = [text for person in [*context.focus, *context.others] if (text := _person(person, images))]
    state = yaml.safe_dump(context.state, allow_unicode=True, sort_keys=False).rstrip()
    return f"""## 用户输入
{context.user_input}

## 剧情内容
{content}

## 状态信息
{state}

## 人物外貌
{chr(10).join(people) or '（无）'}

## 中心人物
{'、'.join(person.name for person in context.focus) or AUTO_FOCUS}

请按系统说明从以上上下文选定画面瞬间，直接输出提示词正文。"""
