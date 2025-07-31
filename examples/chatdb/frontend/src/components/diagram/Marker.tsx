import React from 'react';

// 关系类型常量
const RELATIONSHIP_TYPES = {
  ONE_TO_ONE: '1-to-1',
  ONE_TO_MANY: '1-to-N',
  MANY_TO_ONE: 'N-to-1',  // 添加多对一关系类型
  MANY_TO_MANY: 'N-to-M'
};

// 关系类型对应的颜色
const RELATIONSHIP_TYPE_COLORS = {
  [RELATIONSHIP_TYPES.ONE_TO_ONE]: '#8b5cf6', // 紫色
  [RELATIONSHIP_TYPES.ONE_TO_MANY]: '#0ea5e9', // 蓝色
  [RELATIONSHIP_TYPES.MANY_TO_ONE]: '#10b981', // 绿色
  [RELATIONSHIP_TYPES.MANY_TO_MANY]: '#f59e0b', // 橙色
};

// 标记组件 - 用于显示关系的端点标记
const Marker = () => {
  return (
    <svg style={{ position: 'absolute', top: 0, left: 0 }}>
      <defs>
        {/* 一对一关系的起点标记 */}
        <marker
          id="one-to-one-start"
          viewBox="0 0 10 10"
          refX="5"
          refY="5"
          markerWidth="8"
          markerHeight="8"
          orient="auto-start-reverse"
        >
          <circle cx="5" cy="5" r="4" fill="white" stroke={RELATIONSHIP_TYPE_COLORS[RELATIONSHIP_TYPES.ONE_TO_ONE]} strokeWidth="1" />
          <line x1="2" y1="5" x2="8" y2="5" stroke={RELATIONSHIP_TYPE_COLORS[RELATIONSHIP_TYPES.ONE_TO_ONE]} strokeWidth="1.5" />
        </marker>

        {/* 一对一关系的终点标记 */}
        <marker
          id="one-to-one-end"
          viewBox="0 0 10 10"
          refX="5"
          refY="5"
          markerWidth="8"
          markerHeight="8"
          orient="auto-start-reverse"
        >
          <circle cx="5" cy="5" r="4" fill="white" stroke={RELATIONSHIP_TYPE_COLORS[RELATIONSHIP_TYPES.ONE_TO_ONE]} strokeWidth="1" />
          <line x1="2" y1="5" x2="8" y2="5" stroke={RELATIONSHIP_TYPE_COLORS[RELATIONSHIP_TYPES.ONE_TO_ONE]} strokeWidth="1.5" />
        </marker>

        {/* 一对多关系的"一"端标记 */}
        <marker
          id="one-to-many-start"
          viewBox="0 0 10 10"
          refX="5"
          refY="5"
          markerWidth="8"
          markerHeight="8"
          orient="auto-start-reverse"
        >
          <circle cx="5" cy="5" r="4" fill="white" stroke={RELATIONSHIP_TYPE_COLORS[RELATIONSHIP_TYPES.ONE_TO_MANY]} strokeWidth="1" />
          <line x1="2" y1="5" x2="8" y2="5" stroke={RELATIONSHIP_TYPE_COLORS[RELATIONSHIP_TYPES.ONE_TO_MANY]} strokeWidth="1.5" />
        </marker>

        {/* 一对多关系的"多"端标记 */}
        <marker
          id="one-to-many-end"
          viewBox="0 0 10 10"
          refX="5"
          refY="5"
          markerWidth="8"
          markerHeight="8"
          orient="auto-start-reverse"
        >
          <circle cx="5" cy="5" r="4" fill="white" stroke={RELATIONSHIP_TYPE_COLORS[RELATIONSHIP_TYPES.ONE_TO_MANY]} strokeWidth="1" />
          <path d="M2,3 L8,3 M2,5 L8,5 M2,7 L8,7" stroke={RELATIONSHIP_TYPE_COLORS[RELATIONSHIP_TYPES.ONE_TO_MANY]} strokeWidth="1.5" fill="none" />
        </marker>

        {/* 多对一关系的“多”端标记 */}
        <marker
          id="many-to-one-start"
          viewBox="0 0 10 10"
          refX="5"
          refY="5"
          markerWidth="8"
          markerHeight="8"
          orient="auto-start-reverse"
        >
          <circle cx="5" cy="5" r="4" fill="white" stroke={RELATIONSHIP_TYPE_COLORS[RELATIONSHIP_TYPES.MANY_TO_ONE]} strokeWidth="1" />
          <path d="M2,3 L8,3 M2,5 L8,5 M2,7 L8,7" stroke={RELATIONSHIP_TYPE_COLORS[RELATIONSHIP_TYPES.MANY_TO_ONE]} strokeWidth="1.5" fill="none" />
        </marker>

        {/* 多对一关系的“一”端标记 */}
        <marker
          id="many-to-one-end"
          viewBox="0 0 10 10"
          refX="5"
          refY="5"
          markerWidth="8"
          markerHeight="8"
          orient="auto-start-reverse"
        >
          <circle cx="5" cy="5" r="4" fill="white" stroke={RELATIONSHIP_TYPE_COLORS[RELATIONSHIP_TYPES.MANY_TO_ONE]} strokeWidth="1" />
          <line x1="2" y1="5" x2="8" y2="5" stroke={RELATIONSHIP_TYPE_COLORS[RELATIONSHIP_TYPES.MANY_TO_ONE]} strokeWidth="1.5" />
        </marker>

        {/* 多对多关系的起点标记 */}
        <marker
          id="many-to-many-start"
          viewBox="0 0 10 10"
          refX="5"
          refY="5"
          markerWidth="8"
          markerHeight="8"
          orient="auto-start-reverse"
        >
          <circle cx="5" cy="5" r="4" fill="white" stroke={RELATIONSHIP_TYPE_COLORS[RELATIONSHIP_TYPES.MANY_TO_MANY]} strokeWidth="1" />
          <path d="M2,3 L8,3 M2,5 L8,5 M2,7 L8,7" stroke={RELATIONSHIP_TYPE_COLORS[RELATIONSHIP_TYPES.MANY_TO_MANY]} strokeWidth="1.5" fill="none" />
        </marker>

        {/* 多对多关系的终点标记 */}
        <marker
          id="many-to-many-end"
          viewBox="0 0 10 10"
          refX="5"
          refY="5"
          markerWidth="8"
          markerHeight="8"
          orient="auto-start-reverse"
        >
          <circle cx="5" cy="5" r="4" fill="white" stroke={RELATIONSHIP_TYPE_COLORS[RELATIONSHIP_TYPES.MANY_TO_MANY]} strokeWidth="1" />
          <path d="M2,3 L8,3 M2,5 L8,5 M2,7 L8,7" stroke={RELATIONSHIP_TYPE_COLORS[RELATIONSHIP_TYPES.MANY_TO_MANY]} strokeWidth="1.5" fill="none" />
        </marker>
      </defs>
    </svg>
  );
};

export default Marker;
