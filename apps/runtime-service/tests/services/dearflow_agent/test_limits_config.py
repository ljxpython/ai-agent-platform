import os
from unittest.mock import patch

from runtime_service.services.dearflow_agent.modes import MODES, resolve_mode


def test_modes_default_values_elevated():
    """验证各模式基础默认阈值已提升至安全且合理的区间"""
    assert MODES["standard"].tool_limit >= 100
    assert MODES["standard"].model_limit >= 50
    assert MODES["pro"].tool_limit >= 200
    assert MODES["ultra"].tool_limit >= 500


def test_env_limits_override():
    """验证通过环境变量可灵活覆盖限额"""
    with patch.dict(
        os.environ,
        {
            "AGENT_TOOL_CALL_LIMIT_PER_RUN": "250",
            "AGENT_TOOL_CALL_LIMIT_PER_THREAD": "2000",
            "AGENT_MODEL_CALL_LIMIT_PER_RUN": "120",
            "AGENT_MODEL_CALL_LIMIT_PER_THREAD": "800",
        },
    ):
        from runtime_service.services.dearflow_agent.agent import _get_env_limit

        assert _get_env_limit("AGENT_TOOL_CALL_LIMIT_PER_RUN", 100) == 250
        assert _get_env_limit("AGENT_TOOL_CALL_LIMIT_PER_THREAD", 1000) == 2000
        assert _get_env_limit("AGENT_MODEL_CALL_LIMIT_PER_RUN", 50) == 120
        assert _get_env_limit("AGENT_MODEL_CALL_LIMIT_PER_THREAD", 500) == 800


def test_env_limits_invalid_fallback():
    """验证非法输入自动安全回退"""
    with patch.dict(
        os.environ,
        {
            "AGENT_TOOL_CALL_LIMIT_PER_RUN": "invalid_number",
            "AGENT_TOOL_CALL_LIMIT_PER_THREAD": "-5",
        },
    ):
        from runtime_service.services.dearflow_agent.agent import _get_env_limit

        assert _get_env_limit("AGENT_TOOL_CALL_LIMIT_PER_RUN", 100) == 100
        assert _get_env_limit("AGENT_TOOL_CALL_LIMIT_PER_THREAD", 1000) == 1000
