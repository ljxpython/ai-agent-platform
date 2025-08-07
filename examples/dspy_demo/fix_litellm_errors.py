"""
修复 LiteLLM 日志错误的工具脚本

这个脚本提供了多种方法来解决 LiteLLM 与 Python 3.12 的兼容性问题
"""

import logging
import os
import sys
import warnings
from contextlib import contextmanager


def setup_clean_environment():
    """设置干净的运行环境，禁用 LiteLLM 错误日志"""

    # 方法1: 设置环境变量
    os.environ["LITELLM_LOG"] = "ERROR"
    os.environ["LITELLM_LOG_LEVEL"] = "ERROR"
    os.environ["LITELLM_DROP_PARAMS"] = "true"

    # 方法2: 配置日志级别
    logging.getLogger("litellm").setLevel(logging.CRITICAL)
    logging.getLogger("LiteLLM").setLevel(logging.CRITICAL)
    logging.getLogger("litellm.litellm_core_utils").setLevel(logging.CRITICAL)

    # 方法3: 禁用特定警告
    warnings.filterwarnings("ignore", category=UserWarning, module="litellm")
    warnings.filterwarnings("ignore", message=".*__annotations__.*")

    print("✅ LiteLLM 日志错误已被禁用")


@contextmanager
def suppress_litellm_errors():
    """上下文管理器：临时禁用 LiteLLM 错误"""

    # 保存原始日志级别
    litellm_logger = logging.getLogger("litellm")
    original_level = litellm_logger.level

    try:
        # 临时设置为 CRITICAL
        litellm_logger.setLevel(logging.CRITICAL)

        # 临时禁用警告
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            yield

    finally:
        # 恢复原始设置
        litellm_logger.setLevel(original_level)


def patch_litellm_annotations():
    """尝试修补 LiteLLM 的 __annotations__ 问题"""

    try:
        import litellm
        from litellm.litellm_core_utils.model_param_helper import ModelParamHelper

        # 尝试修补问题方法
        original_method = ModelParamHelper._get_litellm_supported_transcription_kwargs

        def patched_method():
            """修补后的方法，避免 __annotations__ 错误"""
            try:
                return original_method()
            except AttributeError:
                # 如果出现 __annotations__ 错误，返回空集合
                return set()

        ModelParamHelper._get_litellm_supported_transcription_kwargs = staticmethod(
            patched_method
        )
        print("✅ LiteLLM __annotations__ 问题已修补")

    except Exception as e:
        print(f"⚠️ 无法修补 LiteLLM: {e}")


def create_dspy_config_with_error_suppression():
    """创建带有错误抑制的 DSPy 配置"""

    def configure_dspy_clean(api_key, base_url, model="deepseek-chat"):
        """配置 DSPy 并抑制错误"""

        import dspy

        # 设置干净环境
        setup_clean_environment()

        # 配置模型
        lm = dspy.LM(
            model,
            api_key=api_key,
            api_base=base_url,
            temperature=0.1,
            cache=False,  # 禁用缓存避免日志问题
        )

        dspy.configure(lm=lm)
        print(f"✅ DSPy 已配置: {model}")

        return lm

    return configure_dspy_clean


def run_clean_dspy_example():
    """运行一个干净的 DSPy 示例"""

    print("🧪 测试干净的 DSPy 运行环境")

    # 设置环境
    setup_clean_environment()

    try:
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        import dspy
        from conf.config import settings
        from dspy.teleprompt import BootstrapFewShot

        # 配置模型
        configure_dspy = create_dspy_config_with_error_suppression()
        lm = configure_dspy(settings.aimodel.api_key, settings.aimodel.base_url)

        # 简单测试
        class SimpleSignature(dspy.Signature):
            """简单的文本处理任务"""

            text = dspy.InputField(desc="输入文本")
            result = dspy.OutputField(desc="处理结果")

        class SimpleModule(dspy.Module):
            def __init__(self):
                super().__init__()
                self.process = dspy.ChainOfThought(SimpleSignature)

            def forward(self, text):
                return self.process(text=text)

        # 测试基础功能
        module = SimpleModule()

        with suppress_litellm_errors():
            result = module(text="测试文本")
            print(f"✅ 基础功能测试成功: {result.result}")

        # 测试优化功能
        train_data = [dspy.Example(text="输入", result="输出").with_inputs("text")]

        def simple_metric(example, pred, trace=None):
            return 1.0 if pred.result else 0.0

        teleprompter = BootstrapFewShot(
            metric=simple_metric,
            max_bootstrapped_demos=1,
            max_labeled_demos=1,
            max_rounds=1,
        )

        with suppress_litellm_errors():
            optimized = teleprompter.compile(module, trainset=train_data)
            print("✅ 优化功能测试成功")

        return True

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


def main():
    """主函数：演示所有修复方法"""

    print("🔧 LiteLLM 错误修复工具")
    print("=" * 40)

    print("\n1. 设置干净环境...")
    setup_clean_environment()

    print("\n2. 尝试修补 __annotations__ 问题...")
    patch_litellm_annotations()

    print("\n3. 测试修复效果...")
    success = run_clean_dspy_example()

    if success:
        print("\n🎉 修复成功！现在可以使用以下方式运行 DSPy:")
        print("   python examples/dspy_demo/prompt_optimization_clean.py")
    else:
        print("\n❌ 修复失败，建议:")
        print("   1. 降级 LiteLLM 版本: pip install litellm==1.30.0")
        print("   2. 或使用 Python 3.11 代替 Python 3.12")


if __name__ == "__main__":
    main()
