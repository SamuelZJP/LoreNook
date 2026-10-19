"""Strict request contracts and explicit PATCH semantics."""

from typing import Annotated, ClassVar

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Name = Annotated[str, StringConstraints(min_length=1, pattern=r"\S")]
NonnegativeInt = Annotated[int, Field(ge=0)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True, strict=True)


class PatchContract(Contract):
    nullable_fields: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="after")
    def reject_explicit_nulls(self):
        for name in self.model_fields_set - self.nullable_fields:
            if getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null; omit it to leave it unchanged")
        return self
