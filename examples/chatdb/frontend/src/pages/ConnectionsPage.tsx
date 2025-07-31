import React, { useState, useEffect } from 'react';
import {
  Table, Button, Modal, Form, Input, Select,
  Space, message, Popconfirm, Card, Typography
} from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, CheckCircleOutlined, DatabaseOutlined } from '@ant-design/icons';
import * as api from '../services/api';

const { Option } = Select;
const { Title } = Typography;

interface Connection {
  id: number;
  name: string;
  db_type: string;
  host: string;
  port: number;
  username: string;
  database_name: string;
  created_at: string;
  updated_at: string;
}

const ConnectionsPage: React.FC = () => {
  const [connections, setConnections] = useState<Connection[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [modalVisible, setModalVisible] = useState<boolean>(false);
  const [editingConnection, setEditingConnection] = useState<Connection | null>(null);
  const [discoveringSchema, setDiscoveringSchema] = useState<boolean>(false);
  const [form] = Form.useForm();

  useEffect(() => {
    fetchConnections();
  }, []);

  const fetchConnections = async () => {
    setLoading(true);
    try {
      const response = await api.getConnections();
      setConnections(response.data);
    } catch (error) {
      message.error('获取连接失败');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const showModal = (connection?: Connection) => {
    setEditingConnection(connection || null);
    form.resetFields();
    if (connection) {
      form.setFieldsValue({
        name: connection.name,
        db_type: connection.db_type,
        host: connection.host,
        port: connection.port,
        username: connection.username,
        database_name: connection.database_name,
      });
    }
    setModalVisible(true);
  };

  const handleCancel = () => {
    setModalVisible(false);
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();

      if (editingConnection) {
        await api.updateConnection(editingConnection.id, values);
        message.success('连接更新成功');
        setModalVisible(false);
        fetchConnections();
      } else {
        // 创建新连接
        setModalVisible(false); // 先关闭模态框
        const createResponse = await api.createConnection(values);
        message.success('连接创建成功');
        fetchConnections();

        // 自动发现并保存数据库结构
        await handleDiscoverSchema(createResponse.data.id);
      }
    } catch (error) {
      message.error('保存连接失败');
      console.error(error);
    }
  };

  // 发现并保存数据库结构
  const handleDiscoverSchema = async (connectionId: number) => {
    try {
      setDiscoveringSchema(true);
      message.loading({ content: '正在分析数据库结构...', key: 'discoverSchema', duration: 0 });

      const response = await api.discoverAndSaveSchema(connectionId);

      if (response.data.status === 'success') {
        message.success({ content: '数据库结构分析完成', key: 'discoverSchema' });
        console.log('Discovered schema:', response.data);
      } else {
        message.error({ content: '数据库结构分析失败', key: 'discoverSchema' });
      }
    } catch (error) {
      console.error('Failed to discover schema:', error);
      message.error({ content: '数据库结构分析失败', key: 'discoverSchema' });
    } finally {
      setDiscoveringSchema(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await api.deleteConnection(id);
      message.success('连接删除成功');
      fetchConnections();
    } catch (error) {
      message.error('删除连接失败');
      console.error(error);
    }
  };

  const handleTest = async (id: number) => {
    try {
      const response = await api.testConnection(id);
      if (response.data.status === 'success') {
        message.success('连接测试成功');
      } else {
        message.error(`连接测试失败: ${response.data.message}`);
      }
    } catch (error) {
      message.error('连接测试失败');
      console.error(error);
    }
  };

  const columns = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '类型',
      dataIndex: 'db_type',
      key: 'db_type',
    },
    {
      title: '主机',
      dataIndex: 'host',
      key: 'host',
    },
    {
      title: '端口',
      dataIndex: 'port',
      key: 'port',
    },
    {
      title: '数据库',
      dataIndex: 'database_name',
      key: 'database_name',
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: any, record: Connection) => (
        <Space size="middle">
          <Button
            type="primary"
            icon={<CheckCircleOutlined />}
            onClick={() => handleTest(record.id)}
            size="small"
          >
            测试
          </Button>
          <Button
            icon={<DatabaseOutlined />}
            onClick={() => handleDiscoverSchema(record.id)}
            size="small"
            loading={discoveringSchema}
          >
            分析结构
          </Button>
          <Button
            icon={<EditOutlined />}
            onClick={() => showModal(record)}
            size="small"
          >
            编辑
          </Button>
          <Popconfirm
            title="确定要删除这个连接吗？"
            onConfirm={() => handleDelete(record.id)}
            okText="是"
            cancelText="否"
          >
            <Button
              danger
              icon={<DeleteOutlined />}
              size="small"
            >
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div className="connections-page">
      <Card>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
          <Title level={4}>数据库连接</Title>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => showModal()}
            disabled={discoveringSchema}
          >
            添加连接
          </Button>
        </div>

        <Table
          columns={columns}
          dataSource={connections}
          rowKey="id"
          loading={loading || discoveringSchema}
        />
      </Card>

      <Modal
        title={editingConnection ? '编辑连接' : '添加连接'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={handleCancel}
        width={600}
        confirmLoading={discoveringSchema}
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{ db_type: 'mysql', port: 3306 }}
          disabled={discoveringSchema}
        >
          <Form.Item
            name="name"
            label="连接名称"
            rules={[{ required: true, message: '请输入名称' }]}
          >
            <Input placeholder="我的数据库" />
          </Form.Item>

          <Form.Item
            name="db_type"
            label="数据库类型"
            rules={[{ required: true, message: '请选择数据库类型' }]}
          >
            <Select placeholder="选择数据库类型">
              <Option value="mysql">MySQL</Option>
              <Option value="postgresql">PostgreSQL</Option>
              <Option value="sqlite">SQLite</Option>
            </Select>
          </Form.Item>

          <Form.Item
            name="host"
            label="主机"
            rules={[{ required: true, message: '请输入主机' }]}
          >
            <Input placeholder="localhost" />
          </Form.Item>

          <Form.Item
            name="port"
            label="端口"
            rules={[{ required: true, message: '请输入端口' }]}
          >
            <Input type="number" placeholder="3306" />
          </Form.Item>

          <Form.Item
            name="username"
            label="用户名"
            rules={[{ required: true, message: '请输入用户名' }]}
          >
            <Input placeholder="root" />
          </Form.Item>

          <Form.Item
            name="password"
            label="密码"
            rules={[
              {
                required: !editingConnection,
                message: '请输入密码'
              }
            ]}
          >
            <Input.Password placeholder="密码" />
          </Form.Item>

          <Form.Item
            name="database_name"
            label="数据库名称"
            rules={[{ required: true, message: '请输入数据库名称' }]}
          >
            <Input placeholder="我的数据库" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default ConnectionsPage;
