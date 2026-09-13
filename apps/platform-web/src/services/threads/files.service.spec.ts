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
  getThreadFileBlob,
  isValidFileRef,
  previewThreadFileInNewTab,
  uploadThreadFile,
} from "./files.service";

describe("files.service", () => {
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
    if (!URL.createObjectURL) {
      URL.createObjectURL = vi.fn((blob: Blob) => `blob:mock-url-${blob.size}`);
    }
    if (!URL.revokeObjectURL) {
      URL.revokeObjectURL = vi.fn();
    }
  });

  it("validates RuntimeFileRef v1 correctly", () => {
    const valid = {
      version: 1,
      path: "/workspace/uploads/test.pdf",
      file_name: "test.pdf",
      mime_type: "application/pdf",
      size_bytes: 1024,
      sha256: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    };
    expect(isValidFileRef(valid)).toBe(true);

    // Invalid version
    expect(isValidFileRef({ ...valid, version: 2 })).toBe(false);

    // Invalid path prefix
    expect(isValidFileRef({ ...valid, path: "/tmp/evil.pdf" })).toBe(false);

    // Invalid sha256
    expect(isValidFileRef({ ...valid, sha256: "not-a-hash" })).toBe(false);

    // Invalid size
    expect(isValidFileRef({ ...valid, size_bytes: 0 })).toBe(false);
  });

  it("calculates sha256 for a document blob", async () => {
    const blob = new Blob(["hello document"], { type: "text/plain" });
    const hash = await calculateFileSha256(blob);
    expect(hash).toHaveLength(64);
  });

  it("uploads a file and validates returned RuntimeFileRef", async () => {
    const payload = {
      version: 1,
      path: "/workspace/uploads/doc.pdf",
      file_name: "合同.pdf",
      mime_type: "application/pdf",
      size_bytes: 14,
      sha256: "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9",
    };
    platformHttpClientMock.put.mockResolvedValueOnce({ data: payload });

    const file = new File(["hello document"], "合同.pdf", { type: "application/pdf" });
    const result = await uploadThreadFile(
      "proj-1",
      "th-1",
      "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9",
      file,
    );
    expect(result).toEqual(payload);
    expect(platformHttpClientMock.put).toHaveBeenCalledWith(
      "/api/langgraph/threads/th-1/files/uploads/b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9",
      file,
      {
        params: {
          file_name: "合同.pdf",
        },
        headers: {
          "x-project-id": "proj-1",
          "Content-Type": "application/pdf",
        },
      },
    );
  });

  it("fetches file blob with authorization headers", async () => {
    const mockBlob = new Blob(["pdf binary"], { type: "application/pdf" });
    platformHttpClientMock.get.mockResolvedValueOnce({ data: mockBlob });

    const blob = await getThreadFileBlob(
      "proj-1",
      "th-1",
      "/workspace/uploads/doc.pdf",
    );
    expect(blob).toBe(mockBlob);
    expect(platformHttpClientMock.get).toHaveBeenCalledWith(
      "/api/langgraph/threads/th-1/files/content",
      {
        params: { path: "/workspace/uploads/doc.pdf" },
        headers: { "x-project-id": "proj-1" },
        responseType: "blob",
      },
    );
  });

  it("previews text/csv documents in a new tab as HTML table avoiding direct download", async () => {
    const csvContent = "姓名,部门,薪资\n张三,技术部,20000\n李四,产品部,18000";
    const csvBlob = new Blob([csvContent], { type: "text/csv" });
    if (!csvBlob.text) {
      csvBlob.text = async () => csvContent;
    }
    platformHttpClientMock.get.mockResolvedValueOnce({ data: csvBlob });

    let openedUrl = "";
    vi.spyOn(window, "open").mockImplementation((url) => {
      openedUrl = String(url);
      return {} as Window;
    });

    await previewThreadFileInNewTab("proj-1", "th-1", "/workspace/uploads/data.csv", "数据.csv");

    expect(window.open).toHaveBeenCalledTimes(1);
    expect(openedUrl).toMatch(/^blob:/);
  });

  it("previews markdown and txt documents with UTF-8 encoding preventing garbled characters", async () => {
    const mdContent = "# 平台规范\n这是一份重要的中文 Markdown 规范文档。";
    const mdBlob = new Blob([mdContent], { type: "text/markdown" });
    if (!mdBlob.text) {
      mdBlob.text = async () => mdContent;
    }
    platformHttpClientMock.get.mockResolvedValueOnce({ data: mdBlob });

    let openedUrl = "";
    vi.spyOn(window, "open").mockImplementation((url) => {
      openedUrl = String(url);
      return {} as Window;
    });

    await previewThreadFileInNewTab("proj-1", "th-1", "/workspace/uploads/guide.md", "guide.md");

    expect(window.open).toHaveBeenCalledTimes(1);
    expect(openedUrl).toMatch(/^blob:/);
  });
});
