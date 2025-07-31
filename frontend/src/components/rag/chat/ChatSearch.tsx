import React, { useState, useCallback } from 'react';
import { Input, Button, Space } from 'antd';
import { SendOutlined, LoadingOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { SearchProps } from '@/types/rag';
import { debounce } from '@/utils/rag';

const { TextArea } = Input;

interface ChatSearchProps extends SearchProps {
  loading?: boolean;
  multiline?: boolean;
  maxRows?: number;
  onSend?: (query: string) => void;
}

const ChatSearch: React.FC<ChatSearchProps> = ({
  pipeline,
  setQuery,
  placeholder = '搜索您的文档...',
  disabled = false,
  loading = false,
  multiline = true,
  maxRows = 4,
  onSend,
}) => {
  const [value, setValue] = useState('');
  const navigate = useNavigate();

  // 防抖导航函数
  const navigateToSearch = useCallback(
    debounce((searchValue: string) => {
      if (pipeline) {
        navigate(`/rag/chat?q=${encodeURIComponent(searchValue)}`);
      }
    }, 50),
    [navigate, pipeline]
  );

  // 处理提交
  const handleSubmit = () => {
    const trimmedValue = value.trim();
    if (trimmedValue && !disabled && !loading) {
      if (onSend) {
        onSend(trimmedValue);
      } else {
        navigateToSearch(trimmedValue);
        setQuery(trimmedValue);
      }
      setValue('');
    }
  };

  // 处理键盘事件
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      if (e.shiftKey) {
        // Shift+Enter 换行
        return;
      } else {
        // Enter 发送
        e.preventDefault();
        handleSubmit();
      }
    }
  };

  // 处理输入变化
  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setValue(e.target.value);
  };

  return (
    <div style={{ width: '100%' }}>
      <Space.Compact style={{ width: '100%', display: 'flex' }}>
        {multiline ? (
          <TextArea
            value={value}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={disabled || loading}
            autoSize={{ minRows: 1, maxRows }}
            style={{
              flex: 1,
              resize: 'none',
              borderRadius: '8px 0 0 8px'
            }}
          />
        ) : (
          <Input
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onPressEnter={handleSubmit}
            placeholder={placeholder}
            disabled={disabled || loading}
            style={{
              flex: 1,
              borderRadius: '8px 0 0 8px'
            }}
          />
        )}

        <Button
          type="primary"
          icon={loading ? <LoadingOutlined /> : <SendOutlined />}
          onClick={handleSubmit}
          disabled={disabled || loading || !value.trim()}
          style={{
            borderRadius: '0 8px 8px 0',
            height: 'auto',
            minHeight: '32px'
          }}
        >
          发送
        </Button>
      </Space.Compact>

      {multiline && (
        <div style={{
          fontSize: '12px',
          color: '#666',
          marginTop: '4px',
          textAlign: 'right'
        }}>
          按 Enter 发送，Shift+Enter 换行
        </div>
      )}
    </div>
  );
};

export default ChatSearch;
