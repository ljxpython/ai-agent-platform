"use client";

import React, { useState, useMemo, useCallback } from "react";
import {
  ChevronDown,
  ChevronRight,
  ChevronUp,
  Terminal,
  CheckCircle,
  AlertCircle,
  Loader,
  Eye,
  X,
} from "lucide-react";
import { AIMessage, ToolMessage } from "@langchain/langgraph-sdk";

// Helper function to detect and extract images from text (both base64 and URLs)
function extractImagesFromText(text: string): Array<{ data: string; type: string; original: string; isUrl: boolean }> {
  const images: Array<{ data: string; type: string; original: string; isUrl: boolean }> = [];

  // Pattern 1: Standard data URL format
  const dataUrlPattern = /data:image\/(png|jpeg|jpg|gif|webp|bmp);base64,([A-Za-z0-9+/=]+)/gi;
  let match;
  while ((match = dataUrlPattern.exec(text)) !== null) {
    images.push({
      data: match[0],
      type: match[1],
      original: match[0],
      isUrl: false
    });
  }

  // Pattern 2: HTTP/HTTPS image URLs
  const imageUrlPattern = /https?:\/\/[^\s<>"']+\.(?:png|jpe?g|gif|webp|bmp|svg)(?:\?[^\s<>"']*)?(?:#[^\s<>"']*)?/gi;
  while ((match = imageUrlPattern.exec(text)) !== null) {
    const url = match[0];
    const extension = url.match(/\.([^.?#]+)(?:\?|#|$)/)?.[1]?.toLowerCase() || 'unknown';
    images.push({
      data: url,
      type: extension,
      original: url,
      isUrl: true
    });
  }

  // Pattern 3: URLs that might be images (common image hosting patterns)
  const possibleImageUrlPatterns = [
    // Alipay CDN pattern (like the example provided)
    /https?:\/\/[^\s<>"']*\.alipayobjects\.com\/[^\s<>"']+/gi,
    // Common image hosting patterns
    /https?:\/\/[^\s<>"']*(?:imgur|cloudinary|amazonaws|googleusercontent|github|githubusercontent)\.com\/[^\s<>"']+/gi,
    // Generic patterns that often contain images
    /https?:\/\/[^\s<>"']*\/[^\s<>"']*(?:image|img|photo|picture|screenshot|pic)[^\s<>"']*/gi,
  ];

  possibleImageUrlPatterns.forEach(pattern => {
    let urlMatch;
    while ((urlMatch = pattern.exec(text)) !== null) {
      const url = urlMatch[0];
      // Avoid duplicates
      if (!images.some(img => img.data === url)) {
        images.push({
          data: url,
          type: 'unknown',
          original: url,
          isUrl: true
        });
      }
    }
  });

  // Pattern 4: JSON field with base64 data (common patterns)
  const jsonPatterns = [
    /"base64Data":\s*"([A-Za-z0-9+/=]{100,})"/gi,
    /"base64":\s*"([A-Za-z0-9+/=]{100,})"/gi,
    /"image":\s*"([A-Za-z0-9+/=]{100,})"/gi,
    /"screenshot":\s*"([A-Za-z0-9+/=]{100,})"/gi,
    /"imageData":\s*"([A-Za-z0-9+/=]{100,})"/gi
  ];

  jsonPatterns.forEach(pattern => {
    let jsonMatch;
    while ((jsonMatch = pattern.exec(text)) !== null) {
      const base64Data = jsonMatch[1];
      // Validate base64 format and reasonable length
      if (base64Data.length > 100 && base64Data.length % 4 === 0) {
        images.push({
          data: `data:image/png;base64,${base64Data}`,
          type: 'png',
          original: jsonMatch[0],
          isUrl: false
        });
      }
    }
  });

  // Pattern 5: Look for very long base64 strings that might be images
  const longBase64Pattern = /([A-Za-z0-9+/=]{1000,})/g;
  while ((match = longBase64Pattern.exec(text)) !== null) {
    const base64Data = match[1];
    // Additional validation: check if it starts with common image signatures
    if (base64Data.length % 4 === 0 &&
        (base64Data.startsWith('iVBORw0KGgo') || // PNG
         base64Data.startsWith('/9j/') || // JPEG
         base64Data.startsWith('R0lGOD') || // GIF
         base64Data.startsWith('UklGR'))) { // WebP
      images.push({
        data: `data:image/png;base64,${base64Data}`,
        type: 'png',
        original: match[0],
        isUrl: false
      });
    }
  }

  // Remove duplicates based on data content
  const uniqueImages = images.filter((img, index, self) =>
    index === self.findIndex(i => i.data === img.data)
  );

  return uniqueImages;
}

// Image Preview Modal Component
function ImagePreviewModal({
  src,
  isOpen,
  onClose
}: {
  src: string;
  isOpen: boolean;
  onClose: () => void;
}) {
  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50"
      onClick={onClose}
    >
      <div className="relative max-w-[90vw] max-h-[90vh]">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-white hover:text-gray-300 z-10"
        >
          <X size={24} />
        </button>
        <img
          src={src}
          alt="Preview"
          className="max-w-full max-h-full object-contain"
          onClick={(e) => e.stopPropagation()}
        />
      </div>
    </div>
  );
}
// @ts-expect-error  MS80OmFIVnBZMlhtblk3a3ZiUG1yS002UzJoT1J3PT06MmY1YTMyMzk=

// Image Display Component
function ImagePreview({ images }: { images: Array<{ data: string; type: string; original: string; isUrl: boolean }> }) {
  const [selectedImage, setSelectedImage] = useState<string | null>(null);
  const [loadedImages, setLoadedImages] = useState<Set<number>>(new Set());
  const [failedImages, setFailedImages] = useState<Set<number>>(new Set());

  if (images.length === 0) return null;

  const handleImageLoad = (index: number) => {
    setLoadedImages(prev => new Set(prev).add(index));
  };

  const handleImageError = (index: number) => {
    setFailedImages(prev => new Set(prev).add(index));
  };

  const validImages = images.filter((_, index) => !failedImages.has(index));

  if (validImages.length === 0) return null;

  return (
    <>
      <div className="mt-3 space-y-3">
        {images.map((image, index) => {
          if (failedImages.has(index)) return null;

          return (
            <div
              key={index}
              className="relative group cursor-pointer border border-slate-200 rounded-lg overflow-hidden hover:border-slate-300 hover:shadow-sm transition-all duration-200 bg-white"
              onClick={() => setSelectedImage(image.data)}
            >
              {!loadedImages.has(index) && (
                <div className="absolute inset-0 flex items-center justify-center bg-slate-50">
                  <div className="w-6 h-6 border-2 border-slate-300 border-t-slate-600 rounded-full animate-spin"></div>
                </div>
              )}
              <img
                src={image.data}
                alt={image.isUrl ? `Image from URL ${index + 1}` : `Generated image ${index + 1}`}
                className="w-full h-auto max-w-full object-contain"
                onLoad={() => handleImageLoad(index)}
                onError={() => handleImageError(index)}
                style={{ display: loadedImages.has(index) ? 'block' : 'none' }}
                crossOrigin={image.isUrl ? "anonymous" : undefined}
              />
              {loadedImages.has(index) && (
                <div className="absolute top-2 right-2 bg-slate-800 bg-opacity-70 rounded-full p-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
                  <Eye className="text-white" size={14} />
                </div>
              )}
              {/* Show URL indicator for URL-based images */}
              {image.isUrl && loadedImages.has(index) && (
                <div className="absolute bottom-2 left-2 bg-slate-700 text-white text-xs px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity">
                  URL图片
                </div>
              )}
            </div>
          );
        })}
      </div>

      <ImagePreviewModal
        src={selectedImage || ""}
        isOpen={!!selectedImage}
        onClose={() => setSelectedImage(null)}
      />
    </>
  );
}

interface ToolCallBoxProps {
  toolCall: NonNullable<AIMessage["tool_calls"]>[0];
  toolResult?: ToolMessage;
}

// Type guard to check if a tool call is valid
function isValidToolCall(toolCall: any): toolCall is NonNullable<AIMessage["tool_calls"]>[0] {
  return toolCall &&
         typeof toolCall === 'object' &&
         typeof toolCall.name === 'string' &&
         toolCall.name.trim() !== '' &&
         typeof toolCall.args === 'object';
}
// eslint-disable  Mi80OmFIVnBZMlhtblk3a3ZiUG1yS002UzJoT1J3PT06MmY1YTMyMzk=

export const ToolCallBox = React.memo<ToolCallBoxProps>(({ toolCall, toolResult }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  const { name, args, result, status, images } = useMemo(() => {
    if (!toolCall) {
      return {
        name: "Unknown Tool",
        args: {},
        result: null,
        status: "completed" as const,
        resultText: "",
        images: [],
      };
    }

    const toolName = toolCall.name?.trim() || "Unknown Tool";
    const toolArgs = toolCall.args || {};

    let toolResult_content = null;
    let resultAsText = "";

    if (toolResult) {
      try {
        if (typeof toolResult.content === "string") {
          toolResult_content = JSON.parse(toolResult.content);
          resultAsText = toolResult.content;
        } else {
          toolResult_content = toolResult.content;
          resultAsText = JSON.stringify(toolResult.content, null, 2);
        }
      } catch {
        toolResult_content = toolResult.content;
        resultAsText = String(toolResult.content);
      }
    }

    // Extract images from the result text
    const extractedImages = resultAsText ? extractImagesFromText(resultAsText) : [];

    const toolStatus = "completed"; // Default status

    return {
      name: toolName,
      args: toolArgs,
      result: toolResult_content,
      status: toolStatus,
      images: extractedImages,
    };
  }, [toolCall, toolResult]);

  const statusIcon = useMemo(() => {
    const iconProps = { className: "w-5 h-5" };

    switch (status) {
      case "completed":
        return <CheckCircle {...iconProps} className="w-5 h-5 text-green-600" />;
      case "error":
        return <AlertCircle {...iconProps} className="w-5 h-5 text-red-600" />;
      case "pending":
        return <Loader {...iconProps} className="w-5 h-5 text-blue-600 animate-spin" />;
      default:
        return <Terminal {...iconProps} className="w-5 h-5 text-slate-600" />;
    }
  }, [status]);

  const toggleExpanded = useCallback(() => {
    setIsExpanded((prev) => !prev);
  }, []);

  const hasContent = result || Object.keys(args).length > 0 || images.length > 0;

  return (
    <div className="w-full mb-3 group/toolbox">
      {/* Tool Call Box - 高级简洁设计 */}
      <div className="border border-slate-100 rounded-xl bg-gradient-to-br from-white to-slate-50 shadow-[0_2px_8px_rgba(0,0,0,0.04)] hover:shadow-[0_4px_12px_rgba(0,0,0,0.08)] transition-all duration-300 backdrop-blur-sm">
        <button
          onClick={toggleExpanded}
          className="w-full p-4 flex items-center gap-3 text-left transition-all duration-200 hover:bg-gradient-to-r hover:from-slate-50 hover:to-white cursor-pointer disabled:cursor-default group/tool rounded-xl"
          disabled={!hasContent}
        >
          {hasContent && isExpanded ? (
            <ChevronDown size={16} className="flex-shrink-0 text-slate-500 group-hover/tool:text-slate-700 transition-all duration-200" />
          ) : (
            <ChevronRight size={16} className="flex-shrink-0 text-slate-400 group-hover/tool:text-slate-600 transition-all duration-200" />
          )}
          <div className="flex items-center gap-3 flex-1">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-slate-100 to-slate-200 flex items-center justify-center shadow-md border border-slate-200/50">
              {statusIcon}
            </div>
            <span className="text-base font-semibold text-slate-800 group-hover/tool:text-slate-900 transition-colors tracking-wide">{name}</span>
          </div>
          {hasContent && (
            <div className="flex items-center gap-2">
              <div className="hidden sm:block text-xs text-slate-500 group-hover/tool:text-slate-600 transition-colors">
                {isExpanded ? '收起' : '展开'}
              </div>
              <div className="flex items-center justify-center w-6 h-6 rounded-lg bg-slate-100 hover:bg-slate-200 transition-colors border border-slate-200">
                {hasContent && isExpanded ? (
                  <ChevronUp size={12} className="text-slate-600" />
                ) : (
                  <ChevronDown size={12} className="text-slate-600" />
                )}
              </div>
            </div>
          )}
        </button>

        {isExpanded && hasContent && (
          <div className="px-5 pb-5 border-t border-slate-100/80 pt-4">
            {Object.keys(args).length > 0 && (
              <div className="mb-4">
                <div className="flex items-center gap-2 mb-3">
                  <div className="w-2 h-2 rounded-full bg-blue-400"></div>
                  <h4 className="text-xs font-semibold text-slate-600 uppercase tracking-wider">
                    参数
                  </h4>
                </div>
                <div className="bg-white/70 border border-slate-200/60 rounded-lg p-4 backdrop-blur-sm">
                  <pre className="text-xs font-mono text-slate-700 leading-relaxed overflow-x-auto whitespace-pre-wrap break-all m-0">
                    {JSON.stringify(args, null, 2)}
                  </pre>
                </div>
              </div>
            )}
            {result && (
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <div className="w-2 h-2 rounded-full bg-green-400"></div>
                  <h4 className="text-xs font-semibold text-slate-600 uppercase tracking-wider">
                    结果
                  </h4>
                </div>
                <div className="bg-white/70 border border-slate-200/60 rounded-lg p-4 backdrop-blur-sm">
                  <pre className="text-xs font-mono text-slate-700 leading-relaxed overflow-x-auto whitespace-pre-wrap break-all m-0">
                    {typeof result === "string"
                      ? result
                      : JSON.stringify(result, null, 2)}
                  </pre>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Images displayed outside and below the tool box */}
      <ImagePreview images={images} />
    </div>
  );
});

ToolCallBox.displayName = "ToolCallBox";
// TODO  My80OmFIVnBZMlhtblk3a3ZiUG1yS002UzJoT1J3PT06MmY1YTMyMzk=

export function ToolCalls({
  toolCalls,
  toolResults,
}: {
  toolCalls: AIMessage["tool_calls"];
  toolResults?: ToolMessage[];
}) {
  if (!toolCalls || toolCalls.length === 0) return null;

  // Filter out invalid tool calls using type guard
  const validToolCalls = toolCalls.filter(isValidToolCall);

  if (validToolCalls.length === 0) return null;

  return (
    <div className="w-full">
      {validToolCalls.map((tc, idx) => {
        // Find corresponding tool result by tool_call_id
        const correspondingResult = toolResults?.find(
          (result) => result.tool_call_id === tc.id
        );

        return (
          <ToolCallBox
            key={tc.id || idx}
            toolCall={tc}
            toolResult={correspondingResult}
          />
        );
      })}
    </div>
  );
}

// Keep the old ToolResult component for backward compatibility
export function ToolResult({ message }: { message: ToolMessage }) {
  return null; // Hide individual tool results since they're now combined
}
