from fastapi import FastAPI
from starlette.testclient import TestClient

from runtime_service.runtime.errors import RuntimePrivacyError
from runtime_service.webapp import app


def test_privacy_http_error_keeps_fixed_contract_without_exception_details():
    application = FastAPI(exception_handlers=app.exception_handlers)

    @application.post("/blocked")
    async def blocked():
        raise RuntimePrivacyError("PRIVATE_CANARY alice@example.test")

    response = TestClient(application).post("/blocked")
    assert response.status_code == 500
    assert response.json() == {
        "detail": {
            "code": "runtime.privacy.redaction_failed",
            "message": "隐私保护处理失败，本次模型请求未发送。",
        }
    }
