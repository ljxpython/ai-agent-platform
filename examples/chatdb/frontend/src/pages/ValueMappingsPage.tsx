import React, { useState, useEffect, useCallback } from 'react';
import {
  Card, Select, Button, Table, Spin, message,
  Typography, Form, Input, Modal, Popconfirm, Space
} from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import * as api from '../services/api';

const { Option } = Select;
const { Title } = Typography;

interface DBConnection {
  id: number;
  name: string;
}

interface SchemaTable {
  id: number;
  table_name: string;
  description?: string;
}

interface SchemaColumn {
  id: number;
  column_name: string;
  data_type: string;
  description?: string;
  table_id: number;
  table_name: string;
}

interface ValueMapping {
  id: number;
  column_id: number;
  nl_term: string;
  db_value: string;
}

const ValueMappingsPage: React.FC = () => {
  const [connections, setConnections] = useState<DBConnection[]>([]);
  const [selectedConnection, setSelectedConnection] = useState<number | null>(null);
  const [tables, setTables] = useState<SchemaTable[]>([]);
  const [selectedTable, setSelectedTable] = useState<number | null>(null);
  const [columns, setColumns] = useState<SchemaColumn[]>([]);
  const [selectedColumn, setSelectedColumn] = useState<number | null>(null);
  const [valueMappings, setValueMappings] = useState<ValueMapping[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [modalVisible, setModalVisible] = useState<boolean>(false);
  const [editingMapping, setEditingMapping] = useState<ValueMapping | null>(null);
  const [form] = Form.useForm();

  // Define fetch functions with useCallback
  const fetchConnections = async () => {
    try {
      const response = await api.getConnections();
      setConnections(response.data);
    } catch (error) {
      message.error('获取连接失败');
      console.error(error);
    }
  };

  const fetchTables = async (connectionId: number) => {
    setLoading(true);
    try {
      const response = await api.getSchemaMetadata(connectionId);
      setTables(response.data);
      setSelectedTable(null);
      setColumns([]);
      setSelectedColumn(null);
      setValueMappings([]);
    } catch (error) {
      message.error('获取表失败');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const fetchColumns = useCallback(async (tableId: number) => {
    setLoading(true);
    try {
      const selectedTableData = tables.find(t => t.id === tableId);
      if (!selectedTableData) return;

      // Get columns for this table from the schema metadata
      const response = await api.getSchemaMetadata(selectedConnection!);
      const tableData = response.data.find((t: any) => t.id === tableId);

      if (tableData && tableData.columns) {
        const columnsWithTableInfo = tableData.columns.map((col: any) => ({
          ...col,
          table_id: tableId,
          table_name: selectedTableData.table_name
        }));
        setColumns(columnsWithTableInfo);
      } else {
        setColumns([]);
      }

      setSelectedColumn(null);
      setValueMappings([]);
    } catch (error) {
      message.error('获取列失败');
      console.error(error);
    } finally {
      setLoading(false);
    }
  }, [selectedConnection, tables]);

  const fetchValueMappings = async (columnId: number) => {
    setLoading(true);
    try {
      const response = await api.getValueMappings(columnId);
      setValueMappings(response.data);
    } catch (error) {
      message.error('获取值映射失败');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  // Setup effects
  useEffect(() => {
    fetchConnections();
  }, []);

  useEffect(() => {
    if (selectedConnection) {
      fetchTables(selectedConnection);
    }
  }, [selectedConnection]);

  useEffect(() => {
    if (selectedTable) {
      fetchColumns(selectedTable);
    }
  }, [selectedTable, fetchColumns]);

  useEffect(() => {
    if (selectedColumn) {
      fetchValueMappings(selectedColumn);
    }
  }, [selectedColumn]);

  const handleConnectionChange = (value: number) => {
    setSelectedConnection(value);
  };

  const handleTableChange = (value: number) => {
    setSelectedTable(value);
  };

  const handleColumnChange = (value: number) => {
    setSelectedColumn(value);
  };

  const showModal = (mapping?: ValueMapping) => {
    setEditingMapping(mapping || null);
    form.resetFields();
    if (mapping) {
      form.setFieldsValue({
        nl_term: mapping.nl_term,
        db_value: mapping.db_value,
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

      if (editingMapping) {
        await api.updateValueMapping(editingMapping.id, values);
        message.success('值映射更新成功');
      } else {
        await api.createValueMapping({
          ...values,
          column_id: selectedColumn
        });
        message.success('值映射创建成功');
      }

      setModalVisible(false);
      fetchValueMappings(selectedColumn!);
    } catch (error) {
      message.error('保存值映射失败');
      console.error(error);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await api.deleteValueMapping(id);
      message.success('值映射删除成功');
      fetchValueMappings(selectedColumn!);
    } catch (error) {
      message.error('删除值映射失败');
      console.error(error);
    }
  };

  const columns_table = [
    {
      title: '自然语言术语',
      dataIndex: 'nl_term',
      key: 'nl_term',
    },
    {
      title: '数据库值',
      dataIndex: 'db_value',
      key: 'db_value',
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: any, record: ValueMapping) => (
        <Space size="middle">
          <Button
            icon={<EditOutlined />}
            onClick={() => showModal(record)}
            size="small"
          >
            编辑
          </Button>
          <Popconfirm
            title="确定要删除这个映射吗？"
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
    <div className="value-mappings-page">
      <Card>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
          <Title level={4}>值映射</Title>
          <div>
            <Select
              placeholder="选择数据库连接"
              style={{ width: 200, marginRight: 8 }}
              onChange={handleConnectionChange}
              value={selectedConnection || undefined}
            >
              {connections.map(conn => (
                <Option key={conn.id} value={conn.id}>{conn.name}</Option>
              ))}
            </Select>

            <Select
              placeholder="选择表"
              style={{ width: 200, marginRight: 8 }}
              onChange={handleTableChange}
              value={selectedTable || undefined}
              disabled={!selectedConnection}
            >
              {tables.map(table => (
                <Option key={table.id} value={table.id}>{table.table_name}</Option>
              ))}
            </Select>

            <Select
              placeholder="选择列"
              style={{ width: 200 }}
              onChange={handleColumnChange}
              value={selectedColumn || undefined}
              disabled={!selectedTable}
            >
              {columns.map(column => (
                <Option key={column.id} value={column.id}>{column.column_name}</Option>
              ))}
            </Select>
          </div>
        </div>

        {selectedColumn && (
          <div style={{ marginBottom: 16 }}>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => showModal()}
            >
              添加值映射
            </Button>
          </div>
        )}

        {loading ? (
          <div style={{ textAlign: 'center', padding: '20px' }}>
            <Spin />
          </div>
        ) : selectedColumn ? (
          <Table
            columns={columns_table}
            dataSource={valueMappings}
            rowKey="id"
            pagination={{ pageSize: 10 }}
          />
        ) : (
          <div style={{ textAlign: 'center', padding: '20px' }}>
            <p>请选择连接、表和列来管理值映射</p>
          </div>
        )}
      </Card>

      <Modal
        title={editingMapping ? '编辑值映射' : '添加值映射'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={handleCancel}
      >
        <Form
          form={form}
          layout="vertical"
        >
          <Form.Item
            name="nl_term"
            label="自然语言术语"
            rules={[{ required: true, message: '请输入自然语言术语' }]}
          >
            <Input placeholder="e.g., 中石化" />
          </Form.Item>

          <Form.Item
            name="db_value"
            label="数据库值"
            rules={[{ required: true, message: '请输入数据库值' }]}
          >
            <Input placeholder="e.g., 中国石化" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default ValueMappingsPage;
