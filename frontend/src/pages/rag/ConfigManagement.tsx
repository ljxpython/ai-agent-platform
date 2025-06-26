import React, { useState, useEffect } from 'react';
import {
  Card,
  Form,
  Input,
  InputNumber,
  Select,
  Switch,
  Button,
  Space,
  Typography,
  Tabs,
  Row,
  Col,
  Alert,
  Divider,
  message,
  Modal,
  Table,
  Tag,
  Tooltip,
} from 'antd';
import {
  SettingOutlined,
  SaveOutlined,
  ReloadOutlined,
  ExportOutlined,
  ImportOutlined,
  EyeInvisibleOutlined,
  EyeOutlined,
  DeleteOutlined,
  PlusOutlined,
  HeartOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons';
import PageLayout from '@/components/PageLayout';

const { Title, Text, Paragraph } = Typography;
const { TabPane } = Tabs;
const { TextArea } = Input;
const { Option } = Select;
const { Password } = Input;

interface SystemConfig {
  embedding: {
    default_model: string;
    batch_size: number;
    max_tokens: number;
    timeout: number;
  };
  vector_db: {
    host: string;
    port: number;
    timeout: number;
    max_connections: number;
  };
  search: {
    default_top_k: number;
    similarity_threshold: number;
    enable_rerank: boolean;
    rerank_top_k: number;
  };
  chunking: {
    chunk_size: number;
    chunk_overlap: number;
    strategy: string;
  };
  performance: {
    cache_enabled: boolean;
    cache_ttl: number;
    max_concurrent_queries: number;
    query_timeout: number;
  };
}

interface APIKey {
  id: string;
  name: string;
  provider: string;
  key: string;
  status: 'active' | 'inactive';
  created_at: string;
  last_used?: string;
}

const ConfigManagement: React.FC = () => {
  const [config, setConfig] = useState<SystemConfig | null>(null);
  const [apiKeys, setApiKeys] = useState<APIKey[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [keyModalVisible, setKeyModalVisible] = useState(false);
  const [showKeys, setShowKeys] = useState<{ [key: string]: boolean }>({});
  const [form] = Form.useForm();
  const [keyForm] = Form.useForm();

  useEffect(() => {
    loadConfig();
    loadAPIKeys();
  }, []);

  const loadConfig = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/v1/rag/config');
      if (response.ok) {
        const data = await response.json();
        setConfig(data.config);
        form.setFieldsValue(data.config);
      }
    } catch (error) {
      message.error('加载配置失败');
    } finally {
      setLoading(false);
    }
  };

  const loadAPIKeys = async () => {
    try {
      const response = await fetch('/api/v1/rag/config/api-keys');
      if (response.ok) {
        const data = await response.json();
        setApiKeys(data.keys || []);
      }
    } catch (error) {
      message.error('加载API密钥失败');
    }
  };

  const handleSaveConfig = async (values: any) => {
    setSaving(true);
    try {
      const response = await fetch('/api/v1/rag/config', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ config: values }),
      });

      const result = await response.json();
      if (result.success) {
        message.success('配置保存成功');
        setConfig(values);
      } else {
        message.error(result.message || '配置保存失败');
      }
    } catch (error) {
      message.error('配置保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleAddAPIKey = async (values: any) => {
    try {
      const response = await fetch('/api/v1/rag/config/api-keys', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(values),
      });

      const result = await response.json();
      if (result.success) {
        message.success('API密钥添加成功');
        setKeyModalVisible(false);
        keyForm.resetFields();
        loadAPIKeys();
      } else {
        message.error(result.message || 'API密钥添加失败');
      }
    } catch (error) {
      message.error('API密钥添加失败');
    }
  };

  const handleDeleteAPIKey = async (keyId: string) => {
    try {
      const response = await fetch(`/api/v1/rag/config/api-keys/${keyId}`, {
        method: 'DELETE',
      });

      const result = await response.json();
      if (result.success) {
        message.success('API密钥删除成功');
        loadAPIKeys();
      } else {
        message.error(result.message || 'API密钥删除失败');
      }
    } catch (error) {
      message.error('API密钥删除失败');
    }
  };

  const toggleKeyVisibility = (keyId: string) => {
    setShowKeys(prev => ({
      ...prev,
      [keyId]: !prev[keyId]
    }));
  };

  const maskKey = (key: string) => {
    if (key.length <= 8) return '*'.repeat(key.length);
    return key.substring(0, 4) + '*'.repeat(key.length - 8) + key.substring(key.length - 4);
  };

  const keyColumns = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '提供商',
      dataIndex: 'provider',
      key: 'provider',
      render: (provider: string) => <Tag color="blue">{provider}</Tag>,
    },
    {
      title: 'API密钥',
      dataIndex: 'key',
      key: 'key',
      render: (key: string, record: APIKey) => (
        <Space>
          <Text code style={{ fontFamily: 'monospace' }}>
            {showKeys[record.id] ? key : maskKey(key)}
          </Text>
          <Button
            type="link"
            size="small"
            icon={showKeys[record.id] ? <EyeInvisibleOutlined /> : <EyeOutlined />}
            onClick={() => toggleKeyVisibility(record.id)}
          />
        </Space>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => (
        <Tag color={status === 'active' ? 'green' : 'red'}>
          {status === 'active' ? '活跃' : '未激活'}
        </Tag>
      ),
    },
    {
      title: '最后使用',
      dataIndex: 'last_used',
      key: 'last_used',
      render: (date: string) => date ? new Date(date).toLocaleString() : '从未使用',
    },
    {
      title: '操作',
      key: 'actions',
      render: (record: APIKey) => (
        <Space>
          <Tooltip title="删除">
            <Button
              type="link"
              danger
              icon={<DeleteOutlined />}
              onClick={() => {
                Modal.confirm({
                  title: '确定删除这个API密钥吗？',
                  content: '删除后将无法恢复',
                  onOk: () => handleDeleteAPIKey(record.id),
                });
              }}
            />
          </Tooltip>
        </Space>
      ),
    },
  ];

  return (
    <PageLayout>
      <div style={{ padding: '24px' }}>
        <div style={{ marginBottom: '24px' }}>
          <Title level={2}>
            <SettingOutlined style={{ marginRight: '8px' }} />
            配置管理
          </Title>
          <Paragraph type="secondary">
            管理RAG系统的全局配置、API密钥和环境参数
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
                我们正在努力完善配置管理功能，包括系统参数配置、API密钥管理和环境变量设置等核心功能。
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

        <Tabs defaultActiveKey="system">
          <TabPane tab="系统配置" key="system">
            <Card>
              <Alert
                message="配置说明"
                description="修改系统配置后需要重启相关服务才能生效。建议在测试环境中验证配置的正确性。"
                type="info"
                showIcon
                style={{ marginBottom: '24px' }}
              />

              <Form
                form={form}
                layout="vertical"
                onFinish={handleSaveConfig}
                initialValues={config}
              >
                <Row gutter={[24, 0]}>
                  <Col span={12}>
                    <Card size="small" title="嵌入模型配置">
                      <Form.Item
                        name={['embedding', 'default_model']}
                        label="默认模型"
                        rules={[{ required: true, message: '请选择默认模型' }]}
                      >
                        <Select placeholder="选择默认嵌入模型">
                          <Option value="text-embedding-ada-002">text-embedding-ada-002</Option>
                          <Option value="text-embedding-3-small">text-embedding-3-small</Option>
                          <Option value="text-embedding-3-large">text-embedding-3-large</Option>
                          <Option value="nomic-embed-text">nomic-embed-text</Option>
                        </Select>
                      </Form.Item>
                      <Form.Item
                        name={['embedding', 'batch_size']}
                        label="批处理大小"
                        rules={[{ required: true, message: '请输入批处理大小' }]}
                      >
                        <InputNumber min={1} max={100} style={{ width: '100%' }} />
                      </Form.Item>
                      <Form.Item
                        name={['embedding', 'max_tokens']}
                        label="最大Token数"
                        rules={[{ required: true, message: '请输入最大Token数' }]}
                      >
                        <InputNumber min={1} max={8192} style={{ width: '100%' }} />
                      </Form.Item>
                      <Form.Item
                        name={['embedding', 'timeout']}
                        label="超时时间(秒)"
                        rules={[{ required: true, message: '请输入超时时间' }]}
                      >
                        <InputNumber min={1} max={300} style={{ width: '100%' }} />
                      </Form.Item>
                    </Card>
                  </Col>

                  <Col span={12}>
                    <Card size="small" title="向量数据库配置">
                      <Form.Item
                        name={['vector_db', 'host']}
                        label="主机地址"
                        rules={[{ required: true, message: '请输入主机地址' }]}
                      >
                        <Input placeholder="例如: localhost" />
                      </Form.Item>
                      <Form.Item
                        name={['vector_db', 'port']}
                        label="端口号"
                        rules={[{ required: true, message: '请输入端口号' }]}
                      >
                        <InputNumber min={1} max={65535} style={{ width: '100%' }} />
                      </Form.Item>
                      <Form.Item
                        name={['vector_db', 'timeout']}
                        label="连接超时(秒)"
                        rules={[{ required: true, message: '请输入连接超时时间' }]}
                      >
                        <InputNumber min={1} max={60} style={{ width: '100%' }} />
                      </Form.Item>
                      <Form.Item
                        name={['vector_db', 'max_connections']}
                        label="最大连接数"
                        rules={[{ required: true, message: '请输入最大连接数' }]}
                      >
                        <InputNumber min={1} max={1000} style={{ width: '100%' }} />
                      </Form.Item>
                    </Card>
                  </Col>
                </Row>

                <Row gutter={[24, 0]} style={{ marginTop: '16px' }}>
                  <Col span={12}>
                    <Card size="small" title="搜索配置">
                      <Form.Item
                        name={['search', 'default_top_k']}
                        label="默认Top-K"
                        rules={[{ required: true, message: '请输入默认Top-K值' }]}
                      >
                        <InputNumber min={1} max={50} style={{ width: '100%' }} />
                      </Form.Item>
                      <Form.Item
                        name={['search', 'similarity_threshold']}
                        label="相似度阈值"
                        rules={[{ required: true, message: '请输入相似度阈值' }]}
                      >
                        <InputNumber min={0} max={1} step={0.1} style={{ width: '100%' }} />
                      </Form.Item>
                      <Form.Item
                        name={['search', 'enable_rerank']}
                        label="启用重排序"
                        valuePropName="checked"
                      >
                        <Switch />
                      </Form.Item>
                      <Form.Item
                        name={['search', 'rerank_top_k']}
                        label="重排序Top-K"
                        rules={[{ required: true, message: '请输入重排序Top-K值' }]}
                      >
                        <InputNumber min={1} max={20} style={{ width: '100%' }} />
                      </Form.Item>
                    </Card>
                  </Col>

                  <Col span={12}>
                    <Card size="small" title="文档分块配置">
                      <Form.Item
                        name={['chunking', 'chunk_size']}
                        label="分块大小"
                        rules={[{ required: true, message: '请输入分块大小' }]}
                      >
                        <InputNumber min={100} max={4000} style={{ width: '100%' }} />
                      </Form.Item>
                      <Form.Item
                        name={['chunking', 'chunk_overlap']}
                        label="分块重叠"
                        rules={[{ required: true, message: '请输入分块重叠' }]}
                      >
                        <InputNumber min={0} max={500} style={{ width: '100%' }} />
                      </Form.Item>
                      <Form.Item
                        name={['chunking', 'strategy']}
                        label="分块策略"
                        rules={[{ required: true, message: '请选择分块策略' }]}
                      >
                        <Select placeholder="选择分块策略">
                          <Option value="recursive">递归分块</Option>
                          <Option value="sentence">句子分块</Option>
                          <Option value="semantic">语义分块</Option>
                        </Select>
                      </Form.Item>
                    </Card>
                  </Col>
                </Row>

                <Card size="small" title="性能配置" style={{ marginTop: '16px' }}>
                  <Row gutter={[24, 0]}>
                    <Col span={6}>
                      <Form.Item
                        name={['performance', 'cache_enabled']}
                        label="启用缓存"
                        valuePropName="checked"
                      >
                        <Switch />
                      </Form.Item>
                    </Col>
                    <Col span={6}>
                      <Form.Item
                        name={['performance', 'cache_ttl']}
                        label="缓存TTL(秒)"
                        rules={[{ required: true, message: '请输入缓存TTL' }]}
                      >
                        <InputNumber min={60} max={86400} style={{ width: '100%' }} />
                      </Form.Item>
                    </Col>
                    <Col span={6}>
                      <Form.Item
                        name={['performance', 'max_concurrent_queries']}
                        label="最大并发查询"
                        rules={[{ required: true, message: '请输入最大并发查询数' }]}
                      >
                        <InputNumber min={1} max={100} style={{ width: '100%' }} />
                      </Form.Item>
                    </Col>
                    <Col span={6}>
                      <Form.Item
                        name={['performance', 'query_timeout']}
                        label="查询超时(秒)"
                        rules={[{ required: true, message: '请输入查询超时时间' }]}
                      >
                        <InputNumber min={1} max={300} style={{ width: '100%' }} />
                      </Form.Item>
                    </Col>
                  </Row>
                </Card>

                <Divider />

                <Space>
                  <Button type="primary" htmlType="submit" loading={saving} icon={<SaveOutlined />}>
                    保存配置
                  </Button>
                  <Button onClick={loadConfig} icon={<ReloadOutlined />}>
                    重置
                  </Button>
                  <Button icon={<ExportOutlined />}>
                    导出配置
                  </Button>
                  <Button icon={<ImportOutlined />}>
                    导入配置
                  </Button>
                </Space>
              </Form>
            </Card>
          </TabPane>

          <TabPane tab="API密钥管理" key="api-keys">
            <Card>
              <div style={{ marginBottom: '16px', display: 'flex', justifyContent: 'space-between' }}>
                <Space>
                  <Text>管理各种AI服务的API密钥</Text>
                  <Tag color="blue">总计: {apiKeys.length}</Tag>
                  <Tag color="green">活跃: {apiKeys.filter(k => k.status === 'active').length}</Tag>
                </Space>
                <Button
                  type="primary"
                  icon={<PlusOutlined />}
                  onClick={() => setKeyModalVisible(true)}
                >
                  添加API密钥
                </Button>
              </div>

              <Table
                columns={keyColumns}
                dataSource={apiKeys}
                rowKey="id"
                pagination={false}
              />
            </Card>
          </TabPane>
        </Tabs>

        {/* API密钥添加模态框 */}
        <Modal
          title="添加API密钥"
          open={keyModalVisible}
          onCancel={() => setKeyModalVisible(false)}
          footer={null}
          width={500}
        >
          <Form form={keyForm} layout="vertical" onFinish={handleAddAPIKey}>
            <Form.Item
              name="name"
              label="密钥名称"
              rules={[{ required: true, message: '请输入密钥名称' }]}
            >
              <Input placeholder="例如: OpenAI Production Key" />
            </Form.Item>

            <Form.Item
              name="provider"
              label="服务提供商"
              rules={[{ required: true, message: '请选择服务提供商' }]}
            >
              <Select placeholder="选择服务提供商">
                <Option value="openai">OpenAI</Option>
                <Option value="azure">Azure OpenAI</Option>
                <Option value="anthropic">Anthropic</Option>
                <Option value="cohere">Cohere</Option>
                <Option value="huggingface">Hugging Face</Option>
              </Select>
            </Form.Item>

            <Form.Item
              name="key"
              label="API密钥"
              rules={[{ required: true, message: '请输入API密钥' }]}
            >
              <Password placeholder="输入API密钥" />
            </Form.Item>

            <Form.Item>
              <Space>
                <Button type="primary" htmlType="submit">
                  添加密钥
                </Button>
                <Button onClick={() => setKeyModalVisible(false)}>
                  取消
                </Button>
              </Space>
            </Form.Item>
          </Form>
        </Modal>
      </div>
    </PageLayout>
  );
};

export default ConfigManagement;
