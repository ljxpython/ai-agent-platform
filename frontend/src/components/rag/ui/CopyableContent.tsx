import React, { useState } from 'react';
import { Button, message, Tooltip } from 'antd';
import { CopyOutlined, CheckOutlined } from '@ant-design/icons';

interface CopyableContentProps {
  content: string;
  children?: React.ReactNode;
  className?: string;
  showButton?: boolean;
  buttonText?: string;
  successMessage?: string;
}

export const CopyableContent: React.FC<CopyableContentProps> = ({
  content,
  children,
  className = '',
  showButton = true,
  buttonText,
  successMessage = '已复制到剪贴板',
}) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      message.success(successMessage);

      // 重置复制状态
      setTimeout(() => {
        setCopied(false);
      }, 2000);
    } catch (error) {
      console.error('Failed to copy content:', error);
      message.error('复制失败');
    }
  };

  if (showButton) {
    return (
      <div className={`flex items-center gap-2 ${className}`}>
        {children}
        <Tooltip title={copied ? '已复制' : '复制内容'}>
          <Button
            type="text"
            size="small"
            icon={copied ? <CheckOutlined /> : <CopyOutlined />}
            onClick={handleCopy}
            className={copied ? 'text-green-500' : ''}
          >
            {buttonText}
          </Button>
        </Tooltip>
      </div>
    );
  }

  return (
    <div
      className={`cursor-pointer ${className}`}
      onClick={handleCopy}
      title="点击复制"
    >
      {children}
    </div>
  );
};
