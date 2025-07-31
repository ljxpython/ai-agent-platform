import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { tomorrow } from 'react-syntax-highlighter/dist/esm/styles/prism';

interface StreamingMarkdownProps {
  content: string;
  isStreaming?: boolean;
  className?: string;
  style?: React.CSSProperties;
}

const StreamingMarkdown: React.FC<StreamingMarkdownProps> = ({
  content,
  isStreaming = false,
  className = '',
  style = {}
}) => {
  const [displayContent, setDisplayContent] = useState('');
  const [showCursor, setShowCursor] = useState(false);
  const contentRef = useRef<string>('');
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  // 调试信息（生产环境可移除）
  if (process.env.NODE_ENV === 'development') {
    console.log('StreamingMarkdown 渲染:', {
      contentLength: content.length,
      isStreaming,
      contentPreview: content.substring(0, 100),
      hasNewlines: content.includes('\n'),
      hasSpaces: content.includes(' ')
    });
  }

  // 清理定时器
  useEffect(() => {
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, []);

  // 处理内容更新
  useEffect(() => {
    if (content !== contentRef.current) {
      contentRef.current = content;

      if (isStreaming) {
        // 流式显示时，直接更新内容并显示光标
        setDisplayContent(content);
        setShowCursor(true);

        // 光标闪烁效果
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
        }
        intervalRef.current = setInterval(() => {
          setShowCursor(prev => !prev);
        }, 500);
      } else {
        // 非流式显示时，直接显示完整内容并隐藏光标
        setDisplayContent(content);
        setShowCursor(false);
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
      }
    }
  }, [content, isStreaming]);

  // 停止流式显示时隐藏光标
  useEffect(() => {
    if (!isStreaming) {
      setShowCursor(false);
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    }
  }, [isStreaming]);

  return (
    <div
      className={`streaming-markdown ${className}`}
      style={{
        fontSize: '14px',
        lineHeight: '1.6',
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", "Oxygen", "Ubuntu", "Cantarell", "Fira Sans", "Droid Sans", "Helvetica Neue", sans-serif',
        ...style
      }}
    >
      <ReactMarkdown
        components={{
          // 代码块渲染
          code: ({ node, inline, className, children, ...props }: any) => {
            const match = /language-(\w+)/.exec(className || '');
            const language = match ? match[1] : '';

            return !inline && language ? (
              <SyntaxHighlighter
                style={tomorrow as any}
                language={language}
                PreTag="div"
                className="code-block"
                showLineNumbers={true}
                wrapLines={true}
                customStyle={{
                  margin: '16px 0',
                  borderRadius: '6px',
                  fontSize: '14px'
                }}
                {...props}
              >
                {String(children).replace(/\n$/, '')}
              </SyntaxHighlighter>
            ) : (
              <code
                className={`inline-code ${className || ''}`}
                style={{
                  backgroundColor: '#f5f5f5',
                  padding: '2px 6px',
                  borderRadius: '4px',
                  fontSize: '13px',
                  fontFamily: 'Monaco, Menlo, "Ubuntu Mono", monospace'
                }}
                {...props}
              >
                {children}
              </code>
            );
          },
          // 自定义段落渲染
          p: ({ children }: any) => (
            <div style={{ marginBottom: '12px', lineHeight: '1.6' }}>
              {children}
            </div>
          ),
          // 自定义列表渲染
          ul: ({ children }: any) => (
            <ul style={{
              marginLeft: '20px',
              marginBottom: '12px',
              listStyleType: 'disc'
            }}>
              {children}
            </ul>
          ),
          ol: ({ children }: any) => (
            <ol style={{
              marginLeft: '20px',
              marginBottom: '12px',
              listStyleType: 'decimal'
            }}>
              {children}
            </ol>
          ),
          li: ({ children }: any) => (
            <li style={{ marginBottom: '4px', lineHeight: '1.5' }}>
              {children}
            </li>
          ),
          // 自定义标题渲染
          h1: ({ children }: any) => (
            <h1 style={{
              fontSize: '24px',
              fontWeight: 600,
              marginBottom: '16px',
              marginTop: '24px',
              color: '#1f2937',
              borderBottom: '2px solid #e5e7eb',
              paddingBottom: '8px'
            }}>
              {children}
            </h1>
          ),
          h2: ({ children }: any) => (
            <h2 style={{
              fontSize: '20px',
              fontWeight: 600,
              marginBottom: '14px',
              marginTop: '20px',
              color: '#374151'
            }}>
              {children}
            </h2>
          ),
          h3: ({ children }: any) => (
            <h3 style={{
              fontSize: '18px',
              fontWeight: 600,
              marginBottom: '12px',
              marginTop: '16px',
              color: '#4b5563'
            }}>
              {children}
            </h3>
          ),
          h4: ({ children }: any) => (
            <h4 style={{
              fontSize: '16px',
              fontWeight: 600,
              marginBottom: '10px',
              marginTop: '14px',
              color: '#6b7280'
            }}>
              {children}
            </h4>
          ),
          // 自定义引用块
          blockquote: ({ children }: any) => (
            <blockquote style={{
              borderLeft: '4px solid #e5e7eb',
              paddingLeft: '16px',
              margin: '16px 0',
              fontStyle: 'italic',
              color: '#6b7280',
              backgroundColor: '#f9fafb',
              padding: '12px 16px',
              borderRadius: '0 6px 6px 0'
            }}>
              {children}
            </blockquote>
          ),
          // 自定义表格
          table: ({ children }: any) => (
            <div style={{ margin: '16px 0' }}>
              <table style={{
                width: '100%',
                borderCollapse: 'collapse',
                border: '1px solid #e5e7eb',
                tableLayout: 'fixed'
              }}>
                {children}
              </table>
            </div>
          ),
          th: ({ children }: any) => (
            <th style={{
              padding: '12px',
              backgroundColor: '#f9fafb',
              border: '1px solid #e5e7eb',
              fontWeight: 600,
              textAlign: 'left',
              wordWrap: 'break-word',
              wordBreak: 'break-word'
            }}>
              {children}
            </th>
          ),
          td: ({ children }: any) => (
            <td style={{
              padding: '12px',
              border: '1px solid #e5e7eb',
              wordWrap: 'break-word',
              wordBreak: 'break-word'
            }}>
              {children}
            </td>
          ),
          // 自定义分割线
          hr: ({ children }: any) => (
            <hr style={{
              margin: '24px 0',
              border: 'none',
              borderTop: '1px solid #e5e7eb'
            }} />
          ),
          // 自定义链接
          a: ({ children, href, ...props }: any) => (
            <a
              href={href}
              style={{
                color: '#3b82f6',
                textDecoration: 'none'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.textDecoration = 'underline';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.textDecoration = 'none';
              }}
              {...props}
            >
              {children}
            </a>
          ),
          // 自定义强调
          strong: ({ children }: any) => (
            <strong style={{ fontWeight: 600, color: '#1f2937' }}>
              {children}
            </strong>
          ),
          em: ({ children }: any) => (
            <em style={{ fontStyle: 'italic', color: '#4b5563' }}>
              {children}
            </em>
          )
        }}
      >
        {displayContent}
      </ReactMarkdown>
      {showCursor && (
        <span
          className="streaming-cursor"
          style={{
            display: 'inline-block',
            width: '2px',
            height: '1.2em',
            backgroundColor: '#3b82f6',
            marginLeft: '2px'
          }}
        />
      )}
      <style dangerouslySetInnerHTML={{
        __html: `
          .streaming-cursor {
            animation: blink 1s infinite;
          }
          @keyframes blink {
            0%, 50% { opacity: 1; }
            51%, 100% { opacity: 0; }
          }
        `
      }} />
    </div>
  );
};

export default StreamingMarkdown;
