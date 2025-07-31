import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Collapse, Typography, Button, Tooltip, Spin, Table } from 'antd';
import {
  CopyOutlined,
  DownOutlined,
  RightOutlined,
  SearchOutlined,
  CodeOutlined,
  BarChartOutlined,
  BulbOutlined,
  TableOutlined
} from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { tomorrow } from 'react-syntax-highlighter/dist/esm/styles/prism';
// 导入XStreamMessage类型和RegionMessageManager
import type { XStreamMessage } from '../services/XStreamService';
import { RegionMessageManager } from '../services/XStreamService';

// 简化的区域数据管理
interface RegionData {
  content: string;
  hasContent: boolean;
  isStreaming: boolean;
}

const { Panel } = Collapse;
const { Text } = Typography;

// 区域配置
const REGION_CONFIG = {
  analysis: {
    title: '查询分析',
    icon: <SearchOutlined />,
    color: '#1890ff',
    contentType: 'markdown' as const
  },
  sql: {
    title: 'SQL语句',
    icon: <CodeOutlined />,
    color: '#52c41a',
    contentType: 'sql' as const
  },
  explanation: {
    title: '语句解释',
    icon: <BulbOutlined />,
    color: '#faad14',
    contentType: 'markdown' as const
  },
  data: {
    title: '查询结果',
    icon: <TableOutlined />,
    color: '#722ed1',
    contentType: 'table' as const
  },
  visualization: {
    title: '数据可视化',
    icon: <BarChartOutlined />,
    color: '#eb2f96',
    contentType: 'chart' as const
  },
  process: {
    title: '处理过程',
    icon: <Spin size="small" />,
    color: '#8c8c8c',
    contentType: 'text' as const
  }
};

interface XStreamOutputProps {
  messages: XStreamMessage[];
  isStreaming: boolean;
  onCopyContent?: (content: string, region: string) => void;
  className?: string;
}

// 内容渲染组件
const ContentRenderer: React.FC<{
  content: string;
  type: 'markdown' | 'sql' | 'json' | 'text' | 'table' | 'chart';
  isStreaming: boolean;
}> = ({ content, type, isStreaming }) => {
  const renderContent = () => {
    if (!content) return null;

    switch (type) {
      case 'sql':
        return (
          <SyntaxHighlighter
            language="sql"
            style={tomorrow}
            showLineNumbers={true}
            wrapLines={true}
            customStyle={{
              margin: 0,
              borderRadius: '6px',
              fontSize: '14px'
            }}
          >
            {content}
          </SyntaxHighlighter>
        );

      case 'json':
        try {
          const parsed = JSON.parse(content);
          return (
            <SyntaxHighlighter
              language="json"
              style={tomorrow}
              showLineNumbers={true}
              wrapLines={true}
              customStyle={{
                margin: 0,
                borderRadius: '6px',
                fontSize: '14px'
              }}
            >
              {JSON.stringify(parsed, null, 2)}
            </SyntaxHighlighter>
          );
        } catch {
          return (
            <pre style={{
              margin: 0,
              padding: '12px',
              backgroundColor: '#f5f5f5',
              borderRadius: '6px',
              fontSize: '14px',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word'
            }}>
              {content}
            </pre>
          );
        }

      case 'table':
        try {
          const data = JSON.parse(content);
          if (Array.isArray(data) && data.length > 0) {
            // 自动生成表格列
            const columns = Object.keys(data[0]).map(key => ({
              title: key,
              dataIndex: key,
              key: key,
              ellipsis: true,
              width: 150
            }));

            // 添加行键
            const dataSource = data.map((row, index) => ({
              ...row,
              key: index
            }));

            return (
              <Table
                columns={columns}
                dataSource={dataSource}
                pagination={{
                  pageSize: 10,
                  showSizeChanger: true,
                  showQuickJumper: true,
                  showTotal: (total) => `共 ${total} 条记录`
                }}
                scroll={{ x: 'max-content' }}
                size="small"
                style={{ fontSize: '14px' }}
              />
            );
          } else {
            return (
              <div style={{
                padding: '20px',
                textAlign: 'center',
                color: '#8c8c8c',
                backgroundColor: '#f5f5f5',
                borderRadius: '6px'
              }}>
                暂无数据
              </div>
            );
          }
        } catch {
          return (
            <pre style={{
              margin: 0,
              padding: '12px',
              backgroundColor: '#f5f5f5',
              borderRadius: '6px',
              fontSize: '14px',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word'
            }}>
              {content}
            </pre>
          );
        }

      case 'chart':
        try {
          const chartData = JSON.parse(content);
          return (
            <div style={{
              padding: '16px',
              backgroundColor: '#f9f9f9',
              borderRadius: '6px',
              minHeight: '200px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexDirection: 'column',
              gap: '12px'
            }}>
              <BarChartOutlined style={{ fontSize: '32px', color: '#eb2f96' }} />
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '16px', fontWeight: 500, marginBottom: '8px' }}>
                  数据可视化
                </div>
                <div style={{ fontSize: '14px', color: '#8c8c8c' }}>
                  图表类型: {chartData.type || '未知'}
                </div>
                {chartData.title && (
                  <div style={{ fontSize: '14px', color: '#8c8c8c' }}>
                    标题: {chartData.title}
                  </div>
                )}
              </div>
              <details style={{ width: '100%', marginTop: '12px' }}>
                <summary style={{ cursor: 'pointer', fontSize: '12px', color: '#666' }}>
                  查看原始数据
                </summary>
                <pre style={{
                  margin: '8px 0 0 0',
                  padding: '8px',
                  backgroundColor: '#fff',
                  borderRadius: '4px',
                  fontSize: '12px',
                  overflow: 'auto',
                  maxHeight: '200px'
                }}>
                  {JSON.stringify(chartData, null, 2)}
                </pre>
              </details>
            </div>
          );
        } catch {
          return (
            <div style={{
              padding: '16px',
              backgroundColor: '#f9f9f9',
              borderRadius: '6px',
              textAlign: 'center'
            }}>
              <BarChartOutlined style={{ fontSize: '24px', color: '#eb2f96', marginBottom: '8px' }} />
              <div style={{ fontSize: '14px', color: '#8c8c8c' }}>
                可视化数据格式错误
              </div>
              <pre style={{
                margin: '8px 0 0 0',
                padding: '8px',
                backgroundColor: '#fff',
                borderRadius: '4px',
                fontSize: '12px',
                textAlign: 'left'
              }}>
                {content}
              </pre>
            </div>
          );
        }

      case 'markdown':
        return (
          <div style={{ fontSize: '14px', lineHeight: '1.6' }}>
            <ReactMarkdown>{content}</ReactMarkdown>
          </div>
        );

      default:
        return (
          <pre style={{
            margin: 0,
            padding: '12px',
            backgroundColor: '#f5f5f5',
            borderRadius: '6px',
            fontSize: '14px',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word'
          }}>
            {content}
          </pre>
        );
    }
  };

  return (
    <div style={{ position: 'relative' }}>
      {renderContent()}
      {isStreaming && (
        <div style={{
          position: 'absolute',
          bottom: '8px',
          right: '8px',
          display: 'flex',
          alignItems: 'center',
          gap: '4px',
          padding: '4px 8px',
          backgroundColor: 'rgba(24, 144, 255, 0.1)',
          borderRadius: '4px',
          fontSize: '12px',
          color: '#1890ff'
        }}>
          <Spin size="small" />
          <Text type="secondary" style={{ fontSize: '12px' }}>正在生成...</Text>
        </div>
      )}
    </div>
  );
};

const XStreamOutput: React.FC<XStreamOutputProps> = ({
  messages,
  isStreaming,
  onCopyContent,
  className
}) => {
  const [activeKeys, setActiveKeys] = useState<string[]>(['analysis', 'sql', 'explanation', 'data', 'visualization']);
  const regionManager = useMemo(() => new RegionMessageManager(), []);

  // 处理消息更新
  useEffect(() => {
    // 重置管理器
    regionManager.reset();

    // 添加所有消息
    messages.forEach(message => {
      regionManager.addMessage(message);
    });
  }, [messages, regionManager]);

  // 获取所有区域数据
  const regions = regionManager.getAllRegions();

  // 处理复制内容
  const handleCopy = useCallback(async (content: string, region: string) => {
    try {
      await navigator.clipboard.writeText(content);
      onCopyContent?.(content, region);
    } catch (error) {
      console.error('复制失败:', error);
    }
  }, [onCopyContent]);

  // 处理面板变化
  const handlePanelChange = useCallback((keys: string | string[]) => {
    setActiveKeys(Array.isArray(keys) ? keys : [keys]);
  }, []);

  // 渲染区域面板
  const renderRegionPanels = () => {
    // 记录已处理的region
    const handledRegions = new Set<string>();
    const panels = Object.entries(REGION_CONFIG).map(([regionKey, config]) => {
      const regionData = regions[regionKey];
      handledRegions.add(regionKey);

      // 检查是否应该显示该区域
      const shouldShow = regionData && (regionData.hasContent || regionData.isStreaming);
      if (!shouldShow) return null;

      console.log(`渲染区域 ${regionKey}:`, {
        hasContent: regionData.hasContent,
        isStreaming: regionData.isStreaming,
        contentLength: regionData.content.length,
        content: regionData.content.substring(0, 100) + (regionData.content.length > 100 ? '...' : '')
      });

      return (
        <Panel
          key={regionKey}
          header={
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ color: config.color }}>{config.icon}</span>
              <span style={{ fontWeight: 500 }}>{config.title}</span>
              {regionData.isStreaming && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginLeft: 'auto', fontSize: '12px', color: '#1890ff' }}>
                  <Spin size="small" />
                  <Text type="secondary">正在生成...</Text>
                </div>
              )}
              {regionData.hasContent && !regionData.isStreaming && (
                <Tooltip title="复制内容">
                  <Button
                    type="text"
                    size="small"
                    icon={<CopyOutlined />}
                    onClick={e => { e.stopPropagation(); handleCopy(regionData.content, regionKey); }}
                    style={{ marginLeft: 'auto' }}
                  />
                </Tooltip>
              )}
            </div>
          }
          style={{
            borderLeft: regionData.isStreaming ? `3px solid ${config.color}` : undefined,
            backgroundColor: regionData.isStreaming ? `${config.color}08` : undefined
          }}
        >
          <ContentRenderer
            content={regionData.content}
            type={config.contentType}
            isStreaming={regionData.isStreaming}
          />
        </Panel>
      );
    }).filter(Boolean);

    // 处理未在REGION_CONFIG中的region（兜底）
    Object.entries(regions).forEach(([regionKey, regionData]) => {
      if (handledRegions.has(regionKey)) return;
      if (!regionData.hasContent && !regionData.isStreaming) return;
      panels.push(
        <Panel
          key={regionKey}
          header={
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ color: '#888' }}>未知区域</span>
              <span style={{ fontWeight: 500 }}>{regionKey}</span>
            </div>
          }
        >
          <ContentRenderer
            content={regionData.content}
            type={'text'}
            isStreaming={regionData.isStreaming}
          />
        </Panel>
      );
    });
    return panels;
  };

  return (
    <div className={className} style={{ width: '100%' }}>
      <Collapse
        activeKey={activeKeys}
        onChange={handlePanelChange}
        expandIcon={({ isActive }) => isActive ? <DownOutlined /> : <RightOutlined />}
        style={{ backgroundColor: 'transparent', border: 'none' }}
      >
        {renderRegionPanels()}
      </Collapse>
      {/* 如果没有任何内容且不在流式状态，显示空状态 */}
      {Object.values(regions).every(r => !r.hasContent) && !isStreaming && (
        <div style={{ textAlign: 'center', padding: '40px', color: '#8c8c8c' }}>
          <Text type="secondary">暂无内容，请输入查询开始对话</Text>
        </div>
      )}
    </div>
  );
};

export default XStreamOutput;
