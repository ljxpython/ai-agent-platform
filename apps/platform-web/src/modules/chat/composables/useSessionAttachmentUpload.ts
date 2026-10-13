import {
  calculateFileSha256 as calculateImageSha256,
  uploadThreadImage,
} from "@/services/threads/images.service";
import {
  calculateFileSha256,
  uploadThreadFile,
} from "@/services/threads/files.service";
import {
  createRuntimeFileTextBlock,
  createRuntimeImageTextBlock,
} from "@/utils/chat-content";

export function hasAttachmentsToUpload(rawContent: unknown): boolean {
  if (!Array.isArray(rawContent)) return false;
  return rawContent.some(
    (item) =>
      item &&
      typeof item === "object" &&
      ["image", "file"].includes(
        (item as Record<string, unknown>).type as string,
      ) &&
      (item as Record<string, unknown>).file instanceof Blob,
  );
}

export async function uploadSessionAttachmentsAsync(
  projectId: string,
  targetThreadId: string,
  rawContent: unknown[],
): Promise<unknown> {
  return Promise.all(
    rawContent.map(async (item) => {
      if (!item || typeof item !== "object") return item;
      const block = item as Record<string, unknown>;
      if (block.type === "image" && block.file instanceof Blob) {
        const file = block.file;
        const metadata = (block.metadata || {}) as Record<string, unknown>;
        const filename =
          typeof metadata.name === "string"
            ? metadata.name
            : typeof metadata.filename === "string"
              ? metadata.filename
              : file instanceof File && file.name
                ? file.name
                : "image.png";
        const sha256 = await calculateImageSha256(file);
        const actualFileName =
          file instanceof File && file.name
            ? file.name
            : typeof metadata.name === "string"
              ? metadata.name
              : undefined;
        const ref = await uploadThreadImage(
          projectId,
          targetThreadId,
          sha256,
          file,
          actualFileName,
        );
        const shareToKnowledge = Boolean(block.shareToKnowledge);
        return createRuntimeImageTextBlock(filename, ref, shareToKnowledge);
      }
      if (block.type === "file" && block.file instanceof Blob) {
        const file = block.file as File;
        const metadata = (block.metadata || {}) as Record<string, unknown>;
        const filename =
          typeof metadata.name === "string"
            ? metadata.name
            : typeof metadata.filename === "string"
              ? metadata.filename
              : file.name || "document";
        const sha256 = await calculateFileSha256(file);
        const ref = await uploadThreadFile(
          projectId,
          targetThreadId,
          sha256,
          file,
        );
        const shareToKnowledge = Boolean(block.shareToKnowledge);
        return createRuntimeFileTextBlock(filename, ref, shareToKnowledge);
      }
      return item;
    }),
  );
}

export function createSessionAttachmentUploader(projectId: string) {
  return function prepareMessageAttachments(
    targetThreadId: string,
    rawContent: unknown,
  ): unknown | Promise<unknown> {
    if (!hasAttachmentsToUpload(rawContent)) {
      return rawContent;
    }
    return uploadSessionAttachmentsAsync(
      projectId,
      targetThreadId,
      rawContent as unknown[],
    );
  };
}
