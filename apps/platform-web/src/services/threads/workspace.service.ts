import { platformHttpClient } from '@/services/http/client';
import type {
  ArtifactRef,
  PreviewKind,
  TextPreview,
  WorkspaceCapabilities,
  WorkspaceEntry,
  WorkspacePage,
} from '@/types/workspace';

export interface WorkspacePreviewResult {
  kind: PreviewKind;
  textPreview?: TextPreview;
  htmlContent?: string;
  imageBlob?: Blob;
  downloadOnly?: boolean;
}

export interface WorkspaceServiceError extends Error {
  code?: string;
  requestId?: string;
  status?: number;
}

export async function unwrapWorkspaceError(err: unknown): Promise<WorkspaceServiceError> {
  if (err && typeof err === 'object') {
    const maybeAxios = err as {
      response?: {
        data?: unknown;
        status?: number;
      };
      message?: string;
    };
    const response = maybeAxios.response;
    if (response) {
      const status = response.status;
      if (response.data instanceof Blob) {
        try {
          const text = await response.data.text();
          const json = JSON.parse(text);
          if (json && typeof json === 'object') {
            const errObj = (json as Record<string, unknown>).error as Record<string, unknown> | undefined;
            const message = (errObj?.message as string) || (json as Record<string, unknown>).message || maybeAxios.message || '请求失败';
            const customErr = new Error(String(message)) as WorkspaceServiceError;
            customErr.code = (errObj?.code as string) || undefined;
            customErr.requestId = ((json as Record<string, unknown>).request_id as string) || undefined;
            customErr.status = status;
            return customErr;
          }
        } catch {
          // 非 JSON blob，降级回退
        }
      } else if (response.data && typeof response.data === 'object') {
        const json = response.data as Record<string, unknown>;
        const errObj = json.error as Record<string, unknown> | undefined;
        const message = (errObj?.message as string) || (json.message as string) || maybeAxios.message || '请求失败';
        const customErr = new Error(String(message)) as WorkspaceServiceError;
        customErr.code = (errObj?.code as string) || undefined;
        customErr.requestId = (json.request_id as string) || undefined;
        customErr.status = status;
        return customErr;
      }
    }
  }
  return (err instanceof Error ? err : new Error(String(err))) as WorkspaceServiceError;
}

export async function getWorkspaceCapabilities(
  projectId: string,
  threadId: string,
  signal?: AbortSignal,
): Promise<WorkspaceCapabilities> {
  try {
    const res = await platformHttpClient.get<WorkspaceCapabilities>(
      `/api/langgraph/threads/${encodeURIComponent(threadId)}/capabilities`,
      {
        headers: { 'x-project-id': projectId },
        signal,
      },
    );
    return res.data;
  } catch (err) {
    throw await unwrapWorkspaceError(err);
  }
}

export async function getWorkspaceTree(
  projectId: string,
  threadId: string,
  params: { path?: string; limit?: number; cursor?: string } = {},
  signal?: AbortSignal,
): Promise<WorkspacePage<WorkspaceEntry>> {
  try {
    const res = await platformHttpClient.get<WorkspacePage<WorkspaceEntry>>(
      `/api/langgraph/threads/${encodeURIComponent(threadId)}/workspace/tree`,
      {
        params: {
          path: params.path || '/workspace',
          ...(params.limit ? { limit: params.limit } : {}),
          ...(params.cursor ? { cursor: params.cursor } : {}),
        },
        headers: { 'x-project-id': projectId },
        signal,
      },
    );
    return res.data;
  } catch (err) {
    throw await unwrapWorkspaceError(err);
  }
}

export async function getArtifacts(
  projectId: string,
  threadId: string,
  params: { limit?: number; cursor?: string } = {},
  signal?: AbortSignal,
): Promise<WorkspacePage<ArtifactRef>> {
  try {
    const res = await platformHttpClient.get<WorkspacePage<ArtifactRef>>(
      `/api/langgraph/threads/${encodeURIComponent(threadId)}/artifacts`,
      {
        params: {
          ...(params.limit ? { limit: params.limit } : {}),
          ...(params.cursor ? { cursor: params.cursor } : {}),
        },
        headers: { 'x-project-id': projectId },
        signal,
      },
    );
    return res.data;
  } catch (err) {
    throw await unwrapWorkspaceError(err);
  }
}

export async function getWorkspacePreview(
  projectId: string,
  threadId: string,
  path: string,
  signal?: AbortSignal,
): Promise<WorkspacePreviewResult> {
  let res;
  try {
    res = await platformHttpClient.get(
      `/api/langgraph/threads/${encodeURIComponent(threadId)}/workspace/preview`,
      {
        params: { path },
        headers: { 'x-project-id': projectId },
        responseType: 'blob',
        signal,
      },
    );
  } catch (err) {
    throw await unwrapWorkspaceError(err);
  }

  const contentType = (res.headers['content-type'] as string) || '';

  const blobToText = async (data: unknown): Promise<string> => {
    if (typeof data === 'string') return data;
    if (typeof data === 'object' && data !== null && !(data instanceof Blob)) {
      return JSON.stringify(data);
    }
    const blob = data as Blob;
    if (typeof blob.text === 'function') {
      return await blob.text();
    }
    return new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result as string);
      reader.onerror = () => reject(reader.error);
      reader.readAsText(blob);
    });
  };

  if (contentType.includes('application/json')) {
    const textData = await blobToText(res.data);
    const parsed = JSON.parse(textData) as TextPreview;
    return {
      kind: parsed.preview_kind,
      textPreview: parsed,
    };
  }

  if (contentType.includes('text/html')) {
    const htmlText = await blobToText(res.data);
    return {
      kind: 'html-sandbox',
      htmlContent: htmlText,
    };
  }

  if (contentType.startsWith('image/')) {
    return {
      kind: 'image',
      imageBlob: res.data as Blob,
    };
  }

  return {
    kind: 'download',
    downloadOnly: true,
  };
}

export async function getWorkspaceContentBlob(
  projectId: string,
  threadId: string,
  path: string,
  signal?: AbortSignal,
): Promise<{ blob: Blob; fileName: string }> {
  let res;
  try {
    res = await platformHttpClient.get(
      `/api/langgraph/threads/${encodeURIComponent(threadId)}/workspace/content`,
      {
        params: { path },
        headers: { 'x-project-id': projectId },
        responseType: 'blob',
        signal,
      },
    );
  } catch (err) {
    throw await unwrapWorkspaceError(err);
  }

  let fileName = path.split('/').filter(Boolean).pop() || 'file';
  const disposition = res.headers['content-disposition'];
  if (typeof disposition === 'string') {
    const match = disposition.match(/filename\*?=(?:UTF-8'')?["']?([^"';]+)["']?/i);
    if (match?.[1]) {
      try {
        fileName = decodeURIComponent(match[1]);
      } catch {
        fileName = match[1];
      }
    }
  }

  return {
    blob: res.data as Blob,
    fileName,
  };
}

export function triggerBlobDownload(blob: Blob, fileName: string): void {
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = objectUrl;
  anchor.download = fileName;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  setTimeout(() => {
    URL.revokeObjectURL(objectUrl);
  }, 1000);
}

export async function downloadWorkspaceZip(
  projectId: string,
  threadId: string,
  signal?: AbortSignal,
): Promise<void> {
  let res;
  try {
    res = await platformHttpClient.get(
      `/api/langgraph/threads/${encodeURIComponent(threadId)}/workspace/zip`,
      {
        headers: { 'x-project-id': projectId },
        responseType: 'blob',
        signal,
      },
    );
  } catch (err) {
    throw await unwrapWorkspaceError(err);
  }

  let fileName = `workspace-${threadId.slice(0, 8)}.zip`;
  const disposition = res.headers['content-disposition'];
  if (typeof disposition === 'string') {
    const match = disposition.match(/filename\*?=(?:UTF-8'')?["']?([^"';]+)["']?/i);
    if (match?.[1]) {
      try {
        fileName = decodeURIComponent(match[1]);
      } catch {
        fileName = match[1];
      }
    }
  }

  triggerBlobDownload(res.data as Blob, fileName);
}
