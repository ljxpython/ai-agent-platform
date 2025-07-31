import React, { memo, useMemo, useState } from 'react';
import { EdgeProps, getSmoothStepPath, MarkerType } from 'reactflow';
import { DeleteOutlined } from '@ant-design/icons';

// 关系类型常量
const RELATIONSHIP_TYPES = {
  ONE_TO_ONE: '1-to-1',
  ONE_TO_MANY: '1-to-N',
  MANY_TO_ONE: 'N-to-1',  // 添加多对一关系类型
  MANY_TO_MANY: 'N-to-M'
};

// 获取关系类型的颜色
const getStrokeColor = (relationshipType: string): string => {
  switch (relationshipType) {
    case RELATIONSHIP_TYPES.ONE_TO_ONE:
      return '#8b5cf6'; // 紫色
    case RELATIONSHIP_TYPES.ONE_TO_MANY:
      return '#0ea5e9'; // 蓝色
    case RELATIONSHIP_TYPES.MANY_TO_ONE:
      return '#10b981'; // 绿色
    case RELATIONSHIP_TYPES.MANY_TO_MANY:
      return '#f59e0b'; // 橙色
    default:
      return '#64748b'; // 默认灰色
  }
};

// 获取关系类型的端点标记
const getMarkerEnd = (relationshipType: string) => {
  switch (relationshipType) {
    case RELATIONSHIP_TYPES.ONE_TO_ONE:
      return {
        type: 'url',
        orient: 'auto',
        markerUnits: 'userSpaceOnUse',
        id: 'one-to-one-end',
        color: '#8b5cf6',
        width: 15,
        height: 15
      };
    case RELATIONSHIP_TYPES.ONE_TO_MANY:
      return {
        type: 'url',
        orient: 'auto',
        markerUnits: 'userSpaceOnUse',
        id: 'one-to-many-end',
        color: '#0ea5e9',
        width: 15,
        height: 15
      };
    case RELATIONSHIP_TYPES.MANY_TO_ONE:
      return {
        type: 'url',
        orient: 'auto',
        markerUnits: 'userSpaceOnUse',
        id: 'many-to-one-end',
        color: '#10b981',
        width: 15,
        height: 15
      };
    case RELATIONSHIP_TYPES.MANY_TO_MANY:
      return {
        type: 'url',
        orient: 'auto',
        markerUnits: 'userSpaceOnUse',
        id: 'many-to-many-end',
        color: '#f59e0b',
        width: 15,
        height: 15
      };
    default:
      return {
        type: MarkerType.Arrow,
        color: '#64748b',
        width: 15,
        height: 15
      };
  }
};

// 获取关系类型的起点标记
const getMarkerStart = (relationshipType: string) => {
  switch (relationshipType) {
    case RELATIONSHIP_TYPES.ONE_TO_ONE:
      return {
        type: 'url',
        orient: 'auto',
        markerUnits: 'userSpaceOnUse',
        id: 'one-to-one-start',
        color: '#8b5cf6',
        width: 15,
        height: 15
      };
    case RELATIONSHIP_TYPES.ONE_TO_MANY:
      return {
        type: 'url',
        orient: 'auto',
        markerUnits: 'userSpaceOnUse',
        id: 'one-to-many-start',
        color: '#0ea5e9',
        width: 15,
        height: 15
      };
    case RELATIONSHIP_TYPES.MANY_TO_ONE:
      return {
        type: 'url',
        orient: 'auto',
        markerUnits: 'userSpaceOnUse',
        id: 'many-to-one-start',
        color: '#10b981',
        width: 15,
        height: 15
      };
    case RELATIONSHIP_TYPES.MANY_TO_MANY:
      return {
        type: 'url',
        orient: 'auto',
        markerUnits: 'userSpaceOnUse',
        id: 'many-to-many-start',
        color: '#f59e0b',
        width: 15,
        height: 15
      };
    default:
      return {};
  }
};

// 关系类型对应的标签
const RELATIONSHIP_LABELS = {
  [RELATIONSHIP_TYPES.ONE_TO_ONE]: '1:1',
  [RELATIONSHIP_TYPES.ONE_TO_MANY]: '1:N',
  [RELATIONSHIP_TYPES.MANY_TO_ONE]: 'N:1',
  [RELATIONSHIP_TYPES.MANY_TO_MANY]: 'N:M'
};

// 关系类型对应的中文描述
const RELATIONSHIP_TYPE_LABELS = {
  [RELATIONSHIP_TYPES.ONE_TO_ONE]: '一对一 (1:1)',
  [RELATIONSHIP_TYPES.ONE_TO_MANY]: '一对多 (1:N)',
  [RELATIONSHIP_TYPES.MANY_TO_ONE]: '多对一 (N:1)',
  [RELATIONSHIP_TYPES.MANY_TO_MANY]: '多对多 (N:M)'
};

const RelationshipEdge = ({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  selected,
  markerStart,
  markerEnd,
  style = {}
}: EdgeProps) => {
  const [isHovered, setIsHovered] = useState(false);
  // 确定关系类型
  const relationshipType = data?.relationshipType || RELATIONSHIP_TYPES.ONE_TO_MANY;

  // 确定线的颜色和粗细
  const stroke = getStrokeColor(relationshipType);
  const strokeWidth = selected ? 4 : 2.5;

  // 获取端点标记
  const customMarkerEnd = getMarkerEnd(relationshipType);
  const customMarkerStart = getMarkerStart(relationshipType);

  // 使用 getSmoothStepPath 计算路径，这样可以更好地处理不同的连接点位置
  const [edgePath, labelX, labelY] = getSmoothStepPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  // 确定虚线样式 - 多对多和多对一使用虚线
  const strokeDasharray = relationshipType === RELATIONSHIP_TYPES.MANY_TO_MANY || relationshipType === RELATIONSHIP_TYPES.MANY_TO_ONE ? '5,5' : '';

  // 标签文本
  const labelText = RELATIONSHIP_LABELS[relationshipType] || '1:N';

  // 根据关系类型设置样式
  const edgeStyle = {
    strokeWidth,
    stroke,
    strokeDasharray,
    ...style
  };

  // 源表和目标表信息
  const sourceTable = data?.sourceTable || '';
  const sourceColumn = data?.sourceColumn || '';
  const targetTable = data?.targetTable || '';
  const targetColumn = data?.targetColumn || '';

  // 关系描述
  const description = useMemo(() => {
    return {
      type: RELATIONSHIP_TYPE_LABELS[relationshipType] || '',
      from: `${sourceTable}.${sourceColumn}`,
      to: `${targetTable}.${targetColumn}`,
      description: data?.description || '-',
      // 添加更详细的关系描述
      detailedDescription: `${sourceTable}.${sourceColumn} → ${targetTable}.${targetColumn}`
    };
  }, [relationshipType, sourceTable, sourceColumn, targetTable, targetColumn, data?.description]);

  // 选中状态的样式
  const isHighlighted = selected || data?.highlight;
  const edgeClassName = `react-flow__edge-path relationship-${relationshipType} ${isHighlighted ? 'highlighted' : ''}`;

  // 处理鼠标悬停
  const handleMouseEnter = () => {
    setIsHovered(true);
  };

  const handleMouseLeave = () => {
    setIsHovered(false);
  };

  // 处理删除按钮点击
  // const handleDeleteClick = (e: React.MouseEvent) => {
  //   e.stopPropagation();
  //   console.log('Delete button clicked for edge:', id);
  //   console.log('Edge data:', data);

  //   // 获取正确的 ID
  //   // 尝试使用边的 ID
  //   const edgeId = id;
  //   console.log('Using edge ID for deletion:', edgeId);
  //   console.log('Edge object:', { id, data, sourceX, targetX });

  //   // 触发自定义删除事件
  //   const deleteEvent = new CustomEvent('edge-delete', {
  //     detail: { id: edgeId }
  //   });
  //   window.dispatchEvent(deleteEvent);

  //   // 直接触发删除函数
  //   // 如果自定义事件不起作用，可以尝试直接调用全局函数
  //   if (typeof (window as any).deleteRelationship === 'function') {
  //     (window as any).deleteRelationship(edgeId);
  //   }
  // };

  return (
    <>
      <path
        id={id}
        className={edgeClassName}
        d={edgePath as string}
        markerEnd={customMarkerEnd.id ? `url(#${customMarkerEnd.id})` : undefined}
        markerStart={customMarkerStart.id ? `url(#${customMarkerStart.id})` : undefined}
        style={edgeStyle}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
      />

      {/* 标签背景 */}
      <foreignObject
        width={50}
        height={30}
        x={labelX - 25}
        y={labelY - 15}
        style={{ overflow: 'visible', zIndex: 1000, pointerEvents: 'all' }}
        className={`edge-label-container ${isHighlighted ? 'highlighted' : ''}`}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
      >
        <div
          style={{
            background: 'white',
            border: `2px solid ${stroke}`,
            borderRadius: 8,
            color: stroke,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '100%',
            height: '100%',
            fontSize: '13px',
            fontWeight: 600,
            userSelect: 'none',
            pointerEvents: 'all',
            cursor: 'pointer',
            position: 'relative',
            transition: 'transform 0.2s, box-shadow 0.2s',
            transform: selected || isHovered ? 'scale(1.1)' : 'scale(1)',
            boxShadow: selected || isHovered ? `0 3px 6px rgba(0,0,0,0.2), 0 0 0 2px ${stroke}` : '0 2px 4px rgba(0,0,0,0.15)'
          }}
          onClick={(e) => {
            e.stopPropagation();
            // 触发边的点击事件
            const edgeElement = document.getElementById(id);
            if (edgeElement) {
              const event = new MouseEvent('click', {
                bubbles: true,
                cancelable: true,
                view: window
              });
              edgeElement.dispatchEvent(event);
            }
          }}
          title={`${description.detailedDescription}\n\n关系类型: ${description.type}\n描述: ${description.description}`}
        >
          {labelText}

          {/* 删除按钮 */}
          {(isHovered || selected) && (
            <div
              className="edge-delete-button"
              style={{
                position: 'absolute',
                top: '-12px',
                right: '-12px',
                width: '24px',
                height: '24px',
                borderRadius: '50%',
                backgroundColor: '#f5222d',
                color: 'white',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer',
                boxShadow: '0 2px 4px rgba(0,0,0,0.2)',
                zIndex: 1001
              }}
              onClick={(e) => {
                e.stopPropagation();
                e.preventDefault();
                console.log('Delete button clicked directly for edge:', id);
                console.log('Edge data:', data);

                // 尝试直接删除当前边
                if (typeof (window as any).deleteCurrentEdge === 'function') {
                  // 传递当前边的完整对象
                  (window as any).deleteCurrentEdge({
                    id,
                    source: data?.sourceNodeId,
                    target: data?.targetNodeId,
                    data
                  });
                  return;
                }

                // 如果上面的方法不起作用，尝试使用 ID
                const edgeId = id;
                console.log('Using edge ID for deletion:', edgeId);
                console.log('Edge object:', { id, data, sourceX, targetX });

                // 直接调用全局函数
                if (typeof (window as any).deleteRelationship === 'function') {
                  (window as any).deleteRelationship(edgeId);
                } else {
                  console.error('deleteRelationship function not found on window object');
                  // 尝试触发自定义事件
                  const deleteEvent = new CustomEvent('edge-delete', {
                    detail: { id: edgeId }
                  });
                  window.dispatchEvent(deleteEvent);
                }
              }}
              title="删除关系"
            >
              <DeleteOutlined style={{ fontSize: '12px' }} />
            </div>
          )}
        </div>
      </foreignObject>
    </>
  );
};

export default memo(RelationshipEdge);
