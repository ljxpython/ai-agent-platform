import React, { useEffect } from 'react';
import { StreamResponseMessage } from '../api';
import { FormattedOutput as OutputFormatter } from '../utils';
import '../../../styles/GeminiStyle.css';

interface AnalysisTabProps {
  analysisContent: string;
  isStreaming: boolean;
  hasContent: boolean;
  scrollToBottom: () => void;
}

/**
 * 查询分析标签内容组件 - Gemini风格
 */
const AnalysisTab: React.FC<AnalysisTabProps> = ({
  analysisContent,
  isStreaming,
  hasContent,
  scrollToBottom
}) => {
  // 当内容更新时自动滚动到底部，但只在流式输出时
  useEffect(() => {
    // 只有在流式输出时才自动滚动到底部
    if (hasContent && isStreaming) {
      scrollToBottom();
    }
  }, [analysisContent, hasContent, isStreaming, scrollToBottom]);

  // 处理分析内容，移除用户交互提示和格式化问题
  const processedContent = React.useMemo(() => {
    if (!analysisContent) return '';

    // 移除用户交互提示，但保留用户反馈内容
    let processed = analysisContent
      // 移除输入提示，但不移除后面的所有内容
      .replace(/Enter your response: \u8bf7\u8f93\u5165\u4fee\u6539\u5efa\u8bae\u6216\u8005\u76f4\u63a5\u70b9\u51fb\u540c\u610f(?=\s|$)/, '')
      // 保留用户反馈部分，只移除特定的同意操作标记
      .replace(/---+\n### \u7528\u6237\u5df2\u540c\u610f\u64cd\u4f5c\n---+(?!\n### \u7528\u6237\u53cd\u9988)/, '---\n### 用户已同意操作\n---')
      .replace(/\u5206\u6790\u5df2\u5b8c\u6210/, '');

    // 确保内容中的换行符被正确处理
    processed = processed.replace(/\u3010\u8fd9\u91cc\u5e94\u8be5\u6362\u884c\u3011/g, '\n');

    return processed;
  }, [analysisContent]);

  return (
    <div className="gemini-container analysis-content-container">
      {!analysisContent || analysisContent.trim() === '' ? (
        isStreaming ? (
          <div className="gemini-loading">
            <div className="gemini-loading-dots">
              <div className="gemini-loading-dot"></div>
              <div className="gemini-loading-dot"></div>
              <div className="gemini-loading-dot"></div>
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center p-8 text-center text-gray-500">
            <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round" className="mb-4 text-gray-300">
              <circle cx="11" cy="11" r="8"></circle>
              <path d="m21 21-4.3-4.3"></path>
              <path d="m11 8v6"></path>
              <path d="M8 11h6"></path>
            </svg>
            <h3 className="text-lg font-medium mb-2">输入问题并点击分析</h3>
            <p className="text-sm">请在底部输入框中输入您的问题，然后点击分析按钮开始查询。</p>
          </div>
        )
      ) : (
        <div className="gemini-message">
          <div className="gemini-avatar system">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8"></path>
              <path d="M21 3v5h-5"></path>
            </svg>
          </div>
          <div className="gemini-content">
            <div className="gemini-header">
              <div className="gemini-name">查询分析</div>
            </div>
            <div className="gemini-body">
              <div className="prose prose-sm max-w-none analysis-content overflow-auto" style={{ maxHeight: 'none', overflowY: 'auto' }}>
                <div className="analysis-formatted-content">
                  <OutputFormatter content={processedContent} type="markdown" />
                </div>
              </div>
              {/* 调试信息已移除 */}
              {isStreaming && (
                <div className="gemini-loading mt-2">
                  <div className="gemini-loading-dots">
                    <div className="gemini-loading-dot"></div>
                    <div className="gemini-loading-dot"></div>
                    <div className="gemini-loading-dot"></div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AnalysisTab;
