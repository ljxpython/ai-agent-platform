import React, { useState } from 'react';
import { Card, Avatar, Typography, Space, Button, Collapse, Tag, Tooltip } from 'antd';
import {
  UserOutlined,
  RobotOutlined,
  SearchOutlined,
  DatabaseOutlined
} from '@ant-design/icons';
import { Message } from '@/types/rag';
import { CopyableContent } from '../ui/CopyableContent';
import { formatRelativeTime } from '@/utils/rag';

const { Text, Paragraph } = Typography;
const { Panel } = Collapse;

interface MessageBubbleProps {
  message: Message;
  isStreaming?: boolean;
}

const MessageBubble: React.FC<MessageBubbleProps> = ({
  message,
  isStreaming = false,
}) => {
  const [showSources, setShowSources] = useState(false);

  const isUser = message.role === 'user';

  // 解析搜索结果
  const parseSearchResults = (sources: string | null) => {
    if (!sources) return null;
    try {
      return JSON.parse(sources);
    } catch {
      return null;
    }
  };

  const vectorResults = message.sources?.vector ? parseSearchResults(message.sources.vector) : null;
  const kgResults = message.sources?.kg ? parseSearchResults(message.sources.kg) : null;

  return (
    <div
      style={{
        display: 'flex',
        justifyContent: isUser ? 'flex-end' : 'flex-start',
        marginBottom: '16px'
      }}
    >
      <div style={{ maxWidth: '70%', minWidth: '200px' }}>
        <Card
          size="small"
          style={{
            backgroundColor: isUser ? '#1890ff' : '#f5f5f5',
            color: isUser ? 'white' : 'inherit',
            borderRadius: '12px',
            border: 'none',
            boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
          }}
          bodyStyle={{ padding: '12px 16px' }}
        >
          {/* 消息头部 */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            marginBottom: '8px',
            justifyContent: 'space-between'
          }}>
            <Space>
              <Avatar
                size="small"
                icon={isUser ? <UserOutlined /> : <RobotOutlined />}
                style={{
                  backgroundColor: isUser ? 'rgba(255,255,255,0.2)' : '#1890ff'
                }}
              />
              <Text
                strong
                style={{
                  color: isUser ? 'white' : 'inherit',
                  fontSize: '12px'
                }}
              >
                {isUser ? '我' : 'AI助手'}
              </Text>
              <Text
                type="secondary"
                style={{
                  fontSize: '11px',
                  color: isUser ? 'rgba(255,255,255,0.7)' : undefined
                }}
              >
                {formatRelativeTime(new Date(message.timestamp).toISOString())}
              </Text>
            </Space>

            {/* 操作按钮 */}
            <Space size="small">
              {message.searchPerformed && (
                <Tooltip title="查看搜索结果">
                  <Button
                    type="text"
                    size="small"
                    icon={<SearchOutlined />}
                    onClick={() => setShowSources(!showSources)}
                    style={{
                      color: isUser ? 'rgba(255,255,255,0.8)' : undefined,
                      padding: '0 4px'
                    }}
                  />
                </Tooltip>
              )}
              <CopyableContent
                content={message.content}
                showButton={true}
                buttonText=""
                successMessage="消息已复制"
              />
            </Space>
          </div>

          {/* 消息内容 */}
          <div>
            <Paragraph
              style={{
                margin: 0,
                color: isUser ? 'white' : 'inherit',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word'
              }}
            >
              {message.content}
              {(isStreaming || message.isStreaming) && (
                <span
                  style={{
                    display: 'inline-block',
                    animation: 'blink 1s infinite',
                    marginLeft: '2px'
                  }}
                >
                  ▋
                </span>
              )}
            </Paragraph>

            {/* 搜索结果标签 */}
            {message.searchPerformed && (
              <div style={{ marginTop: '8px' }}>
                <Space size="small">
                  <Tag
                    icon={<DatabaseOutlined />}
                    color="blue"
                  >
                    已搜索知识库
                  </Tag>
                  {vectorResults && (
                    <Tag color="green">
                      向量搜索: {Array.isArray(vectorResults) ? vectorResults.length : 0} 条结果
                    </Tag>
                  )}
                  {kgResults && (
                    <Tag color="orange">
                      知识图谱: 已启用
                    </Tag>
                  )}
                </Space>
              </div>
            )}
          </div>
        </Card>

        {/* 搜索结果详情 */}
        {showSources && message.sources && (
          <Card
            size="small"
            style={{
              marginTop: '8px',
              backgroundColor: '#fafafa'
            }}
            title={
              <Space>
                <SearchOutlined />
                <span>搜索结果详情</span>
              </Space>
            }
          >
            <Collapse size="small" ghost>
              {vectorResults && (
                <Panel
                  header={`向量搜索结果 (${Array.isArray(vectorResults) ? vectorResults.length : 0} 条)`}
                  key="vector"
                >
                  {Array.isArray(vectorResults) ? (
                    vectorResults.map((result: any, index: number) => (
                      <Card
                        key={index}
                        size="small"
                        style={{ marginBottom: '8px' }}
                        title={`文档片段 ${index + 1}`}
                        extra={
                          result.score && (
                            <Tag color="blue">
                              相似度: {(result.score * 100).toFixed(1)}%
                            </Tag>
                          )
                        }
                      >
                        <Paragraph
                          ellipsis={{ rows: 3, expandable: true }}
                          style={{ margin: 0 }}
                        >
                          {result.text || result.content || '无内容'}
                        </Paragraph>
                        {result.metadata && (
                          <div style={{ marginTop: '8px' }}>
                            <Text type="secondary" style={{ fontSize: '12px' }}>
                              来源: {result.metadata.title || result.metadata.source || '未知'}
                            </Text>
                          </div>
                        )}
                      </Card>
                    ))
                  ) : (
                    <Text type="secondary">无搜索结果</Text>
                  )}
                </Panel>
              )}

              {kgResults && (
                <Panel header="知识图谱搜索结果" key="kg">
                  <Text type="secondary">知识图谱搜索结果将在此显示</Text>
                </Panel>
              )}
            </Collapse>
          </Card>
        )}
      </div>

      <style>{`
        @keyframes blink {
          0%, 50% { opacity: 1; }
          51%, 100% { opacity: 0; }
        }
      `}</style>
    </div>
  );
};

export default MessageBubble;
