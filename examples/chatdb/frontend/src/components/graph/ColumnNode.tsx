import React, { memo } from 'react';
import { Handle, Position, NodeProps } from 'reactflow';
import { Card, Typography, Tag, Tooltip } from 'antd';
import { ColumnWidthOutlined, KeyOutlined, LinkOutlined } from '@ant-design/icons';

const { Text } = Typography;

// 列节点数据类型
interface ColumnNodeData {
  id: number;
  label: string;
  description?: string;
  nodeType: 'column';
  dataType?: string;
  isPrimaryKey?: boolean;
  isForeignKey?: boolean;
  tableId?: number;
  tableName?: string;
  onNodeClick?: (nodeId: string, nodeData: any) => void;
}

// 列节点组件
const ColumnNode = ({ id, data, selected }: NodeProps<ColumnNodeData>) => {
  const handleNodeClick = () => {
    if (data.onNodeClick) {
      data.onNodeClick(id, data);
    }
  };

  return (
    <div
      onClick={handleNodeClick}
      className="column-node-container"
      style={{ position: 'relative' }}
    >
      {/* 连接点 */}
      <Handle type="source" position={Position.Right} style={{ background: '#52c41a', width: 8, height: 8, zIndex: 10 }} />
      <Handle type="target" position={Position.Left} style={{ background: '#52c41a', width: 8, height: 8, zIndex: 10 }} />
      <Handle type="source" position={Position.Bottom} style={{ background: '#52c41a', width: 8, height: 8, zIndex: 10 }} />
      <Handle type="target" position={Position.Top} style={{ background: '#52c41a', width: 8, height: 8, zIndex: 10 }} />

      <Card
        className={`graph-node column-node ${selected ? 'selected' : ''}`}
        size="small"
        style={{
          width: 150,
          borderRadius: '8px',
          boxShadow: selected ? '0 0 0 2px #52c41a, 0 2px 8px rgba(0, 0, 0, 0.15)' : '0 2px 8px rgba(0, 0, 0, 0.15)',
          border: '1px solid #52c41a',
          background: 'rgba(82, 196, 26, 0.1)',
          opacity: 1,
          visibility: 'visible'
        }}
        bodyStyle={{ padding: '8px', textAlign: 'center' }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px', marginBottom: '4px' }}>
          <ColumnWidthOutlined style={{ color: '#52c41a' }} />
          <Text strong style={{ color: '#52c41a', margin: 0, maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {data.label}
          </Text>
        </div>

        <Tooltip title={`数据类型: ${data.dataType || '未知'}`}>
          <Tag color="green" style={{ margin: '4px 0' }}>{data.dataType || '未知'}</Tag>
        </Tooltip>

        <div style={{ display: 'flex', justifyContent: 'center', gap: '8px', marginTop: '4px' }}>
          {data.isPrimaryKey && (
            <Tooltip title="主键">
              <KeyOutlined style={{ color: 'gold' }} />
            </Tooltip>
          )}
          {data.isForeignKey && (
            <Tooltip title="外键">
              <LinkOutlined style={{ color: 'purple' }} />
            </Tooltip>
          )}
        </div>

        <Text type="secondary" style={{ fontSize: '10px', display: 'block', marginTop: '4px', maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {data.tableName || ''}
        </Text>
      </Card>
    </div>
  );
};

// 使用memo优化渲染性能
export default memo(ColumnNode);
