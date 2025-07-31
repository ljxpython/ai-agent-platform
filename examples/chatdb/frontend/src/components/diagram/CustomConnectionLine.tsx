import React from 'react';
import { ConnectionLineComponentProps, getSmoothStepPath } from 'reactflow';

// 关系类型对应的颜色
const CONNECTION_COLOR = '#0ea5e9'; // 蓝色

// 自定义连接线组件 - 用于拖拽创建关系时显示的连接线
const CustomConnectionLine = ({
  fromX,
  fromY,
  fromPosition,
  toX,
  toY,
  toPosition,
}: ConnectionLineComponentProps) => {
  // 使用平滑步进路径
  const [edgePath] = getSmoothStepPath({
    sourceX: fromX,
    sourceY: fromY,
    sourcePosition: fromPosition,
    targetX: toX,
    targetY: toY,
    targetPosition: toPosition,
  });

  return (
    <path
      className="custom-connection-line"
      d={edgePath}
      fill="none"
      stroke={CONNECTION_COLOR}
      strokeWidth={2}
      strokeDasharray="5,5"
      style={{ pointerEvents: 'none' }}
    />
  );
};

export default CustomConnectionLine;
