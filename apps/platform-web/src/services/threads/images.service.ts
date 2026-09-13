import { platformHttpClient } from "@/services/http/client";

export interface RuntimeImageRef {
  version: 1;
  path: string;
  mime_type: "image/png" | "image/jpeg" | "image/webp";
  size_bytes: number;
  sha256: string;
}

export const ALLOWED_IMAGE_MIMES = [
  "image/png",
  "image/jpeg",
  "image/webp",
] as const;

export function isValidImageRef(val: unknown): val is RuntimeImageRef {
  if (!val || typeof val !== "object" || Array.isArray(val)) {
    return false;
  }
  const obj = val as Record<string, unknown>;
  if (obj.version !== 1) {
    return false;
  }
  if (typeof obj.path !== "string" || !obj.path) {
    return false;
  }
  const allowedPrefixes = [
    "/workspace/uploads/",
    "/workspace/generated/",
    "/workspace/charts/",
  ];
  if (!allowedPrefixes.some((p) => (obj.path as string).startsWith(p))) {
    return false;
  }
  if (
    typeof obj.mime_type !== "string" ||
    !ALLOWED_IMAGE_MIMES.includes(obj.mime_type as (typeof ALLOWED_IMAGE_MIMES)[number])
  ) {
    return false;
  }
  if (typeof obj.size_bytes !== "number" || obj.size_bytes <= 0) {
    return false;
  }
  if (
    typeof obj.sha256 !== "string" ||
    obj.sha256.length !== 64 ||
    !/^[0-9a-f]{64}$/.test(obj.sha256)
  ) {
    return false;
  }
  return true;
}

export async function calculateFileSha256(file: Blob): Promise<string> {
  const buffer = await file.arrayBuffer();
  const digest = await crypto.subtle.digest("SHA-256", buffer);
  const array = Array.from(new Uint8Array(digest));
  return array.map((b) => b.toString(16).padStart(2, "0")).join("");
}

export async function uploadThreadImage(
  projectId: string,
  threadId: string,
  sha256: string,
  file: Blob,
): Promise<RuntimeImageRef> {
  const { data } = await platformHttpClient.put<RuntimeImageRef>(
    `/api/langgraph/threads/${encodeURIComponent(threadId)}/images/uploads/${encodeURIComponent(sha256)}`,
    file,
    {
      headers: {
        "x-project-id": projectId,
        "Content-Type": file.type,
      },
    },
  );
  if (!isValidImageRef(data)) {
    throw new Error("服务端返回的图片引用格式不合法");
  }
  return data;
}

export async function getThreadImageBlob(
  projectId: string,
  threadId: string,
  path: string,
): Promise<Blob> {
  const response = await platformHttpClient.get(
    `/api/langgraph/threads/${encodeURIComponent(threadId)}/images/content`,
    {
      params: { path },
      headers: {
        "x-project-id": projectId,
      },
      responseType: "blob",
    },
  );
  return response.data;
}
