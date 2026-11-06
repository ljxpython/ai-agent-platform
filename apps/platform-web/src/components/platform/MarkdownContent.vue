<script setup lang="ts">
import { computed } from "vue";
import { copyText } from "@/utils/clipboard";
import { renderMarkdown } from "@/utils/markdown";

const props = withDefaults(
  defineProps<{
    content: string;
  }>(),
  {
    content: "",
  },
);

const emit = defineEmits<{
  (e: "artifact-click", artifactId: string, event: MouseEvent): void;
}>();

const renderedHtml = computed(() => renderMarkdown(props.content));

async function handleClick(event: MouseEvent) {
  const target = event.target as HTMLElement | null;

  // 1. 处理 artifact:// 链接点击，拦截并派发事件
  const artifactLink = target?.closest(
    "a[data-artifact-id], a.pw-artifact-link",
  ) as HTMLAnchorElement | null;
  if (artifactLink) {
    event.preventDefault();
    event.stopPropagation();
    const artifactId =
      artifactLink.getAttribute("data-artifact-id") ||
      artifactLink
        .getAttribute("href")
        ?.replace(/^artifact:\/\//, "")
        .split(/[?#]/)[0] ||
      "";
    if (artifactId) {
      emit("artifact-click", artifactId, event);
    }
    return;
  }

  // 2. 处理代码块复制
  const copyButton = target?.closest(
    "[data-copy-code]",
  ) as HTMLButtonElement | null;

  if (!copyButton) {
    return;
  }

  const codeElement = copyButton
    .closest(".pw-markdown-code")
    ?.querySelector("code");
  const code = codeElement?.textContent || "";
  if (!code) {
    return;
  }

  const copied = await copyText(code);
  if (!copied) {
    copyButton.textContent = "复制失败";
    window.setTimeout(() => {
      copyButton.textContent = "复制";
    }, 1600);
    return;
  }

  copyButton.textContent = "已复制";
  window.setTimeout(() => {
    copyButton.textContent = "复制";
  }, 1600);
}
</script>

<!-- eslint-disable vue/no-v-html -->
<template>
  <div class="pw-markdown" @click="handleClick" v-html="renderedHtml" />
</template>
