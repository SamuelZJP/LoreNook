"""Render text definitions without exposing application objects or changing sources."""

import re
from collections.abc import Sequence
from copy import deepcopy
from traceback import extract_tb

from jinja2 import StrictUndefined
from jinja2.sandbox import ImmutableSandboxedEnvironment
from pydantic import JsonValue

from backend.schemas.catalog import DefinitionRead
from backend.schemas.definitions import ResolvedDefinition, ResolvedDefinitions
from backend.shared.errors import DefinitionTemplateError


NAME_PLACEHOLDER = re.compile(r"\{\{\s*(user|char)\s*\}\}", re.IGNORECASE)


def substitute_names(text: str, *, user_name: str, character_name: str) -> str:
    """Replace {{user}} / {{char}} in plain text; everything else is left as written."""
    names = {"user": user_name, "char": character_name}
    return NAME_PLACEHOLDER.sub(lambda match: names[match.group(1).lower()], text)


class DefinitionEnvironment(ImmutableSandboxedEnvironment):
    def getitem(self, obj, argument):
        # Explicit JSON key lookup must not fall back to dict methods for missing keys.
        if isinstance(obj, dict):
            try:
                return obj[argument]
            except (KeyError, TypeError):
                return self.undefined(obj=obj, name=argument)
        return super().getitem(obj, argument)


class DefinitionRenderer:
    def __init__(self, max_output_chars: int = 1_000_000):
        if max_output_chars <= 0:
            raise ValueError("max_output_chars must be positive")
        self.max_output_chars = max_output_chars
        self.environment = DefinitionEnvironment(
            undefined=StrictUndefined, autoescape=False, keep_trailing_newline=True,
        )

    def _render(self, definition: DefinitionRead, state: dict[str, JsonValue], user_name: str,
                character_name: str) -> str:
        if not definition.has_template:
            return substitute_names(definition.content, user_name=user_name, character_name=character_name)
        try:
            # Templates use the same {{user}} / {{char}} spelling as plain text, so the names are variables.
            template = self.environment.from_string(NAME_PLACEHOLDER.sub(
                lambda match: "{{" + match.group(1).lower() + "}}", definition.content))
            parts = []
            size = 0
            for part in template.generate(state=state, user=user_name, char=character_name):
                size += len(part)
                if size > self.max_output_chars:
                    raise ValueError(f"模板输出超过 {self.max_output_chars} 字符")
                parts.append(part)
            return "".join(parts)
        except Exception as error:
            line = getattr(error, "lineno", None)
            if line is None:
                frames = [frame for frame in extract_tb(error.__traceback__) if frame.filename == "<template>"]
                line = frames[-1].lineno if frames else None
            raise DefinitionTemplateError(definition.id, str(error), line) from error

    def resolve(
        self, character_definitions: Sequence[DefinitionRead], user_definitions: Sequence[DefinitionRead],
        state: dict[str, JsonValue], *, user_name: str, character_name: str,
    ) -> ResolvedDefinitions:
        # Every template sees the same detached snapshot; the sandbox blocks mutation.
        state_copy = deepcopy(state)

        def group(definitions):
            return [ResolvedDefinition(id=item.id, order=item.order, content=self._render(item, state_copy, user_name, character_name))
                    for item in sorted(definitions, key=lambda item: (item.order, item.id)) if item.enabled]

        return ResolvedDefinitions(
            character_definitions=group(character_definitions), user_definitions=group(user_definitions),
        )
