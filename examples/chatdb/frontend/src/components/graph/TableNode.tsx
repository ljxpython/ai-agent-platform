import React, { memo } from 'react';
import { Handle, Position, NodeProps } from 'reactflow';
import { Card, Typography, Tooltip, Badge } from 'antd';
import { TableOutlined, InfoCircleOutlined } from '@ant-design/icons';

const { Text, Title } = Typography;

// 表节点数据类型
interface TableNodeData {
  id: number;
  label: string;
  description?: string;
  nodeType: 'table';
  columnCount?: number;
  onNodeClick?: (nodeId: string, nodeData: any) => void;
}

// 表节点组件
const TableNode = ({ id, data, selected }: NodeProps<TableNodeData>) => {
  const handleNodeClick = () => {
    if (data.onNodeClick) {
      data.onNodeClick(id, data);
    }
  };

  return (
    <div
      onClick={handleNodeClick}
      className="table-node-container"
      style={{ position: 'relative' }}
    >
      {/* 连接点 */}
      <Handle type="source" position={Position.Right} style={{ background: '#1890ff', width: 8, height: 8, zIndex: 10 }} />
      <Handle type="target" position={Position.Left} style={{ background: '#1890ff', width: 8, height: 8, zIndex: 10 }} />
      <Handle type="source" position={Position.Bottom} style={{ background: '#1890ff', width: 8, height: 8, zIndex: 10 }} />
      <Handle type="target" position={Position.Top} style={{ background: '#1890ff', width: 8, height: 8, zIndex: 10 }} />

      <Card
        className={`graph-node table-node ${selected ? 'selected' : ''}`}
        size="small"
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <TableOutlined style={{ color: '#1890ff' }} />
            <Text strong style={{ color: '#1890ff', margin: 0, maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {data.label}
            </Text>
          </div>
        }
        style={{
          width: 180,
          borderRadius: '4px',
          boxShadow: selected ? '0 0 0 2px #1890ff, 0 2px 8px rgba(0, 0, 0, 0.15)' : '0 2px 8px rgba(0, 0, 0, 0.15)',
          border: '1px solid #1890ff',
          background: 'rgba(24, 144, 255, 0.1)',
          opacity: 1,
          visibility: 'visible'
        }}
        bodyStyle={{ padding: '8px' }}
        headStyle={{ background: 'rgba(24, 144, 255, 0.2)' }}
      >
        {data.description && (
          <Tooltip title={data.description}>
            <div style={{ display: 'flex', alignItems: 'center', marginBottom: '4px' }}>
              <InfoCircleOutlined style={{ marginRight: '4px', color: '#1890ff' }} />
              <Text ellipsis style={{ flex: 1, maxWidth: 150 }}>{data.description}</Text>
            </div>
          </Tooltip>
        )}

        <Badge
          count={data.columnCount || '?'}
          style={{ backgroundColor: '#52c41a' }}
          title="列数量"
        >
          <Text type="secondary">表</Text>
        </Badge>
      </Card>
    </div>
  );
};

// 使用memo优化渲染性能
export default memo(TableNode);
