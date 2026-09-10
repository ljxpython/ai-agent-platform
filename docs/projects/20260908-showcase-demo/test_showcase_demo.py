#!/usr/bin/env python3
"""Test showcase_demo agent initialization"""

import asyncio
import sys
from pathlib import Path

# Add runtime-service to path
sys.path.insert(0, str(Path(__file__).parent / "apps" / "runtime-service" / "src"))

from runtime_service.services.demo.showcase_demo.agent import get_agent


async def test_showcase_demo():
    """Test showcase_demo agent with local auth"""

    # 模拟本地测试配置
    config = {
        "configurable": {
            "_runtime_test_local_auth": True,
            "thread_id": "test-thread-123",
        }
    }

    try:
        print("🔧 Testing showcase_demo agent initialization...")
        agent = await get_agent(config)
        print("✅ Agent created successfully!")
        print(f"   Graph type: {type(agent).__name__}")

        # 检查工具
        if hasattr(agent, 'nodes'):
            print(f"   Nodes: {list(agent.nodes.keys())}")

        return True

    except Exception as e:
        print(f"❌ Agent creation failed:")
        print(f"   Error type: {type(e).__name__}")
        print(f"   Error message: {e}")

        import traceback
        print("\n📋 Full traceback:")
        traceback.print_exc()

        return False


if __name__ == "__main__":
    result = asyncio.run(test_showcase_demo())
    sys.exit(0 if result else 1)
