import React from 'react';
import { Avatar, Typography, Button, Card, Tag, Space } from 'antd';
import { UserOutlined, CopyOutlined, LikeOutlined, DislikeOutlined, BookOutlined } from '@ant-design/icons';
import { ChatMessage as ChatMessageType } from '@/types/chat';
import MarkdownRenderer from '@/components/MarkdownRenderer';
import dayjs from 'dayjs';

const { Text } = Typography;

interface ChatMessageProps {
  message: ChatMessageType;
}

const ChatMessage: React.FC<ChatMessageProps> = ({ message }) => {
  const isUser = message.role === 'user';
  const isRetrievedDocs = message.role === 'retrieved_docs';
  const isStreaming = message.isStreaming;

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content);
  };

  return (
    <div
      className="fade-in"
      style={{
        display: 'flex',
        flexDirection: 'column',
        marginBottom: 32,
        maxWidth: '100%',
      }}
    >
      {/* 消息头部 */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        marginBottom: 8,
        gap: 8
      }}>
        {isUser ? (
          <>
            <Avatar
              size={24}
              icon={<UserOutlined />}
              style={{
                backgroundColor: '#667eea',
                fontSize: 12
              }}
            />
            <Text style={{ fontSize: 14, fontWeight: 500, color: '#374151' }}>
              您
            </Text>
          </>
        ) : isRetrievedDocs ? (
          <>
            <div style={{
              width: 24,
              height: 24,
              borderRadius: '50%',
              background: 'linear-gradient(135deg, #1890ff 0%, #096dd9 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'white',
              fontSize: 12,
              fontWeight: 'bold'
            }}>
              <BookOutlined style={{ fontSize: 12 }} />
            </div>
            <Text style={{ fontSize: 14, fontWeight: 500, color: '#374151' }}>
              召回的相关文档
            </Text>
          </>
        ) : (
          <>
            <div style={{
              width: 24,
              height: 24,
              borderRadius: '50%',
              background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'white',
              fontSize: 12,
              fontWeight: 'bold'
            }}>
              T
            </div>
            <Text style={{ fontSize: 14, fontWeight: 500, color: '#374151' }}>
              测试助手
            </Text>
          </>
        )}
        <Text style={{ fontSize: 12, color: '#9ca3af' }}>
          {dayjs(message.timestamp).format('HH:mm')}
        </Text>
      </div>

      {/* 消息内容 */}
      <div style={{
        marginLeft: isUser ? 0 : 32,
        backgroundColor: isUser ? '#f3f4f6' : (isRetrievedDocs ? '#f8f9fa' : 'transparent'),
        padding: isUser ? '12px 16px' : (isRetrievedDocs ? '16px' : '0'),
        borderRadius: isUser ? '12px' : (isRetrievedDocs ? '12px' : '0'),
        border: isUser ? '1px solid #e5e7eb' : (isRetrievedDocs ? '1px solid #e8e8e8' : 'none')
      }}>
        {isUser ? (
          // 用户消息：简单文本显示
          <div
            style={{
              margin: 0,
              color: '#374151',
              fontSize: '15px',
              lineHeight: '1.6',
              wordBreak: 'break-word'
            }}
          >
            {message.content}
          </div>
        ) : isRetrievedDocs ? (
          // 召回文档：卡片展示
          <div style={{ maxHeight: '400px', overflowY: 'auto' }}>
            <Space direction="vertical" style={{ width: '100%' }} size="middle">
              {message.retrievedDocuments?.map((doc, index) => (
                <Card
                  key={`${doc.index}-${index}`}
                  size="small"
                  style={{
                    backgroundColor: '#ffffff',
                    border: '1px solid #e8e8e8',
                    borderRadius: '8px'
                  }}
                  title={
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <Text strong style={{ fontSize: 14, color: '#262626' }}>
                        文档 {doc.index}
                      </Text>
                      {doc.similarity && (
                        <Tag color="blue" style={{ fontSize: 12 }}>
                          相似度: {doc.similarity.toFixed(3)}
                        </Tag>
                      )}
                    </div>
                  }
                >
                  <div style={{
                    maxHeight: '120px',
                    overflowY: 'auto',
                    fontSize: 13,
                    lineHeight: 1.5,
                    color: '#595959',
                    whiteSpace: 'pre-wrap'
                  }}>
                    {doc.content}
                  </div>
                </Card>
              ))}
            </Space>
          </div>
        ) : (
          // AI 消息：Markdown 渲染
          <div style={{ position: 'relative' }}>
            <MarkdownRenderer
              content={message.content}
              style={{
                fontFamily: '"Google Sans", -apple-system, BlinkMacSystemFont, sans-serif'
              }}
            />
            {isStreaming && (
              <span className="typing-indicator" style={{ marginLeft: 8 }}>
                <span className="typing-dot"></span>
                <span className="typing-dot"></span>
                <span className="typing-dot"></span>
              </span>
            )}
          </div>
        )}

        {/* 操作按钮 - 仅对 AI 回复显示 */}
        {!isUser && !isRetrievedDocs && !isStreaming && message.content && (
          <div style={{
            marginTop: 12,
            display: 'flex',
            gap: 8,
            opacity: 0.7,
            transition: 'opacity 0.2s'
          }}>
            <Button
              type="text"
              size="small"
              icon={<CopyOutlined />}
              onClick={handleCopy}
              style={{
                color: '#6b7280',
                border: 'none',
                padding: '4px 8px',
                height: 'auto'
              }}
            />
            <Button
              type="text"
              size="small"
              icon={<LikeOutlined />}
              style={{
                color: '#6b7280',
                border: 'none',
                padding: '4px 8px',
                height: 'auto'
              }}
            />
            <Button
              type="text"
              size="small"
              icon={<DislikeOutlined />}
              style={{
                color: '#6b7280',
                border: 'none',
                padding: '4px 8px',
                height: 'auto'
              }}
            />
          </div>
        )}
      </div>
    </div>
  );
};

export default ChatMessage;
