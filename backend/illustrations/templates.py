"""Prompt templates: Jinja2 text that turns a round into the request for the image-prompt model.

Each image workflow owns its template, because models differ in what they want (natural language,
tags, a mix, or edit instructions for image-to-image). The output contract is appended by the code,
so a template can't lose it.
"""

import yaml
from jinja2 import StrictUndefined, TemplateSyntaxError

from backend.illustrations.errors import IllustrationError
from backend.modules.definitions.renderer import DefinitionEnvironment

MAX_OUTPUT_CHARS = 1_000_000

SYSTEM = "你是插图提示词助手。根据角色扮演的当前回合，选出最适合作为插图的一个画面，按要求写出提示词。只输出一个 JSON 对象。"

_CONTEXT = """## 角色设定
{% for item in definitions.character %}{{ item }}

{% else %}（无）

{% endfor %}## 用户角色设定
{% for item in definitions.user %}{{ item }}

{% else %}（无）

{% endfor %}## 当前状态（本回合结束时，YAML）
{{ state_yaml }}
## 本回合摘要
{{ round.summary or '（无）' }}

## 本回合内容
用户输入：{{ round.user_input }}
AI正文：{{ round.content }}
"""

_OTHERS = """{% if others %}## 其他人物（除非本回合确实需要，否则不要入画）
{% for person in others %}- {{ person.name }}{% if person.appearance %}：{{ person.appearance }}{% endif %}
{% endfor %}
{% endif %}"""

TEXT_TO_IMAGE = """## 提示词要求
prompt：英文 danbooru 风格标签，逗号分隔。先写人物数量、外貌、衣着、动作、表情，再写场景、光线和镜头。
negative_prompt：英文标签，写需要避免的内容，例如 lowres, bad hands, extra fingers。

## 主要人物（画面以这些人为中心，人数越少效果越好）
{% for person in focus %}- {{ person.name }}：{{ person.appearance or '（没有外貌描述，依据设定）' }}
{% endfor %}
""" + _OTHERS + _CONTEXT + """
## 任务
选取本回合最具代表性、最适合入画的一个瞬间，写出主要人物的外貌、衣着、姿态、表情，以及场景、时间、光线和氛围。外貌以上面的描述和设定为准，不确定的细节不要编造。"""

IMAGE_TO_IMAGE = """## 提示词要求
人物外貌由参考图决定，不要描述五官、发型等外貌细节。
prompt：用英文自然语言写一段话，说明参考图中的人物正在做什么：动作、表情、衣着变化、场景、光线和镜头。

## 主要人物（按顺序对应参考图）
{% for person in focus %}{{ loop.index }}. {{ person.name }}
{% endfor %}
""" + _OTHERS + _CONTEXT + """
## 任务
选取本回合最具代表性、最适合入画的一个瞬间，写出参考图中的人物在这一瞬间的动作、表情和所处的场景。不确定的细节不要编造。"""

_environment = DefinitionEnvironment(undefined=StrictUndefined, autoescape=False, keep_trailing_newline=True)


def default_template(has_image_inputs: bool) -> str:
    return IMAGE_TO_IMAGE if has_image_inputs else TEXT_TO_IMAGE


def validate_template(source: str) -> str:
    try:
        _environment.parse(source)
    except TemplateSyntaxError as error:
        raise IllustrationError(f"提示词模板第 {error.lineno} 行有语法错误：{error.message}") from None
    return source


def _output_contract(fields: list[str]) -> str:
    names = "、".join(f'"{name}"' for name in fields)
    return (f"\n\n## 输出格式\n只输出一个 JSON 对象，恰好包含这些字符串字段：{names}。"
            "不输出解释、Markdown 代码围栏或其他文字。")


def render_prompt(source: str, fields: list[str], variables: dict) -> str:
    """`variables` is documented by the template editor; see jobs.template_variables."""
    variables = {**variables, "state_yaml": yaml.safe_dump(variables["state"], allow_unicode=True, sort_keys=False),
                 "fields": fields}
    try:
        parts, size = [], 0
        for part in _environment.from_string(source).generate(**variables):
            size += len(part)
            if size > MAX_OUTPUT_CHARS:
                raise ValueError(f"输出超过 {MAX_OUTPUT_CHARS} 字符")
            parts.append(part)
    except Exception as error:
        raise IllustrationError(f"提示词模板错误：{error}") from error
    return "".join(parts).rstrip() + _output_contract(fields)
