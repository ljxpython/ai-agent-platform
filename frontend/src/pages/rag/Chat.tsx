import React, { useState, useEffect, useRef } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import {
  Layout,
  Card,
  Select,
  Button,
  Drawer,
  Space,
  Typography,
  message,
  Spin,
  Row,
  Col
} from 'antd';
import {
  SettingOutlined,
  MessageOutlined,
  RobotOutlined,
  MenuOutlined
} from '@ant-design/icons';
import { useRAGContext } from '@/contexts/RAGContext';
import { Message } from '@/types/rag';
import ChatResult from '@/components/rag/chat/ChatResult';
import ChatSearch from '@/components/rag/chat/ChatSearch';
import ChatSidebar from '@/components/rag/chat/ChatSidebar';
import useSwitchManager from '@/components/rag/hooks/useSwitchManager';

const { Content } = Layout;
const { Title } = Typography;
const { Option } = Select;

interface Collection {
  id: string;
  name: string;
}

const RAGChat: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { pipeline, getClient, selectedModel } = useRAGContext();

  // 基础状态
  const [query, setQuery] = useState('');
  const [hasAttemptedFetch, setHasAttemptedFetch] = useState(false);
  const [selectedCollectionIds, setSelectedCollectionIds] = useState<string[]>([]);
  const [selectedConversationId, setSelectedConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [mode, setMode] = useState<'rag' | 'rag_agent'>('rag_agent');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  // 搜索配置状态
  const [searchLimit, setSearchLimit] = useState<number>(10);
  const [searchFilters, setSearchFilters] = useState('{}');
  const [indexMeasure, setIndexMeasure] = useState<string>('cosine_distance');
  const [includeMetadatas, setIncludeMetadatas] = useState<boolean>(false);
  const [probes, setProbes] = useState<number>();
  const [efSearch, setEfSearch] = useState<number>();

  // 混合搜索配置
  const [fullTextWeight, setFullTextWeight] = useState<number>();
  const [semanticWeight, setSemanticWeight] = useState<number>();
  const [fullTextLimit, setFullTextLimit] = useState<number>();
  const [rrfK, setRrfK] = useState<number>();

  // 知识图谱搜索配置
  const [kgSearchLevel, setKgSearchLevel] = useState<number | null>(null);
  const [maxCommunityDescriptionLength, setMaxCommunityDescriptionLength] = useState<number>(100);
  const [localSearchLimits, setLocalSearchLimits] = useState<Record<string, number>>({});

  // RAG生成配置
  const [temperature, setTemperature] = useState(0.1);
  const [topP, setTopP] = useState(1);
  const [topK, setTopK] = useState(100);
  const [maxTokensToSample, setMaxTokensToSample] = useState(1024);

  // 数据状态
  const [uploadedDocuments, setUploadedDocuments] = useState<string[]>([]);
  const [collections, setCollections] = useState<Collection[]>([]);
  const [userId] = useState(null);

  // 开关管理器
  const { switches, initializeSwitch, updateSwitch } = useSwitchManager();

  // 内容区域引用
  const contentAreaRef = useRef<HTMLDivElement>(null);

  // 从URL参数初始化查询
  useEffect(() => {
    const queryParam = searchParams.get('q');
    if (queryParam) {
      setQuery(decodeURIComponent(queryParam));
    }
  }, [searchParams]);

  // 模式切换时清空查询
  useEffect(() => {
    setQuery('');
  }, [mode]);

  // 初始化开关
  useEffect(() => {
    initializeSwitch(
      'vectorSearch',
      true,
      '向量搜索',
      '向量搜索使用向量表示文档和查询，用于找到与给定查询相似的文档。'
    );
    initializeSwitch(
      'hybridSearch',
      false,
      '混合搜索',
      '混合搜索结合多种搜索方法，提供更准确和相关的搜索结果。'
    );
    initializeSwitch(
      'knowledgeGraphSearch',
      true,
      '知识图谱搜索',
      '请先构建知识图谱才能使用此功能。'
    );
  }, [initializeSwitch]);

  // 处理开关变化
  const handleSwitchChange = (id: string, checked: boolean) => {
    updateSwitch(id, checked);
    message.success(`${switches[id]?.label || id} 已${checked ? '启用' : '禁用'}`);
  };

  // 获取文档列表
  useEffect(() => {
    const fetchDocuments = async () => {
      if (pipeline) {
        try {
          const client = getClient();
          if (!client) {
            throw new Error('Failed to get authenticated client');
          }
          setIsLoading(true);
          const documents = await client.documents.list();
          setUploadedDocuments(documents.results.map((doc: any) => doc.id));
        } catch (error) {
          console.error('Error fetching user documents:', error);
          message.error('获取文档列表失败');
        } finally {
          setIsLoading(false);
          setHasAttemptedFetch(true);
        }
      }
    };

    fetchDocuments();
  }, [pipeline, getClient]);

  // 获取集合列表
  useEffect(() => {
    const fetchCollections = async () => {
      if (pipeline) {
        try {
          const client = getClient();
          if (!client) {
            throw new Error('Failed to get authenticated client');
          }
          const collectionsData = await client.collections.list();
          setCollections(
            collectionsData.results.map((collection: Collection) => ({
              id: collection.id,
              name: collection.name,
            }))
          );
        } catch (error) {
          console.error('Error fetching collections:', error);
          message.error('获取集合列表失败');
        }
      }
    };

    fetchCollections();
  }, [pipeline, getClient]);

  // 安全的JSON解析
  const safeJsonParse = (jsonString: string) => {
    if (typeof jsonString !== 'string') {
      console.warn('Input is not a string:', jsonString);
      return {};
    }
    try {
      return JSON.parse(jsonString);
    } catch (error) {
      console.warn('Invalid JSON input:', error);
      return {};
    }
  };

  // 处理中止请求
  const handleAbortRequest = () => {
    setQuery('');
  };

  // 处理模式变化
  const handleModeChange = (newMode: 'rag' | 'rag_agent') => {
    setMode(newMode);
  };

  // 处理对话选择
  const handleConversationSelect = async (conversationId: string) => {
    setSelectedConversationId(conversationId);
    try {
      const client = getClient();
      if (!client) {
        throw new Error('Failed to get authenticated client');
      }
      const response = await client.conversations.retrieve({
        id: conversationId,
      });
      const fetchedMessages = response.results.map((message: any) => ({
        id: message.id,
        role: message.metadata?.role || 'user',
        content: message.metadata?.content || '',
        timestamp: message.metadata?.timestamp || new Date().toISOString(),
      }));
      setMessages(fetchedMessages);
    } catch (error) {
      console.error('Error fetching conversation:', error);
      message.error('获取对话失败');
    }
  };

  // 侧边栏配置
  const sidebarConfig = {
    showVectorSearch: true,
    showHybridSearch: true,
    showKGSearch: false,
    showRagGeneration: true,
    showConversations: true,
  };

  return (
    <Layout style={{ height: '100vh' }}>
      {/* 侧边栏抽屉 */}
      <Drawer
        title="搜索配置"
        placement="left"
        onClose={() => setSidebarOpen(false)}
        open={sidebarOpen}
        width={400}
        bodyStyle={{ padding: 0 }}
      >
        <ChatSidebar
          isOpen={sidebarOpen}
          onToggle={() => setSidebarOpen(!sidebarOpen)}
          switches={switches}
          handleSwitchChange={handleSwitchChange}
          searchLimit={searchLimit}
          setSearchLimit={setSearchLimit}
          searchFilters={searchFilters}
          setSearchFilters={setSearchFilters}
          collections={collections}
          selectedCollectionIds={selectedCollectionIds}
          setSelectedCollectionIds={setSelectedCollectionIds}
          indexMeasure={indexMeasure}
          setIndexMeasure={setIndexMeasure}
          includeMetadatas={includeMetadatas}
          setIncludeMetadatas={setIncludeMetadatas}
          probes={probes}
          setProbes={setProbes}
          efSearch={efSearch}
          setEfSearch={setEfSearch}
          fullTextWeight={fullTextWeight}
          setFullTextWeight={setFullTextWeight}
          semanticWeight={semanticWeight}
          setSemanticWeight={setSemanticWeight}
          fullTextLimit={fullTextLimit}
          setFullTextLimit={setFullTextLimit}
          rrfK={rrfK}
          setRrfK={setRrfK}
          kgSearchLevel={kgSearchLevel}
          setKgSearchLevel={setKgSearchLevel}
          maxCommunityDescriptionLength={maxCommunityDescriptionLength}
          setMaxCommunityDescriptionLength={setMaxCommunityDescriptionLength}
          localSearchLimits={localSearchLimits}
          setLocalSearchLimits={setLocalSearchLimits}
          temperature={temperature}
          setTemperature={setTemperature}
          topP={topP}
          setTopP={setTopP}
          topK={topK}
          setTopK={setTopK}
          maxTokensToSample={maxTokensToSample}
          setMaxTokensToSample={setMaxTokensToSample}
          config={sidebarConfig}
          onConversationSelect={handleConversationSelect}
        />
      </Drawer>

      <Content style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
        {/* 顶部工具栏 */}
        <Card
          size="small"
          style={{
            borderRadius: 0,
            borderLeft: 0,
            borderRight: 0,
            borderTop: 0,
            marginBottom: 0
          }}
        >
          <Row justify="space-between" align="middle">
            <Col>
              <Space>
                <Button
                  type="text"
                  icon={<MenuOutlined />}
                  onClick={() => setSidebarOpen(true)}
                >
                  配置
                </Button>
                <Select
                  value={mode}
                  onChange={handleModeChange}
                  style={{ width: 150 }}
                >
                  <Option value="rag_agent">
                    <Space>
                      <RobotOutlined />
                      智能助手
                    </Space>
                  </Option>
                  <Option value="rag">
                    <Space>
                      <MessageOutlined />
                      问答模式
                    </Space>
                  </Option>
                </Select>
              </Space>
            </Col>
            <Col>
              <Title level={4} style={{ margin: 0 }}>
                RAG 智能对话
              </Title>
            </Col>
            <Col>
              <Space>
                <Button
                  type="text"
                  icon={<SettingOutlined />}
                  onClick={() => navigate('/rag/settings')}
                >
                  设置
                </Button>
              </Space>
            </Col>
          </Row>
        </Card>

        {/* 主要内容区域 */}
        <div
          ref={contentAreaRef}
          style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden'
          }}
        >
          {isLoading ? (
            <div style={{
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              height: '100%'
            }}>
              <Spin size="large" tip="加载中..." />
            </div>
          ) : (
            <>
              {/* 聊天结果区域 */}
              <div style={{ flex: 1, overflow: 'auto', padding: '16px' }}>
                <ChatResult
                  query={query}
                  setQuery={setQuery}
                  model={selectedModel}
                  userId={userId}
                  pipelineUrl={pipeline?.deploymentUrl || ''}
                  searchLimit={searchLimit}
                  searchFilters={safeJsonParse(searchFilters)}
                  ragTemperature={temperature}
                  ragTopP={topP}
                  ragTopK={topK}
                  ragMaxTokensToSample={maxTokensToSample}
                  uploadedDocuments={uploadedDocuments}
                  setUploadedDocuments={setUploadedDocuments}
                  switches={switches}
                  hasAttemptedFetch={hasAttemptedFetch}
                  mode={mode}
                  selectedCollectionIds={selectedCollectionIds}
                  onAbortRequest={handleAbortRequest}
                  messages={messages}
                  setMessages={setMessages}
                  selectedConversationId={selectedConversationId}
                  setSelectedConversationId={setSelectedConversationId}
                />
              </div>

              {/* 搜索输入区域 */}
              <div style={{ padding: '16px', borderTop: '1px solid #f0f0f0' }}>
                <ChatSearch
                  pipeline={pipeline || undefined}
                  setQuery={setQuery}
                  placeholder={
                    mode === 'rag' ? '请输入您的问题...' : '开始对话...'
                  }
                  disabled={uploadedDocuments?.length === 0 && mode === 'rag'}
                />
              </div>
            </>
          )}
        </div>
      </Content>
    </Layout>
  );
};

export default RAGChat;
