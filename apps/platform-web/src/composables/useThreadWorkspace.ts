import { ref, shallowRef, watch, type Ref } from 'vue';
import type {
  ArtifactRef,
  PreviewKind,
  WorkspaceCapabilities,
  WorkspaceEntry,
} from '@/types/workspace';
import {
  downloadWorkspaceZip,
  getArtifacts,
  getWorkspaceCapabilities,
  getWorkspaceContentBlob,
  getWorkspacePreview,
  getWorkspaceTree,
  triggerBlobDownload,
  type WorkspacePreviewResult,
} from '@/services/threads/workspace.service';

export function useThreadWorkspace(
  projectId: Ref<string>,
  threadId: Ref<string>,
) {
  const capabilities = ref<WorkspaceCapabilities | null>(null);
  const loadingCapabilities = ref(false);

  // 目录树：以目录路径为 key 的缓存
  const directoryCache = ref<Map<string, WorkspaceEntry[]>>(new Map());
  const directoryLoading = ref<Map<string, boolean>>(new Map());
  const expandedPaths = ref<Set<string>>(new Set(['/workspace']));

  // 产物列表
  const artifacts = ref<ArtifactRef[]>([]);
  const artifactsCursor = ref<string | null>(null);
  const loadingArtifacts = ref(false);
  const hasNewArtifactNotice = ref(false);

  // 当前选中预览
  const selectedPath = ref<string>('');
  const previewResult = shallowRef<WorkspacePreviewResult | null>(null);
  const loadingPreview = ref(false);
  const previewError = ref<string | null>(null);

  let activeAbortController: AbortController | null = null;

  function createAbortSignal(): AbortSignal {
    if (activeAbortController) {
      activeAbortController.abort();
    }
    activeAbortController = new AbortController();
    return activeAbortController.signal;
  }

  // 获取能力
  async function loadCapabilities() {
    if (!projectId.value || !threadId.value) return;
    loadingCapabilities.value = true;
    try {
      capabilities.value = await getWorkspaceCapabilities(
        projectId.value,
        threadId.value,
      );
    } catch {
      capabilities.value = { workspace: false };
    } finally {
      loadingCapabilities.value = false;
    }
  }

  // 加载单层目录
  async function loadDirectory(path: string = '/workspace') {
    if (!projectId.value || !threadId.value) return;
    const currentLoading = new Map(directoryLoading.value);
    currentLoading.set(path, true);
    directoryLoading.value = currentLoading;

    try {
      const page = await getWorkspaceTree(projectId.value, threadId.value, {
        path,
        limit: 100,
      });
      const nextCache = new Map(directoryCache.value);
      nextCache.set(path, page.items);
      directoryCache.value = nextCache;
    } catch (err: unknown) {
      // 局部重试/清空
      const nextCache = new Map(directoryCache.value);
      nextCache.set(path, []);
      directoryCache.value = nextCache;
    } finally {
      const doneLoading = new Map(directoryLoading.value);
      doneLoading.set(path, false);
      directoryLoading.value = doneLoading;
    }
  }

  // 加载产物列表
  async function loadArtifacts(cursor?: string) {
    if (!projectId.value || !threadId.value) return;
    loadingArtifacts.value = true;
    try {
      const page = await getArtifacts(projectId.value, threadId.value, {
        cursor,
        limit: 100,
      });
      if (cursor) {
        artifacts.value = [...artifacts.value, ...page.items];
      } else {
        artifacts.value = page.items;
      }
      artifactsCursor.value = page.next_cursor;
    } catch {
      if (!cursor) artifacts.value = [];
    } finally {
      loadingArtifacts.value = false;
    }
  }

  // 展开/收起目录
  function toggleDirectory(path: string) {
    const nextSet = new Set(expandedPaths.value);
    if (nextSet.has(path)) {
      nextSet.delete(path);
    } else {
      nextSet.add(path);
      if (!directoryCache.value.has(path)) {
        void loadDirectory(path);
      }
    }
    expandedPaths.value = nextSet;
  }

  // 选中并预览文件
  async function selectFile(
    path: string,
    entryOrArtifact?: { preview_kind?: PreviewKind | null },
  ) {
    if (!projectId.value || !threadId.value || !path) return;
    selectedPath.value = path;
    previewError.value = null;
    loadingPreview.value = true;
    previewResult.value = null;

    // 若已知为 download 类型，直接装配下载结果，绝不请求 preview 避免 415 报错
    const knownArtifact = artifacts.value.find((a) => a.path === path);
    const kind = entryOrArtifact?.preview_kind ?? knownArtifact?.preview_kind;
    if (kind === 'download') {
      if (selectedPath.value === path) {
        previewResult.value = {
          kind: 'download',
          downloadOnly: true,
        };
        loadingPreview.value = false;
      }
      return;
    }

    try {
      const result = await getWorkspacePreview(
        projectId.value,
        threadId.value,
        path,
      );
      // 避免慢请求覆盖新选择
      if (selectedPath.value === path) {
        previewResult.value = result;
      }
    } catch (err: unknown) {
      if (selectedPath.value === path) {
        previewError.value =
          err instanceof Error ? err.message : '加载文件预览失败';
      }
    } finally {
      if (selectedPath.value === path) {
        loadingPreview.value = false;
      }
    }
  }

  // 下载当前选中或指定文件
  async function downloadCurrentFile(path?: string) {
    const targetPath = path || selectedPath.value;
    if (!projectId.value || !threadId.value || !targetPath) return;
    try {
      const { blob, fileName } = await getWorkspaceContentBlob(
        projectId.value,
        threadId.value,
        targetPath,
      );
      triggerBlobDownload(blob, fileName);
    } catch (err: unknown) {
      console.error('下载文件失败:', err);
    }
  }

  const downloadingArchive = ref(false);

  // 打包下载工作区全部文件
  async function downloadAllFiles() {
    if (!projectId.value || !threadId.value || downloadingArchive.value) return;
    downloadingArchive.value = true;
    try {
      await downloadWorkspaceZip(projectId.value, threadId.value);
    } catch (err: unknown) {
      console.error('打包下载工作区文件失败:', err);
      throw err;
    } finally {
      downloadingArchive.value = false;
    }
  }

  const refreshing = ref(false);

  // 刷新工作区（包含根目录与所有已展开的子目录、产物列表、以及当前预览文件）
  async function refresh(options: { notifyNew?: boolean } = {}) {
    if (!projectId.value || !threadId.value || refreshing.value) return;
    refreshing.value = true;
    try {
      const oldArtifactCount = artifacts.value.length;
      // 收集所有需要刷新的目录：根目录 + 用户当前已展开的所有子目录
      const pathsToRefresh = Array.from(new Set(['/workspace', ...expandedPaths.value]));
      const directoryLoads = pathsToRefresh.map((dirPath) => loadDirectory(dirPath));

      await Promise.all([
        ...directoryLoads,
        loadArtifacts(),
      ]);
      if (options.notifyNew && artifacts.value.length > oldArtifactCount) {
        hasNewArtifactNotice.value = true;
      }
      // 如果当前选中的文件存在，刷新其最新预览
      if (selectedPath.value) {
        void selectFile(selectedPath.value);
      }
    } finally {
      refreshing.value = false;
    }
  }

  function clearNewArtifactNotice() {
    hasNewArtifactNotice.value = false;
  }

  // 切线程重置
  watch(
    [projectId, threadId],
    ([newProject, newThread], [oldProject, oldThread]) => {
      if (newProject !== oldProject || newThread !== oldThread) {
        createAbortSignal();
        capabilities.value = null;
        directoryCache.value = new Map();
        directoryLoading.value = new Map();
        expandedPaths.value = new Set(['/workspace']);
        artifacts.value = [];
        artifactsCursor.value = null;
        selectedPath.value = '';
        previewResult.value = null;
        previewError.value = null;
        hasNewArtifactNotice.value = false;

        if (newProject && newThread) {
          void loadCapabilities();
          void loadDirectory('/workspace');
          void loadArtifacts();
        }
      }
    },
    { immediate: true },
  );

  return {
    capabilities,
    loadingCapabilities,
    directoryCache,
    directoryLoading,
    expandedPaths,
    artifacts,
    artifactsCursor,
    loadingArtifacts,
    hasNewArtifactNotice,
    selectedPath,
    previewResult,
    loadingPreview,
    previewError,
    refreshing,
    downloadingArchive,
    // 方法
    loadCapabilities,
    loadDirectory,
    loadArtifacts,
    toggleDirectory,
    selectFile,
    downloadCurrentFile,
    downloadAllFiles,
    refresh,
    clearNewArtifactNotice,
  };
}
