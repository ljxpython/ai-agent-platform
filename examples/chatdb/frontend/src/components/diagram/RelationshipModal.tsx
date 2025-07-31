import React, { useState, useEffect } from 'react';
import { Modal, Form, Input, Typography, Card, Badge, Radio, Space, Button, Alert } from 'antd';
import { InfoCircleOutlined } from '@ant-design/icons';
import { getRelationshipTips } from '../../services/relationshipTipsService';

const { Text } = Typography;

// 关系类型常量
const RELATIONSHIP_TYPES = {
  ONE_TO_ONE: '1-to-1',
  ONE_TO_MANY: '1-to-N',
  MANY_TO_ONE: 'N-to-1',  // 添加多对一关系类型
  MANY_TO_MANY: 'N-to-M'
};

// 关系类型对应的中文描述
const RELATIONSHIP_TYPE_LABELS = {
  [RELATIONSHIP_TYPES.ONE_TO_ONE]: '一对一 (1:1)',
  [RELATIONSHIP_TYPES.ONE_TO_MANY]: '一对多 (1:N)',
  [RELATIONSHIP_TYPES.MANY_TO_ONE]: '多对一 (N:1)',
  [RELATIONSHIP_TYPES.MANY_TO_MANY]: '多对多 (N:M)'
};

// 关系类型对应的颜色
const RELATIONSHIP_TYPE_COLORS = {
  [RELATIONSHIP_TYPES.ONE_TO_ONE]: '#8b5cf6', // 紫色
  [RELATIONSHIP_TYPES.ONE_TO_MANY]: '#0ea5e9', // 蓝色
  [RELATIONSHIP_TYPES.MANY_TO_ONE]: '#10b981', // 绿色
  [RELATIONSHIP_TYPES.MANY_TO_MANY]: '#f59e0b', // 橙色
};

// 关系类型对应的图标
const RELATIONSHIP_TYPE_ICONS = {
  [RELATIONSHIP_TYPES.ONE_TO_ONE]: '1:1',
  [RELATIONSHIP_TYPES.ONE_TO_MANY]: '1:N',
  [RELATIONSHIP_TYPES.MANY_TO_ONE]: 'N:1',
  [RELATIONSHIP_TYPES.MANY_TO_MANY]: 'N:M',
};

interface RelationshipModalProps {
  visible: boolean;
  onClose: () => void;
  onSubmit: (values: any) => void;
  onDelete?: (relationshipId: string) => void;
  relationshipData: any;
  loading?: boolean;
  deleteLoading?: boolean;
}

const RelationshipModal: React.FC<RelationshipModalProps> = ({
  visible,
  onClose,
  onSubmit,
  onDelete,
  relationshipData,
  loading = false,
  deleteLoading = false
}) => {
  const [form] = Form.useForm();
  const [selectedType, setSelectedType] = useState<string>(RELATIONSHIP_TYPES.ONE_TO_MANY);
  const [relationshipTips, setRelationshipTips] = useState<any>({});
  const [, setTipsLoading] = useState<boolean>(false);

  // 获取关系类型提示信息
  useEffect(() => {
    if (visible) {
      setTipsLoading(true);
      getRelationshipTips()
        .then(data => {
          setRelationshipTips(data);
        })
        .catch(error => {
          console.error('获取关系类型提示信息失败:', error);
        })
        .finally(() => {
          setTipsLoading(false);
        });
    }
  }, [visible]);

  // 当模态框打开时，设置表单初始值
  React.useEffect(() => {
    if (visible && relationshipData) {
      const relType = relationshipData.relationshipType || RELATIONSHIP_TYPES.ONE_TO_MANY;
      form.setFieldsValue({
        relationship_type: relType,
        description: relationshipData.description || ''
      });
      setSelectedType(relType);
    }
  }, [visible, relationshipData, form]);

  // 处理关系类型变化
  const handleTypeChange = (value: string) => {
    setSelectedType(value);
  };

  // 处理表单提交
  const handleSubmit = () => {
    form.validateFields().then(values => {
      onSubmit({
        ...relationshipData,
        relationshipType: values.relationship_type,
        description: values.description
      });
      onClose();
    });
  };

  // 获取当前选中的关系类型颜色
  const getTypeColor = () => {
    return RELATIONSHIP_TYPE_COLORS[selectedType] || '#64748b';
  };

  // 处理删除关系
  const handleDelete = () => {
    if (relationshipData?.id && onDelete) {
      onDelete(relationshipData.id);
    }
  };

  // 自定义底部按钮
  const modalFooter = [
    // 删除按钮，只在编辑已存在的关系时显示
    relationshipData?.id && onDelete && (
      <Button
        key="delete"
        danger
        onClick={handleDelete}
        loading={deleteLoading}
      >
        删除关系
      </Button>
    ),
    // 取消按钮
    <Button key="cancel" onClick={onClose}>
      取消
    </Button>,
    // 确定按钮
    <Button key="submit" type="primary" onClick={handleSubmit} loading={loading}>
      确定
    </Button>
  ].filter(Boolean); // 过滤掉 false 值

  return (
    <Modal
      title={relationshipData?.id ? '编辑关系' : '创建关系'}
      open={visible}
      onCancel={onClose}
      footer={modalFooter}
      maskClosable={false}
      destroyOnClose
      width={500}
    >
      {relationshipData && (
        <Form form={form} layout="vertical">
          {/* 关系可视化展示 */}
          <div style={{ marginBottom: 20 }}>
            <Card
              bordered={false}
              style={{
                background: '#f8fafc',
                borderRadius: 8,
                boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '10px 0' }}>
                <div style={{ textAlign: 'right', width: '45%' }}>
                  <Text strong>{relationshipData.sourceTable}</Text>
                  <div>
                    <Badge
                      status="processing"
                      color="#10b981"
                      text={<Text type="secondary">{relationshipData.sourceColumn}</Text>}
                    />
                  </div>
                </div>
                <div style={{
                  width: '10%',
                  display: 'flex',
                  justifyContent: 'center',
                  alignItems: 'center',
                  color: getTypeColor(),
                  fontWeight: 'bold'
                }}>
                  <Badge
                    count={RELATIONSHIP_TYPE_ICONS[selectedType]}
                    style={{
                      backgroundColor: getTypeColor(),
                      fontSize: 12,
                      fontWeight: 600
                    }}
                  />
                </div>
                <div style={{ width: '45%' }}>
                  <Text strong>{relationshipData.targetTable}</Text>
                  <div>
                    <Badge
                      status="processing"
                      color="#f43f5e"
                      text={<Text type="secondary">{relationshipData.targetColumn}</Text>}
                    />
                  </div>
                </div>
              </div>
            </Card>
          </div>

          {/* 关系类型选择 */}
          <Form.Item
            label="关系类型"
            name="relationship_type"
            rules={[{ required: true, message: '请选择关系类型' }]}
          >
            <Radio.Group
              onChange={(e) => handleTypeChange(e.target.value)}
              buttonStyle="solid"
              style={{ width: '100%' }}
            >
              <Space direction="vertical" style={{ width: '100%' }}>
                <Radio.Button
                  value={RELATIONSHIP_TYPES.ONE_TO_ONE}
                  style={{
                    width: '100%',
                    height: 'auto',
                    padding: '8px 12px',
                    textAlign: 'left',
                    borderColor: selectedType === RELATIONSHIP_TYPES.ONE_TO_ONE ? RELATIONSHIP_TYPE_COLORS[RELATIONSHIP_TYPES.ONE_TO_ONE] : '#d9d9d9'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Badge
                      count="1:1"
                      style={{
                        backgroundColor: RELATIONSHIP_TYPE_COLORS[RELATIONSHIP_TYPES.ONE_TO_ONE],
                        fontSize: 12,
                        fontWeight: 600
                      }}
                    />
                    <span>{RELATIONSHIP_TYPE_LABELS[RELATIONSHIP_TYPES.ONE_TO_ONE]}</span>
                  </div>
                </Radio.Button>

                <Radio.Button
                  value={RELATIONSHIP_TYPES.ONE_TO_MANY}
                  style={{
                    width: '100%',
                    height: 'auto',
                    padding: '8px 12px',
                    textAlign: 'left',
                    borderColor: selectedType === RELATIONSHIP_TYPES.ONE_TO_MANY ? RELATIONSHIP_TYPE_COLORS[RELATIONSHIP_TYPES.ONE_TO_MANY] : '#d9d9d9'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Badge
                      count="1:N"
                      style={{
                        backgroundColor: RELATIONSHIP_TYPE_COLORS[RELATIONSHIP_TYPES.ONE_TO_MANY],
                        fontSize: 12,
                        fontWeight: 600
                      }}
                    />
                    <span>{RELATIONSHIP_TYPE_LABELS[RELATIONSHIP_TYPES.ONE_TO_MANY]}</span>
                  </div>
                </Radio.Button>

                <Radio.Button
                  value={RELATIONSHIP_TYPES.MANY_TO_ONE}
                  style={{
                    width: '100%',
                    height: 'auto',
                    padding: '8px 12px',
                    textAlign: 'left',
                    borderColor: selectedType === RELATIONSHIP_TYPES.MANY_TO_ONE ? RELATIONSHIP_TYPE_COLORS[RELATIONSHIP_TYPES.MANY_TO_ONE] : '#d9d9d9'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Badge
                      count="N:1"
                      style={{
                        backgroundColor: RELATIONSHIP_TYPE_COLORS[RELATIONSHIP_TYPES.MANY_TO_ONE],
                        fontSize: 12,
                        fontWeight: 600
                      }}
                    />
                    <span>{RELATIONSHIP_TYPE_LABELS[RELATIONSHIP_TYPES.MANY_TO_ONE]}</span>
                  </div>
                </Radio.Button>

                <Radio.Button
                  value={RELATIONSHIP_TYPES.MANY_TO_MANY}
                  style={{
                    width: '100%',
                    height: 'auto',
                    padding: '8px 12px',
                    textAlign: 'left',
                    borderColor: selectedType === RELATIONSHIP_TYPES.MANY_TO_MANY ? RELATIONSHIP_TYPE_COLORS[RELATIONSHIP_TYPES.MANY_TO_MANY] : '#d9d9d9'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Badge
                      count="N:M"
                      style={{
                        backgroundColor: RELATIONSHIP_TYPE_COLORS[RELATIONSHIP_TYPES.MANY_TO_MANY],
                        fontSize: 12,
                        fontWeight: 600
                      }}
                    />
                    <span>{RELATIONSHIP_TYPE_LABELS[RELATIONSHIP_TYPES.MANY_TO_MANY]}</span>
                  </div>
                </Radio.Button>
              </Space>
            </Radio.Group>
          </Form.Item>

          {/* 关系类型提示信息 */}
          {selectedType && relationshipTips[selectedType] && (
            <Alert
              type="info"
              showIcon
              icon={<InfoCircleOutlined />}
              message={relationshipTips[selectedType].title}
              description={
                <div>
                  <p>{relationshipTips[selectedType].description}</p>
                  <p><strong>示例：</strong>{relationshipTips[selectedType].example}</p>
                  <p><strong>何时使用：</strong>{relationshipTips[selectedType].when_to_use}</p>
                </div>
              }
              style={{ marginBottom: 16 }}
            />
          )}

          <Form.Item
            label="描述"
            name="description"
          >
            <Input.TextArea rows={3} placeholder="输入关系描述" />
          </Form.Item>
        </Form>
      )}
    </Modal>
  );
};

export default RelationshipModal;
