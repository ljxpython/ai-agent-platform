import React, { useState, useEffect, useRef } from 'react';
import { Empty, Button, Space, Typography, Spin, Alert } from 'antd';
import {
  MessageOutlined,
  RobotOutlined,
  StopOutlined
} from '@ant-design/icons';
import { useRAGContext } from '@/contexts/RAGContext';
import { Message } from '@/types/rag';
import MessageBubble from './MessageBubble';
import DefaultQueries from './DefaultQueries';
import UploadButton from './UploadButton';

const { Title, Text } = Typography;

interface ChatResultProps {
  query: string;
  setQuery: (query: string) => void;
  userId: string | null;
  pipelineUrl: string | null;
  searchLimit: number;
  searchFilters: Record<string, unknown>;
  ragTemperature: number | null;
  ragTopP: number | null;
  ragTopK: number | null;
  ragMaxTokensToSample: number | null;
  model: string | null;
  uploadedDocuments: string[];
  setUploadedDocuments: React.Dispatch<React.SetStateAction<string[]>>;
  hasAttemptedFetch: boolean;
  switches: any;
  mode: 'rag' | 'rag_agent';
  selectedCollectionIds: string[];
  onAbortRequest?: () => void;
  messages: Message[];
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  selectedConversationId: string | null;
  setSelectedConversationId: React.Dispatch<React.SetStateAction<string | null>>;
}

const ChatResult: React.FC<ChatResultProps> = ({
  query,
  setQuery,
  // userId,
  // pipelineUrl,
  searchLimit,
  searchFilters,
  ragTemperature,
  ragTopP,
  ragTopK,
  ragMaxTokensToSample,
  model,
  uploadedDocuments,
  setUploadedDocuments,
  hasAttemptedFetch,
  // switches,
  mode,
  // selectedCollectionIds,
  onAbortRequest,
  messages,
  setMessages,
  selectedConversationId,
  // setSelectedConversationId,
}) => {
  const { getClient } = useRAGContext();
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [isSearching, setIsSearching] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [isProcessingQuery, setIsProcessingQuery] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // 模式切换时重置状态
  useEffect(() => {
    abortCurrentRequest();
    setMessages([]);
    setIsStreaming(false);
    setIsSearching(false);
    setError(null);
    setIsProcessingQuery(false);
  }, [mode]);

  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // 中止当前请求
  const abortCurrentRequest = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsStreaming(false);
    setIsSearching(false);
    setIsProcessingQuery(false);
  };

  // 处理查询
  useEffect(() => {
    if (query && query.trim()) {
      handleQuery(query.trim());
    }
  }, [query]);

  const handleQuery = async (queryText: string) => {
    if (!queryText.trim() || isProcessingQuery) return;

    setIsProcessingQuery(true);
    setError(null);

    // 添加用户消息
    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: queryText,
      timestamp: Date.now(),
    };

    setMessages(prev => [...prev, userMessage]);

    try {
      const client = getClient();
      if (!client) {
        throw new Error('No authenticated client available');
      }

      // 创建中止控制器
      abortControllerRef.current = new AbortController();

      // 添加助手消息占位符
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: '',
        timestamp: Date.now(),
        isStreaming: true,
      };

      setMessages(prev => [...prev, assistantMessage]);
      setIsStreaming(true);

      // 根据模式选择不同的API
      if (mode === 'rag_agent') {
        // 使用对话模式
        await handleAgentQuery(client, queryText, assistantMessage.id);
      } else {
        // 使用RAG搜索模式
        await handleRAGQuery(client, queryText, assistantMessage.id);
      }

    } catch (error: any) {
      console.error('Query error:', error);
      if (error.name !== 'AbortError') {
        setError(error.message || '处理查询时发生错误');
      }
    } finally {
      setIsProcessingQuery(false);
      setIsStreaming(false);
      setIsSearching(false);
      abortControllerRef.current = null;
    }
  };

  const handleAgentQuery = async (client: any, queryText: string, messageId: string) => {
    // 这里实现对话模式的逻辑
    // 由于原始代码很复杂，这里提供一个简化版本

    try {
      const response = await client.agent({
        message: queryText,
        conversation_id: selectedConversationId,
        // 其他配置参数...
      });

      // 更新消息内容
      setMessages(prev => prev.map(msg =>
        msg.id === messageId
          ? { ...msg, content: response.results || '抱歉，没有收到有效回复。', isStreaming: false }
          : msg
      ));

    } catch (error) {
      throw error;
    }
  };

  const handleRAGQuery = async (client: any, queryText: string, messageId: string) => {
    // 这里实现RAG搜索模式的逻辑

    try {
      setIsSearching(true);

      const response = await client.rag({
        query: queryText,
        search_settings: {
          limit: searchLimit,
          filters: searchFilters,
          // 其他搜索配置...
        },
        rag_generation_config: {
          temperature: ragTemperature,
          top_p: ragTopP,
          top_k: ragTopK,
          max_tokens_to_sample: ragMaxTokensToSample,
          model: model,
        },
      });

      setIsSearching(false);

      // 更新消息内容
      setMessages(prev => prev.map(msg =>
        msg.id === messageId
          ? {
              ...msg,
              content: response.results?.completion || '抱歉，没有找到相关信息。',
              isStreaming: false,
              searchPerformed: true,
              sources: response.results?.search_results ? {
                vector: JSON.stringify(response.results.search_results),
                kg: null
              } : undefined
            }
          : msg
      ));

    } catch (error) {
      throw error;
    }
  };

  // 渲染空状态
  const renderEmptyState = () => {
    if (!hasAttemptedFetch) {
      return (
        <div style={{ textAlign: 'center', padding: '40px' }}>
          <Spin size="large" tip="加载中..." />
        </div>
      );
    }

    if (uploadedDocuments.length === 0 && mode === 'rag') {
      return (
        <div style={{ textAlign: 'center', padding: '40px' }}>
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={
              <div>
                <Title level={4}>还没有上传文档</Title>
                <Text type="secondary">
                  请先上传一些文档，然后就可以开始提问了
                </Text>
              </div>
            }
          >
            <UploadButton
              onUploadSuccess={(newDocs) => {
                setUploadedDocuments(prev => [...prev, ...newDocs]);
              }}
            />
          </Empty>
        </div>
      );
    }

    return (
      <div style={{ textAlign: 'center', padding: '40px' }}>
        <div style={{ marginBottom: '24px' }}>
          {mode === 'rag_agent' ? (
            <RobotOutlined style={{ fontSize: '48px', color: '#1890ff' }} />
          ) : (
            <MessageOutlined style={{ fontSize: '48px', color: '#1890ff' }} />
          )}
        </div>
        <Title level={4}>
          {mode === 'rag_agent' ? '智能助手已准备就绪' : '开始您的问答'}
        </Title>
        <Text type="secondary">
          {mode === 'rag_agent'
            ? '我可以帮您解答问题、分析文档内容，开始对话吧！'
            : '基于您上传的文档内容，我可以回答相关问题'
          }
        </Text>

        <div style={{ marginTop: '24px' }}>
          <DefaultQueries setQuery={setQuery} mode={mode} />
        </div>
      </div>
    );
  };

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {error && (
        <Alert
          message="错误"
          description={error}
          type="error"
          closable
          onClose={() => setError(null)}
          style={{ marginBottom: '16px' }}
        />
      )}

      {messages.length === 0 ? (
        renderEmptyState()
      ) : (
        <div style={{ flex: 1, overflowY: 'auto', padding: '16px 0' }}>
          {messages.map((message) => (
            <MessageBubble
              key={message.id}
              message={message}
              isStreaming={message.isStreaming}
            />
          ))}

          {(isStreaming || isSearching || isProcessingQuery) && (
            <div style={{ textAlign: 'center', padding: '16px' }}>
              <Space>
                <Spin />
                <Text type="secondary">
                  {isSearching ? '搜索中...' : isStreaming ? '生成回复中...' : '处理中...'}
                </Text>
                <Button
                  type="text"
                  size="small"
                  icon={<StopOutlined />}
                  onClick={() => {
                    abortCurrentRequest();
                    onAbortRequest?.();
                  }}
                >
                  停止
                </Button>
              </Space>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      )}
    </div>
  );
};

export default ChatResult;
