import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import RuntimeModelEditor from "./RuntimeModelEditor.vue";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseIcon from "@/components/base/BaseIcon.vue";
import BaseSelect from "@/components/base/BaseSelect.vue";
import type { RuntimeModelItem } from "@/types/management";

describe("RuntimeModelEditor", () => {
  function createWrapper(props: Record<string, unknown> = {}) {
    return mount(RuntimeModelEditor, {
      props: {
        editingModel: null,
        busy: false,
        ...props,
      },
      global: {
        components: {
          BaseButton,
          BaseIcon,
          BaseSelect,
        },
      },
    });
  }

  const mockModelWithPricing: RuntimeModelItem = {
    id: "model-1",
    display_name: "DeepSeek V3",
    provider: "deepseek",
    base_url: "https://api.deepseek.com/v1",
    protocol: "openai-compatible",
    model: "deepseek-chat",
    enabled: true,
    credential_configured: true,
    pricing: {
      currency: "USD",
      basis: "per_million_tokens",
      input: "2.0",
      output: "8.0",
      cache_read: "0.2",
      cache_write: null,
      cache_write_5m: null,
      cache_write_1h: null,
      version: "version-uuid-123",
      source: "configured_catalog",
      updated_at: "2026-10-07T08:00:00Z",
    },
  };

  it("renders standard provider presets and recommended models by default", () => {
    const wrapper = createWrapper();
    expect(wrapper.text()).toContain("添加标准提供方");
    expect(wrapper.text()).toContain("公有云提供商 (Provider)");
    expect(wrapper.text()).toContain("包含模型清单 (Model List)");

    // 默认提供商为 deepseek，推荐模型应包含 deepseek-chat 和 deepseek-reasoner
    const inputs = wrapper.findAll("input");
    const values = inputs.map(
      (input) => (input.element as HTMLInputElement).value,
    );
    expect(values).toContain("deepseek-chat");
    expect(values).toContain("deepseek-reasoner");
  });

  it("allows adding and removing model rows in standard mode", async () => {
    const wrapper = createWrapper();
    const addBtn = wrapper
      .findAll("button")
      .find((b) => b.text().includes("添加模型"));
    expect(addBtn).toBeDefined();

    // 初始有 2 行
    let trashButtons = wrapper.findAll('button[title="删除此模型"]');
    expect(trashButtons.length).toBe(2);

    // 点击添加一行
    await addBtn?.trigger("click");
    trashButtons = wrapper.findAll('button[title="删除此模型"]');
    expect(trashButtons.length).toBe(3);

    // 删除第 3 行
    await trashButtons[2].trigger("click");
    trashButtons = wrapper.findAll('button[title="删除此模型"]');
    expect(trashButtons.length).toBe(2);
  });

  it("validates required API key in standard mode", async () => {
    const wrapper = createWrapper();
    const submitBtn = wrapper
      .findAll("button")
      .find((b) => b.text().includes("批量添加标准模型"));
    await submitBtn?.trigger("click");

    // 提示需要 API Key
    expect(wrapper.text()).toContain("请输入该提供商的 API Key");
    expect(wrapper.emitted("submit")).toBeUndefined();
  });

  it("toggles password visibility with eye icon", async () => {
    const wrapper = createWrapper();
    const eyeBtn = wrapper
      .findAll("button")
      .find((b) => b.text().includes("显示"));
    expect(eyeBtn).toBeDefined();

    const apiKeyInput = wrapper.find('input[autocomplete="new-password"]');
    expect(apiKeyInput.attributes("type")).toBe("password");

    await eyeBtn?.trigger("click");
    expect(apiKeyInput.attributes("type")).toBe("text");
  });

  it("emits submit payload when valid in standard mode", async () => {
    const wrapper = createWrapper();
    const apiKeyInput = wrapper.find('input[autocomplete="new-password"]');
    await apiKeyInput.setValue("sk-test-123456");

    const submitBtn = wrapper
      .findAll("button")
      .find((b) => b.text().includes("批量添加标准模型"));
    await submitBtn?.trigger("click");

    const emitted = wrapper.emitted("submit");
    expect(emitted).toBeDefined();
    expect(emitted?.length).toBe(1);
    const payload = emitted?.[0][0] as Record<string, unknown>;
    expect(payload.isEdit).toBe(false);
    expect(payload.provider).toBe("deepseek");
    expect(payload.api_key).toBe("sk-test-123456");
    expect(Array.isArray(payload.models)).toBe(true);
    expect((payload.models as Array<unknown>).length).toBe(2);
  });

  it("supports switching to custom provider mode and validates route ID", async () => {
    const wrapper = createWrapper();
    const customTab = wrapper
      .findAll("button")
      .find((b) => b.text().includes("自定义提供方"));
    expect(customTab).toBeDefined();
    await customTab?.trigger("click");

    expect(wrapper.text()).toContain("添加自定义提供方");
    expect(wrapper.text()).toContain("Provider 标识 (Route ID)");
    expect(wrapper.text()).toContain("创建并接入自定义模型");

    const routeInput = wrapper.find(
      'input[placeholder="例如 my-vllm, company-gateway, ollama-local"]',
    );
    expect(routeInput.exists()).toBe(true);

    // 输入不合法 Route ID（大写字母/数字开头）
    await routeInput.setValue("123-bad-route");
    expect(wrapper.text()).toContain("Provider 标识必须以小写英文字母开头");

    // 点击提交应阻止并提示
    const submitBtn = wrapper
      .findAll("button")
      .find((b) => b.text().includes("创建并接入自定义模型"));
    await submitBtn?.trigger("click");
    expect(wrapper.emitted("submit")).toBeUndefined();
  });

  it("submits custom provider successfully with optional API key", async () => {
    const wrapper = createWrapper({ initialMode: "custom" });
    expect(wrapper.text()).toContain("添加自定义提供方");

    const routeInput = wrapper.find(
      'input[placeholder="例如 my-vllm, company-gateway, ollama-local"]',
    );
    await routeInput.setValue("company-vllm");

    const urlInput = wrapper.find(
      'input[placeholder="例如 http://192.168.1.100:8000/v1 或 https://gateway.company.com/v1"]',
    );
    await urlInput.setValue("http://192.168.1.100:8000/v1");

    const modelIdInput = wrapper.find(
      'input[placeholder="Model ID (必填)，例如 qwen2.5-72b-instruct"]',
    );
    await modelIdInput.setValue("qwen2.5-72b");

    const submitBtn = wrapper
      .findAll("button")
      .find((b) => b.text().includes("创建并接入自定义模型"));
    await submitBtn?.trigger("click");

    const emitted = wrapper.emitted("submit");
    expect(emitted).toBeDefined();
    const payload = emitted?.[0][0] as Record<string, unknown>;
    expect(payload.isEdit).toBe(false);
    expect(payload.provider).toBe("company-vllm");
    expect(payload.base_url).toBe("http://192.168.1.100:8000/v1");
    expect(payload.api_key).toBe(""); // API key 选填
    expect(payload.models).toEqual([{ id: "qwen2.5-72b", name: "" }]);
  });

  it("renders single model inputs in edit mode", async () => {
    const wrapper = createWrapper({
      editingModel: {
        id: "model-101",
        model: "gpt-4o",
        display_name: "GPT-4o Custom",
        provider: "openai",
        base_url: "https://api.openai.com/v1",
        protocol: "openai-compatible",
        enabled: true,
      },
    });

    expect(wrapper.text()).toContain("编辑模型配置");
    expect(wrapper.text()).toContain("保存修改");

    const modelIdInput = wrapper.find(
      'input[placeholder="例如 deepseek-chat, gpt-4o"]',
    );
    expect((modelIdInput.element as HTMLInputElement).value).toBe("gpt-4o");

    const submitBtn = wrapper
      .findAll("button")
      .find((b) => b.text().includes("保存修改"));
    await submitBtn?.trigger("click");

    const emitted = wrapper.emitted("submit");
    expect(emitted).toBeDefined();
    const payload = emitted?.[0][0] as Record<string, unknown>;
    expect(payload.isEdit).toBe(true);
    expect(payload.editingId).toBe("model-101");
    expect(payload.display_name).toBe("GPT-4o Custom");
    expect(payload.context_window_tokens).toBeNull();
  });

  it("supports configuring context_window_tokens in edit mode and emits positive integer", async () => {
    const wrapper = createWrapper({
      editingModel: {
        id: "model-102",
        model: "deepseek-chat",
        display_name: "DeepSeek V3",
        provider: "deepseek",
        base_url: "https://api.deepseek.com/v1",
        protocol: "openai-compatible",
        enabled: true,
        context_window_tokens: 65536,
      },
    });

    const tokenInput = wrapper.find(
      'input[placeholder="例如 128000 (正整数)"]',
    );
    expect((tokenInput.element as HTMLInputElement).value).toBe("65536");

    // 点击 128K 预设按钮
    const presetBtn = wrapper
      .findAll("button")
      .find((b) => b.text().includes("128K"));
    expect(presetBtn).toBeDefined();
    await presetBtn?.trigger("click");
    expect((tokenInput.element as HTMLInputElement).value).toBe("131072");

    const submitBtn = wrapper
      .findAll("button")
      .find((b) => b.text().includes("保存修改"));
    await submitBtn?.trigger("click");

    const emitted = wrapper.emitted("submit");
    expect(emitted).toBeDefined();
    const payload = emitted?.[0][0] as Record<string, unknown>;
    expect(payload.context_window_tokens).toBe(131072);
  });

  it("validates context_window_tokens must be positive integer in edit mode", async () => {
    const wrapper = createWrapper({
      editingModel: {
        id: "model-103",
        model: "deepseek-chat",
        display_name: "DeepSeek V3",
        provider: "deepseek",
        base_url: "https://api.deepseek.com/v1",
        protocol: "openai-compatible",
        enabled: true,
      },
    });

    const tokenInput = wrapper.find(
      'input[placeholder="例如 128000 (正整数)"]',
    );
    await tokenInput.setValue("0");

    const submitBtn = wrapper
      .findAll("button")
      .find((b) => b.text().includes("保存修改"));
    await submitBtn?.trigger("click");

    expect(wrapper.text()).toContain("上下文窗口容量必须为大于 0 的整数");
    expect(wrapper.emitted("submit")).toBeUndefined();
  });

  it("emits context_window_tokens as null when cleared in edit mode", async () => {
    const wrapper = createWrapper({
      editingModel: {
        id: "model-104",
        model: "deepseek-chat",
        display_name: "DeepSeek V3",
        provider: "deepseek",
        base_url: "https://api.deepseek.com/v1",
        protocol: "openai-compatible",
        enabled: true,
        context_window_tokens: 128000,
      },
    });

    const clearBtn = wrapper
      .findAll("button")
      .find((b) => b.text().includes("清除设置"));
    expect(clearBtn).toBeDefined();
    await clearBtn?.trigger("click");

    const tokenInput = wrapper.find(
      'input[placeholder="例如 128000 (正整数)"]',
    );
    expect((tokenInput.element as HTMLInputElement).value).toBe("");

    const submitBtn = wrapper
      .findAll("button")
      .find((b) => b.text().includes("保存修改"));
    await submitBtn?.trigger("click");

    const emitted = wrapper.emitted("submit");
    expect(emitted).toBeDefined();
    const payload = emitted?.[0][0] as Record<string, unknown>;
    expect(payload.context_window_tokens).toBeNull();
  });

  // ================= 费率 (Pricing) 专属测试 =================

  it("在编辑模式下展示模型费率卡片并填充已有定价", () => {
    const wrapper = createWrapper({
      editingModel: mockModelWithPricing,
      initialMode: "edit",
    });

    const pricingSection = wrapper.find(
      '[data-testid="model-pricing-section"]',
    );
    expect(pricingSection.exists()).toBe(true);
    expect(pricingSection.text()).toContain("version-uuid-123");
    expect(pricingSection.text()).toContain("模型费率配置");

    const inputRateField = pricingSection.find('input[placeholder="如 2.0"]');
    expect((inputRateField.element as HTMLInputElement).value).toBe("2.0");
  });

  it("新建模式下完全隐藏模型费率卡片，防止广播误解", () => {
    const wrapper = createWrapper({
      editingModel: null,
      initialMode: "standard",
    });

    const pricingSection = wrapper.find(
      '[data-testid="model-pricing-section"]',
    );
    expect(pricingSection.exists()).toBe(false);
  });

  it("编辑模式下若未改动价格，提交 payload 中 pricing 为 undefined (防误冲掉现有价格)", async () => {
    const wrapper = createWrapper({
      editingModel: mockModelWithPricing,
      initialMode: "edit",
    });

    // 仅修改 display_name
    const nameInput = wrapper
      .findAll("input")
      .find((i) => (i.element as HTMLInputElement).value === "DeepSeek V3");
    expect(nameInput).toBeDefined();
    await nameInput!.setValue("DeepSeek V3 Updated");

    // 点击提交
    const submitBtn = wrapper
      .findAll("button")
      .find((b) => b.text().includes("保存") || b.text().includes("更新"));
    expect(submitBtn).toBeDefined();
    await submitBtn!.trigger("click");

    const submitted = wrapper.emitted("submit");
    expect(submitted).toBeTruthy();
    const payload = submitted![0][0] as any;
    expect(payload.display_name).toBe("DeepSeek V3 Updated");
    expect(payload.pricingDirty).toBe(false);
    expect(payload.pricing).toBeUndefined();
  });

  it("点击清空费率配置后提交，pricing 为 null", async () => {
    const wrapper = createWrapper({
      editingModel: mockModelWithPricing,
      initialMode: "edit",
    });

    const clearBtn = wrapper.find('[data-testid="clear-pricing-btn"]');
    expect(clearBtn.exists()).toBe(true);
    await clearBtn.trigger("click");

    const submitBtn = wrapper
      .findAll("button")
      .find((b) => b.text().includes("保存") || b.text().includes("更新"));
    await submitBtn!.trigger("click");

    const submitted = wrapper.emitted("submit");
    expect(submitted).toBeTruthy();
    const payload = submitted![0][0] as any;
    expect(payload.pricingDirty).toBe(true);
    expect(payload.pricing).toBeNull();
  });

  it("修改费率后提交完整六项 Decimal 字符串对象，并剥离服务端只读字段", async () => {
    const wrapper = createWrapper({
      editingModel: mockModelWithPricing,
      initialMode: "edit",
    });

    const inputRateField = wrapper.find('input[placeholder="如 2.0"]');
    await inputRateField.setValue("3.5");

    const submitBtn = wrapper
      .findAll("button")
      .find((b) => b.text().includes("保存") || b.text().includes("更新"));
    await submitBtn!.trigger("click");

    const submitted = wrapper.emitted("submit");
    expect(submitted).toBeTruthy();
    const payload = submitted![0][0] as any;
    expect(payload.pricingDirty).toBe(true);
    expect(payload.pricing).toEqual({
      currency: "USD",
      basis: "per_million_tokens",
      input: "3.5",
      output: "8.0",
      cache_read: "0.2",
      cache_write: null,
      cache_write_5m: null,
      cache_write_1h: null,
    });
    // 关键断言：绝对不能含有服务端的 version/source/updated_at
    expect((payload.pricing as any).version).toBeUndefined();
  });

  it("输入以点开头的费率（如 .5）失焦或提交时自动规整为 0.5", async () => {
    const wrapper = createWrapper({
      editingModel: mockModelWithPricing,
      initialMode: "edit",
    });

    const inputRateField = wrapper.find('input[placeholder="如 2.0"]');
    await inputRateField.setValue(".5");
    await inputRateField.trigger("blur");

    const submitBtn = wrapper
      .findAll("button")
      .find((b) => b.text().includes("保存") || b.text().includes("更新"));
    await submitBtn!.trigger("click");

    const submitted = wrapper.emitted("submit");
    expect(submitted).toBeTruthy();
    const payload = submitted![0][0] as any;
    expect(payload.pricing.input).toBe("0.5");
  });

  it("点击清空后显示待生效提示条，并可通过撤销恢复还原", async () => {
    const wrapper = createWrapper({
      editingModel: mockModelWithPricing,
      initialMode: "edit",
    });

    const clearBtn = wrapper.find('[data-testid="clear-pricing-btn"]');
    await clearBtn.trigger("click");

    expect(
      wrapper.find('[data-testid="pricing-cleared-banner"]').exists(),
    ).toBe(true);

    // 点击撤销恢复
    const restoreBtn = wrapper.find('[data-testid="restore-pricing-btn"]');
    await restoreBtn.trigger("click");

    expect(
      wrapper.find('[data-testid="pricing-cleared-banner"]').exists(),
    ).toBe(false);
    const inputRateField = wrapper.find('input[placeholder="如 2.0"]');
    expect((inputRateField.element as HTMLInputElement).value).toBe("2.0");
  });
});
