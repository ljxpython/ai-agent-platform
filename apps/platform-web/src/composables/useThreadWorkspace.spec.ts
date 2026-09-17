import { beforeEach, describe, expect, it, vi } from 'vitest';
import { nextTick, ref } from 'vue';

const { workspaceServiceMock } = vi.hoisted(() => ({
  workspaceServiceMock: {
    getWorkspaceCapabilities: vi.fn(),
    getWorkspaceTree: vi.fn(),
    getArtifacts: vi.fn(),
    getWorkspacePreview: vi.fn(),
    getWorkspaceContentBlob: vi.fn(),
    triggerBlobDownload: vi.fn(),
  },
}));

vi.mock('@/services/threads/workspace.service', () => workspaceServiceMock);

import { useThreadWorkspace } from './useThreadWorkspace';

describe('useThreadWorkspace', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('loads capabilities and root tree on mount', async () => {
    const projectId = ref('proj-1');
    const threadId = ref('thread-1');

    workspaceServiceMock.getWorkspaceCapabilities.mockResolvedValueOnce({
      workspace: true,
      terminal: true,
    });
    workspaceServiceMock.getWorkspaceTree.mockResolvedValueOnce({
      items: [
        {
          path: '/workspace/src',
          name: 'src',
          type: 'directory',
          size_bytes: null,
          mtime: '2026-09-17T08:00:00Z',
          mime_type: null,
          preview_kind: null,
          is_artifact: false,
        },
      ],
      next_cursor: null,
    });
    workspaceServiceMock.getArtifacts.mockResolvedValueOnce({
      items: [],
      next_cursor: null,
    });

    const composable = useThreadWorkspace(projectId, threadId);

    // 等待异步完成
    await vi.waitFor(() => {
      expect(composable.capabilities.value?.workspace).toBe(true);
      expect(composable.directoryCache.value.get('/workspace')).toHaveLength(1);
    });
  });

  it('selects file and loads preview', async () => {
    const projectId = ref('proj-1');
    const threadId = ref('thread-1');

    workspaceServiceMock.getWorkspaceCapabilities.mockResolvedValue({ workspace: true });
    workspaceServiceMock.getWorkspaceTree.mockResolvedValue({ items: [], next_cursor: null });
    workspaceServiceMock.getArtifacts.mockResolvedValue({ items: [], next_cursor: null });
    workspaceServiceMock.getWorkspacePreview.mockResolvedValueOnce({
      kind: 'text',
      textPreview: {
        path: '/workspace/test.py',
        file_name: 'test.py',
        mime_type: 'text/x-python',
        size_bytes: 10,
        sha256: 'abc',
        preview_kind: 'text',
        text: 'print(1)',
        truncated: false,
      },
    });

    const composable = useThreadWorkspace(projectId, threadId);
    await composable.selectFile('/workspace/test.py');

    expect(composable.selectedPath.value).toBe('/workspace/test.py');
    expect(composable.previewResult.value?.kind).toBe('text');
    expect(composable.previewResult.value?.textPreview?.text).toBe('print(1)');
  });

  it('resets state when thread changes', async () => {
    const projectId = ref('proj-1');
    const threadId = ref('thread-1');

    workspaceServiceMock.getWorkspaceCapabilities.mockResolvedValue({ workspace: true });
    workspaceServiceMock.getWorkspaceTree.mockResolvedValue({ items: [], next_cursor: null });
    workspaceServiceMock.getArtifacts.mockResolvedValue({ items: [], next_cursor: null });

    const composable = useThreadWorkspace(projectId, threadId);
    composable.selectedPath.value = '/workspace/old-file.txt';

    threadId.value = 'thread-2';
    await nextTick();

    expect(composable.selectedPath.value).toBe('');
    expect(composable.previewResult.value).toBeNull();
  });
});
