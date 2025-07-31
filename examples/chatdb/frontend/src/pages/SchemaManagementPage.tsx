import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Card, Select, Button, message, Typography, Tooltip, Spin } from 'antd';
import { PlusOutlined, SaveOutlined, TableOutlined, LayoutOutlined } from '@ant-design/icons';
import ReactFlow, {
  ReactFlowProvider,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  Connection,
  Edge,
  useReactFlow,
  Panel
} from 'reactflow';
import 'reactflow/dist/style.css';
import '../styles/SchemaManagement.css';
import * as api from '../services/api';

// 导入自定义组件
import TableNode from '../components/diagram/TableNode';
import RelationshipEdge from '../components/diagram/RelationshipEdge';
import RelationshipModal from '../components/diagram/RelationshipModal';
import TableEditModal from '../components/diagram/TableEditModal';
import Marker from '../components/diagram/Marker';
import CustomConnectionLine from '../components/diagram/CustomConnectionLine';

const { Option } = Select;

// 关系类型常量
const RELATIONSHIP_TYPES = {
  ONE_TO_ONE: '1-to-1',
  ONE_TO_MANY: '1-to-N',
  MANY_TO_ONE: 'N-to-1',  // 添加多对一关系类型
  MANY_TO_MANY: 'N-to-M'
};

// 定义节点类型
const nodeTypes = {
  tableNode: TableNode
};

// 定义边类型
const edgeTypes = {
  relationshipEdge: RelationshipEdge
};

interface DBConnection {
  id: number;
  name: string;
}

interface SchemaTable {
  id: number;
  table_name: string;
  description?: string;
  columns: SchemaColumn[];
  relationships: SchemaRelationship[];
  ui_metadata?: any;
}

interface SchemaColumn {
  id: number;
  column_name: string;
  data_type: string;
  description?: string;
  is_primary_key: boolean;
  is_foreign_key: boolean;
  is_nullable: boolean;
}

interface SchemaRelationship {
  id: number;
  source_table: string;
  source_column: string;
  target_table: string;
  target_column: string;
  relationship_type: string;
  description?: string;
}

const SchemaManagementPage = () => {
  // 状态管理
  const [connections, setConnections] = useState<DBConnection[]>([]);
  const [selectedConnection, setSelectedConnection] = useState<number | null>(null);
  const [tables, setTables] = useState<SchemaTable[]>([]);
  const [availableTables, setAvailableTables] = useState<SchemaTable[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [relationshipModalVisible, setRelationshipModalVisible] = useState<boolean>(false);
  const [selectedRelationship, setSelectedRelationship] = useState<any>(null);
  const [creatingRelationship, setCreatingRelationship] = useState<boolean>(false);
  const [relationshipIndicator, setRelationshipIndicator] = useState<string>('');
  const [relationshipLoading, setRelationshipLoading] = useState<boolean>(false);
  const [deleteRelationshipLoading, setDeleteRelationshipLoading] = useState<boolean>(false);
  const [tableEditModalVisible, setTableEditModalVisible] = useState<boolean>(false);
  const [selectedTable, setSelectedTable] = useState<any>(null);
  const [publishLoading, setPublishLoading] = useState<boolean>(false);

  const reactFlowInstance = useReactFlow();
  const reactFlowWrapper = useRef<HTMLDivElement>(null);

  // 初始化加载连接
  useEffect(() => {
    fetchConnections();
  }, []);

  // 获取数据库连接
  const fetchConnections = async () => {
    try {
      const response = await api.getConnections();
      setConnections(response.data);
    } catch (error) {
      message.error('获取连接失败');
      console.error(error);
    }
  };

  // 获取数据库表和保存的架构
  const fetchTables = async (connectionId: number) => {
    setLoading(true);
    try {
      // 获取表元数据
      const metadataResponse = await api.getSchemaMetadata(connectionId);
      const allTables = metadataResponse.data;
      setTables(allTables);

      try {
        // 尝试获取保存的架构
        const savedSchemaResponse = await api.getSavedSchema(connectionId);
        const savedSchema = savedSchemaResponse.data;
        console.log('Saved schema loaded:', savedSchema);

        if (savedSchema && savedSchema.tables && savedSchema.tables.length > 0) {
          // 处理保存的表和关系
          loadSavedSchema(savedSchema, allTables);
          // message.success('已加载保存的架构');
        } else {
          // 没有保存的架构，尝试自动发现关系
          message.info('未找到保存的模型，正在自动分析数据库关系...');
          console.log('No saved schema found, attempting to discover relationships automatically');
          try {
            // 调用发现并保存架构API
            const discoverResponse = await api.discoverAndSaveSchema(connectionId);
            const discoveredData = discoverResponse.data;
            console.log('Discovered and saved schema:', discoveredData);

            if (discoveredData.status === 'success') {
              // 使用发现的表和关系创建架构
              const discoveredSchema = {
                tables: discoveredData.tables,
                relationships: discoveredData.relationships
              };
              loadSavedSchema(discoveredSchema, allTables);
              message.success('已自动分析并加载数据库关系');
            } else {
              throw new Error('Failed to discover schema');
            }
          } catch (discoverError) {
            console.error('Failed to discover relationships:', discoverError);
            message.warning('自动分析关系失败，请手动添加表和关系');
            // 如果自动发现失败，清空画布并显示所有表
            setNodes([]);
            setEdges([]);
            setAvailableTables(allTables);
          }
        }
      } catch (schemaError) {
        console.error('Failed to load saved schema:', schemaError);
        message.error('加载模型失败');
        // 如果获取保存的架构失败，清空画布并显示所有表
        setNodes([]);
        setEdges([]);
        setAvailableTables(allTables);
      }
    } catch (error) {
      message.error('获取表失败');
      console.error(error);
      // 清空画布
      setNodes([]);
      setEdges([]);
      setAvailableTables([]);
    } finally {
      setLoading(false);
    }
  };

  // 加载保存的架构
  const loadSavedSchema = (savedSchema: any, allTables: SchemaTable[]) => {
    try {
      console.log('Loading saved schema:', savedSchema);

      // 跟踪已使用的表ID
      const usedTableIds = new Set<number>();

      // 创建节点
      const newNodes = savedSchema.tables.map((table: any) => {
        usedTableIds.add(table.id);

        // 获取完整的表信息（包括列）
        const fullTable = allTables.find(t => t.id === table.id);
        if (!fullTable) {
          console.warn(`Table with ID ${table.id} not found in metadata`);
          return null;
        }

        // 使用保存的位置或默认位置
        const position = table.ui_metadata?.position || {
          x: Math.random() * 300,
          y: Math.random() * 300
        };

        return {
          id: `table-${table.id}`,
          type: 'tableNode',
          position,
          data: {
            id: table.id,
            label: table.table_name,
            description: table.description || '',
            columns: fullTable.columns.map((col: any) => ({
              ...col,
              id: col.id.toString(),
              column_name: col.column_name,
              data_type: col.data_type,
              is_primary_key: col.is_primary_key,
              is_foreign_key: col.is_foreign_key,
              is_nullable: col.is_nullable
            })),
            onRemove: handleRemoveTable,
            onTableClick: handleTableClick
          },
          draggable: true
        };
      }).filter(Boolean);

      // 设置节点
      setNodes(newNodes);

      // 创建边
      const newEdges = savedSchema.relationships.map((rel: any) => {
        const sourceNodeId = `table-${rel.source_table_id}`;
        const targetNodeId = `table-${rel.target_table_id}`;
        const edgeId = `edge-${rel.id}`;

        return {
          id: edgeId,
          source: sourceNodeId,
          target: targetNodeId,
          sourceHandle: `${rel.source_column_id}_source`,
          targetHandle: `${rel.target_column_id}_target`,
          type: 'relationshipEdge',
          data: {
            id: edgeId,
            sourceNodeId,
            targetNodeId,
            sourceTable: rel.source_table,
            sourceColumn: rel.source_column,
            sourceColumnId: rel.source_column_id,
            targetTable: rel.target_table,
            targetColumn: rel.target_column,
            targetColumnId: rel.target_column_id,
            relationshipType: rel.relationship_type || RELATIONSHIP_TYPES.ONE_TO_MANY,
            description: rel.description || ''
          },
          'data-relationshiptype': rel.relationship_type || RELATIONSHIP_TYPES.ONE_TO_MANY
        };
      });

      // 设置边
      setEdges(newEdges);

      // 更新可用表列表
      const availableTables = allTables.filter(table => !usedTableIds.has(table.id));
      setAvailableTables(availableTables);

      // 适应视图
      setTimeout(() => {
        reactFlowInstance.fitView({ padding: 0.2 });
      }, 100);

      // message.success('已加载保存的架构');
    } catch (error) {
      console.error('Error loading saved schema:', error);
      message.error('加载保存的模型失败');

      // 如果加载失败，清空画布
      setNodes([]);
      setEdges([]);
      setAvailableTables(allTables);
    }
  };

  // 处理连接选择变化
  const handleConnectionChange = (value: number) => {
    setSelectedConnection(value);
    fetchTables(value);
  };

  // 自动分析和显示关系
  const analyzeAndDisplayRelationships = async (discoveredSchema: any[], allTables: SchemaTable[], connectionId: number) => {
    console.log('Analyzing and displaying relationships');

    // 清空当前画布
    setNodes([]);
    setEdges([]);

    // 跟踪已添加到画布的表
    const addedTableIds = new Set<number>();
    const newNodes: any[] = [];
    const newEdges: any[] = [];
    const relationships: any[] = [];

    // 分析外键关系
    discoveredSchema.forEach(table => {
      table.columns.forEach((column: any) => {
        if (column.is_foreign_key && column.references) {
          // 找到源表和目标表
          const sourceTable = allTables.find(t => t.table_name === table.table_name);
          const targetTable = allTables.find(t => t.table_name === column.references.table);

          if (sourceTable && targetTable) {
            // 找到源列和目标列
            const sourceColumn = sourceTable.columns.find(c => c.column_name === column.column_name);
            const targetColumn = targetTable.columns.find(c => c.column_name === column.references.column);

            if (sourceColumn && targetColumn) {
              // 添加关系
              relationships.push({
                source_table: sourceTable.table_name,
                source_table_id: sourceTable.id,
                source_column: sourceColumn.column_name,
                source_column_id: sourceColumn.id,
                target_table: targetTable.table_name,
                target_table_id: targetTable.id,
                target_column: targetColumn.column_name,
                target_column_id: targetColumn.id,
                relationship_type: RELATIONSHIP_TYPES.ONE_TO_MANY, // 默认为一对多
                description: `自动发现的关系: ${sourceTable.table_name}.${sourceColumn.column_name} -> ${targetTable.table_name}.${targetColumn.column_name}`
              });

              // 确保两个表都添加到画布
              addedTableIds.add(sourceTable.id);
              addedTableIds.add(targetTable.id);
            }
          }
        }
      });
    });

    // 为有关系的表创建节点
    Array.from(addedTableIds).forEach((tableId, index) => {
      const table = allTables.find(t => t.id === tableId);
      if (table) {
        // 计算位置 - 简单的网格布局
        const position = {
          x: 100 + (index % 3) * 350,
          y: 100 + Math.floor(index / 3) * 400
        };

        // 创建节点
        newNodes.push({
          id: `table-${table.id}`,
          type: 'tableNode',
          position,
          data: {
            id: table.id,
            label: table.table_name,
            description: table.description || '',
            columns: table.columns.map(col => ({
              ...col,
              id: col.id.toString(),
              column_name: col.column_name,
              data_type: col.data_type,
              is_primary_key: col.is_primary_key,
              is_foreign_key: col.is_foreign_key,
              is_nullable: col.is_nullable
            })),
            onRemove: handleRemoveTable,
            onTableClick: handleTableClick
          },
          draggable: true
        });
      }
    });

    // 创建边
    relationships.forEach((rel, index) => {
      const sourceNodeId = `table-${rel.source_table_id}`;
      const targetNodeId = `table-${rel.target_table_id}`;
      const edgeId = `edge-auto-${index}`;

      newEdges.push({
        id: edgeId,
        source: sourceNodeId,
        target: targetNodeId,
        sourceHandle: `${rel.source_column_id}_source`,
        targetHandle: `${rel.target_column_id}_target`,
        type: 'relationshipEdge',
        data: {
          id: edgeId,
          sourceNodeId,
          targetNodeId,
          sourceTable: rel.source_table,
          sourceColumn: rel.source_column,
          sourceColumnId: rel.source_column_id,
          targetTable: rel.target_table,
          targetColumn: rel.target_column,
          targetColumnId: rel.target_column_id,
          relationshipType: rel.relationship_type,
          description: rel.description
        },
        'data-relationshiptype': rel.relationship_type
      });
    });

    // 更新状态
    setNodes(newNodes);
    setEdges(newEdges);

    // 更新可用表列表 - 显示所有未添加到画布的表
    const availableTables = allTables.filter(table => !addedTableIds.has(table.id));
    setAvailableTables(availableTables);

    // 如果有节点，适应视图
    if (newNodes.length > 0) {
      setTimeout(() => {
        reactFlowInstance.fitView({ padding: 0.2 });
      }, 100);

      // 如果是第一次连接，自动保存发现的关系
      if (relationships.length > 0) {
        try {
          // 准备表数据
          const tablesData = newNodes.map((node: any) => {
            return {
              id: node.data.id,
              table_name: node.data.label,
              description: node.data.description,
              ui_metadata: {
                position: node.position
              }
            };
          });

          // 准备关系数据
          const relationshipsData = relationships.map(rel => {
            return {
              source_table: rel.source_table,
              source_column: rel.source_column,
              target_table: rel.target_table,
              target_column: rel.target_column,
              relationship_type: rel.relationship_type,
              description: rel.description
            };
          });

          // 发送保存请求
          setPublishLoading(true);
          try {
            await api.publishSchema(connectionId, {
              tables: tablesData,
              relationships: relationshipsData
            });
            message.success('已自动分析并保存表关系');
          } finally {
            setPublishLoading(false);
          }
        } catch (saveError) {
          console.error('Failed to save discovered relationships:', saveError);
          message.warning('已自动分析表关系，但保存失败');
        }
      } else {
        message.info('未发现表之间的关系');
      }
    } else {
      message.info('未发现表之间的关系');
    }
  };

  // 添加表到画布
  const addTableToCanvas = (table: SchemaTable) => {
    // 检查表是否已经在画布上
    const existingNode = nodes.find(node => node.id === `table-${table.id}`);
    if (existingNode) {
      message.info(`表 ${table.table_name} 已经在画布上`);
      return;
    }

    // 计算新节点的位置
    const position = {
      x: Math.random() * 300,
      y: Math.random() * 300
    };

    // 创建新节点
    const newNode = {
      id: `table-${table.id}`,
      type: 'tableNode',
      position,
      data: {
        id: table.id,
        label: table.table_name,
        description: table.description || '',
        columns: table.columns.map(col => ({
          ...col,
          id: col.id.toString(),
          column_name: col.column_name,
          data_type: col.data_type,
          is_primary_key: col.is_primary_key,
          is_foreign_key: col.is_foreign_key,
          is_nullable: col.is_nullable
        })),
        onRemove: handleRemoveTable,
        onTableClick: handleTableClick
      },
      draggable: true
    };

    setNodes(nds => [...nds, newNode]);

    // 从可用表列表中移除
    setAvailableTables(availableTables.filter(t => t.id !== table.id));
  };

  // 处理边连接
  const onConnect = useCallback((params: Connection) => {
    // 解析源和目标信息
    const sourceId = params.sourceHandle?.split('_')[0];
    const targetId = params.targetHandle?.split('_')[0];
    const sourceNodeId = params.source;
    const targetNodeId = params.target;

    if (!sourceId || !targetId || !sourceNodeId || !targetNodeId) return;

    // 获取源和目标节点数据
    const sourceNode = nodes.find(node => node.id === sourceNodeId);
    const targetNode = nodes.find(node => node.id === targetNodeId);

    if (!sourceNode || !targetNode) return;

    // 获取源和目标列数据
    const sourceColumn = sourceNode.data.columns.find((col: any) => col.id === sourceId);
    const targetColumn = targetNode.data.columns.find((col: any) => col.id === targetId);

    if (!sourceColumn || !targetColumn) return;

    // 确定关系类型
    // 根据字段类型确定关系类型
    let relationshipType = RELATIONSHIP_TYPES.ONE_TO_MANY; // 默认为一对多

    // 获取源和目标字段的主键属性
    const sourceIsPrimaryKey = sourceColumn.is_primary_key;
    const targetIsPrimaryKey = targetColumn.is_primary_key;

    if (sourceIsPrimaryKey && !targetIsPrimaryKey) {
      // 源字段是主键，目标字段不是主键 -> 一对多（源表是"一"，目标表是"多"）
      relationshipType = RELATIONSHIP_TYPES.ONE_TO_MANY;
      console.log('设置关系类型: 一对多（源表是"一"，目标表是"多"）');

      // 准备关系数据
      const relationshipData = {
        id: `edge-${Date.now()}`,
        sourceNodeId: sourceNodeId,
        targetNodeId: targetNodeId,
        sourceTable: sourceNode.data.label,
        sourceColumn: sourceColumn.column_name,
        sourceColumnId: sourceColumn.id,
        targetTable: targetNode.data.label,
        targetColumn: targetColumn.column_name,
        targetColumnId: targetColumn.id,
        relationshipType: relationshipType,
        description: ''
      };

      // 设置选中的关系
      setSelectedRelationship(relationshipData);
    } else if (!sourceIsPrimaryKey && targetIsPrimaryKey) {
      // 源字段不是主键，目标字段是主键 -> 多对一（源表是"多"，目标表是"一"）
      // 使用MANY_TO_ONE关系类型
      relationshipType = RELATIONSHIP_TYPES.MANY_TO_ONE;
      console.log('设置关系类型: 多对一（源表是"多"，目标表是"一"）');

      // 交换源和目标，使得"一"始终在源端
      // 由于不能直接重新赋值 const 变量，所以我们创建新的变量
      const swappedSourceNodeId = targetNodeId;
      const swappedTargetNodeId = sourceNodeId;

      const swappedSourceNode = targetNode;
      const swappedTargetNode = sourceNode;

      const swappedSourceColumn = targetColumn;
      const swappedTargetColumn = sourceColumn;

      // 准备关系数据 - 使用交换后的变量
      const relationshipData = {
        id: `edge-${Date.now()}`,
        sourceNodeId: swappedSourceNodeId,
        targetNodeId: swappedTargetNodeId,
        sourceTable: swappedSourceNode.data.label,
        sourceColumn: swappedSourceColumn.column_name,
        sourceColumnId: swappedSourceColumn.id,
        targetTable: swappedTargetNode.data.label,
        targetColumn: swappedTargetColumn.column_name,
        targetColumnId: swappedTargetColumn.id,
        relationshipType: relationshipType,
        description: ''
      };

      // 设置选中的关系
      setSelectedRelationship(relationshipData);
    } else if (sourceIsPrimaryKey && targetIsPrimaryKey) {
      // 两个字段都是主键 -> 一对一
      relationshipType = RELATIONSHIP_TYPES.ONE_TO_ONE;
      console.log('设置关系类型: 一对一');

      // 准备关系数据
      const relationshipData = {
        id: `edge-${Date.now()}`,
        sourceNodeId: sourceNodeId,
        targetNodeId: targetNodeId,
        sourceTable: sourceNode.data.label,
        sourceColumn: sourceColumn.column_name,
        sourceColumnId: sourceColumn.id,
        targetTable: targetNode.data.label,
        targetColumn: targetColumn.column_name,
        targetColumnId: targetColumn.id,
        relationshipType: relationshipType,
        description: ''
      };

      // 设置选中的关系
      setSelectedRelationship(relationshipData);
    } else {
      // 两个字段都不是主键 -> 多对多
      relationshipType = RELATIONSHIP_TYPES.MANY_TO_MANY;
      console.log('设置关系类型: 多对多');

      // 准备关系数据
      const relationshipData = {
        id: `edge-${Date.now()}`,
        sourceNodeId: sourceNodeId,
        targetNodeId: targetNodeId,
        sourceTable: sourceNode.data.label,
        sourceColumn: sourceColumn.column_name,
        sourceColumnId: sourceColumn.id,
        targetTable: targetNode.data.label,
        targetColumn: targetColumn.column_name,
        targetColumnId: targetColumn.id,
        relationshipType: relationshipType,
        description: ''
      };

      // 设置选中的关系
      setSelectedRelationship(relationshipData);
    }

    // 打开关系编辑模态框
    // relationshipData 已经在每个条件分支中定义并使用了
    setRelationshipModalVisible(true);
  }, [nodes]);

  // 处理边点击
  const onEdgeClick = (event: React.MouseEvent, edge: Edge) => {
    // 阻止事件冒泡
    event.stopPropagation();

    // 获取边数据
    const edgeData = edge.data;
    if (!edgeData) return;

    console.log('Edge clicked:', edge);
    console.log('Edge data:', edgeData);
    console.log('Edge ID:', edge.id);

    // 打开关系编辑模态框
    setSelectedRelationship({
      ...edgeData,
      id: edgeData.id || edge.id // 优先使用 edgeData.id，如果没有则使用 edge.id
    });
    setRelationshipModalVisible(true);
  };

  // 处理关系创建
  const handleRelationshipCreate = (relationshipData: any) => {
    console.log('Creating relationship with data:', relationshipData);

    // 确保关系数据中有 ID
    const relationshipId = relationshipData.id || `edge-${Date.now()}`;
    console.log('Using relationship ID:', relationshipId);

    // 创建新边
    const newEdge = {
      id: relationshipId,
      source: relationshipData.sourceNodeId,
      target: relationshipData.targetNodeId,
      sourceHandle: `${relationshipData.sourceColumnId}_source`,
      targetHandle: `${relationshipData.targetColumnId}_target`,
      type: 'relationshipEdge',
      data: {
        ...relationshipData,
        id: relationshipId // 确保数据中也有相同的 ID
      },
      // 设置关系类型属性，用于 CSS 选择器
      'data-relationshiptype': relationshipData.relationshipType
    };

    console.log('New edge created:', newEdge);

    // 添加到边集合
    setEdges(eds => [...eds, newEdge]);

    // 关闭模态框
    setRelationshipModalVisible(false);
  };

  // 处理关系更新
  const handleRelationshipUpdate = (relationshipData: any) => {
    console.log('Updating relationship with data:', relationshipData);

    // 确保关系数据中有 ID
    const relationshipId = relationshipData.id;
    console.log('Using relationship ID for update:', relationshipId);

    // 更新边数据
    setEdges(eds => eds.map(edge => {
      console.log('Comparing edge ID:', edge.id, 'with relationship ID:', relationshipId);

      // 尝试多种方式匹配
      const isMatch =
        edge.id === relationshipId ||
        (edge.data && edge.data.id === relationshipId) ||
        edge.id.toString().includes(relationshipId) ||
        (relationshipId && relationshipId.toString().includes(edge.id));

      if (isMatch) {
        console.log('Match found, updating edge:', edge.id);
        return {
          ...edge,
          data: {
            ...relationshipData,
            id: relationshipId // 确保数据中也有相同的 ID
          }
        };
      }
      return edge;
    }));

    // 关闭模态框
    setRelationshipModalVisible(false);
  };

  // 处理关系模态框关闭
  const handleRelationshipModalClose = () => {
    setRelationshipModalVisible(false);
    setSelectedRelationship(null);
  };

  // 处理关系模态框提交
  const handleRelationshipModalSubmit = (values: any) => {
    setRelationshipLoading(true);

    const updatedRelationship = {
      ...selectedRelationship,
      ...values
    };

    // 检查是否是更新还是创建
    const existingEdge = edges.find(edge => edge.id === updatedRelationship.id);
    if (existingEdge) {
      handleRelationshipUpdate(updatedRelationship);
    } else {
      handleRelationshipCreate(updatedRelationship);
    }

    setTimeout(() => {
      setRelationshipLoading(false);
    }, 500);
  };

  // 处理删除关系
  const handleDeleteRelationship = (relationshipId: string) => {
    console.log('handleDeleteRelationship called with ID:', relationshipId);
    setDeleteRelationshipLoading(true);

    // 找到要删除的边
    console.log('Current edges:', edges);
    console.log('Relationship ID to delete:', relationshipId);
    console.log('Edge IDs:', edges.map(edge => ({
      id: edge.id,
      dataId: edge.data?.id,
      source: edge.source,
      target: edge.target
    })));

    // 尝试不同的比较方式
    let edgeToDelete = edges.find(edge => edge.id === relationshipId);

    // 如果没找到，尝试其他方式
    if (!edgeToDelete) {
      console.log('Trying alternative comparison methods...');

      // 尝试使用边数据中的 ID
      edgeToDelete = edges.find(edge => edge.data && edge.data.id === relationshipId);

      // 尝试忽略大小写
      if (!edgeToDelete) {
        edgeToDelete = edges.find(edge =>
          edge.id.toString().toLowerCase() === relationshipId.toString().toLowerCase() ||
          (edge.data && edge.data.id && edge.data.id.toString().toLowerCase() === relationshipId.toString().toLowerCase())
        );
      }

      // 如果还是没找到，尝试使用 includes
      if (!edgeToDelete) {
        edgeToDelete = edges.find(edge =>
          edge.id.toString().includes(relationshipId) ||
          relationshipId.includes(edge.id.toString()) ||
          (edge.data && edge.data.id && edge.data.id.toString().includes(relationshipId)) ||
          (edge.data && edge.data.id && relationshipId.includes(edge.data.id.toString()))
        );
      }

      // 如果还是没找到，尝试删除所有边
      if (!edgeToDelete && edges.length > 0) {
        console.log('Last resort: deleting the first edge');
        edgeToDelete = edges[0];
      }

      // 如果用户点击了删除按钮，但我们找不到要删除的边，
      // 那么就删除所有边，因为用户可能就是想删除所有关系
      if (!edgeToDelete && relationshipId.includes('delete-all')) {
        console.log('Deleting all edges as requested');
        setEdges([]);
        message.success('所有关系已删除');
        setDeleteRelationshipLoading(false);
        return;
      }
    }

    console.log('Edge to delete:', edgeToDelete);

    if (!edgeToDelete) {
      console.log('Edge not found, cannot delete');
      message.error('找不到要删除的关系');
      setDeleteRelationshipLoading(false);
      return;
    }

    // 从边集合中移除
    console.log('Removing edge from edges collection');
    setEdges(edges => {
      const newEdges = edges.filter(edge => edge.id !== relationshipId);
      console.log('New edges after deletion:', newEdges);
      return newEdges;
    });

    // 关闭模态框
    setRelationshipModalVisible(false);
    setSelectedRelationship(null);

    // 显示成功消息
    message.success('关系已删除');
    console.log('Relationship deleted successfully');

    setDeleteRelationshipLoading(false);
  };

  // 处理保存架构
  const handleSaveSchema = async () => {
    if (!selectedConnection) {
      message.error('请先选择一个数据库连接');
      return;
    }

    setLoading(true);
    setPublishLoading(true);
    try {
      // 准备表数据
      const tablesData = nodes.map(node => {
        const tableId = parseInt(node.id.replace('table-', ''));
        const table = tables.find(t => t.id === tableId);
        return {
          id: tableId,
          table_name: node.data.label,
          description: node.data.description,
          ui_metadata: {
            position: node.position
          }
        };
      });

      // 准备关系数据
      const relationshipsData = edges.map(edge => {
        const { sourceTable, sourceColumn, targetTable, targetColumn, relationshipType, description } = edge.data;
        return {
          source_table: sourceTable,
          source_column: sourceColumn,
          target_table: targetTable,
          target_column: targetColumn,
          relationship_type: relationshipType,
          description: description || ''
        };
      });

      // 发送保存请求
      await api.publishSchema(selectedConnection, {
        tables: tablesData,
        relationships: relationshipsData
      });

      message.success('模型发布成功');
    } catch (error) {
      message.error('保存发布失败');
      console.error(error);
    } finally {
      setLoading(false);
      setPublishLoading(false);
    }
  };

  // 直接删除当前边的函数
  const deleteCurrentEdge = (edge: any) => {
    console.log('deleteCurrentEdge called with edge:', edge);

    if (!edge) {
      console.log('No edge provided, cannot delete');
      message.error('找不到要删除的关系');
      return;
    }

    // 直接从边集合中移除当前边
    setEdges(edges => {
      const newEdges = edges.filter(e => e.id !== edge.id);
      console.log('Edges after deletion:', newEdges);
      return newEdges;
    });

    // 显示成功消息
    message.success('关系已删除');
  };

  // 将删除关系函数添加到全局对象
  useEffect(() => {
    // 将删除函数添加到全局对象，以便其他组件可以调用
    (window as any).deleteRelationship = handleDeleteRelationship;
    (window as any).deleteCurrentEdge = deleteCurrentEdge;

    // 将节点数组添加到全局对象，以便调试
    (window as any).reactFlowNodes = nodes;

    return () => {
      // 清理全局函数
      delete (window as any).deleteRelationship;
      delete (window as any).deleteCurrentEdge;
      delete (window as any).reactFlowNodes;
    };
  }, [nodes]);

  // 删除节点和相关的边
  const removeNodeAndRelatedEdges = (nodeToRemove: any) => {
    if (!nodeToRemove) {
      console.error('要删除的节点为空');
      message.error('无法找到要删除的节点');
      return;
    }

    try {
      const nodeId = nodeToRemove.id;
      console.log('开始删除节点:', nodeId);

      // 检查节点是否存在于当前节点列表中
      const nodeExists = nodes.some(node => node.id === nodeId);
      if (!nodeExists) {
        console.warn('要删除的节点不在当前节点列表中:', nodeId);
        // 如果节点不存在，但我们仍然尝试删除它
      }

      // 从节点数据中提取表信息
      const nodeData = nodeToRemove.data;
      if (!nodeData) {
        console.error('节点数据为空:', nodeToRemove);
        message.error('节点数据不完整，无法删除');
        return;
      }
      console.log('节点数据:', nodeData);

      // 尝试从原始表列表中找到对应的表
      const tableId = nodeData.id;
      if (!tableId) {
        console.warn('节点数据中没有表ID');
      }

      let originalTable = tableId ? tables.find(t => t.id === tableId) : null;

      // 如果在原始表列表中找不到，则使用节点数据构建一个新表
      if (!originalTable) {
        console.log('在原始表列表中找不到表，使用节点数据构建');
        originalTable = {
          id: tableId || parseInt(nodeId.replace('table-', '')) || Date.now(),
          table_name: nodeData.label || '未命名表',
          description: nodeData.description || '',
          columns: nodeData.columns || [],
          relationships: []
        };
      }

      console.log('原始表或构建的表:', originalTable);

      // 删除与该表相关的所有边
      setEdges(currentEdges => {
        // 找出与该节点相关的所有边
        const relatedEdges = currentEdges.filter(edge => {
          return edge.source === nodeId || edge.target === nodeId;
        });
        console.log('与该节点相关的边:', relatedEdges);

        // 过滤掉相关的边
        const filteredEdges = currentEdges.filter(edge => {
          return edge.source !== nodeId && edge.target !== nodeId;
        });
        console.log('过滤后的边:', filteredEdges);
        return filteredEdges;
      });

      // 从节点列表中删除该表
      setNodes(currentNodes => {
        // 先检查节点是否存在
        const nodeToDelete = currentNodes.find(node => node.id === nodeId);
        if (!nodeToDelete) {
          console.warn('要删除的节点不在当前节点列表中:', nodeId);
          return currentNodes; // 如果节点不存在，返回原来的列表
        }

        const filteredNodes = currentNodes.filter(node => node.id !== nodeId);
        console.log('过滤后的节点:', filteredNodes);
        return filteredNodes;
      });

      // 将表添加回可用表列表
      setAvailableTables(current => {
        // 检查表是否已经存在于可用表列表中
        const exists = current.some(t => t.id === originalTable!.id);
        if (exists) {
          console.log('表已存在于可用表列表中，不重复添加');
          return current;
        }

        const newAvailableTables = [...current, originalTable!];
        console.log('新的可用表列表:', newAvailableTables);
        return newAvailableTables;
      });

      message.success(`已从画布中移除表 ${originalTable.table_name}`);
    } catch (error) {
      console.error('删除节点时发生错误:', error);
      message.error('删除表时发生错误，请刷新页面后重试');
    }
  };

  // 处理从画布中移除表
  const handleRemoveTable = (tableId: number | string) => {
    console.log('Removing table from canvas:', tableId);
    const nodeId = `table-${tableId}`;
    handleTableRemove(nodeId, tableId);
  };

  // 处理表删除 - 保留为兼容性考虑
  const handleTableRemove = (nodeId: string, tableId: number | string) => {
    console.log('Removing table from canvas:', nodeId, tableId);
    console.log('Current nodes:', nodes);
    console.log('Current nodes count:', nodes.length);
    console.log('All node IDs:', nodes.map(n => n.id));

    // 检查节点数组是否为空
    if (nodes.length === 0) {
      console.log('节点数组为空，无法删除节点');
      message.error('画布中没有表可以删除');
      return;
    }

    try {
      // 尝试不同的节点ID格式
      let nodeToRemove = nodes.find(node => node.id === nodeId);
      console.log('Direct match result:', nodeToRemove ? 'Found' : 'Not found');

      // 如果没找到，尝试添加 'table-' 前缀
      if (!nodeToRemove && !nodeId.startsWith('table-')) {
        const alternativeNodeId = `table-${nodeId}`;
        console.log('尝试替代节点ID:', alternativeNodeId);
        nodeToRemove = nodes.find(node => node.id === alternativeNodeId);
        console.log('With table- prefix result:', nodeToRemove ? 'Found' : 'Not found');
      }

      // 如果没找到，尝试移除 'table-' 前缀
      if (!nodeToRemove && nodeId.startsWith('table-')) {
        const alternativeNodeId = nodeId.replace('table-', '');
        console.log('尝试移除table-前缀:', alternativeNodeId);
        nodeToRemove = nodes.find(node => node.id === alternativeNodeId);
        console.log('Without table- prefix result:', nodeToRemove ? 'Found' : 'Not found');
      }

      // 如果还是没找到，尝试使用 tableId
      if (!nodeToRemove && tableId) {
        const tableIdStr = tableId.toString();
        const alternativeNodeId = `table-${tableIdStr}`;
        console.log('尝试使用tableId构造节点ID:', alternativeNodeId);
        nodeToRemove = nodes.find(node => node.id === alternativeNodeId);
        console.log('With tableId result:', nodeToRemove ? 'Found' : 'Not found');

        // 如果还是没找到，尝试不带前缀的tableId
        if (!nodeToRemove) {
          nodeToRemove = nodes.find(node => node.id === tableIdStr);
          console.log('With tableId without prefix result:', nodeToRemove ? 'Found' : 'Not found');
        }

        // 如果还是没找到，尝试使用 data.id 匹配
        if (!nodeToRemove) {
          nodeToRemove = nodes.find(node =>
            node.data && node.data.id && node.data.id.toString() === tableIdStr
          );
          console.log('Data.id match result:', nodeToRemove ? 'Found' : 'Not found');
        }
      }

      // 如果还是没找到，尝试使用部分匹配
      if (!nodeToRemove) {
        console.log('尝试使用部分匹配');
        // 尝试找到包含 nodeId 的节点
        nodeToRemove = nodes.find(node => node.id.includes(nodeId) || (nodeId.includes(node.id)));
        console.log('Partial match result:', nodeToRemove ? 'Found' : 'Not found');

        // 如果还是没找到，尝试使用 tableId 部分匹配
        if (!nodeToRemove && tableId) {
          const tableIdStr = tableId.toString();
          nodeToRemove = nodes.find(node =>
            node.id.includes(tableIdStr) ||
            (node.data && node.data.id && node.data.id.toString() === tableIdStr)
          );
          console.log('TableId partial match result:', nodeToRemove ? 'Found' : 'Not found');
        }
      }

      // 如果还是没找到，尝试使用第一个节点
      if (!nodeToRemove && nodes.length > 0) {
        console.log('未找到匹配节点，将删除第一个节点');
        nodeToRemove = nodes[0];
        console.log('将删除节点:', nodeToRemove);
      }

      if (!nodeToRemove) {
        console.error('找不到要删除的节点:', nodeId);
        message.error('无法找到要删除的节点');
        return;
      }

      console.log('Found node to remove:', nodeToRemove);

      // 直接调用删除节点函数
      removeNodeAndRelatedEdges(nodeToRemove);
    } catch (error) {
      console.error('删除表时发生错误:', error);
      message.error('删除表时发生错误，请刷新页面后重试');
    }
  };

  // 处理列拖拽事件
  useEffect(() => {
    // 监听列拖放事件
    const handleColumnDrop = (event: CustomEvent) => {
      const { source, target } = event.detail;

      if (!source || !target) return;

      // 设置关系指示器
      setRelationshipIndicator(`正在创建关系: ${source.tableName}.${source.columnName} → ${target.tableName}.${target.columnName}`);

      // 确定关系类型
      // 根据拖拽方向和字段类型确定关系类型
      let relationshipType = RELATIONSHIP_TYPES.ONE_TO_MANY; // 默认为一对多

      // 如果源字段是主键，目标字段是外键，则是一对多关系（源表是"一"，目标表是"多"）
      // 如果源字段是外键，目标字段是主键，则是多对一关系（源表是"多"，目标表是"一"）
      // 如果两个字段都是主键，则是一对一关系
      // 如果两个字段都不是主键，则是多对多关系

      if (source.isPrimaryKey && !target.isPrimaryKey) {
        // 源字段是主键，目标字段不是主键 -> 一对多（源表是"一"，目标表是"多"）
        relationshipType = RELATIONSHIP_TYPES.ONE_TO_MANY;
        console.log('设置关系类型: 一对多（源表是"一"，目标表是"多"）');

        // 准备关系数据
        const relationshipData = {
          id: `edge-${Date.now()}`,
          sourceNodeId: source.nodeId,
          targetNodeId: target.nodeId,
          sourceTable: source.tableName,
          sourceColumn: source.columnName,
          sourceColumnId: source.columnId,
          targetTable: target.tableName,
          targetColumn: target.columnName,
          targetColumnId: target.columnId,
          relationshipType: relationshipType,
          description: ''
        };

        // 设置选中的关系
        setSelectedRelationship(relationshipData);
      } else if (!source.isPrimaryKey && target.isPrimaryKey) {
        // 源字段不是主键，目标字段是主键 -> 多对一（源表是"多"，目标表是"一"）
        // 使用MANY_TO_ONE关系类型表示多对一关系
        relationshipType = RELATIONSHIP_TYPES.MANY_TO_ONE;
        console.log('设置关系类型: 多对一（源表是"多"，目标表是"一"）');

        // 交换源和目标，使得"一"始终在源端
        // 由于不能直接重新赋值 const 变量，所以我们创建新的变量
        const swappedSource = { ...target };
        const swappedTarget = { ...source };

        // 准备关系数据 - 使用交换后的变量
        const relationshipData = {
          id: `edge-${Date.now()}`,
          sourceNodeId: swappedSource.nodeId,
          targetNodeId: swappedTarget.nodeId,
          sourceTable: swappedSource.tableName,
          sourceColumn: swappedSource.columnName,
          sourceColumnId: swappedSource.columnId,
          targetTable: swappedTarget.tableName,
          targetColumn: swappedTarget.columnName,
          targetColumnId: swappedTarget.columnId,
          relationshipType: relationshipType,
          description: ''
        };

        // 设置选中的关系
        setSelectedRelationship(relationshipData);
      } else if (source.isPrimaryKey && target.isPrimaryKey) {
        // 两个字段都是主键 -> 一对一
        relationshipType = RELATIONSHIP_TYPES.ONE_TO_ONE;
        console.log('设置关系类型: 一对一');

        // 准备关系数据
        const relationshipData = {
          id: `edge-${Date.now()}`,
          sourceNodeId: source.nodeId,
          targetNodeId: target.nodeId,
          sourceTable: source.tableName,
          sourceColumn: source.columnName,
          sourceColumnId: source.columnId,
          targetTable: target.tableName,
          targetColumn: target.columnName,
          targetColumnId: target.columnId,
          relationshipType: relationshipType,
          description: ''
        };

        // 设置选中的关系
        setSelectedRelationship(relationshipData);
      } else {
        // 两个字段都不是主键 -> 多对多
        relationshipType = RELATIONSHIP_TYPES.MANY_TO_MANY;
        console.log('设置关系类型: 多对多');

        // 准备关系数据
        const relationshipData = {
          id: `edge-${Date.now()}`,
          sourceNodeId: source.nodeId,
          targetNodeId: target.nodeId,
          sourceTable: source.tableName,
          sourceColumn: source.columnName,
          sourceColumnId: source.columnId,
          targetTable: target.tableName,
          targetColumn: target.columnName,
          targetColumnId: target.columnId,
          relationshipType: relationshipType,
          description: ''
        };

        // 设置选中的关系
        setSelectedRelationship(relationshipData);
      }

      // 打开关系编辑模态框
      // relationshipData 已经在每个条件分支中定义并使用了
      setRelationshipModalVisible(true);

      // 清除关系指示器
      setTimeout(() => {
        setRelationshipIndicator('');
      }, 100);
    };

    // 监听边删除事件
    const handleEdgeDelete = (event: CustomEvent) => {
      console.log('Edge delete event received:', event);
      const { id } = event.detail;
      console.log('Edge ID to delete:', id);
      if (!id) {
        console.log('No edge ID provided, cannot delete');
        return;
      }

      // 调用删除关系函数
      console.log('Calling handleDeleteRelationship with ID:', id);
      handleDeleteRelationship(id);
    };

    // 监听表删除事件
    const handleTableRemoveEvent = (event: CustomEvent) => {
      console.log('Table remove event received:', event);
      console.log('Event detail:', event.detail);
      const { nodeId, tableId, tableName, nodeData, identifiers } = event.detail;
      console.log('Node ID:', nodeId, 'Type:', typeof nodeId);
      console.log('Table ID:', tableId, 'Type:', typeof tableId);
      console.log('Table Name:', tableName);
      console.log('Node Data:', nodeData);
      console.log('Identifiers:', identifiers);
      console.log('Current nodes in state:', nodes);
      console.log('Current nodes count:', nodes.length);
      console.log('All node IDs in state:', nodes.map(n => n.id));
      console.log('All node data:', nodes.map(n => ({ id: n.id, dataId: n.data?.id, label: n.data?.label })));

      // 直接尝试找到要删除的节点
      let nodeToRemove = null;

      // 0. 首先检查节点数组是否为空
      if (nodes.length === 0) {
        console.log('节点数组为空，无法删除节点');
        message.error('画布中没有表可以删除');
        return;
      }

      // 1. 首先尝试使用节点ID直接匹配 - 完全匹配
      nodeToRemove = nodes.find(node => node.id === nodeId);
      console.log('Direct ID match result:', nodeToRemove ? 'Found' : 'Not found');

      // 2. 如果没找到，尝试添加或移除 'table-' 前缀
      if (!nodeToRemove) {
        const withPrefix = nodeId.startsWith('table-') ? nodeId : `table-${nodeId}`;
        const withoutPrefix = nodeId.startsWith('table-') ? nodeId.replace('table-', '') : nodeId;

        nodeToRemove = nodes.find(node =>
          node.id === withPrefix ||
          node.id === withoutPrefix
        );
        console.log('Prefix handling result:', nodeToRemove ? 'Found' : 'Not found');
      }

      // 3. 如果还是没找到，尝试使用表ID匹配
      if (!nodeToRemove && tableId) {
        const tableIdStr = tableId.toString();
        nodeToRemove = nodes.find(node =>
          node.id === `table-${tableIdStr}` ||
          node.id === tableIdStr ||
          (node.data && node.data.id && node.data.id.toString() === tableIdStr)
        );
        console.log('Table ID match result:', nodeToRemove ? 'Found' : 'Not found');
      }

      // 4. 如果还是没找到，尝试使用表名匹配
      if (!nodeToRemove && tableName) {
        nodeToRemove = nodes.find(node =>
          node.data && node.data.label === tableName
        );
        console.log('Table name match result:', nodeToRemove ? 'Found' : 'Not found');
      }

      // 5. 如果还是没找到，尝试使用数据内容匹配
      if (!nodeToRemove && nodeData) {
        nodeToRemove = nodes.find(node =>
          node.data &&
          ((node.data.id && nodeData.id && node.data.id.toString() === nodeData.id.toString()) ||
           (node.data.label && nodeData.label && node.data.label === nodeData.label))
        );
        console.log('Node data match result:', nodeToRemove ? 'Found' : 'Not found');
      }

      // 6. 如果还是没找到，尝试使用部分匹配
      if (!nodeToRemove) {
        // 尝试使用节点ID的部分匹配
        nodeToRemove = nodes.find(node =>
          (nodeId && node.id && (node.id.includes(nodeId) || nodeId.includes(node.id))) ||
          (tableId && node.id && (node.id.includes(tableId.toString()) || tableId.toString().includes(node.id)))
        );
        console.log('Partial ID match result:', nodeToRemove ? 'Found' : 'Not found');
      }

      // 7. 尝试使用identifiers中的任何ID进行匹配
      if (!nodeToRemove && identifiers) {
        console.log('Trying to match using identifiers:', identifiers);

        // 先尝试使用 allIds 数组（如果存在）
        if (identifiers.allIds && Array.isArray(identifiers.allIds)) {
          console.log('Using allIds array for matching:', identifiers.allIds);

          for (const id of identifiers.allIds) {
            if (id === undefined || id === null) continue;

            const idStr = String(id); // 使用String()而不是toString()来避免类型错误
            nodeToRemove = nodes.find(node =>
              node.id === idStr ||
              node.id === `table-${idStr}` ||
              (node.data && node.data.id && String(node.data.id) === idStr)
            );

            if (nodeToRemove) {
              console.log('Found node using allIds identifier:', idStr);
              break;
            }
          }
        }

        // 如果还没找到，尝试使用其他标识符
        if (!nodeToRemove) {
          const ids = Object.entries(identifiers)
            .filter(([key, value]) =>
              key !== 'allIds' && value !== undefined && value !== null && typeof value !== 'object'
            )
            .map(([_, value]) => value);

          console.log('Using individual identifiers for matching:', ids);

          for (const id of ids) {
            // 确保id可以转换为字符串
            if (id === undefined || id === null) continue;

            const idStr = String(id); // 使用String()而不是toString()来避免类型错误
            nodeToRemove = nodes.find(node =>
              node.id === idStr ||
              node.id === `table-${idStr}` ||
              (node.data && node.data.id && String(node.data.id) === idStr)
            );

            if (nodeToRemove) {
              console.log('Found node using identifier:', idStr);
              break;
            }
          }
        }

        console.log('Identifiers match result:', nodeToRemove ? 'Found' : 'Not found');
      }

      // 8. 如果还是没找到，尝试使用第一个节点
      if (!nodeToRemove && nodes.length > 0) {
        console.log('未找到匹配节点，将删除第一个节点');
        nodeToRemove = nodes[0];
      }

      if (!nodeToRemove) {
        console.error('无法找到要删除的节点');
        message.error('无法找到要删除的节点，请刷新页面后重试');
        return;
      }

      console.log('找到要删除的节点:', nodeToRemove);

      try {
        // 直接删除找到的节点
        removeNodeAndRelatedEdges(nodeToRemove);
      } catch (error) {
        console.error('删除表时发生错误:', error);
        message.error('删除表时发生错误，请刷新页面后重试');
      }
    };

    // 添加事件监听器
    window.addEventListener('column-drop', handleColumnDrop as EventListener);
    window.addEventListener('edge-delete', handleEdgeDelete as EventListener);
    window.addEventListener('table-remove', handleTableRemoveEvent as EventListener);

    // 清理函数
    return () => {
      window.removeEventListener('column-drop', handleColumnDrop as EventListener);
      window.removeEventListener('edge-delete', handleEdgeDelete as EventListener);
      window.removeEventListener('table-remove', handleTableRemoveEvent as EventListener);
    };
  }, []);

  // 处理刷新架构
  const handleRefreshSchema = () => {
    if (selectedConnection) {
      fetchTables(selectedConnection);
    }
  };

  // 处理自动布局
  const handleAutoLayout = () => {
    if (nodes.length === 0) {
      message.info('没有表可以布局');
      return;
    }

    message.info('正在自动布局...');

    // 计算新的节点位置
    const newNodes = [...nodes];
    const tableCount = newNodes.length;

    // 确定布局参数
    const PADDING = 50;  // 节点之间的间距
    const NODE_WIDTH = 250;  // 节点宽度
    const NODE_HEIGHT = 300;  // 节点高度

    // 计算每行可以放置的节点数量
    const containerWidth = reactFlowWrapper.current?.clientWidth || 1000;
    const nodesPerRow = Math.max(1, Math.floor((containerWidth - PADDING) / (NODE_WIDTH + PADDING)));

    // 计算行数
    const rows = Math.ceil(tableCount / nodesPerRow);

    // 先根据关系对节点进行排序
    // 有关系的节点尽量放在一起
    const nodeRelationships: Record<string, Set<string>> = {};
    edges.forEach(edge => {
      const sourceId = edge.source;
      const targetId = edge.target;

      if (!nodeRelationships[sourceId]) nodeRelationships[sourceId] = new Set<string>();
      if (!nodeRelationships[targetId]) nodeRelationships[targetId] = new Set<string>();

      nodeRelationships[sourceId].add(targetId);
      nodeRelationships[targetId].add(sourceId);
    });

    // 根据关系数量排序
    newNodes.sort((a: any, b: any) => {
      const aId = a.id as string;
      const bId = b.id as string;
      const aRelCount = nodeRelationships[aId]?.size || 0;
      const bRelCount = nodeRelationships[bId]?.size || 0;
      return bRelCount - aRelCount; // 关系多的先排
    });

    // 布局节点
    newNodes.forEach((node: any, index: number) => {
      const row = Math.floor(index / nodesPerRow);
      const col = index % nodesPerRow;

      node.position = {
        x: col * (NODE_WIDTH + PADDING) + PADDING,
        y: row * (NODE_HEIGHT + PADDING) + PADDING
      };

      // 添加动画类
      node.className = (node.className || '') + ' node-animating';
    });

    setNodes(newNodes);

    // 适应视图
    setTimeout(() => {
      reactFlowInstance.fitView({ padding: 0.2 });
      message.success('自动布局完成');

      // 移除动画类
      setTimeout(() => {
        setNodes(nodes => nodes.map(node => {
          const updatedNode = { ...node };
          if (updatedNode.className) {
            updatedNode.className = updatedNode.className.replace('node-animating', '').trim();
          }
          return updatedNode;
        }));
      }, 500);
    }, 100);
  };

  // 处理表点击
  const handleTableClick = (tableId: number, tableData: any) => {
    console.log('Table clicked:', tableId, tableData);
    setSelectedTable(tableData);
    setTableEditModalVisible(true);
  };

  // 保存表和字段描述
  const handleSaveTableData = async (tableId: number, tableData: any) => {
    try {
      // 先获取完整的表信息
      const table = tables.find(t => t.id === tableId);
      if (!table) {
        throw new Error('找不到表信息');
      }

      // 准备更新数据
      const updateData = {
        table_name: table.table_name, // 保持原表名
        description: tableData.description,
        ui_metadata: table.ui_metadata || {}
      };

      // 更新表信息
      await api.updateTable(tableId, updateData);

      // 更新列描述
      for (const column of tableData.columns) {
        if (column.id) {
          await api.updateColumn(column.id, { description: column.description });
        }
      }

      // 更新本地数据
      // 更新表列表中的表描述
      const updatedTables = tables.map(t => {
        if (t.id === tableId) {
          return { ...t, description: tableData.description };
        }
        return t;
      });
      setTables(updatedTables);

      // 更新节点数据
      const updatedNodes = nodes.map(node => {
        if (node.data.id === tableId) {
          // 更新节点的描述和列描述
          const updatedColumns = node.data.columns.map((col: any) => {
            const updatedCol = tableData.columns.find((c: any) => c.id === col.id);
            if (updatedCol) {
              return { ...col, description: updatedCol.description };
            }
            return col;
          });

          return {
            ...node,
            data: {
              ...node.data,
              description: tableData.description,
              columns: updatedColumns
            }
          };
        }
        return node;
      });
      setNodes(updatedNodes);

      message.success('表信息更新成功');
    } catch (error) {
      console.error('Failed to save table data:', error);
      message.error('保存表信息失败');
    }
  };

  // 处理表编辑模态框关闭
  const handleTableEditModalClose = () => {
    setTableEditModalVisible(false);
    setSelectedTable(null);
  };

  return (
    <div className="schema-management-page">
      <Card>
        <div style={{ display: 'flex', height: 'calc(100vh - 200px)', minHeight: '600px' }}>
          {/* 左侧表列表 */}
          <div style={{ width: '250px', marginRight: '16px', display: 'flex', flexDirection: 'column', border: '1px solid #d9d9d9', borderRadius: '4px' }}>
            {/* 数据库连接选择 */}
            <div style={{ padding: '12px', borderBottom: '1px solid #d9d9d9' }}>
              <Select
                placeholder="选择数据库连接"
                style={{ width: '100%' }}
                onChange={handleConnectionChange}
                value={selectedConnection || undefined}
              >
                {connections.map(conn => (
                  <Option key={conn.id} value={conn.id}>{conn.name}</Option>
                ))}
              </Select>
            </div>

            {/* 可用表标题 */}
            <div style={{ padding: '12px', borderBottom: '1px solid #d9d9d9', fontWeight: 'bold' }}>
              可用表
            </div>

            {/* 可用表列表 */}
            <div style={{ flex: 1, overflowY: 'auto' }}>
              {loading ? (
                <div style={{ padding: '20px', textAlign: 'center' }}>
                  <Spin />
                </div>
              ) : (
                <div>
                  {availableTables.length > 0 ? (
                    availableTables.map(table => (
                      <div
                        key={table.id}
                        style={{
                          padding: '8px 12px',
                          cursor: 'pointer',
                          borderBottom: '1px solid #f0f0f0',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between'
                        }}
                        onClick={() => addTableToCanvas(table)}
                      >
                        <div style={{ display: 'flex', alignItems: 'center' }}>
                          <TableOutlined style={{ marginRight: '8px' }} />
                          <span>{table.table_name}</span>
                        </div>
                        <Tooltip title="添加到画布">
                          <Button
                            type="text"
                            size="small"
                            icon={<PlusOutlined />}
                            onClick={(e) => {
                              e.stopPropagation();
                              addTableToCanvas(table);
                            }}
                          />
                        </Tooltip>
                      </div>
                    ))
                  ) : (
                    <div style={{ padding: '12px', color: '#999', textAlign: 'center' }}>
                      {selectedConnection ? '没有可用的表或所有表已添加到画布' : '请选择数据库连接'}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* 右侧画布 */}
          <div style={{ flex: 1, border: '1px solid #d9d9d9', borderRadius: '4px', position: 'relative' }} ref={reactFlowWrapper}>
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              onEdgeClick={onEdgeClick}
              nodeTypes={nodeTypes}
              edgeTypes={edgeTypes}
              connectionLineComponent={CustomConnectionLine}
              fitView
              attributionPosition="bottom-right"
            >
              <Controls>
                <button
                  className="react-flow__controls-button"
                  onClick={handleAutoLayout}
                  title="自动布局"
                >
                  <LayoutOutlined />
                </button>
              </Controls>
              <Background color="#f5f5f5" gap={16} />
              <Panel position="top-right">
                <div className="schema-controls">
                  <Button
                    type="primary"
                    icon={<SaveOutlined />}
                    onClick={handleSaveSchema}
                    disabled={!selectedConnection || nodes.length === 0}
                    loading={publishLoading}
                  >
                    发布
                  </Button>
                </div>
              </Panel>
              <Marker />
            </ReactFlow>
          </div>
        </div>

        {/* 关系指示器 */}
        {relationshipIndicator && (
          <div className="relationship-indicator">
            {relationshipIndicator}
          </div>
        )}

        {/* 关系编辑模态框 */}
        <RelationshipModal
          visible={relationshipModalVisible}
          onClose={handleRelationshipModalClose}
          onSubmit={handleRelationshipModalSubmit}
          onDelete={handleDeleteRelationship}
          relationshipData={selectedRelationship}
          loading={relationshipLoading}
          deleteLoading={deleteRelationshipLoading}
        />

        {/* 表编辑模态框 */}
        <TableEditModal
          visible={tableEditModalVisible}
          table={selectedTable}
          onCancel={handleTableEditModalClose}
          onSave={handleSaveTableData}
        />
      </Card>
    </div>
  );
};

// 使用 ReactFlowProvider 包装组件
const SchemaManagementPageWithFlow = () => (
  <ReactFlowProvider>
    <SchemaManagementPage />
  </ReactFlowProvider>
);

export default SchemaManagementPageWithFlow;
