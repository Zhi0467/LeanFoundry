"""Private Pydantic defaults shared by public schemas."""

from pydantic import BaseModel, ConfigDict


class LeanFoundryModel(BaseModel):
    """Base model for stable, strict LeanFoundry wire schemas."""

    model_config = ConfigDict(extra="forbid", frozen=True)
