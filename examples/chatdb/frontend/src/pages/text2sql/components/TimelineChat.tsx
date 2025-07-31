import React, { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import { format } from 'date-fns';
import { zhCN } from 'date-fns/locale';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { tomorrow } from 'react-syntax-highlighter/dist/esm/styles/prism';
// 导入共享类型
import type { TimelineMessage, Connection, TimelineChatProps } from '../../../types/chat';

// 区域内容接口
interface RegionContent {
  region: string;
  title: string;
  icon: string;
  messages: TimelineMessage[];
  content: string;
  isStreaming: boolean;
  hasContent: boolean;
}

// 可折叠区域组件
interface CollapsibleRegionProps {
  region: RegionContent;
  isCollapsed: boolean;
  onToggle: () => void;
}

const TimelineChat: React.FC<TimelineChatProps> = ({
  messages,
  isStreaming,
  connections = [],
  selectedConnectionId,
  onConnectionChange,
  loadingConnections = false
}) => {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 折叠状态管理
  const [collapsedRegions, setCollapsedRegions] = useState<Record<string, boolean>>({
    analysis: false,
    sql: false,
    explanation: false,
    data: false,
    visualization: false,
    process: true // 默认折叠处理过程
  });

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    if (isStreaming) {
      scrollToBottom();
    }
  }, [messages, isStreaming]);

  // 切换区域折叠状态 - 使用useCallback优化
  const toggleRegionCollapse = useCallback((region: string) => {
    setCollapsedRegions(prev => ({
      ...prev,
      [region]: !prev[region]
    }));
  }, []);

  // 使用useMemo优化区域分组，避免频繁重新计算
  const groupedRegions = useMemo((): RegionContent[] => {
    const regionMap = new Map<string, TimelineMessage[]>();

    // 按区域分组消息，只处理assistant类型的消息
    messages.forEach(message => {
      if (message.type === 'assistant' && message.metadata?.region) {
        const region = message.metadata.region;
        if (!regionMap.has(region)) {
          regionMap.set(region, []);
        }
        regionMap.get(region)!.push(message);
      }
    });

    // 定义区域配置
    const regionConfigs = [
      {
        region: 'analysis',
        title: '查询分析',
        icon: '🔍',
        order: 1
      },
      {
        region: 'sql',
        title: 'SQL语句',
        icon: '💾',
        order: 2
      },
      {
        region: 'explanation',
        title: 'SQL解释',
        icon: '📝',
        order: 3
      },
      {
        region: 'data',
        title: '查询结果',
        icon: '📊',
        order: 4
      },
      {
        region: 'visualization',
        title: '数据可视化',
        icon: '📈',
        order: 5
      },
      {
        region: 'process',
        title: '处理过程',
        icon: '⚙️',
        order: 6
      }
    ];

    // 构建区域内容
    const regions: RegionContent[] = [];

    regionConfigs.forEach(config => {
      const regionMessages = regionMap.get(config.region) || [];
      if (regionMessages.length > 0) {
        // 合并区域内容，去重并保持时间顺序
        const uniqueMessages = regionMessages.filter((msg, index, arr) =>
          arr.findIndex(m => m.id === msg.id) === index
        ).sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime());

        // 智能合并内容 - 连续输出而不是换行分割
        let content = '';
        if (uniqueMessages.length > 0) {
          // 对于流式输出，直接连接内容，不添加额外的换行
          content = uniqueMessages.map(msg => msg.content).join('');
        }

        // 检查是否有流式输出
        const isStreaming = uniqueMessages.some(msg => msg.status === 'streaming');

        regions.push({
          region: config.region,
          title: config.title,
          icon: config.icon,
          messages: uniqueMessages,
          content,
          isStreaming,
          hasContent: content.length > 0
        });
      }
    });

    return regions.sort((a, b) => {
      const aConfig = regionConfigs.find(c => c.region === a.region);
      const bConfig = regionConfigs.find(c => c.region === b.region);
      return (aConfig?.order || 999) - (bConfig?.order || 999);
    });
  }, [messages]); // 只依赖messages，减少重新计算

  const formatTime = (timestamp: Date) => {
    return format(timestamp, 'HH:mm:ss', { locale: zhCN });
  };

  const getMessageIcon = (type: string, metadata?: any) => {
    if (type === 'user') return '👤';
    if (metadata?.region === 'analysis') return '🔍';
    if (metadata?.region === 'sql') return '💾';
    if (metadata?.region === 'explanation') return '📝';
    if (metadata?.region === 'data') return '📊';
    if (metadata?.region === 'visualization') return '📈';
    return '🤖';
  };

  const getStatusIndicator = (status: string) => {
    switch (status) {
      case 'sending':
        return <div className="status-indicator sending">发送中...</div>;
      case 'streaming':
        return <div className="status-indicator streaming">
          <div className="typing-dots">
            <span></span>
            <span></span>
            <span></span>
          </div>
        </div>;
      case 'error':
        return <div className="status-indicator error">❌ 错误</div>;
      default:
        return null;
    }
  };

  // 优化的Markdown组件配置
  const markdownComponents = {
    // 代码块渲染
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
    // 段落渲染
    p: ({ children }: any) => <p className="markdown-paragraph">{children}</p>,
    // 标题渲染
    h1: ({ children }: any) => <h1 className="markdown-h1">{children}</h1>,
    h2: ({ children }: any) => <h2 className="markdown-h2">{children}</h2>,
    h3: ({ children }: any) => <h3 className="markdown-h3">{children}</h3>,
    h4: ({ children }: any) => <h4 className="markdown-h4">{children}</h4>,
    h5: ({ children }: any) => <h5 className="markdown-h5">{children}</h5>,
    h6: ({ children }: any) => <h6 className="markdown-h6">{children}</h6>,
    // 列表渲染
    ul: ({ children }: any) => <ul className="markdown-ul">{children}</ul>,
    ol: ({ children }: any) => <ol className="markdown-ol">{children}</ol>,
    li: ({ children }: any) => <li className="markdown-li">{children}</li>,
    // 链接渲染
    a: ({ href, children }: any) => (
      <a href={href} className="markdown-link" target="_blank" rel="noopener noreferrer">
        {children}
      </a>
    ),
    // 强调渲染
    strong: ({ children }: any) => <strong className="markdown-strong">{children}</strong>,
    em: ({ children }: any) => <em className="markdown-em">{children}</em>,
    // 引用渲染
    blockquote: ({ children }: any) => <blockquote className="markdown-blockquote">{children}</blockquote>,
    // 表格渲染
    table: ({ children }: any) => <table className="markdown-table">{children}</table>,
    thead: ({ children }: any) => <thead className="markdown-thead">{children}</thead>,
    tbody: ({ children }: any) => <tbody className="markdown-tbody">{children}</tbody>,
    tr: ({ children }: any) => <tr className="markdown-tr">{children}</tr>,
    th: ({ children }: any) => <th className="markdown-th">{children}</th>,
    td: ({ children }: any) => <td className="markdown-td">{children}</td>,
    // 分割线渲染
    hr: () => <hr className="markdown-hr" />
  };

  // 可折叠区域组件 - 优化版本，使用React.memo防止不必要的重新渲染
  const CollapsibleRegion: React.FC<CollapsibleRegionProps> = React.memo(({ region, isCollapsed, onToggle }) => {
    // 防止事件冒泡
    const handleToggle = (e: React.MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();
      onToggle();
    };

    // 复制功能
    const handleCopy = (text: string, e: React.MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();
      navigator.clipboard.writeText(text).then(() => {
        console.log('内容已复制到剪贴板');
      }).catch(err => {
        console.error('复制失败:', err);
      });
    };

    return (
      <div className={`collapsible-region ${region.region}-region ${isCollapsed ? 'collapsed' : 'expanded'}`}>
        <div className="region-header" onClick={handleToggle}>
          <div className="region-title">
            <span className="region-icon">{region.icon}</span>
            <span className="region-name">{region.title}</span>
            {region.isStreaming && (
              <span className="streaming-indicator">
                <div className="pulse-dot"></div>
                正在生成...
              </span>
            )}
          </div>
          <div className="region-controls">
            {region.hasContent && (
              <span className="content-count">{region.messages.length} 条消息</span>
            )}
            <button
              className={`collapse-btn ${isCollapsed ? 'collapsed' : 'expanded'}`}
              onClick={handleToggle}
              type="button"
            >
              {isCollapsed ? '▶' : '▼'}
            </button>
          </div>
        </div>

        {!isCollapsed && region.hasContent && (
          <div className="region-content">
            {/* 显示合并后的完整内容 */}
            {region.content && (
              <div className="region-summary">
                <div className="summary-header">
                  <span className="summary-title">内容</span>
                  <button
                    className="copy-btn"
                    onClick={(e) => handleCopy(region.content, e)}
                    title="复制内容"
                    type="button"
                  >
                    📋
                  </button>
                </div>
                <div className="summary-content">
                  {region.region === 'sql' ? (
                    <SyntaxHighlighter
                      language="sql"
                      style={tomorrow}
                      className="sql-content"
                    >
                      {region.content}
                    </SyntaxHighlighter>
                  ) : (
                    <ReactMarkdown components={markdownComponents}>
                      {region.content}
                    </ReactMarkdown>
                  )}
                </div>
              </div>
            )}

            {/* 显示消息历史（可选，默认折叠） */}
            {region.messages.length > 1 && (
              <details className="region-messages-details">
                <summary className="messages-summary">
                  消息历史 ({region.messages.length} 条)
                </summary>
                <div className="region-messages">
                  {region.messages.map((message, index) => (
                    <div key={`${message.id}-${index}`} className={`region-message ${message.type}`}>
                      <div className="message-meta">
                        <span className="message-source">
                          {message.metadata?.source || '系统'}
                        </span>
                        <span className="message-time">
                          {formatTime(message.timestamp)}
                        </span>
                        <span className={`message-status ${message.status}`}>
                          {getStatusIndicator(message.status)}
                        </span>
                      </div>
                      <div className="message-content">
                        {message.metadata?.isSQL ? (
                          <div className="sql-block">
                            <div className="sql-header">
                              <span className="sql-label">SQL 查询</span>
                              <button
                                className="copy-btn"
                                onClick={(e) => handleCopy(message.content, e)}
                                title="复制SQL"
                                type="button"
                              >
                                📋
                              </button>
                            </div>
                            <SyntaxHighlighter
                              language="sql"
                              style={tomorrow}
                              className="sql-content"
                            >
                              {message.content}
                            </SyntaxHighlighter>
                          </div>
                        ) : (
                          <div className="message-text">
                            <ReactMarkdown components={markdownComponents}>
                              {message.content}
                            </ReactMarkdown>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </details>
            )}
          </div>
        )}
      </div>
    );
  });

  return (
    <div className="timeline-chat">
      {/* 左上角数据库选择器 */}
      {connections.length > 0 && (
        <div className="chat-header-controls">
          <div className="database-selector">
            <label className="selector-label">
              <span className="database-icon">🗄️</span>
              数据库连接
            </label>
            <select
              value={selectedConnectionId || ''}
              onChange={(e) => onConnectionChange?.(Number(e.target.value))}
              className="database-select"
              disabled={loadingConnections}
            >
              <option value="">请选择数据库</option>
              {connections.map((conn) => (
                <option key={conn.id} value={conn.id}>
                  {conn.name} ({conn.type})
                </option>
              ))}
            </select>
            {loadingConnections && (
              <div className="loading-indicator">
                <span className="spinner">⏳</span>
              </div>
            )}
          </div>
        </div>
      )}

      <div className="timeline-container">
        {/* 用户消息 */}
        {messages.filter(msg => msg.type === 'user').map((message, index) => (
          <div key={message.id} className={`timeline-item ${message.type}`}>
            {/* 时间轴线条 */}
            <div className="timeline-line">
              <div className="timeline-dot">
                <span className="message-icon">
                  {getMessageIcon(message.type, message.metadata)}
                </span>
              </div>
              <div className="timeline-connector"></div>
            </div>

            {/* 消息内容 */}
            <div className="timeline-content">
              <div className="message-header">
                <div className="message-meta">
                  <span className="message-type">用户</span>
                  <span className="message-time">
                    {formatTime(message.timestamp)}
                  </span>
                </div>
                {getStatusIndicator(message.status)}
              </div>

              <div className="message-body">
                <div className="message-text">
                  <ReactMarkdown components={markdownComponents}>
                    {message.content}
                  </ReactMarkdown>
                </div>
              </div>
            </div>
          </div>
        ))}

        {/* 区域化内容 */}
        {groupedRegions.map((region, index) => (
          <div key={`region-${region.region}`} className="timeline-item assistant">
            {/* 时间轴线条 */}
            <div className="timeline-line">
              <div className="timeline-dot">
                <span className="message-icon">{region.icon}</span>
              </div>
              {index < groupedRegions.length - 1 && <div className="timeline-connector"></div>}
            </div>

            {/* 区域内容 */}
            <div className="timeline-content">
              <CollapsibleRegion
                region={region}
                isCollapsed={collapsedRegions[region.region] || false}
                onToggle={() => toggleRegionCollapse(region.region)}
              />
            </div>
          </div>
        ))}

        {/* 流式输出指示器 */}
        {isStreaming && (
          <div className="timeline-item streaming-indicator">
            <div className="timeline-line">
              <div className="timeline-dot streaming">
                <div className="pulse-ring"></div>
                <span className="message-icon">⚡</span>
              </div>
            </div>
            <div className="timeline-content">
              <div className="streaming-text">AI 正在思考中...</div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>
    </div>
  );
};

export default TimelineChat;
