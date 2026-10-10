"""Export the implemented completion API schema and validate real frontend examples."""

import argparse
import json
from pathlib import Path

from fastapi import FastAPI

from platform_api.modules.runtime_gateway.domain.completion import (
    ReadCompletion,
    RunCompletion,
    RunNotifications,
)
from platform_api.modules.runtime_gateway.presentation.completion_http import router


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--contract-pack", type=Path, required=True)
    parser.add_argument("--http-matrix", type=Path, required=True)
    args = parser.parse_args()
    pack = json.loads(args.contract_pack.read_text())
    for value in pack["history"]:
        RunCompletion.model_validate(value)
    RunNotifications.model_validate(pack["feed"])
    ReadCompletion.model_validate(pack["read"])
    matrix = json.loads(args.http_matrix.read_text())
    for response in matrix["responses"]:
        assert response["cache_control"] == "private, no-store"
        if response["status_code"] == 200:
            model = (
                RunCompletion
                if response["path"].endswith("/completion")
                else ReadCompletion
                if response["path"].endswith("/read")
                else RunNotifications
            )
            model.model_validate(response["body"])
        else:
            assert response["body"]["error"]["code"]
    app = FastAPI(title="Run Completion API", version="1")
    app.include_router(router)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "openapi.json").write_text(json.dumps(app.openapi(), indent=2))
    (args.output_dir / "real-responses.json").write_text(json.dumps(pack, indent=2))
    (args.output_dir / "http-matrix.json").write_text(json.dumps(matrix, indent=2))
    print("Validated completion schemas and real response examples exported")


if __name__ == "__main__":
    main()
