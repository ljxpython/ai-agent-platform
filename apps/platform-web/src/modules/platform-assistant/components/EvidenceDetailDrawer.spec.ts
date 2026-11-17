import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import EvidenceDetailDrawer from "./EvidenceDetailDrawer.vue";
import type { EvidenceDetail } from "../types";

describe("EvidenceDetailDrawer", () => {
  const emptyDocEvidence: EvidenceDetail = {
    evidence_id: "be43d869-7296-4480-ad8e-63aa9a438ee0",
    operation: "documents",
    observed_at: "2026-11-17T09:46:04Z",
    scope: { project_id: "0ee1d5a0-5716-56ff-9795-9a9f2d72f247" },
    data: {
      sources: [],
      revision: "platform-assistant-v1",
    },
  };

  const hitDocEvidence: EvidenceDetail = {
    evidence_id: "cba35ed0-1111-2222-3333-444455556666",
    operation: "documents",
    observed_at: "2026-11-17T09:46:10Z",
    scope: { project_id: "0ee1d5a0-5716-56ff-9795-9a9f2d72f247" },
    data: {
      sources: [
        {
          title: "平台助手使用指南",
          text: "平台助手是一个基于只读审计事实的智能助手。",
          line_start: 1,
          line_end: 10,
        },
      ],
      revision: "platform-assistant-v1",
    },
  };

  it("当文档检索未命中时，正确展示操作摘要与清晰的空状态提示", () => {
    const wrapper = mount(EvidenceDetailDrawer, {
      props: {
        evidence: emptyDocEvidence,
        isOpen: true,
      },
      global: {
        stubs: {
          BaseDrawer: {
            template: "<div><slot /></div>",
          },
          BaseIcon: true,
        },
      },
    });

    // 检查元数据与操作说明
    expect(wrapper.text()).toContain("be43d869");
    expect(wrapper.text()).toContain("官方帮助与知识资料检索");
    expect(wrapper.text()).toContain("未匹配到相关内容 (0条结果)");

    // 检查空状态提示卡片
    expect(wrapper.text()).toContain(
      "知识库检索完成，未命中相关文档 (0 Matches)",
    );
    expect(wrapper.text()).toContain("暂无与当前关键词直接匹配的条目");
  });

  it("当文档检索命中时，正确展示命中状态并渲染文档卡片", () => {
    const wrapper = mount(EvidenceDetailDrawer, {
      props: {
        evidence: hitDocEvidence,
        isOpen: true,
      },
      global: {
        stubs: {
          BaseDrawer: {
            template: "<div><slot /></div>",
          },
          BaseIcon: true,
        },
      },
    });

    expect(wrapper.text()).toContain("cba35ed0");
    expect(wrapper.text()).toContain("已命中 1 条事实记录");
    expect(wrapper.text()).toContain("平台助手使用指南");
    expect(wrapper.text()).toContain(
      "平台助手是一个基于只读审计事实的智能助手",
    );
  });
});
