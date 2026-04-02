"use client";

import { BaseChatTemplate } from "@/components/chat-template/base-chat-template";
import {
  TestcaseChatHeader,
  TestcaseWorkspaceNav,
} from "@/components/platform/testcase-chat-header";
import { getConfiguredPlatformApiUrl } from "@/lib/platform-api-url";

export default function TestcaseGeneratePage() {
  const defaultPlatformApiUrl = getConfiguredPlatformApiUrl();

  return (
    <BaseChatTemplate
      target={{
        targetType: "graph",
        graphId: "test_case_agent",
        apiUrl: defaultPlatformApiUrl,
      }}
      display={{
        title: "Testcase · AI 对话生成",
        description: "固定接入 `test_case_agent`，用于上传 PDF 并生成正式测试用例。",
        emptyTitle: "上传 PDF 开始生成",
        emptyDescription: "推荐使用真实需求文档，例如 runtime_service/test_data/接口文档.pdf。",
      }}
      features={{
        allowAssistantSwitch: false,
        allowApiUrlEdit: false,
        allowRunOptions: true,
        showHistory: true,
        showArtifacts: true,
        showContextBar: true,
      }}
      slots={{
        headerSlot: <TestcaseWorkspaceNav />,
        contextSlot: <TestcaseChatHeader />,
      }}
    />
  );
}
