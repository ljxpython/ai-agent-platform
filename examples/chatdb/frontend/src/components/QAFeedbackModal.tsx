import React, { useState } from 'react';
import {
  Modal,
  Form,
  Rate,
  Input,
  Button,
  message,
  Space,
  Typography,
  Divider
} from 'antd';
import { LikeOutlined, DislikeOutlined } from '@ant-design/icons';
import { hybridQAService } from '../services/hybridQA';
import type { QAPair } from '../types/hybridQA';

const { TextArea } = Input;
const { Text } = Typography;

interface QAFeedbackModalProps {
  visible: boolean;
  onCancel: () => void;
  qaPair: QAPair | null;
  onFeedbackSubmitted?: () => void;
}

const QAFeedbackModal: React.FC<QAFeedbackModalProps> = ({
  visible,
  onCancel,
  qaPair,
  onFeedbackSubmitted
}) => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [quickFeedback, setQuickFeedback] = useState<'agree' | 'disagree' | null>(null);

  const handleSubmit = async (values: any) => {
    if (!qaPair) return;

    try {
      setLoading(true);

      // 将评分转换为0-1的满意度分数
      const satisfaction = values.rating ? values.rating / 5 :
                          (quickFeedback === 'agree' ? 1.0 : 0.2);

      await hybridQAService.submitFeedback({
        qa_id: qaPair.id,
        user_satisfaction: satisfaction,
        feedback_text: values.feedback_text || ''
      });

      message.success('反馈提交成功，感谢您的评价！');
      form.resetFields();
      setQuickFeedback(null);
      onCancel();

      if (onFeedbackSubmitted) {
        onFeedbackSubmitted();
      }
    } catch (error) {
      message.error('反馈提交失败');
      console.error('提交反馈失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleQuickFeedback = (type: 'agree' | 'disagree') => {
    setQuickFeedback(type);
    // 自动设置评分
    if (type === 'agree') {
      form.setFieldsValue({ rating: 5 });
    } else {
      form.setFieldsValue({ rating: 1 });
    }
  };

  const handleCancel = () => {
    form.resetFields();
    setQuickFeedback(null);
    onCancel();
  };

  return (
    <Modal
      title="问答对反馈"
      open={visible}
      onCancel={handleCancel}
      footer={null}
      width={600}
    >
      {qaPair && (
        <div>
          {/* 问答对预览 */}
          <div style={{ marginBottom: '20px', padding: '12px', background: '#f8f9fa', borderRadius: '6px' }}>
            <Text strong>问题：</Text>
            <div style={{ marginBottom: '8px' }}>{qaPair.question}</div>
            <Text strong>SQL：</Text>
            <pre style={{
              fontSize: '12px',
              background: '#fff',
              padding: '8px',
              borderRadius: '4px',
              margin: '4px 0 0 0',
              overflow: 'auto'
            }}>
              {qaPair.sql}
            </pre>
          </div>

          {/* 快速反馈按钮 */}
          <div style={{ marginBottom: '20px', textAlign: 'center' }}>
            <Text style={{ display: 'block', marginBottom: '12px' }}>
              这个问答对对您有帮助吗？
            </Text>
            <Space size="large">
              <Button
                type={quickFeedback === 'agree' ? 'primary' : 'default'}
                icon={<LikeOutlined />}
                onClick={() => handleQuickFeedback('agree')}
                size="large"
              >
                有帮助
              </Button>
              <Button
                type={quickFeedback === 'disagree' ? 'primary' : 'default'}
                icon={<DislikeOutlined />}
                onClick={() => handleQuickFeedback('disagree')}
                size="large"
                danger={quickFeedback === 'disagree'}
              >
                没帮助
              </Button>
            </Space>
          </div>

          <Divider />

          {/* 详细反馈表单 */}
          <Form
            form={form}
            layout="vertical"
            onFinish={handleSubmit}
          >
            <Form.Item
              name="rating"
              label="整体评分"
              rules={[{ required: true, message: '请给出评分' }]}
            >
              <Rate allowHalf />
            </Form.Item>

            <Form.Item
              name="feedback_text"
              label="详细反馈（可选）"
            >
              <TextArea
                rows={4}
                placeholder="请描述您的使用体验，或提出改进建议..."
              />
            </Form.Item>

            <Form.Item style={{ marginBottom: 0, textAlign: 'right' }}>
              <Space>
                <Button onClick={handleCancel}>
                  取消
                </Button>
                <Button
                  type="primary"
                  htmlType="submit"
                  loading={loading}
                >
                  提交反馈
                </Button>
              </Space>
            </Form.Item>
          </Form>
        </div>
      )}
    </Modal>
  );
};

export default QAFeedbackModal;
