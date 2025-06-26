import React, { useState, useEffect } from 'react';
import {
  Card,
  Table,
  Button,
  Upload,
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
  Popconfirm,
  Tooltip,
  Divider,
} from 'antd';
import {
  UploadOutlined,
  FileTextOutlined,
  DeleteOutlined,
  EyeOutlined,
  EditOutlined,
  CloudUploadOutlined,
  SyncOutlined,
  DatabaseOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import PageLayout from '@/components/PageLayout';

const { Title, Text, Paragraph } = Typography;
const { TabPane } = Tabs;
const { TextArea } = Input;
const { Option } = Select;

interface Document {
  id: string;
  title: string;
  content: string;
  file_path?: string;
  file_type: string;
  file_size: number;
  collection_name: string;
  node_count: number;
  embedding_status: 'pending' | 'processing' | 'completed' | 'failed';
  created_at: string;
  updated_at: string;
  metadata: any;
}

interface ProcessingJob {
  id: string;
  file_name: string;
  collection_name: string;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  progress: number;
  created_at: string;
  error_message?: string;
}

const DocumentManagement: React.FC = () => {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [processingJobs, setProcessingJobs] = useState<ProcessingJob[]>([]);
  const [collections, setCollections] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploadModalVisible, setUploadModalVisible] = useState(false);
  const [textModalVisible, setTextModalVisible] = useState(false);
  const [selectedCollection, setSelectedCollection] = useState<string>('');
  const [selectedFiles, setSelectedFiles] = useState<any[]>([]);
  const [uploading, setUploading] = useState(false);
  const [form] = Form.useForm();
  const [textForm] = Form.useForm();

  useEffect(() => {
    loadDocuments();
    loadCollections();
    loadProcessingJobs();
  }, []);

  const loadDocuments = async () => {
    const operationId = `load_docs_${Date.now()}`;
    console.log(`🚀 [${operationId}] 开始加载文档列表...`);
    setLoading(true);

    try {
      console.log(`📡 [${operationId}] 发送API请求: /api/v1/rag/documents/`);
      const response = await fetch('/api/v1/rag/documents/');

      if (response.ok) {
        const data = await response.json();
        console.log(`📋 [${operationId}] API响应成功:`, {
          code: data.code,
          total: data.total,
          documentCount: data.data?.documents?.length || 0
        });

        // 转换数据格式以匹配前端期望的字段
        const documents = (data.data?.documents || []).map((doc: any, index: number) => {
          console.log(`🔄 [${operationId}] 处理文档 ${index + 1}:`, {
            id: doc.id,
            title: doc.title,
            collection: doc.collection_name,
            fileSize: doc.metadata?.file_size
          });

          return {
            ...doc,
            file_size: doc.metadata?.file_size || 0,
            node_count: Math.floor(Math.random() * 50) + 10, // 临时模拟数据
            embedding_status: doc.metadata?.status || 'completed'
          };
        });

        setDocuments(documents);
        console.log(`✅ [${operationId}] 文档列表加载完成: ${documents.length} 个文档`);

        if (documents.length === 0) {
          console.warn(`⚠️ [${operationId}] 文档列表为空，可能需要检查数据源`);
        }
      } else {
        console.error(`❌ [${operationId}] API请求失败:`, response.status, response.statusText);
        message.error('获取文档列表失败');
      }
    } catch (error) {
      console.error(`💥 [${operationId}] 加载文档异常:`, error);
      message.error('加载文档列表失败');
    } finally {
      setLoading(false);
      console.log(`🏁 [${operationId}] 文档加载操作结束`);
    }
  };

  const loadCollections = async () => {
    try {
      const response = await fetch('/api/v1/rag/collections');
      if (response.ok) {
        const data = await response.json();
        console.log('Collections API response:', data); // 调试日志

        // 解析collections数据
        if (data.data?.collections && Array.isArray(data.data.collections)) {
          // 提取collection名称
          const collectionNames = data.data.collections.map((col: any) => col.name);
          setCollections(collectionNames);
          console.log('Loaded collections:', collectionNames); // 调试日志
        } else {
          console.warn('Collections data format unexpected:', data);
          // 设置默认collections
          setCollections(['ai_chat', 'general', 'testcase', 'ui_testing']);
        }
      } else {
        console.error('Collections API failed:', response.status);
        setCollections(['ai_chat', 'general', 'testcase', 'ui_testing']);
      }
    } catch (error) {
      console.error('加载Collections失败:', error);
      // 设置默认collections
      setCollections(['ai_chat', 'general', 'testcase', 'ui_testing']);
    }
  };

  const loadProcessingJobs = async () => {
    try {
      const response = await fetch('/api/v1/rag/processing/jobs');
      if (response.ok) {
        const data = await response.json();
        setProcessingJobs(data.data?.jobs || []);
      }
    } catch (error) {
      console.error('加载处理任务失败:', error);
    }
  };

  // 文件选择处理
  const handleFileChange = ({ fileList }: any) => {
    setSelectedFiles(fileList);
  };

  // 确认上传文件
  const handleConfirmUpload = async () => {
    try {
      // 验证表单
      const values = await form.validateFields();

      if (selectedFiles.length === 0) {
        message.error('请先选择要上传的文件');
        return;
      }

      setUploading(true);
      const formData = new FormData();

      selectedFiles.forEach(file => {
        formData.append('files', file.originFileObj || file);
      });
      formData.append('collection_name', values.collection_name);

      const response = await fetch('/api/v1/chat/upload', {
        method: 'POST',
        body: formData,
      });

      const result = await response.json();
      if (response.ok && result.success) {
        const { summary } = result;
        let message_text = `文件处理完成！`;

        if (summary.success > 0) {
          message_text += ` 成功上传 ${summary.success} 个文件`;
        }
        if (summary.duplicate > 0) {
          message_text += ` ${summary.duplicate} 个文件已存在`;
        }
        if (summary.failed > 0) {
          message_text += ` ${summary.failed} 个文件失败`;
        }

        message.success(message_text);

        // 重置状态
        setSelectedFiles([]);
        setUploadModalVisible(false);
        form.resetFields();
        loadDocuments();
      } else {
        message.error(result.message || result.msg || '文件上传失败');
      }
    } catch (error: any) {
      if (error.errorFields) {
        // 表单验证错误
        message.error('请填写完整的表单信息');
      } else {
        message.error('文件上传失败');
      }
    } finally {
      setUploading(false);
    }
  };

  // 取消上传
  const handleCancelUpload = () => {
    setSelectedFiles([]);
    setUploadModalVisible(false);
    form.resetFields();
  };

  const handleTextAdd = async (values: any) => {
    try {
      const response = await fetch('/api/v1/rag/documents/add-text', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(values),
      });

      const result = await response.json();
      if (response.ok && result.code === 200) {
        message.success(result.msg || '文本添加成功');
        setTextModalVisible(false);
        textForm.resetFields();
        loadDocuments();
      } else {
        message.error(result.msg || '文本添加失败');
      }
    } catch (error) {
      message.error('文本添加失败');
    }
  };

  const handleDeleteDocument = async (documentId: string) => {
    try {
      const response = await fetch(`/api/v1/rag/documents/${documentId}`, {
        method: 'DELETE',
      });

      const result = await response.json();
      if (response.ok && result.code === 200) {
        message.success(result.msg || '文档删除成功');
        loadDocuments();
      } else {
        message.error(result.msg || '文档删除失败');
      }
    } catch (error) {
      message.error('文档删除失败');
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'green';
      case 'processing': return 'blue';
      case 'pending': return 'orange';
      case 'failed': return 'red';
      default: return 'default';
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case 'completed': return '已完成';
      case 'processing': return '处理中';
      case 'pending': return '等待中';
      case 'failed': return '失败';
      default: return '未知';
    }
  };

  const documentColumns = [
    {
      title: '文档标题',
      dataIndex: 'title',
      key: 'title',
      render: (text: string, record: Document) => (
        <Space>
          <FileTextOutlined />
          <div>
            <div style={{ fontWeight: 'bold' }}>{text}</div>
            <Text type="secondary" style={{ fontSize: '12px' }}>
              {record.file_type} • {(record.file_size / 1024).toFixed(1)} KB
            </Text>
          </div>
        </Space>
      ),
    },
    {
      title: 'Collection',
      dataIndex: 'collection_name',
      key: 'collection_name',
      render: (text: string) => <Tag color="blue">{text}</Tag>,
    },
    {
      title: '节点数量',
      dataIndex: 'node_count',
      key: 'node_count',
      render: (count: number) => (
        <Statistic value={count} suffix="个" valueStyle={{ fontSize: '14px' }} />
      ),
    },
    {
      title: '处理状态',
      dataIndex: 'embedding_status',
      key: 'embedding_status',
      render: (status: string) => (
        <Tag color={getStatusColor(status)}>{getStatusText(status)}</Tag>
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
      render: (record: Document) => (
        <Space>
          <Tooltip title="查看详情">
            <Button type="link" icon={<EyeOutlined />} size="small" />
          </Tooltip>
          <Tooltip title="编辑">
            <Button type="link" icon={<EditOutlined />} size="small" />
          </Tooltip>
          <Popconfirm
            title="确定删除这个文档吗？"
            onConfirm={() => handleDeleteDocument(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Tooltip title="删除">
              <Button type="link" danger icon={<DeleteOutlined />} size="small" />
            </Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const processingColumns = [
    {
      title: '文件名',
      dataIndex: 'filename',
      key: 'filename',
    },
    {
      title: 'Collection',
      dataIndex: 'collection',
      key: 'collection',
      render: (text: string) => <Tag color="blue">{text}</Tag>,
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
      title: '进度',
      dataIndex: 'progress',
      key: 'progress',
      render: (progress: number, record: ProcessingJob) => (
        <Progress
          percent={progress}
          size="small"
          status={record.status === 'failed' ? 'exception' : 'active'}
        />
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date: string) => new Date(date).toLocaleString(),
    },
  ];

  return (
    <PageLayout>
      <div style={{ padding: '24px' }}>
        <div style={{ marginBottom: '24px' }}>
          <Title level={2}>
            <FileTextOutlined style={{ marginRight: '8px' }} />
            文档管理
          </Title>
          <Paragraph type="secondary">
            管理RAG知识库中的文档，支持文件上传、文本添加、批量处理和状态监控
          </Paragraph>
        </div>

        {/* 统计信息 */}
        <Row gutter={[16, 16]} style={{ marginBottom: '24px' }}>
          <Col span={6}>
            <Card>
              <Statistic
                title="总文档数"
                value={documents.length}
                prefix={<FileTextOutlined />}
                valueStyle={{ color: '#1890ff' }}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="处理中"
                value={documents.filter(d => d.embedding_status === 'processing').length}
                prefix={<SyncOutlined />}
                valueStyle={{ color: '#fa8c16' }}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="已完成"
                value={documents.filter(d => d.embedding_status === 'completed').length}
                prefix={<DatabaseOutlined />}
                valueStyle={{ color: '#52c41a' }}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="总节点数"
                value={documents.reduce((sum, d) => sum + d.node_count, 0)}
                prefix={<CloudUploadOutlined />}
                valueStyle={{ color: '#722ed1' }}
              />
            </Card>
          </Col>
        </Row>

        <Tabs defaultActiveKey="documents">
          <TabPane tab="文档列表" key="documents">
            <Card>
              <div style={{ marginBottom: '16px', display: 'flex', justifyContent: 'space-between' }}>
                <Space>
                  <Button
                    type="primary"
                    icon={<UploadOutlined />}
                    onClick={() => setUploadModalVisible(true)}
                  >
                    上传文件
                  </Button>
                  <Button
                    icon={<EditOutlined />}
                    onClick={() => setTextModalVisible(true)}
                  >
                    添加文本
                  </Button>
                </Space>
                <Button icon={<ReloadOutlined />} onClick={loadDocuments}>
                  刷新
                </Button>
              </div>

              <Table
                columns={documentColumns}
                dataSource={documents}
                rowKey="id"
                loading={loading}
                pagination={{
                  pageSize: 10,
                  showSizeChanger: true,
                  showQuickJumper: true,
                  showTotal: (total) => `共 ${total} 个文档`,
                }}
              />
            </Card>
          </TabPane>

          <TabPane tab="处理队列" key="processing">
            <Card>
              <div style={{ marginBottom: '16px', display: 'flex', justifyContent: 'space-between' }}>
                <Text>实时监控文档处理状态</Text>
                <Button icon={<ReloadOutlined />} onClick={loadProcessingJobs}>
                  刷新
                </Button>
              </div>

              <Table
                columns={processingColumns}
                dataSource={processingJobs}
                rowKey="id"
                pagination={false}
                locale={{ emptyText: '暂无处理任务' }}
              />
            </Card>
          </TabPane>
        </Tabs>

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
          <Form form={form} layout="vertical">
            <Form.Item
              name="collection_name"
              label="目标Collection"
              rules={[{ required: true, message: '请选择Collection' }]}
            >
              <Select
                placeholder="选择要上传到的Collection"
              >
                {collections.map(collection => (
                  <Option key={collection} value={collection}>
                    {collection}
                  </Option>
                ))}
              </Select>
            </Form.Item>

            <Form.Item label="选择文件">
              <Upload.Dragger
                multiple
                fileList={selectedFiles}
                beforeUpload={() => false}
                onChange={handleFileChange}
                disabled={uploading}
              >
                <p className="ant-upload-drag-icon">
                  <UploadOutlined style={{ fontSize: 48, color: '#1890ff' }} />
                </p>
                <p className="ant-upload-text">点击或拖拽文件到此区域选择</p>
                <p className="ant-upload-hint">
                  支持PDF、Word、TXT、Markdown等格式，支持多文件选择。
                  <br />
                  选择完成后点击"确认上传"按钮开始上传。
                </p>
              </Upload.Dragger>
            </Form.Item>

            {selectedFiles.length > 0 && (
              <Form.Item label={`已选择 ${selectedFiles.length} 个文件`}>
                <div style={{
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
              </Form.Item>
            )}
          </Form>
        </Modal>

        {/* 文本添加模态框 */}
        <Modal
          title="添加文本到知识库"
          open={textModalVisible}
          onCancel={() => setTextModalVisible(false)}
          footer={null}
          width={600}
        >
          <Form form={textForm} layout="vertical" onFinish={handleTextAdd}>
            <Form.Item
              name="collection_name"
              label="目标Collection"
              rules={[{ required: true, message: '请选择Collection' }]}
            >
              <Select placeholder="选择要添加到的Collection">
                {collections.map(collection => (
                  <Option key={collection} value={collection}>
                    {collection}
                  </Option>
                ))}
              </Select>
            </Form.Item>

            <Form.Item
              name="title"
              label="文档标题"
              rules={[{ required: true, message: '请输入文档标题' }]}
            >
              <Input placeholder="输入文档标题" />
            </Form.Item>

            <Form.Item
              name="content"
              label="文档内容"
              rules={[{ required: true, message: '请输入文档内容' }]}
            >
              <TextArea
                rows={8}
                placeholder="输入文档内容..."
                showCount
                maxLength={10000}
              />
            </Form.Item>

            <Form.Item>
              <Space>
                <Button type="primary" htmlType="submit">
                  添加文档
                </Button>
                <Button onClick={() => setTextModalVisible(false)}>
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

export default DocumentManagement;
