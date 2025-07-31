import React, { useState, useCallback } from 'react';
import { Button, Input, Card, Typography, Space, Divider } from 'antd';
import { xStreamService, XStreamMessage, createStreamHandler } from '../services/XStreamService';

const { Text, Paragraph } = Typography;

interface RegionData {
  [region: string]: {
    content: string;
    isStreaming: boolean;
    messageCount: number;
  };
}

const SSETestComponent: React.FC = () => {
  const [query, setQuery] = useState('查询用户信息');
  const [connectionId] = useState(1);
  const [loading, setLoading] = useState(false);
  const [regions, setRegions] = useState<RegionData>({});
  const [logs, setLogs] = useState<string[]>([]);

  const addLog = useCallback((message: string) => {
    setLogs(prev => [...prev.slice(-20), `${new Date().toLocaleTimeString()}: ${message}`]);
  }, []);

  const handleStreamMessage = useCallback((message: XStreamMessage) => {
    addLog(`收到消息: ${message.type} | ${message.region} | ${message.content.length}字符`);

    setRegions(prev => {
      const region = message.region;
      const current = prev[region] || { content: '', isStreaming: false, messageCount: 0 };

      return {
        ...prev,
        [region]: {
          content: message.type === 'message' ? current.content + message.content : message.content,
          isStreaming: !message.is_final,
          messageCount: current.messageCount + 1
        }
      };
    });
  }, [addLog]);

  const handleStreamError = useCallback((error: Error) => {
    addLog(`错误: ${error.message}`);
    setLoading(false);
  }, [addLog]);

  const handleStreamComplete = useCallback(() => {
    addLog('流处理完成');
    setLoading(false);
  }, [addLog]);

  const handleTest = useCallback(async () => {
    if (!query.trim()) return;

    setLoading(true);
    setRegions({});
    setLogs([]);
    addLog('开始测试SSE连接...');

    try {
      const handler = createStreamHandler(
        handleStreamMessage,
        handleStreamError,
        handleStreamComplete
      );

      await xStreamService.startStream(query, handler, {
        connectionId,
        sessionId: `test-${Date.now()}`
      });

      addLog('SSE请求已发送');
    } catch (error) {
      addLog(`请求失败: ${error instanceof Error ? error.message : '未知错误'}`);
      setLoading(false);
    }
  }, [query, connectionId, handleStreamMessage, handleStreamError, handleStreamComplete, addLog]);

  return (
    <div style={{ padding: '20px', maxWidth: '1200px', margin: '0 auto' }}>
      <Card title="SSE连接测试" style={{ marginBottom: '20px' }}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="输入测试查询"
            style={{ width: '300px' }}
          />
          <Button
            type="primary"
            onClick={handleTest}
            loading={loading}
            disabled={!query.trim()}
          >
            测试SSE连接
          </Button>
        </Space>
      </Card>

      <div style={{ display: 'flex', gap: '20px' }}>
        {/* 区域数据显示 */}
        <div style={{ flex: 1 }}>
          <Card title="区域数据" size="small">
            {Object.keys(regions).length === 0 ? (
              <Text type="secondary">暂无数据</Text>
            ) : (
              Object.entries(regions).map(([region, data]) => (
                <Card
                  key={region}
                  size="small"
                  style={{ marginBottom: '10px' }}
                  title={
                    <span>
                      {region}
                      {data.isStreaming && <Text type="warning"> (流式中...)</Text>}
                      <Text type="secondary"> ({data.messageCount}条消息)</Text>
                    </span>
                  }
                >
                  <Paragraph
                    style={{
                      maxHeight: '200px',
                      overflow: 'auto',
                      backgroundColor: '#f5f5f5',
                      padding: '8px',
                      borderRadius: '4px',
                      fontSize: '12px',
                      whiteSpace: 'pre-wrap'
                    }}
                  >
                    {data.content || '暂无内容'}
                  </Paragraph>
                </Card>
              ))
            )}
          </Card>
        </div>

        {/* 日志显示 */}
        <div style={{ width: '400px' }}>
          <Card title="调试日志" size="small">
            <div style={{
              height: '400px',
              overflow: 'auto',
              backgroundColor: '#f5f5f5',
              padding: '8px',
              borderRadius: '4px',
              fontSize: '12px'
            }}>
              {logs.length === 0 ? (
                <Text type="secondary">暂无日志</Text>
              ) : (
                logs.map((log, index) => (
                  <div key={index} style={{ marginBottom: '4px' }}>
                    {log}
                  </div>
                ))
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default SSETestComponent;
