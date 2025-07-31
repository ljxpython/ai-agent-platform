import React, { useState, useEffect, useCallback } from 'react';
import { Handle, Position } from 'reactflow';
import { Typography, Tooltip, Button } from 'antd';
import { TableOutlined, KeyOutlined, LinkOutlined, CloseCircleOutlined } from '@ant-design/icons';

const { Text } = Typography;

// 表节点组件 - 参考 src-old/components/diagram/customNode/ModelNode.tsx
const TableNode = ({ data, id, selected }: { data: any, id: string, selected?: boolean }) => {
  const [hoveredColumn, setHoveredColumn] = useState<string | null>(null);
  const [, setActiveHandles] = useState<{[key: string]: boolean}>({});
  const [isHovered, setIsHovered] = useState<boolean>(false);

  // 当鼠标移到列上时，显示该列的连接点
  useEffect(() => {
    if (hoveredColumn) {
      setActiveHandles({ [hoveredColumn]: true });
    } else {
      setActiveHandles({});
    }
  }, [hoveredColumn]);

  // 处理拖拽开始
  const onDragStart = (event: React.DragEvent, columnData: any) => {
    // 开始拖拽时，设置要传输的数据
    const columnId = columnData.id || columnData.column_name;
    const dragData = {
      nodeId: id,
      columnId: columnId,
      columnName: columnData.column_name,
      tableName: data.label,
      isPrimaryKey: columnData.is_primary_key,
      isForeignKey: columnData.is_foreign_key,
      dataType: columnData.data_type
    };

    console.log('拖拽开始，列信息：', dragData);

    // 设置拖拽数据
    event.dataTransfer.setData('application/reactflow', JSON.stringify(dragData));
    event.dataTransfer.effectAllowed = 'move';

    // 添加视觉反馈
    const el = event.currentTarget as HTMLElement;
    el.style.opacity = '0.6';

    // 显示所有可能的目标连接点
    document.querySelectorAll('.column').forEach((col) => {
      if (col !== el) {
        col.classList.add('potential-target');
      }
    });
  };

  // 处理拖拽结束
  const onDragEnd = (event: React.DragEvent) => {
    // 恢复正常外观
    const el = event.currentTarget as HTMLElement;
    el.style.opacity = '1';

    // 移除目标高亮
    document.querySelectorAll('.column').forEach((col) => {
      col.classList.remove('potential-target');
      col.classList.remove('active-target');
    });
  };

  // 处理拖拽经过
  const onDragOver = (event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';

    // 添加视觉反馈
    const el = event.currentTarget as HTMLElement;
    el.classList.add('active-target');
  };

  // 处理拖拽离开
  const onDragLeave = (event: React.DragEvent) => {
    const el = event.currentTarget as HTMLElement;
    el.classList.remove('active-target');
  };

  // 处理拖拽放置
  const onDrop = (event: React.DragEvent, columnData: any) => {
    event.preventDefault();
    event.stopPropagation();

    // 获取源列数据
    try {
      const dataTransfer = event.dataTransfer.getData('application/reactflow');
      const sourceData = JSON.parse(dataTransfer);

      // 清除视觉反馈
      document.querySelectorAll('.column').forEach((col) => {
        col.classList.remove('potential-target');
        col.classList.remove('active-target');
      });

      // 确保不是同一个列
      if (sourceData.nodeId === id && sourceData.columnName === columnData.column_name) {
        console.log('拖拽到同一列，忽略');
        return;
      }

      // 准备目标数据
      const columnId = columnData.id || columnData.column_name;
      const targetData = {
        nodeId: id,
        columnId: columnId,
        columnName: columnData.column_name,
        tableName: data.label,
        isPrimaryKey: columnData.is_primary_key,
        isForeignKey: columnData.is_foreign_key,
        dataType: columnData.data_type
      };

      console.log('创建连接：', {
        source: sourceData,
        target: targetData
      });

      // 创建自定义事件
      const customEvent = new CustomEvent('column-drop', {
        detail: {
          source: sourceData,
          target: targetData
        }
      });

      // 触发事件
      window.dispatchEvent(customEvent);
    } catch (error) {
      console.error('处理拖拽时出错：', error);
    }
  };

  // 处理列的鼠标悬停事件 - 高亮相关的边和节点
  const onColumnMouseEnter = useCallback((columnId: string) => {
    console.log('Column mouse enter:', columnId);
    setHoveredColumn(columnId);

    // 这里可以添加高亮相关边的逻辑，类似 src-old 中的 ModelNode
  }, []);

  const onColumnMouseLeave = useCallback((columnId: string) => {
    console.log('Column mouse leave:', columnId);
    setHoveredColumn(null);

    // 这里可以添加取消高亮相关边的逻辑
  }, []);

  // 处理节点鼠标悬停事件
  const handleMouseEnter = useCallback(() => {
    console.log('Node mouse enter:', id);
    setIsHovered(true);
  }, [id]);

  const handleMouseLeave = useCallback(() => {
    console.log('Node mouse leave:', id);
    setIsHovered(false);
  }, [id]);

  // 添加鼠标按下事件处理
  const handleMouseDown = useCallback((event: React.MouseEvent) => {
    console.log('Node mouse down:', id, event);
    // 防止事件冒泡
    event.stopPropagation();

    // 添加视觉反馈
    const el = event.currentTarget as HTMLElement;
    el.style.cursor = 'grabbing';

    // 触发一个全局的鼠标事件，以确保正确的拖拽行为
    const mouseDownEvent = new MouseEvent('mousedown', {
      bubbles: true,
      cancelable: true,
      clientX: event.clientX,
      clientY: event.clientY,
      button: 0,
    });
    document.dispatchEvent(mouseDownEvent);
  }, [id]);

  // 确保表头部分可拖拽
  const handleDragHandleMouseDown = (event: React.MouseEvent) => {
    // 防止事件冒泡和默认行为
    event.stopPropagation();

    // 添加视觉反馈
    const el = event.currentTarget as HTMLElement;
    el.style.cursor = 'grabbing';

    // 记录鼠标按下事件，以便在src-old中的方式处理
    console.log('Mouse down on drag handle', event);

    // 触发一个全局的鼠标事件，以确保正确的拖拽行为
    const mouseDownEvent = new MouseEvent('mousedown', {
      bubbles: true,
      cancelable: true,
      clientX: event.clientX,
      clientY: event.clientY,
      button: 0,
    });
    document.dispatchEvent(mouseDownEvent);
  };

  // 处理表节点点击 - 打开编辑模态框
  const handleTableClick = (e: React.MouseEvent) => {
    // 确保点击的是表头而不是列或者其他元素
    if ((e.target as HTMLElement).closest('.node-header')) {
      // 触发自定义事件，通知父组件打开编辑模态框
      if (data.onTableClick) {
        data.onTableClick(data.id, data);
      }
    }
  };

  return (
    <div
      className={`table-node ${selected ? 'selected' : ''} ${isHovered ? 'hovered' : ''}`}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onMouseDown={handleMouseDown}
      onClick={handleTableClick}
      style={{ pointerEvents: 'all', cursor: 'move', touchAction: 'none' }}
      draggable={false}
    >
      <div
        className="node-header dragHandle"
        onMouseDown={handleDragHandleMouseDown}
        style={{ cursor: 'grab', userSelect: 'none', touchAction: 'none', pointerEvents: 'all' }}
        draggable={false}
        data-drag-handle="true"
      >
        <div className="node-title">
          <TableOutlined className="node-icon" />
          <Text ellipsis title={data.label}>
            {data.label}
          </Text>

          {/* 删除按钮 */}
          <Tooltip title="从画布中移除表">
            <Button
              type="text"
              size="small"
              danger
              icon={<CloseCircleOutlined />}
              className="table-remove-btn"
              onClick={(e) => {
                e.stopPropagation();
                // 打印详细信息以便调试
                console.log('Delete button clicked for table:', id);
                console.log('Table data:', data);
                console.log('Table ID:', data.id, 'Type:', typeof data.id);

                // 确保我们有正确的 nodeId，保持原始格式
                const nodeId = id;
                console.log('Using nodeId for removal:', nodeId);

                // 从节点ID中提取表ID，确保格式一致
                const tableIdFromNodeId = id.startsWith('table-') ? id.replace('table-', '') : id;
                const tableId = data.id || tableIdFromNodeId;
                console.log('Extracted tableId for removal:', tableId);

                // 收集所有可能的识别符
                const allPossibleIds = [
                  nodeId,
                  tableId,
                  data.id,
                  tableIdFromNodeId,
                  `table-${tableId}`,
                  data.label
                ].filter(Boolean); // 过滤掉空值

                console.log('All possible identifiers:', allPossibleIds);

                const removeEvent = new CustomEvent('table-remove', {
                  detail: {
                    nodeId: nodeId,
                    tableId: tableId,
                    tableName: data.label,
                    nodeData: data,
                    // 传递更多的识别信息
                    identifiers: {
                      id: nodeId,
                      nodeId: nodeId,
                      tableId: tableId,
                      tableName: data.label,
                      dataId: data.id,
                      rawId: id,
                      allIds: allPossibleIds
                    }
                  }
                });
                window.dispatchEvent(removeEvent);

                // 直接调用删除函数（如果存在）
                if (typeof data.onRemove === 'function') {
                  console.log('Directly calling onRemove function with tableId:', tableId);
                  data.onRemove(tableId);
                }
              }}
            />
          </Tooltip>
        </div>
        {data.description && (
          <div className="node-description" title={data.description}>
            {data.description}
          </div>
        )}
      </div>

      <div className="node-content">
        <div className="columns-container">
          {data.columns && data.columns.map((column: any) => {
            const columnId = column.id || column.column_name;
            const isHovered = hoveredColumn === columnId;

            return (
              <div
                key={columnId}
                className={`column ${column.is_primary_key ? 'primary-key' : ''} ${
                  column.is_foreign_key ? 'foreign-key' : ''
                } ${isHovered ? 'hovered' : ''}`}
                data-column-id={columnId}
                data-column-name={column.column_name}
                data-is-pk={column.is_primary_key}
                data-is-fk={column.is_foreign_key}
                draggable
                onDragStart={(e) => onDragStart(e, column)}
                onDragEnd={onDragEnd}
                onDragOver={onDragOver}
                onDragLeave={onDragLeave}
                onDrop={(e) => onDrop(e, column)}
                onMouseEnter={() => onColumnMouseEnter(columnId)}
                onMouseLeave={() => onColumnMouseLeave(columnId)}
                onClick={(e) => e.stopPropagation()} // 防止点击列时触发节点点击事件
                style={{ touchAction: 'none', pointerEvents: 'all' }}
              >
                <div className="column-content">
                  <div className="column-name">
                    {column.is_primary_key && (
                      <Tooltip title="主键">
                        <KeyOutlined className="column-icon primary-key-icon" />
                      </Tooltip>
                    )}
                    {column.is_foreign_key && (
                      <Tooltip title="外键">
                        <LinkOutlined className="column-icon foreign-key-icon" />
                      </Tooltip>
                    )}
                    <span className="column-text">{column.column_name}</span>
                  </div>
                  <div className="column-type">
                    <span className="type-badge">{column.data_type}</span>
                  </div>
                </div>

                {/* 连接点 - 使用 MarkerHandle 组件 */}
                <div className="marker-handle-container">
                  <Handle
                    type="source"
                    position={Position.Right}
                    id={`${columnId}_source`}
                    className={`column-handle source-handle ${isHovered ? 'visible' : ''}`}
                    style={{ right: -8, top: '50%' }}
                  />
                  <Handle
                    type="target"
                    position={Position.Left}
                    id={`${columnId}_target`}
                    className={`column-handle target-handle ${isHovered ? 'visible' : ''}`}
                    style={{ left: -8, top: '50%' }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default TableNode;
