import React, { useEffect, useState, useRef } from 'react';
import { Button, Input, List, Card, Tag, Space, Typography, Divider, Alert, Spin } from 'antd';
import { SendOutlined, ReloadOutlined, DisconnectOutlined, InfoCircleOutlined } from '@ant-design/icons';
import { getWebSocketManager, WebSocketConnectionState } from '../services/websocket-manager';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

/**
 * WebSocket演示组件
 *
 * 展示如何使用WebSocket管理器进行多用户通信
 */
const WebSocketDemo: React.FC = () => {
  // 状态
  const [connectionState, setConnectionState] = useState<WebSocketConnectionState>(WebSocketConnectionState.DISCONNECTED);
  const [connectionId, setConnectionId] = useState<string | null>(null);
  const [userId, setUserId] = useState<string>('');
  const [messages, setMessages] = useState<any[]>([]);
  const [inputMessage, setInputMessage] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  // 引用
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const wsManager = useRef(getWebSocketManager());

  // 连接WebSocket
  const connect = async () => {
    try {
      setLoading(true);
      setError(null);

      // 如果提供了用户ID，则使用它
      if (userId) {
        wsManager.current = getWebSocketManager(userId);
      }

      // 连接
      const success = await wsManager.current.connect();
      if (success) {
        setConnectionState(wsManager.current.getConnectionState());
        setConnectionId(wsManager.current.getConnectionId());
      }
    } catch (error) {
      setError(`连接错误: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setLoading(false);
    }
  };

  // 断开WebSocket连接
  const disconnect = () => {
    wsManager.current.disconnect();
    setConnectionState(WebSocketConnectionState.DISCONNECTED);
    setConnectionId(null);
  };

  // 发送消息
  const sendMessage = async () => {
    if (!inputMessage.trim()) return;

    try {
      setLoading(true);
      setError(null);

      // 发送消息
      const success = await wsManager.current.sendMessage({
        content: inputMessage,
        type: 'chat',
        timestamp: new Date().toISOString()
      });

      if (success) {
        // 添加到消息列表
        setMessages(prev => [...prev, {
          content: inputMessage,
          type: 'chat',
          source: 'user',
          timestamp: new Date().toISOString(),
          sent: true
        }]);

        // 清空输入框
        setInputMessage('');
      } else {
        setError('发送消息失败');
      }
    } catch (error) {
      setError(`发送错误: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setLoading(false);
    }
  };

  // 发送查询
  const sendQuery = async () => {
    if (!inputMessage.trim()) return;

    try {
      setLoading(true);
      setError(null);

      // 发送查询
      const success = await wsManager.current.sendQuery(inputMessage);

      if (success) {
        // 添加到消息列表
        setMessages(prev => [...prev, {
          content: inputMessage,
          type: 'query',
          source: 'user',
          timestamp: new Date().toISOString(),
          sent: true
        }]);

        // 清空输入框
        setInputMessage('');
      } else {
        setError('发送查询失败');
      }
    } catch (error) {
      setError(`发送错误: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setLoading(false);
    }
  };

  // 清空消息
  const clearMessages = () => {
    setMessages([]);
  };

  // 滚动到底部
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // 设置事件监听器
  useEffect(() => {
    const manager = wsManager.current;

    // 连接事件
    manager.on('connected', () => {
      setConnectionState(manager.getConnectionState());
      setConnectionId(manager.getConnectionId());
      setMessages(prev => [...prev, {
        content: '已连接到WebSocket服务器',
        type: 'system',
        timestamp: new Date().toISOString()
      }]);
    });

    // 断开连接事件
    manager.on('disconnected', (reason: string) => {
      setConnectionState(manager.getConnectionState());
      setConnectionId(null);
      setMessages(prev => [...prev, {
        content: `已断开连接: ${reason || '未知原因'}`,
        type: 'system',
        timestamp: new Date().toISOString()
      }]);
    });

    // 错误事件
    manager.on('error', (error: Error) => {
      setError(error.message);
      setMessages(prev => [...prev, {
        content: `错误: ${error.message}`,
        type: 'error',
        timestamp: new Date().toISOString()
      }]);
    });

    // 重连事件
    manager.on('reconnecting', (attempt: number) => {
      setConnectionState(manager.getConnectionState());
      setMessages(prev => [...prev, {
        content: `正在尝试重新连接 (${attempt})...`,
        type: 'system',
        timestamp: new Date().toISOString()
      }]);
    });

    // 重连成功事件
    manager.on('reconnected', () => {
      setConnectionState(manager.getConnectionState());
      setConnectionId(manager.getConnectionId());
      setMessages(prev => [...prev, {
        content: '重新连接成功',
        type: 'system',
        timestamp: new Date().toISOString()
      }]);
    });

    // 重连失败事件
    manager.on('reconnect_failed', () => {
      setConnectionState(manager.getConnectionState());
      setMessages(prev => [...prev, {
        content: '重新连接失败，请手动刷新页面',
        type: 'error',
        timestamp: new Date().toISOString()
      }]);
    });

    // 消息事件
    manager.on('message', (message: any) => {
      setMessages(prev => [...prev, message]);
    });

    // 清理函数
    return () => {
      manager.removeAllListeners();
    };
  }, []);

  // 滚动到底部
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // 渲染连接状态标签
  const renderConnectionState = () => {
    switch (connectionState) {
      case WebSocketConnectionState.CONNECTED:
        return <Tag color="success">已连接</Tag>;
      case WebSocketConnectionState.CONNECTING:
        return <Tag color="processing">连接中</Tag>;
      case WebSocketConnectionState.DISCONNECTED:
        return <Tag color="default">未连接</Tag>;
      case WebSocketConnectionState.ERROR:
        return <Tag color="error">连接错误</Tag>;
      case WebSocketConnectionState.RECONNECTING:
        return <Tag color="warning">重新连接中</Tag>;
      default:
        return <Tag color="default">未知状态</Tag>;
    }
  };

  // 渲染消息类型标签
  const renderMessageType = (type: string) => {
    switch (type) {
      case 'system':
        return <Tag color="blue">系统</Tag>;
      case 'error':
        return <Tag color="red">错误</Tag>;
      case 'chat':
        return <Tag color="green">聊天</Tag>;
      case 'query':
        return <Tag color="purple">查询</Tag>;
      case 'message':
        return <Tag color="cyan">消息</Tag>;
      default:
        return <Tag color="default">{type}</Tag>;
    }
  };

  return (
    <div style={{ maxWidth: '800px', margin: '0 auto', padding: '20px' }}>
      <Title level={2}>WebSocket多用户通信演示</Title>

      <Card title="连接信息" extra={renderConnectionState()}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <div>
            <Text strong>连接ID: </Text>
            <Text>{connectionId || '未连接'}</Text>
          </div>

          <Space>
            <Input
              placeholder="用户ID（可选）"
              value={userId}
              onChange={e => setUserId(e.target.value)}
              disabled={connectionState === WebSocketConnectionState.CONNECTED}
              style={{ width: '200px' }}
            />

            <Button
              type="primary"
              onClick={connect}
              loading={loading && connectionState !== WebSocketConnectionState.CONNECTED}
              disabled={connectionState === WebSocketConnectionState.CONNECTED}
              icon={<ReloadOutlined />}
            >
              连接
            </Button>

            <Button
              danger
              onClick={disconnect}
              disabled={connectionState !== WebSocketConnectionState.CONNECTED}
              icon={<DisconnectOutlined />}
            >
              断开
            </Button>
          </Space>

          {error && (
            <Alert
              message="错误"
              description={error}
              type="error"
              showIcon
              closable
              onClose={() => setError(null)}
            />
          )}
        </Space>
      </Card>

      <Divider />

      <Card
        title="消息"
        extra={
          <Button onClick={clearMessages} disabled={messages.length === 0}>
            清空
          </Button>
        }
      >
        <div style={{ height: '400px', overflowY: 'auto', marginBottom: '16px' }}>
          <List
            itemLayout="horizontal"
            dataSource={messages}
            renderItem={(message) => (
              <List.Item>
                <List.Item.Meta
                  avatar={renderMessageType(message.type)}
                  title={
                    <Space>
                      <Text strong>{message.source || '系统'}</Text>
                      <Text type="secondary" style={{ fontSize: '12px' }}>
                        {new Date(message.timestamp).toLocaleString()}
                      </Text>
                    </Space>
                  }
                  description={
                    <div>
                      {message.content}
                      {message.region && (
                        <Tag color="blue" style={{ marginLeft: '8px' }}>
                          {message.region}
                        </Tag>
                      )}
                    </div>
                  }
                />
              </List.Item>
            )}
          />
          <div ref={messagesEndRef} />
        </div>

        <Space.Compact style={{ width: '100%' }}>
          <TextArea
            placeholder="输入消息或查询"
            value={inputMessage}
            onChange={e => setInputMessage(e.target.value)}
            onPressEnter={e => {
              if (!e.shiftKey) {
                e.preventDefault();
                sendMessage();
              }
            }}
            autoSize={{ minRows: 2, maxRows: 6 }}
            disabled={connectionState !== WebSocketConnectionState.CONNECTED}
          />
          <div>
            <Button
              type="primary"
              onClick={sendMessage}
              disabled={connectionState !== WebSocketConnectionState.CONNECTED || !inputMessage.trim()}
              loading={loading}
              icon={<SendOutlined />}
              style={{ height: '100%', borderTopLeftRadius: 0, borderBottomLeftRadius: 0 }}
            >
              发送消息
            </Button>
            <Button
              onClick={sendQuery}
              disabled={connectionState !== WebSocketConnectionState.CONNECTED || !inputMessage.trim()}
              loading={loading}
              icon={<InfoCircleOutlined />}
              style={{ height: '100%', borderTopLeftRadius: 0, borderBottomLeftRadius: 0 }}
            >
              发送查询
            </Button>
          </div>
        </Space.Compact>
      </Card>

      <Divider />

      <Paragraph type="secondary">
        <Text strong>使用说明：</Text>
        <ul>
          <li>输入可选的用户ID并点击"连接"按钮建立WebSocket连接</li>
          <li>连接成功后，可以在输入框中输入消息或查询</li>
          <li>点击"发送消息"按钮发送普通消息，点击"发送查询"按钮发送查询请求</li>
          <li>收到的消息将显示在消息列表中</li>
          <li>点击"断开"按钮断开WebSocket连接</li>
        </ul>
      </Paragraph>
    </div>
  );
};

export default WebSocketDemo;
