import { computed, ref, shallowRef, watch, type Ref } from 'vue';
import type { ArtifactRef } from '@/types/workspace';
import {
  getArtifacts,
  getWorkspaceContentBlob,
  getWorkspacePreview,
  triggerBlobDownload,
  type WorkspacePreviewResult,
} from '@/services/threads/workspace.service';

export function useArtifacts(
  projectId: Ref<string>,
  threadId: Ref<string>,
) {
  const artifacts = ref<ArtifactRef[]>([]);
  const cursor = ref<string | null>(null);
  const loading = ref(false);
  const error = ref<string | null>(null);
  const hasMore = computed(() => cursor.value !== null);

  // 选中项与预览状态
  const selectedArtifact = ref<ArtifactRef | null>(null);
  const selectedPath = computed(() => selectedArtifact.value?.path || '');
  const previewResult = shallowRef<WorkspacePreviewResult | null>(null);
  const loadingPreview = ref(false);
  const previewError = ref<string | null>(null);
  const downloadingPath = ref<string | null>(null);

  // 代际生命周期控制
  let currentGeneration = 0;
  let activeAbortController: AbortController | null = null;
  let previewSequence = 0;

  function nextAbortSignal(): AbortSignal {
    if (activeAbortController) {
      activeAbortController.abort();
    }
    activeAbortController = new AbortController();
    return activeAbortController.signal;
  }

  // 加载第一页成果
  async function loadInitial(force = false, isRetry = false): Promise<void> {
    if (!projectId.value || !threadId.value) {
      artifacts.value = [];
      cursor.value = null;
      return;
    }
    if (loading.value && !force && !isRetry) return;

    const thisGen = ++currentGeneration;
    const signal = nextAbortSignal();
    loading.value = true;
    error.value = null;

    try {
      const page = await getArtifacts(
        projectId.value,
        threadId.value,
        { limit: 100 },
        signal,
      );

      if (thisGen !== currentGeneration) return;

      artifacts.value = page.items;
      cursor.value = page.next_cursor;
    } catch (err: unknown) {
      if (thisGen !== currentGeneration) return;

      const e = err as { code?: string; message?: string };
      // 409 workspace_directory_changed: 游标失效，自动重试首页一次
      if (e.code === 'workspace_directory_changed' && !isRetry) {
        return await loadInitial(true, true);
      }
      error.value = e.message || '加载成果列表失败';
      artifacts.value = [];
      cursor.value = null;
    } finally {
      if (thisGen === currentGeneration) {
        loading.value = false;
      }
    }
  }

  // 游标翻页加载更多
  async function loadMore(): Promise<void> {
    if (!projectId.value || !threadId.value || !cursor.value || loading.value) {
      return;
    }

    const thisGen = currentGeneration;
    loading.value = true;
    error.value = null;

    try {
      const page = await getArtifacts(
        projectId.value,
        threadId.value,
        { limit: 100, cursor: cursor.value },
      );

      if (thisGen !== currentGeneration) return;

      const existingPaths = new Set(artifacts.value.map((item) => item.path));
      const newItems = page.items.filter((item) => !existingPaths.has(item.path));
      artifacts.value = [...artifacts.value, ...newItems];
      cursor.value = page.next_cursor;
    } catch (err: unknown) {
      if (thisGen !== currentGeneration) return;
      const e = err as { message?: string };
      error.value = e.message || '加载更多成果失败';
    } finally {
      if (thisGen === currentGeneration) {
        loading.value = false;
      }
    }
  }

  // 刷新当前列表，并保持选中文档的最新状态
  async function refresh(): Promise<void> {
    const prevPath = selectedArtifact.value?.path;
    await loadInitial(true);

    if (prevPath) {
      const stillExists = artifacts.value.find((item) => item.path === prevPath);
      if (stillExists) {
        selectedArtifact.value = stillExists;
        // 如果不是 download 类型，重新拉取最新预览
        if (stillExists.preview_kind !== 'download') {
          void fetchPreview(stillExists);
        }
      } else {
        clearSelection();
      }
    }
  }

  // 实际预览请求核心封装
  async function fetchPreview(item: ArtifactRef): Promise<void> {
    const thisGen = currentGeneration;
    const thisSeq = ++previewSequence;
    loadingPreview.value = true;
    previewError.value = null;

    try {
      const result = await getWorkspacePreview(
        projectId.value,
        threadId.value,
        item.path,
      );

      if (
        thisGen === currentGeneration &&
        thisSeq === previewSequence &&
        selectedArtifact.value?.path === item.path
      ) {
        previewResult.value = result;
      }
    } catch (err: unknown) {
      if (
        thisGen === currentGeneration &&
        thisSeq === previewSequence &&
        selectedArtifact.value?.path === item.path
      ) {
        const e = err as { message?: string };
        previewError.value = e.message || '加载文件预览失败';
      }
    } finally {
      if (
        thisGen === currentGeneration &&
        thisSeq === previewSequence &&
        selectedArtifact.value?.path === item.path
      ) {
        loadingPreview.value = false;
      }
    }
  }

  // 选中文件并展示预览
  async function selectArtifact(item: ArtifactRef): Promise<void> {
    selectedArtifact.value = item;
    previewError.value = null;

    // 核心决策：若已知为 download 类型，直接装配下载卡片，严禁发起 preview HTTP 请求避免 415 报错
    if (item.preview_kind === 'download') {
      previewResult.value = {
        kind: 'download',
        downloadOnly: true,
      };
      loadingPreview.value = false;
      return;
    }

    await fetchPreview(item);
  }

  // 清除选中
  function clearSelection(): void {
    selectedArtifact.value = null;
    previewResult.value = null;
    previewError.value = null;
    loadingPreview.value = false;
  }

  // 下载当前选中或指定文件
  async function downloadArtifact(target?: ArtifactRef | null): Promise<void> {
    const item = target || selectedArtifact.value;
    if (!projectId.value || !threadId.value || !item) return;

    downloadingPath.value = item.path;
    try {
      const { blob, fileName } = await getWorkspaceContentBlob(
        projectId.value,
        threadId.value,
        item.path,
      );
      triggerBlobDownload(blob, fileName);
    } catch (err: unknown) {
      const e = err as { message?: string };
      console.error('下载成果失败:', e.message || err);
      throw err;
    } finally {
      downloadingPath.value = null;
    }
  }

  // 监听 projectId 与 threadId 变更，重置并触发加载
  watch(
    [projectId, threadId],
    ([newProject, newThread], [oldProject, oldThread]) => {
      if (newProject !== oldProject || newThread !== oldThread) {
        if (activeAbortController) {
          activeAbortController.abort();
        }
        currentGeneration++;
        previewSequence++;
        artifacts.value = [];
        cursor.value = null;
        error.value = null;
        selectedArtifact.value = null;
        previewResult.value = null;
        previewError.value = null;
        loadingPreview.value = false;

        if (newProject && newThread) {
          void loadInitial();
        }
      }
    },
    { immediate: true },
  );

  return {
    artifacts,
    cursor,
    loading,
    error,
    hasMore,
    selectedArtifact,
    selectedPath,
    previewResult,
    loadingPreview,
    previewError,
    downloadingPath,
    loadInitial,
    loadMore,
    refresh,
    selectArtifact,
    clearSelection,
    downloadArtifact,
  };
}
