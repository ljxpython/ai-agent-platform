import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import KnowledgeSubmissionCard from "./KnowledgeSubmissionCard.vue";
import type { KnowledgeSubmission } from "@/services/knowledge/knowledge.service";

describe("KnowledgeSubmissionCard.vue", () => {
  const baseSubmission: KnowledgeSubmission = {
    version: 1,
    job_id: "job-12345678-abcd",
    document_id: "doc-87654321-dcba",
    file_name: "test_architecture.md",
    status: "queued",
    searchable: false,
    error_code: null,
    reused: false,
    created_at: "2026-10-12T10:00:00Z",
    updated_at: "2026-10-12T10:00:00Z",
  };

  it("renders queued status correctly with blue tone and job id", () => {
    const wrapper = mount(KnowledgeSubmissionCard, {
      props: { submission: baseSubmission },
    });

    expect(wrapper.text()).toContain("已受理，等待排队");
    expect(wrapper.text()).toContain("test_architecture.md");
    expect(wrapper.text()).toContain("任务编号：job-12345678-abcd");
    expect(wrapper.text()).toContain("暂不可检索");
  });

  it("renders ready status with searchable green badge", () => {
    const readySubmission: KnowledgeSubmission = {
      ...baseSubmission,
      status: "ready",
      searchable: true,
    };
    const wrapper = mount(KnowledgeSubmissionCard, {
      props: { submission: readySubmission },
    });

    expect(wrapper.text()).toContain("已入库，当前可检索");
    expect(wrapper.text()).toContain("文档知识已成功入库并发布");
    expect(wrapper.text()).toContain("当前可检索");
  });

  it("renders failed status with mapped friendly error message", () => {
    const failedSubmission: KnowledgeSubmission = {
      ...baseSubmission,
      status: "failed",
      error_code: "knowledge_file_too_large",
    };
    const wrapper = mount(KnowledgeSubmissionCard, {
      props: { submission: failedSubmission },
    });

    expect(wrapper.text()).toContain("入库处理失败");
    expect(wrapper.text()).toContain(
      "文件大小超出知识库单文档/图片上限（图片5MB/文档20MB）",
    );
  });

  it("renders reused submission correctly without task id for null job", () => {
    const reusedNullJob: KnowledgeSubmission = {
      ...baseSubmission,
      job_id: null,
      reused: true,
      status: "ready",
      searchable: true,
    };
    const wrapper = mount(KnowledgeSubmissionCard, {
      props: { submission: reusedNullJob },
    });

    expect(wrapper.text()).toContain("已复用");
    expect(wrapper.text()).toContain("已复用历史入库记录（无需等待异步任务）");
    expect(wrapper.text()).not.toContain("任务编号：");
  });

  it("renders awaiting review status without false queued claim", () => {
    const wrapper = mount(KnowledgeSubmissionCard, {
      props: { isAwaitingReview: true },
    });
    expect(wrapper.text()).toContain("等待审批，尚未受理");
    expect(wrapper.text()).not.toContain("已受理");
  });

  it("renders unconfirmed status when submission is missing", () => {
    const wrapper = mount(KnowledgeSubmissionCard, {
      props: {},
    });
    expect(wrapper.text()).toContain("提交结果未确认");
  });
});
