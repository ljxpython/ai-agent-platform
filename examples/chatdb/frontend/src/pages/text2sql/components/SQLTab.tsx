import React, { useState, useEffect, useRef } from 'react';
import { FormattedOutput as OutputFormatter } from '../utils';
import '../../../styles/GeminiStyle.css';
import '../../../styles/Text2SQL.css';

interface SQLTabProps {
  sqlResult: string | null;
  explanationResult: string | null;
  sqlStreaming: boolean;
  explanationStreaming: boolean;
  sqlHasContent: boolean;
  explanationHasContent: boolean;
}

/**
 * SQL语句及解释标签内容组件 - 简化版本
 */
const SQLTab: React.FC<SQLTabProps> = ({
  sqlResult,
  explanationResult,
  sqlStreaming,
  explanationStreaming,
  sqlHasContent,
  explanationHasContent
}) => {
  const [copiedSQL, setCopiedSQL] = useState(false);

  // 引用解释内容区域DOM元素，用于自动滚动
  const explanationContentRef = useRef<HTMLDivElement>(null);

  // 当解释内容更新或流式状态变化时，自动滚动到底部
  useEffect(() => {
    if (explanationResult && explanationContentRef.current) {
      console.log('解释内容更新，自动滚动到底部，内容长度:', explanationResult.length);
      setTimeout(() => {
        if (explanationContentRef.current) {
          explanationContentRef.current.scrollTop = explanationContentRef.current.scrollHeight;
        }
      }, 50);
    }
  }, [explanationResult]);

  // 复制SQL到剪贴板
  const handleCopySQL = () => {
    if (sqlResult) {
      navigator.clipboard.writeText(sqlResult);
      setCopiedSQL(true);
      setTimeout(() => setCopiedSQL(false), 2000);
    }
  };



  return (
    <div className="text2sql-visualization-tab" style={{ display: 'block', width: '100%' }}>
      {/* SQL语句部分 - 使用与可视化图表相似的卡片样式 */}
      {sqlHasContent ? (
        <div className="text2sql-card mb-4">
          <div className="text2sql-card-header" style={{ background: 'linear-gradient(135deg, rgba(79, 70, 229, 0.1) 0%, rgba(59, 130, 246, 0.1) 100%)' }}>
            <div className="text2sql-card-title">
              <div className="text2sql-card-icon" style={{ background: 'linear-gradient(135deg, rgba(79, 70, 229, 0.2) 0%, rgba(59, 130, 246, 0.2) 100%)' }}>
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  style={{ color: '#4f46e5' }}
                >
                  <path d="M8 9h8"></path>
                  <path d="M8 13h6"></path>
                  <path d="M18 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2Z"></path>
                </svg>
              </div>
              <span>生成的SQL语句</span>
            </div>
            <button
              className="text2sql-card-action"
              onClick={handleCopySQL}
              title="复制SQL"
            >
              {copiedSQL ? (
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M20 6 9 17l-5-5"></path>
                </svg>
              ) : (
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                  <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                </svg>
              )}
            </button>
          </div>
          <div className="text2sql-card-content">
            <div className="text2sql-code text2sql-code-sql">
              {sqlResult ? (
                <OutputFormatter content={sqlResult} type="sql" />
              ) : (
                <div className="gemini-loading">
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
      ) : (
        <div className="text2sql-card mb-4">
          <div className="text2sql-card-header" style={{ background: 'linear-gradient(135deg, rgba(79, 70, 229, 0.1) 0%, rgba(59, 130, 246, 0.1) 100%)' }}>
            <div className="text2sql-card-title">
              <div className="text2sql-card-icon" style={{ background: 'linear-gradient(135deg, rgba(79, 70, 229, 0.2) 0%, rgba(59, 130, 246, 0.2) 100%)' }}>
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  style={{ color: '#4f46e5' }}
                >
                  <path d="M8 9h8"></path>
                  <path d="M8 13h6"></path>
                  <path d="M18 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2Z"></path>
                </svg>
              </div>
              <span>SQL语句</span>
            </div>
          </div>
          <div className="text2sql-card-content">
            <div className="h-20 flex items-center justify-center text-gray-500 italic">
              {sqlStreaming ? (
                <div className="flex flex-col items-center">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500 mb-2"></div>
                  <p>正在生成SQL语句...</p>
                </div>
              ) : (
                <p>暂无SQL语句</p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* SQL解释部分 - 使用与SQL语句相同的卡片样式 */}
      <div className="text2sql-card mb-4">
        <div className="text2sql-card-header" style={{ background: 'linear-gradient(135deg, rgba(79, 70, 229, 0.1) 0%, rgba(59, 130, 246, 0.1) 100%)' }}>
          <div className="text2sql-card-title">
            <div className="text2sql-card-icon" style={{ background: 'linear-gradient(135deg, rgba(79, 70, 229, 0.2) 0%, rgba(59, 130, 246, 0.2) 100%)' }}>
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="24"
                height="24"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                style={{ color: '#4f46e5' }}
              >
                <path d="M12 8v4l3 3m6-3a9 9 0 1 1-18 0 9 9 0 0 1 18 0z"></path>
              </svg>
            </div>
            <span>SQL解释</span>
          </div>
        </div>
        <div className="text2sql-card-content">
          <div
            ref={explanationContentRef}
            className="sql-explanation-content"
            style={{
              display: 'block',
              width: '100%',
              minHeight: '100px',
              maxHeight: 'none',
              overflow: 'auto'
            }}
          >
            {(explanationResult && explanationResult.trim().length > 0) ? (
              <div className="text2sql-explanation">
                <OutputFormatter content={explanationResult} type="markdown" />
                {explanationStreaming && (
                  <span className="typing-cursor"></span>
                )}
              </div>
            ) : (
              <div className="h-20 flex items-center justify-center text-gray-500 italic">
                {explanationStreaming ? (
                  <div className="flex flex-col items-center">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500 mb-2"></div>
                    <p>正在生成SQL解释...</p>
                  </div>
                ) : (
                  <p>暂无SQL解释</p>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
      {/* 添加CSS样式 */}
      <style>{`
        .streaming-content {
          animation: fadeIn 0.3s ease-in-out;
        }

        @keyframes fadeIn {
          from { opacity: 0.7; }
          to { opacity: 1; }
        }

        /* 减少SQL解释区域的间距 */
        .text2sql-explanation p {
          margin: 0.3rem 0 !important;
          line-height: 1.4 !important;
        }

        .text2sql-explanation {
          line-height: 1.4 !important;
          font-size: 14px !important;
        }

        .text2sql-explanation h1,
        .text2sql-explanation h2,
        .text2sql-explanation h3,
        .text2sql-explanation h4,
        .text2sql-explanation h5,
        .text2sql-explanation h6 {
          margin-top: 0.8rem !important;
          margin-bottom: 0.3rem !important;
        }

        .text2sql-explanation ul,
        .text2sql-explanation ol {
          margin: 0.3rem 0 !important;
          padding-left: 1.2rem !important;
        }

        .text2sql-explanation li {
          margin: 0.1rem 0 !important;
        }

        .text2sql-explanation pre {
          margin: 0.5rem 0 !important;
        }
      `}</style>
    </div>
  );
};

export default SQLTab;
