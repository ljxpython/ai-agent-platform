import React, { useState, useEffect } from 'react';
import {
  Card,
  Table,
  Button,
  Space,
  Tag,
  Modal,
  Form,
  Input,
  InputNumber,
  Select,
  message,
  Popconfirm,
  Typography,
  Statistic,
  Row,
  Col,
  Tooltip,
} from 'antd';
import {
  DatabaseOutlined,
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  EyeOutlined,
  ReloadOutlined,
  SettingOutlined,
  FileTextOutlined,
} from '@ant-design/icons';
import PageLayout from '../../components/PageLayout';

const { Title, Paragraph, Text } = Typography;
const { Option } = Select;

interface Collection {
  id: number;
  name: string;
  display_name: string;
  description: string;
  business_type: string;
  chunk_size: number;
  chunk_overlap: number;
  dimension: number;
  top_k: number;
  similarity_threshold: number;
  is_active: boolean;
  document_count: number;
  created_at: string;
  updated_at: string;
}

const CollectionManagement: React.FC = () => {
  const [collections, setCollections] = useState<Collection[]>([]);
  const [loading, setLoading] = useState(false);
  const [createModalVisible, setCreateModalVisible] = useState(false);
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [statsModalVisible, setStatsModalVisible] = useState(false);
  const [selectedCollection, setSelectedCollection] = useState<Collection | null>(null);
  const [collectionStats, setCollectionStats] = useState<any>(null);
  const [createForm] = Form.useForm();
  const [editForm] = Form.useForm();

  useEffect(() => {
    loadCollections();
  }, []);

  const loadCollections = async () => {
    console.log('🔄 开始加载Collection列表...');
    setLoading(true);
    try {
      const response = await fetch('/api/v1/rag/collections-manage/');
      if (response.ok) {
        const data = await response.json();
        console.log('📋 Collection API响应:', data);

        if (data.code === 200) {
          setCollections(data.data?.collections || []);
          console.log('✅ Collection列表加载成功:', data.data?.collections?.length || 0);
        } else {
          console.error('❌ Collection API返回错误:', data.msg);
          message.error(data.msg || '获取Collection列表失败');
        }
      } else {
        console.error('❌ Collection API请求失败:', response.status);
        message.error('获取Collection列表失败');
      }
    } catch (error) {
      console.error('❌ 加载Collection列表异常:', error);
      message.error('加载Collection列表失败');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateCollection = async (values: any) => {
    console.log('📝 创建Collection:', values);
    try {
      const response = await fetch('/api/v1/rag/collections-manage/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(values),
      });

      const result = await response.json();
      if (response.ok && result.code === 200) {
        console.log('✅ Collection创建成功:', result.data?.collection?.name);
        message.success(result.msg || 'Collection创建成功');
        setCreateModalVisible(false);
        createForm.resetFields();
        loadCollections();
      } else {
        console.error('❌ Collection创建失败:', result.msg);
        message.error(result.msg || 'Collection创建失败');
      }
    } catch (error) {
      console.error('❌ Collection创建异常:', error);
      message.error('Collection创建失败');
    }
  };

  const handleEditCollection = async (values: any) => {
    if (!selectedCollection) return;

    console.log('✏️ 更新Collection:', selectedCollection.id, values);
    try {
      const response = await fetch(`/api/v1/rag/collections-manage/${selectedCollection.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(values),
      });

      const result = await response.json();
      if (response.ok && result.code === 200) {
        console.log('✅ Collection更新成功:', selectedCollection.name);
        message.success(result.msg || 'Collection更新成功');
        setEditModalVisible(false);
        editForm.resetFields();
        setSelectedCollection(null);
        loadCollections();
      } else {
        console.error('❌ Collection更新失败:', result.msg);
        message.error(result.msg || 'Collection更新失败');
      }
    } catch (error) {
      console.error('❌ Collection更新异常:', error);
      message.error('Collection更新失败');
    }
  };

  const handleDeleteCollection = async (collection: Collection) => {
    console.log('🗑️ 删除Collection:', collection.name);
    try {
      const response = await fetch(`/api/v1/rag/collections-manage/${collection.id}`, {
        method: 'DELETE',
      });

      const result = await response.json();
      if (response.ok && result.code === 200) {
        console.log('✅ Collection删除成功:', collection.name);
        message.success(result.msg || 'Collection删除成功');
        loadCollections();
      } else {
        console.error('❌ Collection删除失败:', result.msg);
        message.error(result.msg || 'Collection删除失败');
      }
    } catch (error) {
      console.error('❌ Collection删除异常:', error);
      message.error('Collection删除失败');
    }
  };

  const handleViewStats = async (collection: Collection) => {
    console.log('📊 查看Collection统计:', collection.name);
    try {
      const response = await fetch(`/api/v1/rag/collections-manage/${collection.id}/stats`);
      const result = await response.json();

      if (response.ok && result.code === 200) {
        console.log('✅ Collection统计获取成功:', result.data?.stats);
        setCollectionStats(result.data?.stats);
        setSelectedCollection(collection);
        setStatsModalVisible(true);
      } else {
        console.error('❌ Collection统计获取失败:', result.msg);
        message.error(result.msg || '获取统计信息失败');
      }
    } catch (error) {
      console.error('❌ Collection统计获取异常:', error);
      message.error('获取统计信息失败');
    }
  };

  const openEditModal = (collection: Collection) => {
    console.log('✏️ 打开编辑模态框:', collection.name);
    setSelectedCollection(collection);
    editForm.setFieldsValue({
      display_name: collection.display_name,
      description: collection.description,
      business_type: collection.business_type,
      chunk_size: collection.chunk_size,
      chunk_overlap: collection.chunk_overlap,
      dimension: collection.dimension,
      top_k: collection.top_k,
      similarity_threshold: collection.similarity_threshold,
    });
    setEditModalVisible(true);
  };

  const columns = [
    {
      title: 'Collection名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: Collection) => (
        <Space direction="vertical" size={0}>
          <Text strong>{text}</Text>
          <Text type="secondary" style={{ fontSize: '12px' }}>
            {record.display_name}
          </Text>
        </Space>
      ),
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
      render: (text: string) => (
        <Tooltip title={text}>
          <Text type="secondary">{text || '暂无描述'}</Text>
        </Tooltip>
      ),
    },
    {
      title: '业务类型',
      dataIndex: 'business_type',
      key: 'business_type',
      render: (text: string) => <Tag color="blue">{text}</Tag>,
    },
    {
      title: '文档数量',
      dataIndex: 'document_count',
      key: 'document_count',
      render: (count: number) => (
        <Statistic value={count} suffix="个" valueStyle={{ fontSize: '14px' }} />
      ),
    },
    {
      title: '分块配置',
      key: 'chunk_config',
      render: (record: Collection) => (
        <Space direction="vertical" size={0}>
          <Text style={{ fontSize: '12px' }}>大小: {record.chunk_size}</Text>
          <Text style={{ fontSize: '12px' }}>重叠: {record.chunk_overlap}</Text>
        </Space>
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date: string) => new Date(date).toLocaleString(),
    },
    {
      title: '操作',
      key: 'actions',
      render: (record: Collection) => (
        <Space>
          <Tooltip title="查看统计">
            <Button
              type="link"
              icon={<EyeOutlined />}
              size="small"
              onClick={() => handleViewStats(record)}
            />
          </Tooltip>
          <Tooltip title="编辑">
            <Button
              type="link"
              icon={<EditOutlined />}
              size="small"
              onClick={() => openEditModal(record)}
            />
          </Tooltip>
          <Popconfirm
            title="确定删除这个Collection吗？"
            description={`删除后将无法恢复，请确保Collection中没有文档。`}
            onConfirm={() => handleDeleteCollection(record)}
            okText="确定"
            cancelText="取消"
          >
            <Tooltip title="删除">
              <Button
                type="link"
                danger
                icon={<DeleteOutlined />}
                size="small"
                disabled={record.document_count > 0}
              />
            </Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <PageLayout>
      <div style={{ padding: '24px' }}>
        <div style={{ marginBottom: '24px' }}>
          <Title level={2}>
            <DatabaseOutlined style={{ marginRight: '8px' }} />
            Collection管理
          </Title>
          <Paragraph type="secondary">
            管理RAG知识库的Collection，包括创建、编辑、删除和统计信息查看
          </Paragraph>
        </div>

        {/* 统计信息 */}
        <Row gutter={[16, 16]} style={{ marginBottom: '24px' }}>
          <Col span={6}>
            <Card>
              <Statistic
                title="总Collection数"
                value={collections.length}
                prefix={<DatabaseOutlined />}
                valueStyle={{ color: '#1890ff' }}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="总文档数"
                value={collections.reduce((sum, c) => sum + c.document_count, 0)}
                prefix={<FileTextOutlined />}
                valueStyle={{ color: '#52c41a' }}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="有文档的Collection"
                value={collections.filter(c => c.document_count > 0).length}
                prefix={<SettingOutlined />}
                valueStyle={{ color: '#fa8c16' }}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="空Collection"
                value={collections.filter(c => c.document_count === 0).length}
                prefix={<DatabaseOutlined />}
                valueStyle={{ color: '#722ed1' }}
              />
            </Card>
          </Col>
        </Row>

        <Card>
          <div style={{ marginBottom: '16px', display: 'flex', justifyContent: 'space-between' }}>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => setCreateModalVisible(true)}
            >
              创建Collection
            </Button>
            <Button icon={<ReloadOutlined />} onClick={loadCollections}>
              刷新
            </Button>
          </div>

          <Table
            columns={columns}
            dataSource={collections}
            rowKey="id"
            loading={loading}
            pagination={{
              pageSize: 10,
              showSizeChanger: true,
              showQuickJumper: true,
              showTotal: (total) => `共 ${total} 个Collection`,
            }}
          />
        </Card>

        {/* 创建Collection模态框 */}
        <Modal
          title="创建Collection"
          open={createModalVisible}
          onCancel={() => {
            setCreateModalVisible(false);
            createForm.resetFields();
          }}
          footer={null}
          width={600}
        >
          <Form
            form={createForm}
            layout="vertical"
            onFinish={handleCreateCollection}
          >
            <Form.Item
              name="name"
              label="Collection名称"
              rules={[
                { required: true, message: '请输入Collection名称' },
                { pattern: /^[a-zA-Z0-9_-]+$/, message: '只能包含字母、数字、下划线和连字符' }
              ]}
            >
              <Input placeholder="例如: ai_chat, documents" />
            </Form.Item>

            <Form.Item
              name="display_name"
              label="显示名称"
              rules={[{ required: true, message: '请输入显示名称' }]}
            >
              <Input placeholder="例如: AI聊天知识库" />
            </Form.Item>

            <Form.Item
              name="description"
              label="描述"
            >
              <Input.TextArea rows={3} placeholder="Collection的用途和说明" />
            </Form.Item>

            <Form.Item
              name="business_type"
              label="业务类型"
              initialValue="general"
              rules={[{ required: true, message: '请选择业务类型' }]}
            >
              <Select>
                <Option value="general">通用知识库</Option>
                <Option value="testcase">测试用例</Option>
                <Option value="ui_testing">UI测试</Option>
                <Option value="ai_chat">AI对话</Option>
              </Select>
            </Form.Item>

            <Row gutter={16}>
              <Col span={12}>
                <Form.Item
                  name="chunk_size"
                  label="分块大小"
                  initialValue={512}
                  rules={[{ required: true, message: '请输入分块大小' }]}
                >
                  <InputNumber min={100} max={2048} style={{ width: '100%' }} />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item
                  name="chunk_overlap"
                  label="分块重叠"
                  initialValue={50}
                  rules={[{ required: true, message: '请输入分块重叠' }]}
                >
                  <InputNumber min={0} max={200} style={{ width: '100%' }} />
                </Form.Item>
              </Col>
            </Row>

            <Form.Item style={{ marginBottom: 0, textAlign: 'right' }}>
              <Space>
                <Button onClick={() => {
                  setCreateModalVisible(false);
                  createForm.resetFields();
                }}>
                  取消
                </Button>
                <Button type="primary" htmlType="submit">
                  创建
                </Button>
              </Space>
            </Form.Item>
          </Form>
        </Modal>

        {/* 编辑Collection模态框 */}
        <Modal
          title={`编辑Collection: ${selectedCollection?.name}`}
          open={editModalVisible}
          onCancel={() => {
            setEditModalVisible(false);
            editForm.resetFields();
            setSelectedCollection(null);
          }}
          footer={null}
          width={600}
        >
          <Form
            form={editForm}
            layout="vertical"
            onFinish={handleEditCollection}
          >
            <Form.Item
              name="display_name"
              label="显示名称"
              rules={[{ required: true, message: '请输入显示名称' }]}
            >
              <Input placeholder="例如: AI聊天知识库" />
            </Form.Item>

            <Form.Item
              name="description"
              label="描述"
            >
              <Input.TextArea rows={3} placeholder="Collection的用途和说明" />
            </Form.Item>

            <Form.Item
              name="business_type"
              label="业务类型"
              rules={[{ required: true, message: '请选择业务类型' }]}
            >
              <Select>
                <Option value="general">通用知识库</Option>
                <Option value="testcase">测试用例</Option>
                <Option value="ui_testing">UI测试</Option>
                <Option value="ai_chat">AI对话</Option>
              </Select>
            </Form.Item>

            <Row gutter={16}>
              <Col span={12}>
                <Form.Item
                  name="chunk_size"
                  label="分块大小"
                  rules={[{ required: true, message: '请输入分块大小' }]}
                >
                  <InputNumber min={100} max={2048} style={{ width: '100%' }} />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item
                  name="chunk_overlap"
                  label="分块重叠"
                  rules={[{ required: true, message: '请输入分块重叠' }]}
                >
                  <InputNumber min={0} max={200} style={{ width: '100%' }} />
                </Form.Item>
              </Col>
            </Row>

            <Form.Item style={{ marginBottom: 0, textAlign: 'right' }}>
              <Space>
                <Button onClick={() => {
                  setEditModalVisible(false);
                  editForm.resetFields();
                  setSelectedCollection(null);
                }}>
                  取消
                </Button>
                <Button type="primary" htmlType="submit">
                  更新
                </Button>
              </Space>
            </Form.Item>
          </Form>
        </Modal>

        {/* 统计信息模态框 */}
        <Modal
          title={`Collection统计: ${selectedCollection?.display_name}`}
          open={statsModalVisible}
          onCancel={() => {
            setStatsModalVisible(false);
            setCollectionStats(null);
            setSelectedCollection(null);
          }}
          footer={[
            <Button key="close" onClick={() => {
              setStatsModalVisible(false);
              setCollectionStats(null);
              setSelectedCollection(null);
            }}>
              关闭
            </Button>
          ]}
          width={600}
        >
          {collectionStats && (
            <Row gutter={[16, 16]}>
              <Col span={12}>
                <Card>
                  <Statistic
                    title="总文档数"
                    value={collectionStats.total_documents}
                    prefix={<FileTextOutlined />}
                  />
                </Card>
              </Col>
              <Col span={12}>
                <Card>
                  <Statistic
                    title="已完成"
                    value={collectionStats.completed_documents}
                    prefix={<DatabaseOutlined />}
                    valueStyle={{ color: '#52c41a' }}
                  />
                </Card>
              </Col>
              <Col span={12}>
                <Card>
                  <Statistic
                    title="处理中"
                    value={collectionStats.processing_documents}
                    prefix={<SettingOutlined />}
                    valueStyle={{ color: '#fa8c16' }}
                  />
                </Card>
              </Col>
              <Col span={12}>
                <Card>
                  <Statistic
                    title="成功率"
                    value={collectionStats.success_rate}
                    suffix="%"
                    valueStyle={{ color: '#1890ff' }}
                  />
                </Card>
              </Col>
              <Col span={24}>
                <Card>
                  <Statistic
                    title="总大小"
                    value={collectionStats.total_size_mb}
                    suffix="MB"
                    precision={2}
                  />
                </Card>
              </Col>
            </Row>
          )}
        </Modal>
      </div>
    </PageLayout>
  );
};

export default CollectionManagement;
