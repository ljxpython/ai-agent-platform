import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import RuntimeModelEditor from "./RuntimeModelEditor.vue";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseIcon from "@/components/base/BaseIcon.vue";
import BaseSelect from "@/components/base/BaseSelect.vue";

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
    expect(wrapper.text()).toContain(
      "Provider 标识必须以小写英文字母开头",
    );

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
  });
});
