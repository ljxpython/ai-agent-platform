import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Card, Spin, Alert, Button, Collapse, Typography } from 'antd';
import { CopyOutlined, ExpandAltOutlined, CompressOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { tomorrow } from 'react-syntax-highlighter/dist/esm/styles/prism';
import '../../../styles/StreamingOutput.css';

const { Panel } = Collapse;
const { Text, Paragraph } = Typography;

// 流式输出区域类型
interface StreamingRegion {
  id: string;
  title: string;
  icon: React.ReactNode;
  content: string;
  isStreaming: boolean;
  hasContent: boolean;
  isCollapsed: boolean;
  type: 'markdown' | 'sql' | 'json' | 'text';
}

// 组件属性
interface StreamingOutputProps {
  regions: StreamingRegion[];
  onRegionToggle: (regionId: string) => void;
  onCopyContent: (content: string, regionId: string) => void;
  className?: string;
}

// 流式文本组件
const StreamingText: React.FC<{
  content: string;
  isStreaming: boolean;
  type: 'markdown' | 'sql' | 'json' | 'text';
  onContentUpdate?: () => void;
}> = ({ content, isStreaming, type, onContentUpdate }) => {
  const [displayContent, setDisplayContent] = useState('');
  const [currentIndex, setCurrentIndex] = useState(0);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // 流式显示效果
  useEffect(() => {
    if (isStreaming && content.length > displayContent.length) {
      // 清除之前的定时器
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }

      // 计算需要添加的内容
      const newContent = content.slice(displayContent.length);
      let charIndex = 0;

      intervalRef.current = setInterval(() => {
        if (charIndex < newContent.length) {
          setDisplayContent(prev => prev + newContent[charIndex]);
          charIndex++;
          onContentUpdate?.();
        } else {
          if (intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
          }
        }
      }, 20); // 每20ms显示一个字符
    } else if (!isStreaming) {
      // 如果不是流式状态，直接显示完整内容
      setDisplayContent(content);
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [content, isStreaming, displayContent.length, onContentUpdate]);

  // 自动滚动到底部
  useEffect(() => {
    if (isStreaming && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [displayContent, isStreaming]);

  // Markdown组件配置
  const markdownComponents = {
    code: ({ node, inline, className, children, ...props }: any) => {
      const match = /language-(\w+)/.exec(className || '');
      const language = match ? match[1] : '';

      return !inline && language ? (
        <SyntaxHighlighter
          style={tomorrow}
          language={language}
          PreTag="div"
          className="code-block"
          showLineNumbers={true}
          wrapLines={true}
          {...props}
        >
          {String(children).replace(/\n$/, '')}
        </SyntaxHighlighter>
      ) : (
        <code className={`inline-code ${className || ''}`} {...props}>
          {children}
        </code>
      );
    },
    // 自定义段落渲染，避免额外的换行
    p: ({ children }: any) => <div className="markdown-paragraph">{children}</div>,
    // 自定义列表渲染
    ul: ({ children }: any) => <ul className="markdown-list">{children}</ul>,
    ol: ({ children }: any) => <ol className="markdown-ordered-list">{children}</ol>,
    // 自定义标题渲染
    h1: ({ children }: any) => <h1 className="markdown-h1">{children}</h1>,
    h2: ({ children }: any) => <h2 className="markdown-h2">{children}</h2>,
    h3: ({ children }: any) => <h3 className="markdown-h3">{children}</h3>,
    h4: ({ children }: any) => <h4 className="markdown-h4">{children}</h4>,
  };

  const renderContent = () => {
    const contentToRender = displayContent || '';

    switch (type) {
      case 'sql':
        return (
          <SyntaxHighlighter
            language="sql"
            style={tomorrow}
            className="sql-content"
            showLineNumbers={true}
            wrapLines={true}
          >
            {contentToRender}
          </SyntaxHighlighter>
        );
      case 'json':
        return (
          <SyntaxHighlighter
            language="json"
            style={tomorrow}
            className="json-content"
            showLineNumbers={true}
            wrapLines={true}
          >
            {contentToRender}
          </SyntaxHighlighter>
        );
      case 'markdown':
        return (
          <div className="markdown-content">
            <ReactMarkdown components={markdownComponents}>
              {contentToRender}
            </ReactMarkdown>
          </div>
        );
      default:
        return (
          <div className="text-content">
            <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
              {contentToRender}
            </pre>
          </div>
        );
    }
  };

  return (
    <div
      ref={containerRef}
      className="streaming-text-container"
      style={{
        maxHeight: '400px',
        overflowY: 'auto',
        padding: '12px',
        backgroundColor: '#fafafa',
        borderRadius: '6px',
        border: '1px solid #d9d9d9'
      }}
    >
      {renderContent()}
      {isStreaming && (
        <div className="streaming-indicator" style={{ marginTop: '8px' }}>
          <Spin size="small" />
          <Text type="secondary" style={{ marginLeft: '8px' }}>正在生成内容...</Text>
        </div>
      )}
    </div>
  );
};

// 主组件
const StreamingOutput: React.FC<StreamingOutputProps> = ({
  regions,
  onRegionToggle,
  onCopyContent,
  className = ''
}) => {
  const handleCopy = useCallback(async (content: string, regionId: string) => {
    try {
      await navigator.clipboard.writeText(content);
      onCopyContent(content, regionId);
    } catch (err) {
      console.error('复制失败:', err);
    }
  }, [onCopyContent]);

  const renderRegionExtra = (region: StreamingRegion) => (
    <div className="region-extra" onClick={(e) => e.stopPropagation()}>
      <Button
        type="text"
        size="small"
        icon={<CopyOutlined />}
        onClick={() => handleCopy(region.content, region.id)}
        disabled={!region.content}
        title="复制内容"
      />
      <Button
        type="text"
        size="small"
        icon={region.isCollapsed ? <ExpandAltOutlined /> : <CompressOutlined />}
        onClick={() => onRegionToggle(region.id)}
        title={region.isCollapsed ? "展开" : "折叠"}
      />
    </div>
  );

  return (
    <div className={`streaming-output ${className}`}>
      <Collapse
        activeKey={regions.filter(r => !r.isCollapsed && r.hasContent).map(r => r.id)}
        onChange={(keys) => {
          // 处理折叠状态变化
          regions.forEach(region => {
            const shouldBeOpen = Array.isArray(keys) ? keys.includes(region.id) : keys === region.id;
            if (region.isCollapsed === shouldBeOpen) {
              onRegionToggle(region.id);
            }
          });
        }}
        size="large"
        ghost
      >
        {regions.map(region => (
          region.hasContent && (
            <Panel
              key={region.id}
              header={
                <div className="region-header">
                  <div className="region-title">
                    {region.icon}
                    <span style={{ marginLeft: '8px' }}>{region.title}</span>
                    {region.isStreaming && (
                      <Spin size="small" style={{ marginLeft: '8px' }} />
                    )}
                  </div>
                </div>
              }
              extra={renderRegionExtra(region)}
              className={`region-panel ${region.isStreaming ? 'streaming' : ''}`}
            >
              <StreamingText
                content={region.content}
                isStreaming={region.isStreaming}
                type={region.type}
              />
            </Panel>
          )
        ))}
      </Collapse>

      {/* 如果没有任何内容，显示空状态 */}
      {regions.every(r => !r.hasContent) && (
        <div className="empty-state" style={{ textAlign: 'center', padding: '40px' }}>
          <Text type="secondary">暂无内容</Text>
        </div>
      )}
    </div>
  );
};

export default StreamingOutput;
