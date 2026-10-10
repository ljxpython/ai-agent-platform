import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import ThreadFile from "./ThreadFile.vue";
import type { RuntimeFileRef } from "@/services/threads/files.service";

const downloadThreadFileMock = vi.fn().mockResolvedValue(undefined);
const previewThreadFileInNewTabMock = vi.fn().mockResolvedValue(undefined);

vi.mock("@/services/threads/files.service", () => ({
  downloadThreadFile: (...args: unknown[]) => downloadThreadFileMock(...args),
  previewThreadFileInNewTab: (...args: unknown[]) =>
    previewThreadFileInNewTabMock(...args),
}));

describe("ThreadFile.vue", () => {
  function createWrapper(fileRef: RuntimeFileRef) {
    return mount(ThreadFile, {
      props: {
        projectId: "proj-test",
        threadId: "thread-test",
        fileRef,
      },
      global: {
        stubs: {
          BaseIcon: true,
        },
      },
    });
  }

  describe("fileBadge calculation", () => {
    it("renders DOC badge for docx files", () => {
      const ref: RuntimeFileRef = {
        path: "/workspace/uploads/10.docx",
        file_name: "10.docx",
        mime_type:
          "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        size_bytes: 10240,
        sha256: "abcdef123456",
      };
      const wrapper = createWrapper(ref);
      expect(wrapper.text()).toContain("DOC");
      expect(wrapper.find(".font-mono.font-bold").text()).toBe("DOC");
    });

    it("renders PPT badge for pptx files", () => {
      const ref: RuntimeFileRef = {
        path: "/workspace/uploads/slides.pptx",
        file_name: "slides.pptx",
        mime_type:
          "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        size_bytes: 20480,
        sha256: "123456abcdef",
      };
      const wrapper = createWrapper(ref);
      expect(wrapper.find(".font-mono.font-bold").text()).toBe("PPT");
    });

    it("renders XLS badge for xlsx files", () => {
      const ref: RuntimeFileRef = {
        path: "/workspace/uploads/budget.xlsx",
        file_name: "budget.xlsx",
        mime_type:
          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        size_bytes: 4096,
        sha256: "fedcba654321",
      };
      const wrapper = createWrapper(ref);
      expect(wrapper.find(".font-mono.font-bold").text()).toBe("XLS");
    });

    it("renders PDF badge for pdf files", () => {
      const ref: RuntimeFileRef = {
        path: "/workspace/uploads/doc.pdf",
        file_name: "doc.pdf",
        mime_type: "application/pdf",
        size_bytes: 8192,
        sha256: "9876543210ab",
      };
      const wrapper = createWrapper(ref);
      expect(wrapper.find(".font-mono.font-bold").text()).toBe("PDF");
    });

    it("renders MD badge for markdown files", () => {
      const ref: RuntimeFileRef = {
        path: "/workspace/uploads/readme.md",
        file_name: "readme.md",
        mime_type: "text/markdown",
        size_bytes: 512,
        sha256: "112233445566",
      };
      const wrapper = createWrapper(ref);
      expect(wrapper.find(".font-mono.font-bold").text()).toBe("MD");
    });
  });

  describe("canPreview and action buttons", () => {
    it("hides preview button and only shows download button for docx files", () => {
      const ref: RuntimeFileRef = {
        path: "/workspace/uploads/10.docx",
        file_name: "10.docx",
        mime_type:
          "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        size_bytes: 10240,
        sha256: "abcdef123456",
      };
      const wrapper = createWrapper(ref);

      const buttons = wrapper.findAll("button");
      expect(buttons).toHaveLength(1);
      expect(buttons[0].text()).toContain("下载");
      expect(wrapper.text()).not.toContain("预览");
    });

    it("hides preview button and only shows download button for pptx files", () => {
      const ref: RuntimeFileRef = {
        path: "/workspace/uploads/slides.pptx",
        file_name: "slides.pptx",
        mime_type:
          "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        size_bytes: 20480,
        sha256: "123456abcdef",
      };
      const wrapper = createWrapper(ref);

      const buttons = wrapper.findAll("button");
      expect(buttons).toHaveLength(1);
      expect(buttons[0].text()).toContain("下载");
      expect(wrapper.text()).not.toContain("预览");
    });

    it("shows both preview and download buttons for pdf files", () => {
      const ref: RuntimeFileRef = {
        path: "/workspace/uploads/doc.pdf",
        file_name: "doc.pdf",
        mime_type: "application/pdf",
        size_bytes: 8192,
        sha256: "9876543210ab",
      };
      const wrapper = createWrapper(ref);

      const buttons = wrapper.findAll("button");
      expect(buttons).toHaveLength(2);
      expect(buttons[0].text()).toContain("预览");
      expect(buttons[1].text()).toContain("下载");
    });

    it("shows both preview and download buttons for csv files", () => {
      const ref: RuntimeFileRef = {
        path: "/workspace/uploads/data.csv",
        file_name: "data.csv",
        mime_type: "text/csv",
        size_bytes: 1024,
        sha256: "aabbccddeeff",
      };
      const wrapper = createWrapper(ref);

      const buttons = wrapper.findAll("button");
      expect(buttons).toHaveLength(2);
      expect(buttons[0].text()).toContain("预览");
      expect(buttons[1].text()).toContain("下载");
    });

    it("calls downloadThreadFile when clicking download on docx", async () => {
      downloadThreadFileMock.mockClear();
      const ref: RuntimeFileRef = {
        path: "/workspace/uploads/10.docx",
        file_name: "10.docx",
        mime_type:
          "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        size_bytes: 10240,
        sha256: "abcdef123456",
      };
      const wrapper = createWrapper(ref);

      const downloadBtn = wrapper.find("button");
      await downloadBtn.trigger("click");

      expect(downloadThreadFileMock).toHaveBeenCalledWith(
        "proj-test",
        "thread-test",
        "/workspace/uploads/10.docx",
        "10.docx",
      );
    });

    it("calls previewThreadFileInNewTab when clicking preview on pdf", async () => {
      previewThreadFileInNewTabMock.mockClear();
      const ref: RuntimeFileRef = {
        path: "/workspace/uploads/doc.pdf",
        file_name: "doc.pdf",
        mime_type: "application/pdf",
        size_bytes: 8192,
        sha256: "9876543210ab",
      };
      const wrapper = createWrapper(ref);

      const previewBtn = wrapper.findAll("button")[0];
      await previewBtn.trigger("click");

      expect(previewThreadFileInNewTabMock).toHaveBeenCalledWith(
        "proj-test",
        "thread-test",
        "/workspace/uploads/doc.pdf",
        "doc.pdf",
      );
    });
  });
});
