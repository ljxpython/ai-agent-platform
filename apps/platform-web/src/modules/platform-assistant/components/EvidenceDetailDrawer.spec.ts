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
    expect(wrapper.text()).toContain("平台用户指南阅读");
    expect(wrapper.text()).toContain("未匹配到相关内容 (0条结果)");

    // 检查空状态提示卡片
    expect(wrapper.text()).toContain("暂无可读用户指南");
    expect(wrapper.text()).toContain("空结果不能证明平台没有此功能");
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

  it("目录明确尚未读正文，不显示关键词未命中提示", () => {
    const wrapper = mount(EvidenceDetailDrawer, {
      props: {
        evidence: {
          ...emptyDocEvidence,
          data: {
            sources: [],
            catalog: [
              { document_id: "chat", title: "聊天", summary: "前端操作" },
            ],
          },
        },
        isOpen: true,
      },
      global: {
        stubs: {
          BaseDrawer: { template: "<div><slot /></div>" },
          BaseIcon: true,
        },
      },
    });
    expect(wrapper.text()).toContain("用户指南目录（尚未读取正文）");
    expect(wrapper.text()).toContain("聊天 · chat");
    expect(wrapper.text()).not.toContain("暂无可读用户指南");
  });

  it("追踪不可用时仍展示运行失败阶段，空日志不显示命中", async () => {
    const wrapper = mount(EvidenceDetailDrawer, {
      props: {
        evidence: {
          ...emptyDocEvidence,
          operation: "diagnostics",
          data: {
            run_status: "error",
            availability: "disabled",
            persistent_state: {
              availability: "available",
              approval_pending: false,
              failed_tasks: [
                {
                  node: "ExecutionSkillsMiddleware.before_agent",
                  error_code: "runtime.execution_failed",
                },
              ],
            },
          },
        },
        isOpen: true,
      },
      global: {
        stubs: {
          BaseDrawer: { template: "<div><slot /></div>" },
          BaseIcon: true,
        },
      },
    });
    expect(wrapper.text()).toContain("已命中 1 条事实记录");
    expect(wrapper.text()).toContain("ExecutionSkillsMiddleware.before_agent");
    expect(wrapper.text()).toContain("是否待审批：未观察到");
    expect(wrapper.text()).toContain("失败阶段不等于底层根因");
    await wrapper.setProps({
      evidence: {
        ...emptyDocEvidence,
        operation: "logs",
        data: {
          total: 0,
          availability: "empty",
          source: "fixed_files",
          correlation_type: "run_id",
          partial: true,
        },
      },
    });
    expect(wrapper.text()).toContain("未匹配到相关内容 (0条结果)");
    expect(wrapper.text()).toContain("日志来源：fixed_files；关联方式：run_id");
    expect(wrapper.text()).not.toContain("已命中");
    await wrapper.setProps({
      evidence: {
        ...emptyDocEvidence,
        operation: "logs",
        data: { total: 0, availability: "unavailable", source: "fixed_files" },
      },
    });
    expect(wrapper.text()).toContain("日志来源不可用");
    expect(wrapper.text()).not.toContain("未匹配到相关内容");
  });

  it("日志窗口和部分覆盖直接可见，文档保留来源哈希与截断提示", async () => {
    const wrapper = mount(EvidenceDetailDrawer, {
      props: {
        evidence: {
          ...emptyDocEvidence,
          operation: "logs",
          scope: {
            project_id: "assistant-project",
            target_project_id: "target-project",
          },
          data: {
            query_start: "2026-10-01T08:00:00Z",
            query_end: "2026-10-01T09:00:00Z",
            partial: true,
          },
        },
        isOpen: true,
      },
      global: {
        stubs: {
          BaseDrawer: { template: "<div><slot /></div>" },
          BaseIcon: true,
        },
      },
    });
    expect(wrapper.text()).toContain("实际日志查询窗口：2026-10-01T08:00:00Z");
    expect(wrapper.text()).toContain("助手会话项目: assistant-project");
    expect(wrapper.text()).toContain("排查目标项目: target-project");
    expect(wrapper.text()).toContain("资料读取时间");
    expect(wrapper.text()).toContain("没有记录不能证明没有故障");
    await wrapper.setProps({
      evidence: {
        ...hitDocEvidence,
        data: {
          sources: [
            {
              title: "聊天",
              text: "当前正文",
              revision: "current",
              sha256: "abc123",
              truncated: true,
            },
          ],
        },
      },
    });
    expect(wrapper.text()).toContain("SHA256：abc123");
    expect(wrapper.text()).toContain("正文已截断");
  });
});
