import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import RuntimeModelEditor from "./RuntimeModelEditor.vue";
import type { RuntimeModelItem } from "@/types/management";

describe("RuntimeModelEditor.vue", () => {
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

  it("在编辑模式下展示模型费率卡片并填充已有定价", () => {
    const wrapper = mount(RuntimeModelEditor, {
      props: {
        editingModel: mockModelWithPricing,
        initialMode: "edit",
      },
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
    const wrapper = mount(RuntimeModelEditor, {
      props: {
        editingModel: null,
        initialMode: "standard",
      },
    });

    const pricingSection = wrapper.find(
      '[data-testid="model-pricing-section"]',
    );
    expect(pricingSection.exists()).toBe(false);
  });

  it("编辑模式下若未改动价格，提交 payload 中 pricing 为 undefined (防误冲掉现有价格)", async () => {
    const wrapper = mount(RuntimeModelEditor, {
      props: {
        editingModel: mockModelWithPricing,
        initialMode: "edit",
      },
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
    const wrapper = mount(RuntimeModelEditor, {
      props: {
        editingModel: mockModelWithPricing,
        initialMode: "edit",
      },
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
    const wrapper = mount(RuntimeModelEditor, {
      props: {
        editingModel: mockModelWithPricing,
        initialMode: "edit",
      },
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
    const wrapper = mount(RuntimeModelEditor, {
      props: {
        editingModel: mockModelWithPricing,
        initialMode: "edit",
      },
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
    const wrapper = mount(RuntimeModelEditor, {
      props: {
        editingModel: mockModelWithPricing,
        initialMode: "edit",
      },
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
