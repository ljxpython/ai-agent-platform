import { beforeEach, describe, expect, it, vi } from "vitest";

const { platformHttpClientMock } = vi.hoisted(() => ({
  platformHttpClientMock: {
    get: vi.fn(),
    put: vi.fn(),
  },
}));

vi.mock("@/services/http/client", () => ({
  platformHttpClient: platformHttpClientMock,
}));

import {
  calculateFileSha256,
  getThreadImageBlob,
  isValidImageRef,
  uploadThreadImage,
} from "./images.service";

describe("images.service", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    if (!Blob.prototype.arrayBuffer) {
      Blob.prototype.arrayBuffer = async function () {
        return new Promise((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = () => resolve(reader.result as ArrayBuffer);
          reader.onerror = () => reject(reader.error);
          reader.readAsArrayBuffer(this);
        });
      };
    }
  });

  it("validates RuntimeImageRef v1 correctly", () => {
    const valid = {
      version: 1,
      path: "/workspace/uploads/test.png",
      mime_type: "image/png",
      size_bytes: 1024,
      sha256: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    };
    expect(isValidImageRef(valid)).toBe(true);

    // Invalid version
    expect(isValidImageRef({ ...valid, version: 2 })).toBe(false);

    // Invalid path prefix
    expect(isValidImageRef({ ...valid, path: "/tmp/evil.png" })).toBe(false);

    // Invalid mime
    expect(isValidImageRef({ ...valid, mime_type: "image/gif" })).toBe(false);

    // Invalid sha256
    expect(isValidImageRef({ ...valid, sha256: "not-a-hash" })).toBe(false);

    // Invalid size
    expect(isValidImageRef({ ...valid, size_bytes: -1 })).toBe(false);
  });

  it("calculates sha256 for a file blob", async () => {
    const blob = new Blob(["hello world"], { type: "text/plain" });
    const hash = await calculateFileSha256(blob);
    // sha256 of "hello world"
    expect(hash).toBe("b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9");
  });

  it("uploads an image and validates returned RuntimeImageRef", async () => {
    const payload = {
      version: 1,
      path: "/workspace/uploads/pic.png",
      mime_type: "image/png",
      size_bytes: 11,
      sha256: "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9",
    };
    platformHttpClientMock.put.mockResolvedValueOnce({ data: payload });

    const file = new File(["hello world"], "pic.png", { type: "image/png" });
    const result = await uploadThreadImage(
      "proj-1",
      "th-1",
      "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9",
      file,
    );
    expect(result).toEqual(payload);
    expect(platformHttpClientMock.put).toHaveBeenCalledWith(
      "/api/langgraph/threads/th-1/images/uploads/b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9",
      file,
      {
        headers: {
          "x-project-id": "proj-1",
          "Content-Type": "image/png",
        },
      },
    );
  });

  it("fetches image blob with authorization headers", async () => {
    const mockBlob = new Blob(["binary data"], { type: "image/png" });
    platformHttpClientMock.get.mockResolvedValueOnce({ data: mockBlob });

    const blob = await getThreadImageBlob(
      "proj-1",
      "th-1",
      "/workspace/uploads/pic.png",
    );
    expect(blob).toBe(mockBlob);
    expect(platformHttpClientMock.get).toHaveBeenCalledWith(
      "/api/langgraph/threads/th-1/images/content",
      {
        params: { path: "/workspace/uploads/pic.png" },
        headers: { "x-project-id": "proj-1" },
        responseType: "blob",
      },
    );
  });
});
