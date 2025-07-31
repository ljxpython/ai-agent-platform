import React, { useState } from 'react';
import { Button, Upload, message, Modal } from 'antd';
import { UploadOutlined, InboxOutlined } from '@ant-design/icons';
import { useRAGContext } from '@/contexts/RAGContext';

const { Dragger } = Upload;

interface UploadButtonProps {
  onUploadSuccess?: (documentIds: string[]) => void;
  buttonText?: string;
  type?: 'button' | 'dragger';
  disabled?: boolean;
}

const UploadButton: React.FC<UploadButtonProps> = ({
  onUploadSuccess,
  buttonText = '上传文档',
  type = 'button',
  disabled = false,
}) => {
  const { getClient } = useRAGContext();
  const [uploading, setUploading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);

  const handleUpload = async (file: File) => {
    const client = getClient();
    if (!client) {
      message.error('请先连接到服务器');
      return false;
    }

    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await client.documents.create({
        file: file,
        metadata: {
          title: file.name,
          source: 'upload',
          upload_time: new Date().toISOString(),
        },
      });

      message.success(`文档 "${file.name}" 上传成功`);

      if (onUploadSuccess && response.results?.documentId) {
        onUploadSuccess([response.results.documentId]);
      }

      return true;
    } catch (error: any) {
      console.error('Upload error:', error);
      message.error(`上传失败: ${error.message || '未知错误'}`);
      return false;
    } finally {
      setUploading(false);
    }
  };

  const uploadProps = {
    name: 'file',
    multiple: true,
    accept: '.pdf,.txt,.doc,.docx,.md,.html,.csv,.json',
    beforeUpload: (file: File) => {
      // 检查文件大小 (50MB)
      const isLt50M = file.size / 1024 / 1024 < 50;
      if (!isLt50M) {
        message.error('文件大小不能超过 50MB');
        return false;
      }

      // 检查文件类型
      const allowedTypes = [
        'application/pdf',
        'text/plain',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'text/markdown',
        'text/html',
        'text/csv',
        'application/json',
      ];

      if (!allowedTypes.includes(file.type) && !file.name.match(/\.(pdf|txt|doc|docx|md|html|csv|json)$/i)) {
        message.error('不支持的文件类型');
        return false;
      }

      handleUpload(file);
      return false; // 阻止默认上传行为
    },
    showUploadList: false,
  };

  if (type === 'dragger') {
    return (
      <Dragger {...uploadProps} disabled={disabled || uploading}>
        <p className="ant-upload-drag-icon">
          <InboxOutlined />
        </p>
        <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
        <p className="ant-upload-hint">
          支持 PDF, TXT, DOC, DOCX, MD, HTML, CSV, JSON 格式
          <br />
          文件大小限制: 50MB
        </p>
      </Dragger>
    );
  }

  return (
    <>
      <Button
        type="primary"
        icon={<UploadOutlined />}
        onClick={() => setModalVisible(true)}
        loading={uploading}
        disabled={disabled}
      >
        {buttonText}
      </Button>

      <Modal
        title="上传文档"
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        footer={null}
        width={600}
      >
        <div style={{ padding: '20px 0' }}>
          <Dragger {...uploadProps} disabled={disabled || uploading}>
            <p className="ant-upload-drag-icon">
              <InboxOutlined />
            </p>
            <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
            <p className="ant-upload-hint">
              支持格式: PDF, TXT, DOC, DOCX, MD, HTML, CSV, JSON
              <br />
              文件大小限制: 50MB
              <br />
              可以同时上传多个文件
            </p>
          </Dragger>

          <div style={{ marginTop: '16px', fontSize: '12px', color: '#666' }}>
            <h4>支持的文件格式：</h4>
            <ul style={{ margin: '8px 0', paddingLeft: '20px' }}>
              <li><strong>PDF</strong> - 便携式文档格式</li>
              <li><strong>TXT</strong> - 纯文本文件</li>
              <li><strong>DOC/DOCX</strong> - Microsoft Word 文档</li>
              <li><strong>MD</strong> - Markdown 文档</li>
              <li><strong>HTML</strong> - 网页文档</li>
              <li><strong>CSV</strong> - 逗号分隔值文件</li>
              <li><strong>JSON</strong> - JSON 数据文件</li>
            </ul>

            <h4>注意事项：</h4>
            <ul style={{ margin: '8px 0', paddingLeft: '20px' }}>
              <li>上传的文档将被自动解析和索引</li>
              <li>处理时间取决于文档大小和复杂度</li>
              <li>上传完成后可以在文档管理页面查看状态</li>
            </ul>
          </div>
        </div>
      </Modal>
    </>
  );
};

export default UploadButton;
