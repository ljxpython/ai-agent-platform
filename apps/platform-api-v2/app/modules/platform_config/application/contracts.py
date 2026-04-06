from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class UpdateFeatureFlagsCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    feature_flags: dict[str, bool] = Field(default_factory=dict)

