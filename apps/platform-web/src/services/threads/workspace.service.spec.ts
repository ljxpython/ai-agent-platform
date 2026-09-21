import { beforeEach, describe, expect, it, vi } from 'vitest';

const { platformHttpClientMock } = vi.hoisted(() => ({
  platformHttpClientMock: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  },
}));

vi.mock('@/services/http/client', () => ({
  platformHttpClient: platformHttpClientMock,
}));

import {
  downloadWorkspaceZip,
  getArtifacts,
  getWorkspaceCapabilities,
  getWorkspaceContentBlob,
  getWorkspacePreview,
  getWorkspaceTree,
} from './workspace.service';

describe('workspace.service', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    if (!Blob.prototype.text) {
      Blob.prototype.text = async function () {
        return new Promise((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = () => resolve(reader.result as string);
          reader.onerror = () => reject(reader.error);
          reader.readAsText(this);
        });
      };
    }
  });

  it('fetches capabilities correctly', async () => {
    platformHttpClientMock.get.mockResolvedValueOnce({
      data: { workspace: true, terminal: true, artifacts: ['application/json'] },
    });

    const caps = await getWorkspaceCapabilities('proj-1', 'thread-1');
    expect(caps.workspace).toBe(true);
    expect(caps.terminal).toBe(true);
    expect(platformHttpClientMock.get).toHaveBeenCalledWith(
      '/api/langgraph/threads/thread-1/capabilities',
      expect.objectContaining({
        headers: { 'x-project-id': 'proj-1' },
      }),
    );
  });

  it('fetches workspace tree with path and limit', async () => {
    platformHttpClientMock.get.mockResolvedValueOnce({
      data: {
        items: [
          {
            path: '/workspace/work',
            name: 'work',
            type: 'directory',
            size_bytes: null,
            mtime: '2026-09-17T08:00:00Z',
            mime_type: null,
            preview_kind: null,
            is_artifact: false,
          },
        ],
        next_cursor: null,
      },
    });

    const tree = await getWorkspaceTree('proj-1', 'thread-1', {
      path: '/workspace',
      limit: 100,
    });
    expect(tree.items).toHaveLength(1);
    expect(tree.items[0].name).toBe('work');
    expect(platformHttpClientMock.get).toHaveBeenCalledWith(
      '/api/langgraph/threads/thread-1/workspace/tree',
      expect.objectContaining({
        params: { path: '/workspace', limit: 100 },
        headers: { 'x-project-id': 'proj-1' },
      }),
    );
  });

  it('fetches artifacts page', async () => {
    platformHttpClientMock.get.mockResolvedValueOnce({
      data: {
        items: [
          {
            version: 1,
            artifact_id: 'art-1',
            path: '/workspace/outputs/chart.html',
            file_name: 'chart.html',
            mime_type: 'text/html',
            size_bytes: 1234,
            sha256: 'abc...',
            kind: 'chart',
            preview_kind: 'html-sandbox',
          },
        ],
        next_cursor: null,
      },
    });

    const arts = await getArtifacts('proj-1', 'thread-1');
    expect(arts.items).toHaveLength(1);
    expect(arts.items[0].kind).toBe('chart');
  });

  it('handles workspace preview text response', async () => {
    const textBlob = new Blob(
      [
        JSON.stringify({
          path: '/workspace/work/test.py',
          file_name: 'test.py',
          mime_type: 'text/x-python',
          size_bytes: 20,
          sha256: 'sha256...',
          preview_kind: 'text',
          text: 'print("hello")',
          truncated: false,
        }),
      ],
      { type: 'application/json' },
    );

    platformHttpClientMock.get.mockResolvedValueOnce({
      data: textBlob,
      headers: { 'content-type': 'application/json' },
    });

    const result = await getWorkspacePreview('proj-1', 'thread-1', '/workspace/work/test.py');
    expect(result.kind).toBe('text');
    expect(result.textPreview?.text).toBe('print("hello")');
  });

  it('handles workspace content blob and filename extraction', async () => {
    const contentBlob = new Blob(['sample content'], { type: 'text/plain' });

    platformHttpClientMock.get.mockResolvedValueOnce({
      data: contentBlob,
      headers: {
        'content-type': 'text/plain',
        'content-disposition': 'attachment; filename="test.txt"',
      },
    });

    const result = await getWorkspaceContentBlob('proj-1', 'thread-1', '/workspace/test.txt');
    expect(result.fileName).toBe('test.txt');
    expect(result.blob).toBe(contentBlob);
  });

  it('downloads workspace zip and triggers download', async () => {
    const zipBlob = new Blob(['mock-zip-bytes'], { type: 'application/zip' });
    platformHttpClientMock.get.mockResolvedValueOnce({
      data: zipBlob,
      headers: {
        'content-type': 'application/zip',
        'content-disposition': "attachment; filename*=UTF-8''workspace-thread-1.zip",
      },
    });

    const createObjectURLMock = vi.fn().mockReturnValue('blob:http://localhost/mock-uuid');
    const revokeObjectURLMock = vi.fn();
    window.URL.createObjectURL = createObjectURLMock;
    window.URL.revokeObjectURL = revokeObjectURLMock;

    await downloadWorkspaceZip('proj-1', 'thread-1');
    expect(platformHttpClientMock.get).toHaveBeenCalledWith(
      '/api/langgraph/threads/thread-1/workspace/zip',
      expect.objectContaining({
        headers: { 'x-project-id': 'proj-1' },
        responseType: 'blob',
      }),
    );
    expect(createObjectURLMock).toHaveBeenCalledWith(zipBlob);
  });

  it('unwraps error from Blob response when HTTP request fails', async () => {
    const errorPayload = JSON.stringify({
      request_id: 'req-400-abc',
      error: {
        code: 'project_id_required',
        message: 'x-project-id header is required',
      },
    });
    const errorBlob = new Blob([errorPayload], { type: 'application/json' });
    const axiosError = {
      isAxiosError: true,
      message: 'Request failed with status code 400',
      response: {
        status: 400,
        data: errorBlob,
      },
    };
    platformHttpClientMock.get.mockRejectedValueOnce(axiosError);

    await expect(
      getWorkspacePreview('proj-1', 'thread-1', '/workspace/outputs/bad.md'),
    ).rejects.toMatchObject({
      message: 'x-project-id header is required',
      code: 'project_id_required',
      requestId: 'req-400-abc',
      status: 400,
    });
  });
});

