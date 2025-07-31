import React, { useState, useEffect, useRef } from 'react';
import { Select, Button, message, Typography, Space, Spin } from 'antd';
import { DatabaseOutlined, ReloadOutlined } from '@ant-design/icons';
import ReactFlow, {
  ReactFlowProvider,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  MarkerType,
  ReactFlowInstance
} from 'reactflow';
import 'reactflow/dist/style.css';
import * as api from '../services/api';

// 简化类型定义
// interface NodeData {
//   id: number;
//   label: string;
//   nodeType: string;
//   [key: string]: any;
// }

interface GraphData {
  nodes: any[];
  edges: any[];
}

const { Option } = Select;
const { Title, Text } = Typography;

// 内部流程组件
const GraphFlow = () => {
  // 状态管理
  const [connections, setConnections] = useState<any[]>([]);
  const [selectedConnection, setSelectedConnection] = useState<number | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [, setReactFlowInstance] = useState<ReactFlowInstance | null>(null);

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

  // 处理连接选择变化
  const handleConnectionChange = (value: number) => {
    setSelectedConnection(value);
    fetchGraphData(value);
  };

  // 获取图数据
  const fetchGraphData = async (connectionId: number) => {
    setLoading(true);
    try {
      const response = await api.getGraphVisualization(connectionId);
      console.log('收到图数据:', response.data);

      if (!response.data || !response.data.nodes || response.data.nodes.length === 0) {
        message.info('没有找到图数据');
        setNodes([]);
        setEdges([]);
        setLoading(false);
        return;
      }

      // 处理节点和边，确保能显示
      const processedData = processGraphData(response.data);

      // 设置节点和边
      setNodes([...processedData.nodes]);
      setEdges([...processedData.edges]);

      message.success(`已加载图数据: ${processedData.nodes.length} 个节点, ${processedData.edges.length} 个边`);

    } catch (error) {
      console.error('加载图数据失败:', error);
      message.error('加载图数据失败');
      setNodes([]);
      setEdges([]);
    } finally {
      setLoading(false);
    }
  };

  // 最简单的图数据处理器 - 重点确保节点可见
  const processGraphData = (data: GraphData) => {
    // 创建简单的随机位置布局
    const nodes = data.nodes.map((node, index) => {
      // 随机计算位置，确保节点分散
      const x = 100 + (index % 5) * 300 + Math.random() * 50;
      const y = 100 + Math.floor(index / 5) * 200 + Math.random() * 50;

      // 确定节点类型和样式
      const isTableNode = node.type === 'table' || (node.data && node.data.nodeType === 'table');

      return {
        id: node.id || `node-${index}`,
        type: 'default', // 使用默认节点类型
        position: { x, y },
        data: {
          ...node.data,
          label: (node.data && node.data.label) || node.label || `Node ${index + 1}`
        },
        style: {
          background: isTableNode ? '#3498db' : '#e74c3c', // 蓝色或红色
          color: 'white',
          border: '1px solid #000',
          padding: '10px',
          borderRadius: '5px',
          width: 150,
          height: 'auto',
          fontSize: 16,
          fontWeight: 'bold',
          boxShadow: '0 4px 6px rgba(0,0,0,0.3)'
        }
      };
    });

    // 简化边的处理
    const edges = data.edges.map((edge, index) => {
      return {
        id: edge.id || `edge-${index}`,
        source: edge.source,
        target: edge.target,
        type: 'default', // 使用默认边类型
        animated: true,
        style: {
          stroke: '#555',
          strokeWidth: 2
        },
        markerEnd: {
          type: MarkerType.ArrowClosed
        }
      };
    });

    return { nodes, edges };
  };

  // 刷新图数据
  const refreshGraph = () => {
    if (selectedConnection) {
      fetchGraphData(selectedConnection);
    }
  };

  // 发现并同步到 Neo4j
  const discoverAndSync = async () => {
    if (!selectedConnection) return;

    setLoading(true);
    try {
      const response = await api.discoverAndSyncSchema(selectedConnection);
      console.log('Discover and sync response:', response.data);

      if (response.data.status === 'success') {
        message.success(response.data.message);
        // 同步成功后刷新图数据
        fetchGraphData(selectedConnection);
      } else {
        message.warning(response.data.message);
      }
    } catch (error) {
      console.error('Error discovering and syncing schema:', error);
      message.error('发现并同步架构失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="graph-visualization-page" style={{ display: 'flex', flexDirection: 'column', minHeight: '100%' }}>
      <Title level={4} style={{ marginBottom: '16px' }}>图数据可视化</Title>

      {/* 顶部控制区 */}
      <div style={{ marginBottom: '16px', display: 'flex', justifyContent: 'space-between' }}>
        <Space>
          <Select
            placeholder="选择数据库连接"
            style={{ width: 240 }}
            onChange={handleConnectionChange}
            loading={loading}
          >
            {connections.map(conn => (
              <Option key={conn.id} value={conn.id}>{conn.name}</Option>
            ))}
          </Select>

          <Button
            icon={<ReloadOutlined />}
            onClick={refreshGraph}
            disabled={!selectedConnection}
          >
            刷新
          </Button>

          <Button
            type="primary"
            onClick={discoverAndSync}
            disabled={!selectedConnection}
            loading={loading}
          >
            发现并同步
          </Button>
        </Space>
      </div>

      {/* 调试信息 */}
      {nodes.length > 0 && (
        <div style={{ marginBottom: '16px', padding: '8px', background: '#f0f0f0' }}>
          <Text>已加载: {nodes.length} 个节点, {edges.length} 条边</Text>
        </div>
      )}

      {/* 图可视化区域 */}
      <div
        className="react-flow-wrapper"
        style={{
          flex: 1,
          border: '2px solid #ddd',
          borderRadius: '4px',
          minHeight: '500px', // 使用最小高度而不是固定高度
          width: '100%'
        }}
        ref={reactFlowWrapper}
      >
        {loading ? (
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
            <Spin size="large" tip="加载图数据中..." />
          </div>
        ) : nodes.length > 0 ? (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            defaultViewport={{ x: 0, y: 0, zoom: 0.7 }}
            minZoom={0.1}
            maxZoom={2}
            onInit={setReactFlowInstance}
            fitView
            attributionPosition="bottom-right"
            style={{ background: '#f5f5f5' }}
          >
            <Controls />
            <Background color="#aaa" gap={16} />
          </ReactFlow>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
            <DatabaseOutlined style={{ fontSize: '48px', color: '#bfbfbf', marginBottom: '16px' }} />
            <Text style={{ color: '#8c8c8c', marginBottom: '24px' }}>
              {selectedConnection ? '没有找到图数据，请尝试同步到Neo4j' : '请选择一个数据库连接'}
            </Text>
            {selectedConnection && (
              <Button
                type="primary"
                onClick={discoverAndSync}
                loading={loading}
              >
                发现并同步架构
              </Button>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

// 外部包装组件
const GraphVisualizationPage = () => {
  return (
    <ReactFlowProvider>
      <GraphFlow />
    </ReactFlowProvider>
  );
};

export default GraphVisualizationPage;
