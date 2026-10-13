<script setup lang="ts">
import { computed, onMounted, watch } from "vue";
import BaseIcon from "@/components/base/BaseIcon.vue";
import type { ToolItem } from "../transcript";
import { useKnowledgeJobTracker } from "@/composables/useKnowledgeJobTracker";
import {
  isValidJobId,
  type KnowledgeJob,
  type KnowledgeSubmission,
} from "@/services/knowledge/knowledge.service";

export type SubmissionDisplayStatus =
  | "awaiting_review"
  | "running"
  | "queued"
  | "parsing"
  | "indexing"
  | "publishing"
  | "ready"
  | "failed"
  | "unconfirmed";

const props = defineProps<{
  tool?: ToolItem;
  submission?: KnowledgeSubmission;
  projectId?: string;
  isAwaitingReview?: boolean;
}>();

const tracker = useKnowledgeJobTracker();

// 解析工具输出的结构化内容
function parseStructuredOutput(tool?: ToolItem): KnowledgeSubmission | null {
  if (!tool) return null;
  // 1. 尝试从 artifact.structured_content 取
  const artifact = tool.artifact as Record<string, unknown> | undefined;
  if (
    artifact?.structured_content &&
    typeof artifact.structured_content === "object"
  ) {
    return artifact.structured_content as unknown as KnowledgeSubmission;
  }

  // 2. 尝试从 tool.output 取
  if (typeof tool.output === "string") {
    try {
      const parsed = JSON.parse(tool.output);
      if (parsed && typeof parsed === "object") {
        if (parsed.structured_content) {
          return parsed.structured_content as KnowledgeSubmission;
        }
        return parsed as KnowledgeSubmission;
      }
    } catch {
      // ignore
    }
  }

  if (Array.isArray(tool.output)) {
    for (const item of tool.output) {
      if (
        item &&
        typeof item === "object" &&
        item.type === "text" &&
        typeof item.text === "string"
      ) {
        try {
          const parsed = JSON.parse(item.text);
          if (parsed && typeof parsed === "object") {
            return parsed as KnowledgeSubmission;
          }
        } catch {
          // ignore
        }
      }
    }
  }

  if (tool.output && typeof tool.output === "object") {
    return tool.output as unknown as KnowledgeSubmission;
  }

  return null;
}

const initialData = computed(
  () =>
    props.submission ?? (props.tool ? parseStructuredOutput(props.tool) : null),
);
const activeJobId = computed(() => initialData.value?.job_id || null);

// 跟踪实时状态
const liveJob = computed<KnowledgeJob | null>(() => {
  if (!activeJobId.value) return null;
  return tracker.getJob(activeJobId.value) || null;
});

// 最终生效的状态与字段（严禁未受理默认 queued）
const currentStatus = computed<SubmissionDisplayStatus>(() => {
  if (liveJob.value?.status) return liveJob.value.status;
  if (initialData.value?.status) return initialData.value.status;
  if (props.isAwaitingReview) return "awaiting_review";
  if (props.tool?.status === "running" || props.tool?.status === "incomplete")
    return "running";
  if (props.tool?.status === "error") return "failed";
  return "unconfirmed";
});

const isSearchable = computed<boolean>(() => {
  if (liveJob.value !== null && typeof liveJob.value.searchable === "boolean") {
    return liveJob.value.searchable;
  }
  return Boolean(initialData.value?.searchable);
});

const currentErrorCode = computed<string | null>(() => {
  if (liveJob.value?.error_code) return liveJob.value.error_code;
  if (initialData.value?.error_code) return initialData.value.error_code;
  if (props.tool?.status === "error")
    return (props.tool.error as string) || "tool_execution_error";
  return null;
});

const fileName = computed<string>(() => {
  if (liveJob.value?.file_name) return liveJob.value.file_name;
  if (initialData.value?.file_name) return initialData.value.file_name;
  const toolInput = props.tool?.input as Record<string, unknown> | undefined;
  const fileRef = (toolInput?.file_ref || toolInput?.image_ref) as
    | Record<string, unknown>
    | undefined;
  if (typeof fileRef?.file_name === "string") return fileRef.file_name;
  if (typeof fileRef?.path === "string") {
    const parts = fileRef.path.split("/");
    return parts[parts.length - 1] || "知识附件";
  }
  return "知识附件";
});

const isReused = computed<boolean>(() => {
  return Boolean(initialData.value?.reused);
});

// 状态映射配置
const statusMeta = computed(() => {
  switch (currentStatus.value) {
    case "awaiting_review":
      return {
        label: "等待审批，尚未受理",
        tone: "warning",
        bgClass:
          "bg-amber-50 dark:bg-amber-950/40 border-amber-200 dark:border-amber-800",
        textClass: "text-amber-700 dark:text-amber-300",
        icon: "alert" as const,
        desc: "附件提交需要项目管理员审批，审批通过后方可正式受理排队。",
      };
    case "running":
      return {
        label: "执行中，尚未受理",
        tone: "info",
        bgClass:
          "bg-blue-50 dark:bg-blue-950/40 border-blue-200 dark:border-blue-800",
        textClass: "text-blue-700 dark:text-blue-300",
        icon: "refresh" as const,
        desc: "正在向服务端发起知识库提交申请，请稍候……",
      };
    case "queued":
      return {
        label: "已受理，等待排队",
        tone: "info",
        bgClass:
          "bg-blue-50 dark:bg-blue-950/40 border-blue-200 dark:border-blue-800",
        textClass: "text-blue-700 dark:text-blue-300",
        icon: "activity" as const,
        desc: "任务已受理，后台正在排队等待处理。您可以继续进行正常对话。",
      };
    case "parsing":
      return {
        label: "正在解析内容",
        tone: "info",
        bgClass:
          "bg-blue-50 dark:bg-blue-950/40 border-blue-200 dark:border-blue-800",
        textClass: "text-blue-700 dark:text-blue-300",
        icon: "refresh" as const,
        desc: "正在提取文档段落与切分内容块，无需停留在本页面等待。",
      };
    case "indexing":
      return {
        label: "正在构建索引",
        tone: "info",
        bgClass:
          "bg-blue-50 dark:bg-blue-950/40 border-blue-200 dark:border-blue-800",
        textClass: "text-blue-700 dark:text-blue-300",
        icon: "refresh" as const,
        desc: "正在生成向量嵌入与图谱索引……",
      };
    case "publishing":
      return {
        label: "正在发布生效",
        tone: "warning",
        bgClass:
          "bg-amber-50 dark:bg-amber-950/40 border-amber-200 dark:border-amber-800",
        textClass: "text-amber-700 dark:text-amber-300",
        icon: "refresh" as const,
        desc: "索引已生成完毕，正在发布至当前项目成员的检索视图。",
      };
    case "ready":
      return {
        label: isSearchable.value
          ? "已入库，当前可检索"
          : "处理完成（当前版本暂不可查）",
        tone: isSearchable.value ? "success" : "warning",
        bgClass: isSearchable.value
          ? "bg-emerald-50 dark:bg-emerald-950/40 border-emerald-200 dark:border-emerald-800"
          : "bg-amber-50 dark:bg-amber-950/40 border-amber-200 dark:border-amber-800",
        textClass: isSearchable.value
          ? "text-emerald-700 dark:text-emerald-300"
          : "text-amber-700 dark:text-amber-300",
        icon: "check" as const,
        desc: isSearchable.value
          ? "文档知识已成功入库并发布，本项目所有成员均可检索使用。"
          : "入库处理已完成，但当前版本未对外发布或已回退，暂不可检索。",
      };
    case "failed":
      return {
        label: "入库处理失败",
        tone: "danger",
        bgClass:
          "bg-rose-50 dark:bg-rose-950/40 border-rose-200 dark:border-rose-800",
        textClass: "text-rose-700 dark:text-rose-300",
        icon: "alert" as const,
        desc: getErrorFriendlyMessage(currentErrorCode.value),
      };
    default:
      return {
        label: "提交结果未确认",
        tone: "neutral",
        bgClass: "bg-slate-50 dark:bg-dark-800 border-border",
        textClass: "text-text-sub",
        icon: "file" as const,
        desc: "未获取到有效受理回执，请前往项目详情页任务面板查看真实状态。",
      };
  }
});

function getErrorFriendlyMessage(code: string | null): string {
  if (!code) return "处理遇到未知错误，请重试或联系管理员。";
  if (code.includes("disabled") || code.includes("not_configured")) {
    return "当前项目未启用知识库入库服务。";
  }
  if (code.includes("denied")) {
    return "权限不足：当前角色无权将文件加入该项目知识库。";
  }
  if (code.includes("unsupported") || code.includes("format")) {
    return "格式不支持：当前仅支持 TXT/MD/PDF/DOCX/PPTX/PNG/JPEG 文档与图片。";
  }
  if (code.includes("too_large")) {
    return "文件大小超出知识库单文档/图片上限（图片5MB/文档20MB）。";
  }
  if (code.includes("queue_full") || code.includes("quota")) {
    return "当前后台任务队列已满或项目配额不足，请稍后重试。";
  }
  if (code.includes("expired") || code.includes("invalid_file_ref")) {
    return "附件引用已失效或上传过期，请重新上传后重试。";
  }
  if (code.includes("unconfirmed")) {
    return "提交状态尚未确认，请前往项目详情页任务面板查看。";
  }
  return `处理失败（原因：${code}）`;
}

// 自动向 Tracker 注册（仅合法 job_id 注册）
onMounted(() => {
  if (
    props.projectId &&
    activeJobId.value &&
    isValidJobId(activeJobId.value) &&
    initialData.value
  ) {
    tracker.trackJob(props.projectId, activeJobId.value, {
      ...initialData.value,
      job_id: activeJobId.value,
    });
  }
});

watch(
  () => [props.projectId, activeJobId.value],
  ([pId, jId]) => {
    if (pId && jId && isValidJobId(jId) && initialData.value) {
      tracker.trackJob(pId, jId, {
        ...initialData.value,
        job_id: jId,
      });
    }
  },
);
</script>

<template>
  <div
    class="rounded-xl border p-3.5 transition-all duration-200"
    :class="statusMeta.bgClass"
  >
    <!-- 卡片头部 -->
    <div class="flex items-center justify-between gap-3">
      <div class="flex min-w-0 items-center gap-2.5">
        <div
          class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border bg-white/80 shadow-xs dark:bg-dark-900"
          :class="statusMeta.textClass"
        >
          <BaseIcon :name="statusMeta.icon" size="sm" />
        </div>
        <div class="min-w-0">
          <div class="flex items-center gap-2">
            <span
              class="truncate text-xs font-semibold text-text-main"
              :title="fileName"
            >
              {{ fileName }}
            </span>
            <span
              v-if="isReused"
              class="rounded bg-primary-100 px-1.5 py-0.5 text-[10px] font-medium text-primary-700 dark:bg-primary-950 dark:text-primary-300"
            >
              已复用
            </span>
          </div>
          <div class="text-[11px] font-medium" :class="statusMeta.textClass">
            {{ statusMeta.label }}
          </div>
        </div>
      </div>

      <!-- 右侧可检索性 Pill -->
      <div class="shrink-0 text-right">
        <span
          v-if="isSearchable"
          class="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-medium text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300"
        >
          <span class="h-1.5 w-1.5 rounded-full bg-emerald-500"></span>
          当前可检索
        </span>
        <span
          v-else-if="currentStatus !== 'failed'"
          class="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-600 dark:bg-dark-700 dark:text-dark-300"
        >
          <span class="h-1.5 w-1.5 rounded-full bg-slate-400"></span>
          暂不可检索
        </span>
      </div>
    </div>

    <!-- 描述与附加说明 -->
    <div class="mt-2.5 text-xs leading-relaxed text-text-sub">
      {{ statusMeta.desc }}
    </div>

    <!-- 底部任务标识 -->
    <div
      v-if="activeJobId"
      class="mt-2 flex items-center justify-between border-t border-black/5 pt-2 text-[10px] text-text-sub/80 dark:border-white/5"
    >
      <span
        >任务编号：<code class="font-mono">{{ activeJobId }}</code></span
      >
      <span
        v-if="currentStatus !== 'ready' && currentStatus !== 'failed'"
        class="flex items-center gap-1"
      >
        <span
          class="inline-block h-1.5 w-1.5 animate-ping rounded-full bg-blue-500"
        ></span>
        后台处理中
      </span>
    </div>
    <div
      v-else-if="isReused"
      class="mt-2 border-t border-black/5 pt-2 text-[10px] text-text-sub/80 dark:border-white/5"
    >
      已复用历史入库记录（无需等待异步任务）
    </div>
  </div>
</template>
