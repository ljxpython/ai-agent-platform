import { beforeEach, describe, expect, it, vi } from 'vitest';
import { nextTick, ref } from 'vue';
import type { ArtifactRef } from '@/types/workspace';

const { workspaceServiceMock } = vi.hoisted(() => ({
  workspaceServiceMock: {
    getArtifacts: vi.fn(),
    getWorkspacePreview: vi.fn(),
    getWorkspaceContentBlob: vi.fn(),
    triggerBlobDownload: vi.fn(),
  },
}));

vi.mock('@/services/threads/workspace.service', () => workspaceServiceMock);

import { useArtifacts } from './useArtifacts';

describe('useArtifacts', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const mockArtifact1: ArtifactRef = {
    version: 1,
    artifact_id: 'art-1',
    path: '/workspace/outputs/doc.md',
    file_name: 'doc.md',
    mime_type: 'text/markdown',
    size_bytes: 100,
    sha256: 'sha-1',
    kind: 'document',
    preview_kind: 'markdown',
  };

  const mockArtifact2: ArtifactRef = {
    version: 1,
    artifact_id: 'art-2',
    path: '/workspace/outputs/archive.zip',
    file_name: 'archive.zip',
    mime_type: 'application/zip',
    size_bytes: 2048,
    sha256: 'sha-2',
    kind: 'archive',
    preview_kind: 'download',
  };

  it('loads initial artifacts on project/thread set', async () => {
    const projectId = ref('proj-1');
    const threadId = ref('thread-1');

    workspaceServiceMock.getArtifacts.mockResolvedValueOnce({
      items: [mockArtifact1],
      next_cursor: 'cursor-1',
    });

    const composable = useArtifacts(projectId, threadId);

    await vi.waitFor(() => {
      expect(composable.artifacts.value).toHaveLength(1);
      expect(composable.artifacts.value[0].path).toBe('/workspace/outputs/doc.md');
      expect(composable.cursor.value).toBe('cursor-1');
      expect(composable.hasMore.value).toBe(true);
    });

    expect(workspaceServiceMock.getArtifacts).toHaveBeenCalledWith(
      'proj-1',
      'thread-1',
      { limit: 100 },
      expect.any(AbortSignal),
    );
  });

  it('loads more artifacts and deduplicates by path', async () => {
    const projectId = ref('proj-1');
    const threadId = ref('thread-1');

    workspaceServiceMock.getArtifacts.mockResolvedValueOnce({
      items: [mockArtifact1],
      next_cursor: 'cursor-1',
    });

    const composable = useArtifacts(projectId, threadId);
    await vi.waitFor(() => expect(composable.artifacts.value).toHaveLength(1));

    // 第二页包含重复的 mockArtifact1 和新的 mockArtifact2
    workspaceServiceMock.getArtifacts.mockResolvedValueOnce({
      items: [mockArtifact1, mockArtifact2],
      next_cursor: null,
    });

    await composable.loadMore();

    expect(composable.artifacts.value).toHaveLength(2);
    expect(composable.artifacts.value[1].path).toBe('/workspace/outputs/archive.zip');
    expect(composable.cursor.value).toBeNull();
    expect(composable.hasMore.value).toBe(false);
  });

  it('blocks preview request when preview_kind is download', async () => {
    const projectId = ref('proj-1');
    const threadId = ref('thread-1');

    workspaceServiceMock.getArtifacts.mockResolvedValueOnce({
      items: [mockArtifact2],
      next_cursor: null,
    });

    const composable = useArtifacts(projectId, threadId);
    await vi.waitFor(() => expect(composable.artifacts.value).toHaveLength(1));

    await composable.selectArtifact(mockArtifact2);

    expect(composable.selectedArtifact.value).toEqual(mockArtifact2);
    expect(composable.previewResult.value).toEqual({
      kind: 'download',
      downloadOnly: true,
    });
    // 关键断言：绝不调用 getWorkspacePreview！杜绝 415 报错！
    expect(workspaceServiceMock.getWorkspacePreview).not.toHaveBeenCalled();
  });

  it('fetches preview when preview_kind is markdown', async () => {
    const projectId = ref('proj-1');
    const threadId = ref('thread-1');

    workspaceServiceMock.getArtifacts.mockResolvedValueOnce({
      items: [mockArtifact1],
      next_cursor: null,
    });
    workspaceServiceMock.getWorkspacePreview.mockResolvedValueOnce({
      kind: 'markdown',
      textPreview: {
        path: mockArtifact1.path,
        file_name: mockArtifact1.file_name,
        mime_type: mockArtifact1.mime_type,
        size_bytes: mockArtifact1.size_bytes,
        sha256: mockArtifact1.sha256,
        preview_kind: 'markdown',
        text: '# Content',
        truncated: false,
      },
    });

    const composable = useArtifacts(projectId, threadId);
    await vi.waitFor(() => expect(composable.artifacts.value).toHaveLength(1));

    await composable.selectArtifact(mockArtifact1);

    expect(workspaceServiceMock.getWorkspacePreview).toHaveBeenCalledWith(
      'proj-1',
      'thread-1',
      mockArtifact1.path,
    );
    expect(composable.previewResult.value?.kind).toBe('markdown');
  });

  it('resets state and reloads when switching thread', async () => {
    const projectId = ref('proj-1');
    const threadId = ref('thread-1');

    workspaceServiceMock.getArtifacts.mockResolvedValueOnce({
      items: [mockArtifact1],
      next_cursor: null,
    });

    const composable = useArtifacts(projectId, threadId);
    await vi.waitFor(() => expect(composable.artifacts.value).toHaveLength(1));

    workspaceServiceMock.getArtifacts.mockResolvedValueOnce({
      items: [mockArtifact2],
      next_cursor: null,
    });

    threadId.value = 'thread-2';

    await vi.waitFor(() => {
      expect(composable.artifacts.value).toHaveLength(1);
      expect(composable.artifacts.value[0].path).toBe('/workspace/outputs/archive.zip');
      expect(workspaceServiceMock.getArtifacts).toHaveBeenLastCalledWith(
        'proj-1',
        'thread-2',
        expect.anything(),
        expect.anything(),
      );
    });
  });

  it('retries once on workspace_directory_changed 409 error', async () => {
    const projectId = ref('proj-1');
    const threadId = ref('thread-1');

    const conflictErr = new Error('conflict');
    (conflictErr as any).code = 'workspace_directory_changed';

    // 第一次报错 409，第二次重试成功
    workspaceServiceMock.getArtifacts
      .mockRejectedValueOnce(conflictErr)
      .mockResolvedValueOnce({
        items: [mockArtifact1],
        next_cursor: null,
      });

    const composable = useArtifacts(projectId, threadId);

    await vi.waitFor(() => {
      expect(composable.artifacts.value).toHaveLength(1);
      expect(workspaceServiceMock.getArtifacts).toHaveBeenCalledTimes(2);
    });
  });
});
