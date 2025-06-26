import React, { useState, useEffect } from 'react';
import {
  Card,
  Table,
  Button,
  Modal,
  Form,
  Input,
  Select,
  Space,
  Tag,
  Progress,
  message,
  Tabs,
  Typography,
  Row,
  Col,
  Statistic,
  Switch,
  Slider,
  InputNumber,
  Alert,
  Tooltip,
  Divider,
} from 'antd';
import {
  CloudOutlined,
  SettingOutlined,
  ThunderboltOutlined,
  DatabaseOutlined,
  RobotOutlined,
  SearchOutlined,
  ReloadOutlined,
  ExperimentOutlined,
  BarChartOutlined,
  HeartOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons';
import PageLayout from '@/components/PageLayout';

const { Title, Text, Paragraph } = Typography;
const { TabPane } = Tabs;
const { Option } = Select;

interface EmbeddingModel {
  id: string;
  name: string;
  provider: string;
  dimension: number;
  max_tokens: number;
  status: 'active' | 'inactive' | 'loading';
  performance_score: number;
  usage_count: number;
  avg_latency: number;
}

interface VectorDatabase {
  id: string;
  name: string;
  type: 'milvus' | 'pinecone' | 'weaviate' | 'qdrant';
  host: string;
  port: number;
  status: 'connected' | 'disconnected' | 'error';
  total_vectors: number;
  collections: number;
  storage_size: string;
}

interface SearchConfig {
  collection_name: string;
  top_k: number;
  similarity_threshold: number;
  rerank_enabled: boolean;
  hybrid_search: boolean;
  search_strategy: 'semantic' | 'keyword' | 'hybrid';
}

const VectorManagement: React.FC = () => {
  const [embeddingModels, setEmbeddingModels] = useState<EmbeddingModel[]>([]);
  const [vectorDatabases, setVectorDatabases] = useState<VectorDatabase[]>([]);
  const [searchConfigs, setSearchConfigs] = useState<SearchConfig[]>([]);
  const [loading, setLoading] = useState(false);
  const [modelModalVisible, setModelModalVisible] = useState(false);
  const [dbModalVisible, setDbModalVisible] = useState(false);
  const [testModalVisible, setTestModalVisible] = useState(false);
  const [form] = Form.useForm();

  useEffect(() => {
    loadEmbeddingModels();
    loadVectorDatabases();
    loadSearchConfigs();
  }, []);

  const loadEmbeddingModels = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/v1/rag/models/embedding');
      if (response.ok) {
        const data = await response.json();
        setEmbeddingModels(data.models || []);
      }
    } catch (error) {
      message.error('加载嵌入模型失败');
    } finally {
      setLoading(false);
    }
  };

  const loadVectorDatabases = async () => {
    try {
      const response = await fetch('/api/v1/rag/vector-db');
      if (response.ok) {
        const data = await response.json();
        setVectorDatabases(data.databases || []);
      }
    } catch (error) {
      message.error('加载向量数据库失败');
    }
  };

  const loadSearchConfigs = async () => {
    try {
      const response = await fetch('/api/v1/rag/search/configs');
      if (response.ok) {
        const data = await response.json();
        setSearchConfigs(data.configs || []);
      }
    } catch (error) {
      message.error('加载搜索配置失败');
    }
  };

  const handleAddModel = async (values: any) => {
    try {
      const response = await fetch('/api/v1/rag/models/embedding', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(values),
      });

      const result = await response.json();
      if (result.success) {
        message.success('嵌入模型添加成功');
        setModelModalVisible(false);
        form.resetFields();
        loadEmbeddingModels();
      } else {
        message.error(result.message || '嵌入模型添加失败');
      }
    } catch (error) {
      message.error('嵌入模型添加失败');
    }
  };

  const handleTestModel = async (modelId: string) => {
    try {
      const response = await fetch(`/api/v1/rag/models/embedding/${modelId}/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: '这是一个测试文本' }),
      });

      const result = await response.json();
      if (result.success) {
        message.success(`模型测试成功，耗时: ${result.latency}ms`);
      } else {
        message.error(result.message || '模型测试失败');
      }
    } catch (error) {
      message.error('模型测试失败');
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
      case 'connected': return 'green';
      case 'loading': return 'blue';
      case 'inactive':
      case 'disconnected': return 'orange';
      case 'error': return 'red';
      default: return 'default';
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case 'active': return '活跃';
      case 'inactive': return '未激活';
      case 'loading': return '加载中';
      case 'connected': return '已连接';
      case 'disconnected': return '未连接';
      case 'error': return '错误';
      default: return '未知';
    }
  };

  const modelColumns = [
    {
      title: '模型名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: EmbeddingModel) => (
        <Space>
          <RobotOutlined />
          <div>
            <div style={{ fontWeight: 'bold' }}>{text}</div>
            <Text type="secondary" style={{ fontSize: '12px' }}>
              {record.provider} • {record.dimension}维
            </Text>
          </div>
        </Space>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => (
        <Tag color={getStatusColor(status)}>{getStatusText(status)}</Tag>
      ),
    },
    {
      title: '性能评分',
      dataIndex: 'performance_score',
      key: 'performance_score',
      render: (score: number) => (
        <div style={{ width: 100 }}>
          <Progress
            percent={score}
            size="small"
            strokeColor={score > 80 ? '#52c41a' : score > 60 ? '#faad14' : '#ff4d4f'}
          />
        </div>
      ),
    },
    {
      title: '使用次数',
      dataIndex: 'usage_count',
      key: 'usage_count',
      render: (count: number) => count.toLocaleString(),
    },
    {
      title: '平均延迟',
      dataIndex: 'avg_latency',
      key: 'avg_latency',
      render: (latency: number) => `${latency}ms`,
    },
    {
      title: '操作',
      key: 'actions',
      render: (record: EmbeddingModel) => (
        <Space>
          <Button
            type="link"
            icon={<ExperimentOutlined />}
            onClick={() => handleTestModel(record.id)}
          >
            测试
          </Button>
          <Button type="link" icon={<SettingOutlined />}>
            配置
          </Button>
        </Space>
      ),
    },
  ];

  const dbColumns = [
    {
      title: '数据库名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: VectorDatabase) => (
        <Space>
          <DatabaseOutlined />
          <div>
            <div style={{ fontWeight: 'bold' }}>{text}</div>
            <Text type="secondary" style={{ fontSize: '12px' }}>
              {record.type} • {record.host}:{record.port}
            </Text>
          </div>
        </Space>
      ),
    },
    {
      title: '连接状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => (
        <Tag color={getStatusColor(status)}>{getStatusText(status)}</Tag>
      ),
    },
    {
      title: '向量总数',
      dataIndex: 'total_vectors',
      key: 'total_vectors',
      render: (count: number) => count.toLocaleString(),
    },
    {
      title: 'Collections',
      dataIndex: 'collections',
      key: 'collections',
    },
    {
      title: '存储大小',
      dataIndex: 'storage_size',
      key: 'storage_size',
    },
    {
      title: '操作',
      key: 'actions',
      render: (record: VectorDatabase) => (
        <Space>
          <Button type="link" icon={<BarChartOutlined />}>
            监控
          </Button>
          <Button type="link" icon={<SettingOutlined />}>
            配置
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <PageLayout>
      <div style={{ padding: '24px' }}>
        <div style={{ marginBottom: '24px' }}>
          <Title level={2}>
            <CloudOutlined style={{ marginRight: '8px' }} />
            向量管理
          </Title>
          <Paragraph type="secondary">
            管理嵌入模型、向量数据库和搜索配置，优化RAG系统的检索性能
          </Paragraph>
        </div>

        {/* 暖心提醒 */}
        <Alert
          message={
            <span>
              <HeartOutlined style={{ color: '#ff7875', marginRight: '8px' }} />
              暖心提醒
            </span>
          }
          description={
            <div>
              <p style={{ margin: 0, marginBottom: '8px' }}>
                <ExclamationCircleOutlined style={{ color: '#faad14', marginRight: '6px' }} />
                该模块当前正处于开发过程中，暂不对外使用。
              </p>
              <p style={{ margin: 0, color: '#666' }}>
                我们正在努力完善向量管理功能，包括嵌入模型优化、向量数据库监控和搜索参数调优等核心功能。
                预计将在下个版本中正式发布，敬请期待！
              </p>
            </div>
          }
          type="warning"
          showIcon
          style={{
            marginBottom: '24px',
            border: '1px solid #ffe7ba',
            backgroundColor: '#fffbf0'
          }}
          closable
        />

        {/* 统计信息 */}
        <Row gutter={[16, 16]} style={{ marginBottom: '24px' }}>
          <Col span={6}>
            <Card>
              <Statistic
                title="嵌入模型"
                value={embeddingModels.length}
                prefix={<RobotOutlined />}
                valueStyle={{ color: '#1890ff' }}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="向量数据库"
                value={vectorDatabases.length}
                prefix={<DatabaseOutlined />}
                valueStyle={{ color: '#52c41a' }}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="总向量数"
                value={vectorDatabases.reduce((sum, db) => sum + db.total_vectors, 0)}
                prefix={<CloudOutlined />}
                valueStyle={{ color: '#722ed1' }}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="活跃模型"
                value={embeddingModels.filter(m => m.status === 'active').length}
                prefix={<ThunderboltOutlined />}
                valueStyle={{ color: '#fa8c16' }}
              />
            </Card>
          </Col>
        </Row>

        <Tabs defaultActiveKey="models">
          <TabPane tab="嵌入模型" key="models">
            <Card>
              <div style={{ marginBottom: '16px', display: 'flex', justifyContent: 'space-between' }}>
                <Space>
                  <Button
                    type="primary"
                    icon={<RobotOutlined />}
                    onClick={() => setModelModalVisible(true)}
                  >
                    添加模型
                  </Button>
                  <Button icon={<ExperimentOutlined />}>
                    批量测试
                  </Button>
                </Space>
                <Button icon={<ReloadOutlined />} onClick={loadEmbeddingModels}>
                  刷新
                </Button>
              </div>

              <Table
                columns={modelColumns}
                dataSource={embeddingModels}
                rowKey="id"
                loading={loading}
                pagination={false}
              />
            </Card>
          </TabPane>

          <TabPane tab="向量数据库" key="databases">
            <Card>
              <div style={{ marginBottom: '16px', display: 'flex', justifyContent: 'space-between' }}>
                <Space>
                  <Button
                    type="primary"
                    icon={<DatabaseOutlined />}
                    onClick={() => setDbModalVisible(true)}
                  >
                    添加数据库
                  </Button>
                  <Button icon={<BarChartOutlined />}>
                    性能监控
                  </Button>
                </Space>
                <Button icon={<ReloadOutlined />} onClick={loadVectorDatabases}>
                  刷新
                </Button>
              </div>

              <Table
                columns={dbColumns}
                dataSource={vectorDatabases}
                rowKey="id"
                loading={loading}
                pagination={false}
              />
            </Card>
          </TabPane>

          <TabPane tab="搜索配置" key="search">
            <Card title="搜索参数优化">
              <Alert
                message="搜索配置优化"
                description="调整搜索参数以获得最佳的检索效果，建议在测试环境中验证后再应用到生产环境。"
                type="info"
                showIcon
                style={{ marginBottom: '16px' }}
              />

              <Row gutter={[16, 16]}>
                <Col span={12}>
                  <Card size="small" title="相似度搜索">
                    <Form layout="vertical">
                      <Form.Item label="Top-K 数量">
                        <Slider
                          min={1}
                          max={20}
                          defaultValue={5}
                          marks={{ 1: '1', 5: '5', 10: '10', 20: '20' }}
                        />
                      </Form.Item>
                      <Form.Item label="相似度阈值">
                        <Slider
                          min={0}
                          max={1}
                          step={0.1}
                          defaultValue={0.7}
                          marks={{ 0: '0', 0.5: '0.5', 1: '1' }}
                        />
                      </Form.Item>
                      <Form.Item label="启用重排序">
                        <Switch defaultChecked />
                      </Form.Item>
                    </Form>
                  </Card>
                </Col>
                <Col span={12}>
                  <Card size="small" title="混合搜索">
                    <Form layout="vertical">
                      <Form.Item label="搜索策略">
                        <Select defaultValue="hybrid">
                          <Option value="semantic">语义搜索</Option>
                          <Option value="keyword">关键词搜索</Option>
                          <Option value="hybrid">混合搜索</Option>
                        </Select>
                      </Form.Item>
                      <Form.Item label="语义权重">
                        <Slider
                          min={0}
                          max={1}
                          step={0.1}
                          defaultValue={0.7}
                          marks={{ 0: '关键词', 0.5: '平衡', 1: '语义' }}
                        />
                      </Form.Item>
                      <Form.Item label="启用查询扩展">
                        <Switch />
                      </Form.Item>
                    </Form>
                  </Card>
                </Col>
              </Row>

              <Divider />

              <Space>
                <Button type="primary">保存配置</Button>
                <Button onClick={() => setTestModalVisible(true)}>测试搜索</Button>
                <Button>重置默认</Button>
              </Space>
            </Card>
          </TabPane>
        </Tabs>

        {/* 添加模型模态框 */}
        <Modal
          title="添加嵌入模型"
          open={modelModalVisible}
          onCancel={() => setModelModalVisible(false)}
          footer={null}
          width={600}
        >
          <Form form={form} layout="vertical" onFinish={handleAddModel}>
            <Form.Item
              name="name"
              label="模型名称"
              rules={[{ required: true, message: '请输入模型名称' }]}
            >
              <Input placeholder="例如: text-embedding-ada-002" />
            </Form.Item>

            <Form.Item
              name="provider"
              label="提供商"
              rules={[{ required: true, message: '请选择提供商' }]}
            >
              <Select placeholder="选择模型提供商">
                <Option value="openai">OpenAI</Option>
                <Option value="huggingface">Hugging Face</Option>
                <Option value="ollama">Ollama</Option>
                <Option value="azure">Azure OpenAI</Option>
              </Select>
            </Form.Item>

            <Row gutter={16}>
              <Col span={12}>
                <Form.Item
                  name="dimension"
                  label="向量维度"
                  rules={[{ required: true, message: '请输入向量维度' }]}
                >
                  <InputNumber min={1} max={4096} placeholder="1536" style={{ width: '100%' }} />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item
                  name="max_tokens"
                  label="最大Token数"
                  rules={[{ required: true, message: '请输入最大Token数' }]}
                >
                  <InputNumber min={1} max={8192} placeholder="8192" style={{ width: '100%' }} />
                </Form.Item>
              </Col>
            </Row>

            <Form.Item>
              <Space>
                <Button type="primary" htmlType="submit">
                  添加模型
                </Button>
                <Button onClick={() => setModelModalVisible(false)}>
                  取消
                </Button>
              </Space>
            </Form.Item>
          </Form>
        </Modal>

        {/* 搜索测试模态框 */}
        <Modal
          title="搜索测试"
          open={testModalVisible}
          onCancel={() => setTestModalVisible(false)}
          footer={null}
          width={800}
        >
          <Form layout="vertical">
            <Form.Item label="测试查询">
              <Input.TextArea
                rows={3}
                placeholder="输入测试查询..."
                defaultValue="什么是人工智能？"
              />
            </Form.Item>
            <Form.Item label="目标Collection">
              <Select defaultValue="general">
                <Option value="general">通用知识库</Option>
                <Option value="testcase">测试用例</Option>
                <Option value="ui_testing">UI测试</Option>
              </Select>
            </Form.Item>
            <Space>
              <Button type="primary">执行测试</Button>
              <Button>清除结果</Button>
            </Space>
          </Form>
        </Modal>
      </div>
    </PageLayout>
  );
};

export default VectorManagement;
