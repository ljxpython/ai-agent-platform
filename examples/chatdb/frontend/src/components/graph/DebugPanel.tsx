import React, { useState } from 'react';
import { Card, Typography, Collapse, Button, Switch, List, Badge } from 'antd';
import { BugOutlined, ReloadOutlined, EyeOutlined, EyeInvisibleOutlined } from '@ant-design/icons';

const { Text, Title } = Typography;
const { Panel } = Collapse;

interface DebugPanelProps {
  nodes: any[];
  edges: any[];
  onRefresh: () => void;
}

const DebugPanel = ({ nodes, edges, onRefresh }: DebugPanelProps) => {
  const [showDebug, setShowDebug] = useState(false);
  const [showNodesDetail, setShowNodesDetail] = useState(false);
  const [showEdgesDetail, setShowEdgesDetail] = useState(false);

  // 获取节点类型统计
  const tableNodes = nodes.filter(node => node.type === 'table');
  const columnNodes = nodes.filter(node => node.type === 'column');

  // 获取边类型统计
  const tableRelations = edges.filter(edge =>
    !edge.source.includes('column-') && !edge.target.includes('column-')
  );
  const columnRelations = edges.filter(edge =>
    edge.source.includes('column-') || edge.target.includes('column-')
  );

  return (
    <div
      style={{
        position: 'absolute',
        bottom: 10,
        right: 10,
        zIndex: 999,
        maxWidth: showDebug ? '400px' : 'auto'
      }}
    >
      {!showDebug ? (
        <Button
          type="primary"
          icon={<BugOutlined />}
          onClick={() => setShowDebug(true)}
          style={{ opacity: 0.8 }}
        >
          调试面板
        </Button>
      ) : (
        <Card
          title={
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span><BugOutlined /> 调试面板</span>
              <Button
                size="small"
                type="text"
                onClick={() => setShowDebug(false)}
                icon={<EyeInvisibleOutlined />}
              />
            </div>
          }
          size="small"
          style={{ boxShadow: '0 2px 8px rgba(0, 0, 0, 0.15)', maxHeight: '500px', overflowY: 'auto' }}
        >
          <div style={{ marginBottom: '10px' }}>
            <Button
              type="primary"
              icon={<ReloadOutlined />}
              size="small"
              onClick={onRefresh}
              style={{ marginRight: '8px' }}
            >
              刷新图数据
            </Button>
          </div>

          <div style={{ margin: '10px 0' }}>
            <Title level={5}>图数据统计</Title>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px' }}>
              <Badge count={nodes.length} overflowCount={9999}>
                <Card size="small" title="总节点数">
                  <div style={{ textAlign: 'center' }}>
                    <Text strong>{nodes.length}</Text>
                  </div>
                </Card>
              </Badge>

              <Badge count={edges.length} overflowCount={9999}>
                <Card size="small" title="总边数">
                  <div style={{ textAlign: 'center' }}>
                    <Text strong>{edges.length}</Text>
                  </div>
                </Card>
              </Badge>
            </div>

            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', marginTop: '10px' }}>
              <Card size="small" title="表节点">
                <div style={{ textAlign: 'center' }}>
                  <Text type={tableNodes.length > 0 ? "success" : "danger"} strong>
                    {tableNodes.length}
                  </Text>
                </div>
              </Card>

              <Card size="small" title="列节点">
                <div style={{ textAlign: 'center' }}>
                  <Text type={columnNodes.length > 0 ? "success" : "danger"} strong>
                    {columnNodes.length}
                  </Text>
                </div>
              </Card>

              <Card size="small" title="表关系">
                <div style={{ textAlign: 'center' }}>
                  <Text type={tableRelations.length > 0 ? "success" : "danger"} strong>
                    {tableRelations.length}
                  </Text>
                </div>
              </Card>

              <Card size="small" title="列关系">
                <div style={{ textAlign: 'center' }}>
                  <Text type={columnRelations.length > 0 ? "success" : "danger"} strong>
                    {columnRelations.length}
                  </Text>
                </div>
              </Card>
            </div>
          </div>

          <Collapse ghost>
            <Panel header="节点详情" key="1">
              <div style={{ marginBottom: '8px' }}>
                <Switch
                  checkedChildren="隐藏详情"
                  unCheckedChildren="显示详情"
                  checked={showNodesDetail}
                  onChange={setShowNodesDetail}
                  size="small"
                />
              </div>

              {showNodesDetail ? (
                <List
                  size="small"
                  bordered
                  dataSource={nodes.slice(0, 5)}
                  renderItem={(node) => (
                    <List.Item>
                      <div>
                        <Text strong>ID: {node.id}</Text>
                        <br />
                        <Text>类型: {node.type}</Text>
                        <br />
                        <Text>位置: ({node.position?.x || 'N/A'}, {node.position?.y || 'N/A'})</Text>
                        <br />
                        <Text>标签: {node.data?.label || 'N/A'}</Text>
                      </div>
                    </List.Item>
                  )}
                />
              ) : (
                <Text type="secondary">切换开关查看节点详情</Text>
              )}

              {nodes.length > 5 && showNodesDetail && (
                <Text type="secondary">显示前5个节点 (共{nodes.length}个)</Text>
              )}
            </Panel>

            <Panel header="边详情" key="2">
              <div style={{ marginBottom: '8px' }}>
                <Switch
                  checkedChildren="隐藏详情"
                  unCheckedChildren="显示详情"
                  checked={showEdgesDetail}
                  onChange={setShowEdgesDetail}
                  size="small"
                />
              </div>

              {showEdgesDetail ? (
                <List
                  size="small"
                  bordered
                  dataSource={edges.slice(0, 5)}
                  renderItem={(edge) => (
                    <List.Item>
                      <div>
                        <Text strong>ID: {edge.id}</Text>
                        <br />
                        <Text>类型: {edge.type}</Text>
                        <br />
                        <Text>从: {edge.source} 到: {edge.target}</Text>
                      </div>
                    </List.Item>
                  )}
                />
              ) : (
                <Text type="secondary">切换开关查看边详情</Text>
              )}

              {edges.length > 5 && showEdgesDetail && (
                <Text type="secondary">显示前5个边 (共{edges.length}个)</Text>
              )}
            </Panel>

            <Panel header="渲染问题排查" key="3">
              <List
                size="small"
                bordered
                dataSource={[
                  { id: 1, check: "节点位置定义", status: nodes.every(n => n.position && typeof n.position.x === 'number'), message: nodes.every(n => n.position && typeof n.position.x === 'number') ? "正常" : "异常" },
                  { id: 2, check: "节点样式", status: nodes.every(n => n.style && n.style.opacity == 1), message: nodes.every(n => n.style && n.style.opacity == 1) ? "正常" : "异常" },
                  { id: 3, check: "边连接性", status: edges.every(e => e.source && e.target), message: edges.every(e => e.source && e.target) ? "正常" : "异常" },
                  { id: 4, check: "节点选择性", status: nodes.every(n => n.selectable !== false), message: nodes.every(n => n.selectable !== false) ? "正常" : "异常" },
                  { id: 5, check: "节点类型", status: nodes.every(n => n.type === 'table' || n.type === 'column'), message: nodes.every(n => n.type === 'table' || n.type === 'column') ? "正常" : "异常" }
                ]}
                renderItem={(item) => (
                  <List.Item>
                    <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%' }}>
                      <Text>{item.check}</Text>
                      <Text type={item.status ? "success" : "danger"}>{item.message}</Text>
                    </div>
                  </List.Item>
                )}
              />
            </Panel>
          </Collapse>
        </Card>
      )}
    </div>
  );
};

export default DebugPanel;
