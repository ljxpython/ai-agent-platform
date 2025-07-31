import React, { useState, memo } from 'react';
import { EdgeProps, getBezierPath, EdgeLabelRenderer, MarkerType } from 'reactflow';
import { Tooltip } from 'antd';

// 关系类型颜色
const RELATIONSHIP_COLORS = {
  references: '#722ed1', // 紫色
  hasColumn: '#faad14', // 橙色
  default: '#1890ff' // 蓝色
};

// 关系边数据类型
interface RelationshipEdgeData {
  relationshipType: string;
  description?: string;
  markerId?: string;
  markerColor?: string;
}

// 关系边组件
const RelationshipEdge = ({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  markerEnd,
  style = {},
  selected
}: EdgeProps<RelationshipEdgeData>) => {
  const [isHovered, setIsHovered] = useState(false);

  // 确定关系类型和颜色
  const relationshipType = data?.relationshipType || 'unknown';
  const edgeType = id.includes('table-') && id.includes('column-') ? 'hasColumn' : 'references';
  const stroke = data?.markerColor || RELATIONSHIP_COLORS[edgeType] || RELATIONSHIP_COLORS.default;

  // 计算贝塞尔曲线路径
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
    curvature: 0.3
  });

  // 边样式
  const edgeStyle = {
    stroke,
    strokeWidth: selected ? 3 : isHovered ? 2.5 : 2,
    // 移除可能导致TypeScript错误的属性
    ...style,
  };

  // 鼠标事件处理
  const handleMouseEnter = () => setIsHovered(true);
  const handleMouseLeave = () => setIsHovered(false);

  // 始终显示标签
  const showLabel = isHovered || selected;

  return (
    <>
      <path
        id={id}
        className="react-flow__edge-path"
        d={edgePath}
        style={edgeStyle}
        markerEnd={markerEnd}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
      />

      {showLabel && (
        <EdgeLabelRenderer>
          <div
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
              background: '#fff',
              padding: '4px 8px',
              borderRadius: '4px',
              fontSize: 12,
              fontWeight: 500,
              pointerEvents: 'all',
              border: `1px solid ${stroke}`,
              boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
              zIndex: 1000
            }}
          >
            <Tooltip title={data?.description || ''}>
              {edgeType === 'hasColumn' ? '包含' : relationshipType}
            </Tooltip>
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
};

// 使用memo优化渲染性能
export default memo(RelationshipEdge);
