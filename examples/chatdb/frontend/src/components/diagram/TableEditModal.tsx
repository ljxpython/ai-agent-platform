import React, { useState, useEffect } from 'react';
import { Modal, Form, Input, Button, Table, Typography, message } from 'antd';
import { EditOutlined } from '@ant-design/icons';

const { TextArea } = Input;
const { Title } = Typography;

interface TableEditModalProps {
  visible: boolean;
  table: any;
  onCancel: () => void;
  onSave: (tableId: number, tableData: any) => Promise<void>;
}

const TableEditModal: React.FC<TableEditModalProps> = ({
  visible,
  table,
  onCancel,
  onSave
}) => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState<boolean>(false);
  const [editingColumn, setEditingColumn] = useState<number | null>(null);
  const [columnDescriptions, setColumnDescriptions] = useState<{[key: number]: string}>({});

  useEffect(() => {
    if (visible && table) {
      // Initialize form with table data
      form.setFieldsValue({
        tableName: table.label,
        tableDescription: table.description || '',
      });

      // Initialize column descriptions
      const descriptions: {[key: number]: string} = {};
      table.columns.forEach((column: any) => {
        descriptions[column.id] = column.description || '';
      });
      setColumnDescriptions(descriptions);
    }
  }, [visible, table, form]);

  const handleSave = async () => {
    try {
      setLoading(true);
      const values = await form.validateFields();

      // Prepare data for saving
      const tableData = {
        table_name: table.label, // Keep original table name
        description: values.tableDescription,
        columns: table.columns.map((column: any) => ({
          id: column.id,
          description: columnDescriptions[column.id] || ''
        }))
      };

      await onSave(table.id, tableData);
      message.success('表信息更新成功');
      onCancel();
    } catch (error) {
      console.error('Failed to save table data:', error);
      message.error('保存失败');
    } finally {
      setLoading(false);
    }
  };

  const handleColumnDescriptionChange = (columnId: number, description: string) => {
    setColumnDescriptions(prev => ({
      ...prev,
      [columnId]: description
    }));
  };

  const columns = [
    {
      title: '列名',
      dataIndex: 'column_name',
      key: 'column_name',
      width: '25%',
    },
    {
      title: '数据类型',
      dataIndex: 'data_type',
      key: 'data_type',
      width: '20%',
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      width: '45%',
      render: (_: any, record: any) => (
        editingColumn === record.id ? (
          <Input
            value={columnDescriptions[record.id] || ''}
            onChange={(e) => handleColumnDescriptionChange(record.id, e.target.value)}
            onPressEnter={() => setEditingColumn(null)}
            onBlur={() => setEditingColumn(null)}
            autoFocus
          />
        ) : (
          <div
            style={{ cursor: 'pointer' }}
            onClick={() => setEditingColumn(record.id)}
          >
            {columnDescriptions[record.id] || <span style={{ color: '#ccc' }}>点击添加描述</span>}
            <EditOutlined style={{ marginLeft: 8, color: '#1890ff' }} />
          </div>
        )
      ),
    },
  ];

  if (!table) return null;

  return (
    <Modal
      title="编辑表信息"
      open={visible}
      width={800}
      onCancel={onCancel}
      footer={[
        <Button key="cancel" onClick={onCancel}>
          取消
        </Button>,
        <Button
          key="save"
          type="primary"
          loading={loading}
          onClick={handleSave}
        >
          保存
        </Button>,
      ]}
    >
      <Form
        form={form}
        layout="vertical"
      >
        <Form.Item
          name="tableName"
          label="表名"
        >
          <Input disabled />
        </Form.Item>

        <Form.Item
          name="tableDescription"
          label="表描述"
        >
          <TextArea
            rows={3}
            placeholder="请输入表的描述信息"
          />
        </Form.Item>

        <Title level={5} style={{ marginTop: 16 }}>列信息</Title>
        <Table
          dataSource={table.columns}
          columns={columns}
          rowKey="id"
          pagination={false}
          size="small"
          scroll={{ y: 300 }}
        />
      </Form>
    </Modal>
  );
};

export default TableEditModal;
