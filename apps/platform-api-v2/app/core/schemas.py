from pydantic import BaseModel, ConfigDict


class AckResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    ok: bool = True
