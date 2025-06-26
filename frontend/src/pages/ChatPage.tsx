import React, { useState, useEffect, useRef } from 'react';
import {
  Button,
  Typography,
  message as antMessage,
  Dropdown,
  Select,
  Upload,
  Modal,
  Space,
  Tag,
  Divider,
  Card
} from 'antd';
import {
  ClearOutlined,
  SettingOutlined,
  StarOutlined,
  ShareAltOutlined,
  MoreOutlined,
  BulbOutlined,
  CodeOutlined,
  EditOutlined,
  FileTextOutlined,
  HistoryOutlined,
  UploadOutlined,
  DatabaseOutlined,
  RobotOutlined,
  BookOutlined,
  EyeOutlined,
  EyeInvisibleOutlined,

} from '@ant-design/icons';
import { v4 as uuidv4 } from 'uuid';
import ChatMessage from '@/components/ChatMessage';
import ChatInput from '@/components/ChatInput';
import ConversationHistory from '@/components/ConversationHistory';
import SettingsPanel from '@/components/SettingsPanel';
import PageLayout from '@/components/PageLayout';
import { ChatMessage as ChatMessageType, StreamChunk } from '@/types/chat';
import { chatApi } from '@/services/api';

const { Title, Text } = Typography;
const { Option } = Select;

// RAG消息类型
interface RAGMessage {
  type: 'rag_start' | 'rag_retrieval' | 'rag_retrieved_start' | 'rag_retrieved_chunk' | 'rag_retrieved_end' | 'rag_no_result' | 'agent_start' | 'streaming_chunk' | 'complete' | 'error';
  source: string;
  content: string;
  rag_answer?: string;
  retrieved_count?: number;
  collection_name?: string;
  document_index?: number;
  timestamp: string;
}

const ChatPage: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessageType[]>([]);
  const [loading, setLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string>('');
  const [historyVisible, setHistoryVisible] = useState(false);
  const [settingsVisible, setSettingsVisible] = useState(false);
  const [uploadModalVisible, setUploadModalVisible] = useState(false);
  const [selectedCollection, setSelectedCollection] = useState<string>('ai_chat');
  const [useRAG, setUseRAG] = useState<boolean>(true);
  const [availableCollections, setAvailableCollections] = useState<string[]>([]);
  const [ragStatus, setRagStatus] = useState<any>(null);
  const [isUserScrolling, setIsUserScrolling] = useState<boolean>(false);
  const [shouldAutoScroll, setShouldAutoScroll] = useState<boolean>(true);

  // 文件上传相关状态
  const [selectedFiles, setSelectedFiles] = useState<any[]>([]);
  const [uploading, setUploading] = useState(false);

  // RAG召回文档相关状态
  const [retrievedDocuments, setRetrievedDocuments] = useState<any[]>([]);
  const [showRetrievedDocs, setShowRetrievedDocs] = useState<boolean>(false);
  const [retrievedDocsMessageId, setRetrievedDocsMessageId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const lastScrollTop = useRef<number>(0);
  const isAutoScrolling = useRef<boolean>(false);
  const scrollTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // 滚动到底部
  const scrollToBottom = () => {
    if (shouldAutoScroll && !isUserScrolling && messagesEndRef.current) {
      isAutoScrolling.current = true;
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });

      // 设置一个短暂的延迟来重置自动滚动标志
      setTimeout(() => {
        isAutoScrolling.current = false;
      }, 1000);
    }
  };

  // 检查是否在底部
  const isAtBottom = () => {
    if (!messagesContainerRef.current) return true;
    const { scrollTop, scrollHeight, clientHeight } = messagesContainerRef.current;
    return scrollHeight - scrollTop - clientHeight < 100; // 100px容差
  };

  // 检测用户是否在滚动
  const handleScroll = () => {
    if (!messagesContainerRef.current || isAutoScrolling.current) return;

    const container = messagesContainerRef.current;
    const currentScrollTop = container.scrollTop;

    // 清除之前的超时
    if (scrollTimeoutRef.current) {
      clearTimeout(scrollTimeoutRef.current);
    }

    // 检测滚动方向
    const isScrollingUp = currentScrollTop < lastScrollTop.current;
    const isScrollingDown = currentScrollTop > lastScrollTop.current;

    if (isScrollingUp) {
      // 用户向上滚动，停止自动滚动
      setIsUserScrolling(true);
      setShouldAutoScroll(false);
    } else if (isScrollingDown && isAtBottom()) {
      // 用户向下滚动到底部，恢复自动滚动
      setIsUserScrolling(false);
      setShouldAutoScroll(true);
    }

    lastScrollTop.current = currentScrollTop;

    // 设置超时来检测滚动停止
    scrollTimeoutRef.current = setTimeout(() => {
      if (isAtBottom()) {
        setIsUserScrolling(false);
        setShouldAutoScroll(true);
      }
    }, 150);
  };

  // 只在新消息到达且应该自动滚动时才滚动
  useEffect(() => {
    if (messages.length > 0 && shouldAutoScroll && !isUserScrolling) {
      // 使用requestAnimationFrame确保DOM更新后再滚动
      requestAnimationFrame(() => {
        scrollToBottom();
      });
    }
  }, [messages.length, shouldAutoScroll, isUserScrolling]);

  // 添加滚动事件监听
  useEffect(() => {
    const container = messagesContainerRef.current;
    if (container) {
      container.addEventListener('scroll', handleScroll, { passive: true });
      return () => {
        container.removeEventListener('scroll', handleScroll);
        if (scrollTimeoutRef.current) {
          clearTimeout(scrollTimeoutRef.current);
        }
      };
    }
  }, []);

  // 初始化对话ID和RAG状态
  useEffect(() => {
    setConversationId(uuidv4());
    loadRAGCollections();
    loadRAGStatus();
  }, []);

  // 加载可用的RAG collections
  const loadRAGCollections = async () => {
    try {
      const response = await fetch('/api/v1/chat/collections');
      const data = await response.json();
      if (data.success) {
        setAvailableCollections(data.collections);
      }
    } catch (error) {
      console.error('加载RAG collections失败:', error);
    }
  };

  // 加载RAG状态
  const loadRAGStatus = async () => {
    try {
      const response = await fetch('/api/v1/chat/stats');
      const data = await response.json();
      setRagStatus(data);
    } catch (error) {
      console.error('加载RAG状态失败:', error);
    }
  };

  // 文件选择处理
  const handleFileChange = ({ fileList }: any) => {
    setSelectedFiles(fileList);
  };

  // 确认上传文件
  const handleConfirmUpload = async () => {
    if (selectedFiles.length === 0) {
      antMessage.warning('请先选择要上传的文件');
      return;
    }

    setUploading(true);
    const formData = new FormData();

    selectedFiles.forEach(file => {
      formData.append('files', file.originFileObj || file);
    });
    formData.append('collection_name', selectedCollection);
    formData.append('user_id', 'frontend_user');

    try {
      const response = await fetch('/api/v1/chat/upload', {
        method: 'POST',
        body: formData,
      });

      const result = await response.json();

      if (result.success) {
        const { summary } = result;
        let message = `文件处理完成！`;

        if (summary.success > 0) {
          message += ` 成功上传 ${summary.success} 个文件`;
        }
        if (summary.duplicate > 0) {
          message += ` ${summary.duplicate} 个文件已存在`;
        }
        if (summary.failed > 0) {
          message += ` ${summary.failed} 个文件失败`;
        }

        antMessage.success(message);

        // 显示详细结果
        result.results.forEach((fileResult: any) => {
          if (fileResult.status === 'duplicate') {
            antMessage.info(`${fileResult.filename}: 文件已存在于知识库中`);
          } else if (!fileResult.success) {
            antMessage.error(`${fileResult.filename}: ${fileResult.message}`);
          }
        });

        // 重置状态
        setSelectedFiles([]);
        setUploadModalVisible(false);

        // 刷新RAG状态
        loadRAGStatus();
      } else {
        antMessage.error('文件上传失败');
      }
    } catch (error) {
      console.error('文件上传失败:', error);
      antMessage.error('文件上传失败');
    } finally {
      setUploading(false);
    }
  };

  // 取消上传
  const handleCancelUpload = () => {
    setSelectedFiles([]);
    setUploadModalVisible(false);
  };

  // 清理 EventSource
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  const handleSendMessage = async (content: string) => {
    if (!content.trim()) return;

    const userMessage: ChatMessageType = {
      id: uuidv4(),
      content,
      role: 'user',
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setLoading(true);

    // 创建助手消息占位符（但不立即添加到消息列表）
    const assistantMessageId = uuidv4();
    const assistantMessage: ChatMessageType = {
      id: assistantMessageId,
      content: '',
      role: 'assistant',
      timestamp: new Date(),
      isStreaming: true,
    };

    try {
      // 使用RAG增强的流式API
      const apiUrl = useRAG ? '/api/v1/chat/stream/rag' : '/api/v1/chat/stream';
      const requestBody = useRAG ? {
        message: content,
        conversation_id: conversationId,
        system_message: '你是一个有用的AI助手，请用中文回答问题。',
        collection_name: selectedCollection,
        use_rag: useRAG,
      } : {
        message: content,
        conversation_id: conversationId,
        system_message: '你是一个有用的AI助手，请用中文回答问题。',
      };

      const response = await fetch(apiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        throw new Error('网络请求失败');
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (reader) {
        let buffer = '';
        let ragInfo = '';

        while (true) {
          const { done, value } = await reader.read();

          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6));

                if (useRAG) {
                  // 处理RAG增强的消息
                  const ragMessage: RAGMessage = data;

                  if (ragMessage.type === 'rag_start') {
                    // RAG查询开始 - 清空之前的召回文档
                    setRetrievedDocuments([]);
                    setShowRetrievedDocs(false);
                    setRetrievedDocsMessageId(null);
                    setMessages(prev =>
                      prev.map(msg =>
                        msg.id === assistantMessageId
                          ? { ...msg, content: msg.content + `🔍 ${ragMessage.content}\n` }
                          : msg
                      )
                    );
                  } else if (ragMessage.type === 'rag_retrieval') {
                    // RAG检索结果
                    setMessages(prev =>
                      prev.map(msg =>
                        msg.id === assistantMessageId
                          ? { ...msg, content: msg.content + `📄 ${ragMessage.content}\n` }
                          : msg
                      )
                    );
                  } else if (ragMessage.type === 'rag_retrieved_start') {
                    // 召回内容开始 - 创建召回文档消息
                    const docsMessageId = uuidv4();
                    setRetrievedDocsMessageId(docsMessageId);

                    const retrievedDocsMessage: ChatMessageType = {
                      id: docsMessageId,
                      content: ragMessage.content,
                      role: 'retrieved_docs',
                      timestamp: new Date(),
                      retrievedDocuments: []
                    };

                    setMessages(prev => [...prev, retrievedDocsMessage]);
                  } else if (ragMessage.type === 'rag_retrieved_chunk') {
                    // 召回文档内容块 - 更新召回文档消息
                    const docIndex = ragMessage.document_index || 0;
                    const content = ragMessage.content;

                    // 解析相似度分数（如果存在）
                    const similarityMatch = content.match(/相似度:\s*([\d.]+)/);
                    const similarity = similarityMatch ? parseFloat(similarityMatch[1]) : undefined;

                    // 更新召回文档列表
                    setRetrievedDocuments(prev => {
                      const existingDoc = prev.find(doc => doc.index === docIndex);
                      if (existingDoc) {
                        // 更新现有文档内容
                        return prev.map(doc =>
                          doc.index === docIndex
                            ? { ...doc, content: doc.content + content, similarity: similarity || doc.similarity }
                            : doc
                        );
                      } else {
                        // 添加新文档
                        return [...prev, { index: docIndex, content, similarity }];
                      }
                    });

                    // 更新召回文档消息
                    if (retrievedDocsMessageId) {
                      setMessages(prev =>
                        prev.map(msg => {
                          if (msg.id === retrievedDocsMessageId) {
                            const updatedDocs = [...(msg.retrievedDocuments || [])];
                            const existingDocIndex = updatedDocs.findIndex(doc => doc.index === docIndex);

                            if (existingDocIndex >= 0) {
                              updatedDocs[existingDocIndex] = {
                                ...updatedDocs[existingDocIndex],
                                content: updatedDocs[existingDocIndex].content + content,
                                similarity: similarity || updatedDocs[existingDocIndex].similarity
                              };
                            } else {
                              updatedDocs.push({ index: docIndex, content, similarity });
                            }

                            return { ...msg, retrievedDocuments: updatedDocs };
                          }
                          return msg;
                        })
                      );
                    }
                  } else if (ragMessage.type === 'rag_retrieved_end') {
                    // 召回内容结束 - 创建AI助手消息
                    setMessages(prev => [...prev, assistantMessage]);
                  } else if (ragMessage.type === 'rag_no_result') {
                    // RAG无结果
                    setMessages(prev =>
                      prev.map(msg =>
                        msg.id === assistantMessageId
                          ? { ...msg, content: msg.content + ragMessage.content + '\n\n' }
                          : msg
                      )
                    );
                  } else if (ragMessage.type === 'agent_start') {
                    // Agent开始处理 - 添加AI助手消息到消息列表
                    const updatedAssistantMessage = {
                      ...assistantMessage,
                      content: ragMessage.content + '\n\n'
                    };
                    setMessages(prev => [...prev, updatedAssistantMessage]);
                  } else if (ragMessage.type === 'streaming_chunk') {
                    // 流式内容
                    setMessages(prev =>
                      prev.map(msg =>
                        msg.id === assistantMessageId
                          ? { ...msg, content: msg.content + ragMessage.content }
                          : msg
                      )
                    );
                  } else if (ragMessage.type === 'complete') {
                    // 完成
                    setMessages(prev =>
                      prev.map(msg =>
                        msg.id === assistantMessageId
                          ? { ...msg, isStreaming: false }
                          : msg
                      )
                    );
                    break;
                  } else if (ragMessage.type === 'error') {
                    // 错误
                    setMessages(prev =>
                      prev.map(msg =>
                        msg.id === assistantMessageId
                          ? { ...msg, content: msg.content + '\n\n' + ragMessage.content, isStreaming: false }
                          : msg
                      )
                    );
                    break;
                  }
                } else {
                  // 处理普通流式消息
                  const chunk: StreamChunk = data;

                  if (chunk.content) {
                    setMessages(prev =>
                      prev.map(msg =>
                        msg.id === assistantMessageId
                          ? { ...msg, content: msg.content + chunk.content }
                          : msg
                      )
                    );
                  }

                  if (chunk.is_complete) {
                    setMessages(prev =>
                      prev.map(msg =>
                        msg.id === assistantMessageId
                          ? { ...msg, isStreaming: false }
                          : msg
                      )
                    );
                    break;
                  }
                }
              } catch (e) {
                console.error('解析SSE数据失败:', e);
              }
            }
          }
        }
      }
    } catch (error) {
      console.error('发送消息失败:', error);
      antMessage.error('发送消息失败，请重试');

      // 移除失败的助手消息
      setMessages(prev => prev.filter(msg => msg.id !== assistantMessageId));
    } finally {
      setLoading(false);
    }
  };

  const handleClearChat = async () => {
    try {
      if (conversationId) {
        await chatApi.clearConversation(conversationId);
      }
      setMessages([]);
      setConversationId(uuidv4());
      antMessage.success('对话已清除');
    } catch (error) {
      console.error('清除对话失败:', error);
      antMessage.error('清除对话失败');
    }
  };

  // 测试平台相关的建议卡片
  const suggestionCards = [
    {
      icon: <FileTextOutlined />,
      title: "测试用例生成",
      description: "根据用户登录功能需求，生成完整的测试用例",
      color: "#f59e0b"
    },
    {
      icon: <CodeOutlined />,
      title: "自动化脚本",
      description: "用 Selenium 编写 Web 自动化测试脚本，包含页面对象模式",
      color: "#10b981"
    },
    {
      icon: <BulbOutlined />,
      title: "问题诊断",
      description: "分析测试失败的原因，并提供解决方案和优化建议",
      color: "#8b5cf6"
    },
    {
      icon: <EditOutlined />,
      title: "测试报告",
      description: "帮我分析测试结果数据，生成测试报告和改进建议",
      color: "#ef4444"
    }
  ];

  const menuItems = [
    {
      key: 'upload',
      icon: <UploadOutlined />,
      label: '上传文件到知识库',
      onClick: () => setUploadModalVisible(true)
    },
    {
      key: 'collections',
      icon: <DatabaseOutlined />,
      label: '知识库管理',
      onClick: loadRAGCollections
    },
    {
      key: 'divider1',
      type: 'divider'
    },
    {
      key: 'history',
      icon: <HistoryOutlined />,
      label: '对话历史',
      onClick: () => setHistoryVisible(true)
    },
    {
      key: 'clear',
      icon: <ClearOutlined />,
      label: '清除对话',
      onClick: handleClearChat,
      disabled: messages.length === 0
    },
    {
      key: 'divider2',
      type: 'divider'
    },
    {
      key: 'share',
      icon: <ShareAltOutlined />,
      label: '分享对话'
    },
    {
      key: 'star',
      icon: <StarOutlined />,
      label: '收藏对话'
    },
    {
      key: 'settings',
      icon: <SettingOutlined />,
      label: '设置',
      onClick: () => setSettingsVisible(true)
    }
  ];

  return (
    <PageLayout
      background="#f5f5f5"
      padding="0"
    >
      <div style={{ minHeight: 'calc(100vh - 64px)', position: 'relative', background: 'transparent' }}>

        <div style={{
          height: 'calc(100vh - 64px)',
          display: 'flex',
          flexDirection: 'column',
          maxWidth: '1200px',
          margin: '0 auto',
          padding: '20px',
          position: 'relative',
          zIndex: 1
        }}>
        {/* Gemini 风格头部 */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '20px 0',
          borderBottom: messages.length > 0 ? '1px solid #e8e8e8' : 'none'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{
              width: 40,
              height: 40,
              borderRadius: '50%',
              background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'white',
              fontSize: 18,
              fontWeight: 'bold'
            }}>
              G
            </div>
            <div>
              <Title level={3} style={{ margin: 0, color: '#262626', fontWeight: 500 }}>
                测试助手
              </Title>
              <Text style={{ color: '#8c8c8c', fontSize: 14 }}>
                自动化测试平台 AI 模块 {useRAG && `• 知识库: ${selectedCollection}`}
              </Text>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            {/* RAG控制面板 */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '6px 12px',
              background: useRAG ? '#f6ffed' : '#fafafa',
              border: `1px solid ${useRAG ? '#b7eb8f' : '#d9d9d9'}`,
              borderRadius: 20,
              transition: 'all 0.3s ease',
            }}>
              <DatabaseOutlined
                style={{
                  color: useRAG ? '#52c41a' : '#8c8c8c',
                  fontSize: 14
                }}
              />
              <Select
                value={selectedCollection}
                onChange={setSelectedCollection}
                style={{
                  width: 100,
                  fontSize: 12,
                }}
                size="small"
                placeholder="知识库"
                variant="borderless"
                suffixIcon={null}
                disabled={!useRAG}
              >
                {availableCollections.map(collection => (
                  <Option key={collection} value={collection}>
                    <Space size={4}>
                      <DatabaseOutlined style={{ fontSize: 12 }} />
                      {collection}
                    </Space>
                  </Option>
                ))}
              </Select>

              <Divider type="vertical" style={{ margin: '0 4px', height: 16 }} />

              <Button
                type="text"
                size="small"
                icon={<BookOutlined style={{ fontSize: 12 }} />}
                onClick={() => setUseRAG(!useRAG)}
                style={{
                  color: useRAG ? '#52c41a' : '#8c8c8c',
                  fontSize: 12,
                  height: 24,
                  padding: '0 6px',
                  border: 'none',
                  background: 'transparent',
                }}
              >
                {useRAG ? '已启用' : '启用'}
              </Button>
            </div>

            <Dropdown menu={{ items: menuItems }} trigger={['click']}>
              <Button
                type="text"
                icon={<MoreOutlined />}
                style={{
                  color: '#595959',
                  border: '1px solid #d9d9d9',
                  borderRadius: 20,
                  width: 32,
                  height: 32,
                }}
                className="gemini-hover"
              />
            </Dropdown>
          </div>
        </div>

        {/* 主要内容区域 */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', paddingTop: 20 }}>
          {messages.length === 0 ? (
            /* 欢迎页面 - Gemini 风格 */
            <div style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              textAlign: 'center',
              padding: '40px 20px'
            }}>
              <div style={{
                marginBottom: 48,
                animation: 'geminiSlideIn 0.8s cubic-bezier(0.4, 0, 0.2, 1)'
              }}>
                <Title level={1} style={{
                  color: '#262626',
                  fontSize: 48,
                  fontWeight: 300,
                  marginBottom: 16,
                  background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent'
                }}>
                  你好，我是测试助手
                </Title>
                <Text style={{
                  color: '#595959',
                  fontSize: 18,
                  display: 'block',
                  marginBottom: 8
                }}>
                  我可以帮助您生成测试用例、编写自动化脚本、诊断问题等
                </Text>
                <Text style={{
                  color: '#8c8c8c',
                  fontSize: 14
                }}>
                  选择下面的测试场景开始对话，或者直接描述您的测试需求
                </Text>
              </div>

              {/* 建议卡片 */}
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
                gap: 16,
                width: '100%',
                maxWidth: 800,
                marginBottom: 40
              }}>
                {suggestionCards.map((card, index) => (
                  <div
                    key={index}
                    className="glass-effect gemini-hover"
                    style={{
                      padding: 20,
                      borderRadius: 16,
                      cursor: 'pointer',
                      transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                      animationDelay: `${index * 0.1}s`
                    }}
                    onClick={() => handleSendMessage(card.description)}
                  >
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      marginBottom: 12
                    }}>
                      <div style={{
                        width: 32,
                        height: 32,
                        borderRadius: 8,
                        backgroundColor: card.color,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: 'white',
                        marginRight: 12
                      }}>
                        {card.icon}
                      </div>
                      <Text style={{
                        color: '#262626',
                        fontWeight: 500,
                        fontSize: 16
                      }}>
                        {card.title}
                      </Text>
                    </div>
                    <Text style={{
                      color: '#595959',
                      fontSize: 14,
                      lineHeight: 1.5
                    }}>
                      {card.description}
                    </Text>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            /* 对话模式 */
            <div style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              backgroundColor: 'white',
              borderRadius: '20px 20px 0 0',
              overflow: 'hidden',
              position: 'relative'
            }}>
              {/* 消息列表 */}
              <div
                ref={messagesContainerRef}
                style={{
                  flex: 1,
                  overflowY: 'auto',
                  padding: '24px',
                  backgroundColor: 'transparent'
                }}
              >
                {messages.map((message) => (
                  <ChatMessage key={message.id} message={message} />
                ))}
                <div ref={messagesEndRef} />
              </div>

              {/* 滚动控制按钮 */}
              {!shouldAutoScroll && (
                <div style={{
                  position: 'absolute',
                  bottom: 80,
                  right: 24,
                  zIndex: 1000
                }}>
                  <Button
                    type="primary"
                    shape="circle"
                    size="small"
                    icon={<div style={{ fontSize: 12 }}>↓</div>}
                    onClick={() => {
                      setIsUserScrolling(false);
                      setShouldAutoScroll(true);
                      isAutoScrolling.current = true;
                      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
                      setTimeout(() => {
                        isAutoScrolling.current = false;
                      }, 1000);
                    }}
                    style={{
                      backgroundColor: '#1890ff',
                      borderColor: '#1890ff',
                      boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
                    }}
                    title="回到底部"
                  />
                </div>
              )}
            </div>
          )}

          {/* 输入区域 - 始终显示 */}
          <div style={{
            backgroundColor: messages.length > 0 ? 'white' : 'white',
            borderRadius: messages.length > 0 ? '0 0 20px 20px' : '20px'
          }}>
            <ChatInput
              onSend={handleSendMessage}
              loading={loading}
              placeholder="输入您的问题..."
            />
          </div>
        </div>
      </div>

      {/* 对话历史侧边栏 */}
      <ConversationHistory
        visible={historyVisible}
        onClose={() => setHistoryVisible(false)}
        onSelectConversation={(id) => {
          // 这里应该加载选中的对话
          console.log('选择对话:', id);
          setHistoryVisible(false);
        }}
        currentConversationId={conversationId}
      />

      {/* 设置面板 */}
      <SettingsPanel
        visible={settingsVisible}
        onClose={() => setSettingsVisible(false)}
      />

      {/* 文件上传模态框 */}
      <Modal
        title="上传文件到知识库"
        open={uploadModalVisible}
        onCancel={handleCancelUpload}
        footer={[
          <Button key="cancel" onClick={handleCancelUpload}>
            取消
          </Button>,
          <Button
            key="upload"
            type="primary"
            loading={uploading}
            disabled={selectedFiles.length === 0}
            onClick={handleConfirmUpload}
          >
            确认上传 {selectedFiles.length > 0 && `(${selectedFiles.length}个文件)`}
          </Button>
        ]}
        width={700}
      >
        <div style={{ padding: '20px 0' }}>
          <Space direction="vertical" style={{ width: '100%' }} size="large">
            <div>
              <Text strong>选择知识库：</Text>
              <Select
                value={selectedCollection}
                onChange={setSelectedCollection}
                style={{ width: '100%', marginTop: 8 }}
                placeholder="选择要上传到的知识库"
              >
                {availableCollections.map(collection => (
                  <Select.Option key={collection} value={collection}>
                    <Space>
                      <DatabaseOutlined />
                      {collection}
                    </Space>
                  </Select.Option>
                ))}
              </Select>
            </div>

            <div>
              <Text strong>选择文件：</Text>
              <Upload.Dragger
                multiple
                fileList={selectedFiles}
                beforeUpload={() => false}
                onChange={handleFileChange}
                style={{ marginTop: 8 }}
                disabled={uploading}
              >
                <p className="ant-upload-drag-icon">
                  <UploadOutlined style={{ fontSize: 48, color: '#1890ff' }} />
                </p>
                <p className="ant-upload-text">点击或拖拽文件到此区域选择</p>
                <p className="ant-upload-hint">
                  支持多文件选择。选择完成后点击"确认上传"按钮开始上传。
                  <br />
                  系统会自动检测重复文件，避免重复上传相同内容。
                </p>
              </Upload.Dragger>
            </div>

            {selectedFiles.length > 0 && (
              <div>
                <Text strong>已选择 {selectedFiles.length} 个文件：</Text>
                <div style={{
                  marginTop: 8,
                  maxHeight: 200,
                  overflowY: 'auto',
                  border: '1px solid #d9d9d9',
                  borderRadius: 6,
                  padding: 12
                }}>
                  {selectedFiles.map((file, index) => (
                    <div key={index} style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      padding: '4px 0',
                      borderBottom: index < selectedFiles.length - 1 ? '1px solid #f0f0f0' : 'none'
                    }}>
                      <span>{file.name}</span>
                      <Tag color="blue">{(file.size / 1024).toFixed(1)} KB</Tag>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {ragStatus && (
              <Card size="small" title="知识库状态">
                <Space direction="vertical" style={{ width: '100%' }}>
                  <div>
                    <Tag color={ragStatus.rag_available ? 'green' : 'red'}>
                      {ragStatus.rag_available ? '知识库可用' : '知识库不可用'}
                    </Tag>
                  </div>
                  {ragStatus.rag_available && (
                    <div>
                      <Text type="secondary">
                        可用知识库: {ragStatus.rag_collections?.join(', ') || '无'}
                      </Text>
                    </div>
                  )}
                </Space>
              </Card>
            )}
          </Space>
        </div>
      </Modal>
      </div>
    </PageLayout>
  );
};

export default ChatPage;
