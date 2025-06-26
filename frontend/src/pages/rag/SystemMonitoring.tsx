import React, { useState, useEffect } from 'react';
import {
  Card,
  Row,
  Col,
  Statistic,
  Progress,
  Table,
  Tag,
  Space,
  Button,
  Typography,
  Alert,
  Tabs,
  List,
  Timeline,
  Select,
  DatePicker,
  Tooltip,
} from 'antd';
import {
  BarChartOutlined,
  ClockCircleOutlined,
  DatabaseOutlined,
  ThunderboltOutlined,
  WarningOutlined,
  CheckCircleOutlined,
  ReloadOutlined,
  DownloadOutlined,
  LineChartOutlined,
  PieChartOutlined,
  HeartOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons';
import PageLayout from '@/components/PageLayout';

const { Title, Text, Paragraph } = Typography;
const { TabPane } = Tabs;
const { RangePicker } = DatePicker;
const { Option } = Select;

interface SystemMetrics {
  cpu_usage: number;
  memory_usage: number;
  disk_usage: number;
  network_io: number;
  query_rate: number;
  avg_response_time: number;
  error_rate: number;
  uptime: string;
}

interface QueryLog {
  id: string;
  query: string;
  collection_name: string;
  response_time: number;
  status: 'success' | 'error';
  timestamp: string;
  user_id?: string;
  retrieved_count: number;
}

interface PerformanceAlert {
  id: string;
  type: 'warning' | 'error' | 'info';
  title: string;
  description: string;
  timestamp: string;
  resolved: boolean;
}

const SystemMonitoring: React.FC = () => {
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null);
  const [queryLogs, setQueryLogs] = useState<QueryLog[]>([]);
  const [alerts, setAlerts] = useState<PerformanceAlert[]>([]);
  const [loading, setLoading] = useState(false);
  const [timeRange, setTimeRange] = useState<string>('24h');

  useEffect(() => {
    loadSystemMetrics();
    loadQueryLogs();
    loadAlerts();

    // 设置定时刷新
    const interval = setInterval(() => {
      loadSystemMetrics();
    }, 30000); // 30秒刷新一次

    return () => clearInterval(interval);
  }, [timeRange]);

  const loadSystemMetrics = async () => {
    try {
      const response = await fetch(`/api/v1/rag/monitoring/metrics?range=${timeRange}`);
      if (response.ok) {
        const data = await response.json();
        setMetrics(data.metrics);
      }
    } catch (error) {
      console.error('加载系统指标失败:', error);
    }
  };

  const loadQueryLogs = async () => {
    setLoading(true);
    try {
      const response = await fetch(`/api/v1/rag/monitoring/query-logs?range=${timeRange}&limit=100`);
      if (response.ok) {
        const data = await response.json();
        setQueryLogs(data.logs || []);
      }
    } catch (error) {
      console.error('加载查询日志失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadAlerts = async () => {
    try {
      const response = await fetch('/api/v1/rag/monitoring/alerts');
      if (response.ok) {
        const data = await response.json();
        setAlerts(data.alerts || []);
      }
    } catch (error) {
      console.error('加载告警信息失败:', error);
    }
  };

  const getProgressColor = (value: number, thresholds = { warning: 70, danger: 90 }) => {
    if (value >= thresholds.danger) return '#ff4d4f';
    if (value >= thresholds.warning) return '#faad14';
    return '#52c41a';
  };

  const getStatusColor = (status: string) => {
    return status === 'success' ? 'green' : 'red';
  };

  const getAlertIcon = (type: string) => {
    switch (type) {
      case 'error': return <WarningOutlined style={{ color: '#ff4d4f' }} />;
      case 'warning': return <WarningOutlined style={{ color: '#faad14' }} />;
      case 'info': return <CheckCircleOutlined style={{ color: '#1890ff' }} />;
      default: return <CheckCircleOutlined />;
    }
  };

  const queryColumns = [
    {
      title: '查询内容',
      dataIndex: 'query',
      key: 'query',
      render: (text: string) => (
        <Tooltip title={text}>
          <Text ellipsis style={{ maxWidth: 200 }}>
            {text}
          </Text>
        </Tooltip>
      ),
    },
    {
      title: 'Collection',
      dataIndex: 'collection_name',
      key: 'collection_name',
      render: (text: string) => <Tag color="blue">{text}</Tag>,
    },
    {
      title: '响应时间',
      dataIndex: 'response_time',
      key: 'response_time',
      render: (time: number) => (
        <Text style={{ color: time > 1000 ? '#ff4d4f' : time > 500 ? '#faad14' : '#52c41a' }}>
          {time}ms
        </Text>
      ),
      sorter: (a: QueryLog, b: QueryLog) => a.response_time - b.response_time,
    },
    {
      title: '检索数量',
      dataIndex: 'retrieved_count',
      key: 'retrieved_count',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => (
        <Tag color={getStatusColor(status)}>
          {status === 'success' ? '成功' : '失败'}
        </Tag>
      ),
    },
    {
      title: '时间',
      dataIndex: 'timestamp',
      key: 'timestamp',
      render: (time: string) => new Date(time).toLocaleString(),
    },
  ];

  return (
    <PageLayout>
      <div style={{ padding: '24px' }}>
        <div style={{ marginBottom: '24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <Title level={2}>
              <BarChartOutlined style={{ marginRight: '8px' }} />
              系统监控
            </Title>
            <Paragraph type="secondary">
              实时监控RAG系统性能、查询日志和系统健康状态
            </Paragraph>
          </div>
          <Space>
            <Select value={timeRange} onChange={setTimeRange} style={{ width: 120 }}>
              <Option value="1h">最近1小时</Option>
              <Option value="24h">最近24小时</Option>
              <Option value="7d">最近7天</Option>
              <Option value="30d">最近30天</Option>
            </Select>
            <Button icon={<ReloadOutlined />} onClick={loadSystemMetrics}>
              刷新
            </Button>
          </Space>
        </div>

        {/* 暖心提醒 */}
        <Alert
          message={
            <span>
              <HeartOutlined style={{ color: '#ff7875', marginRight: '8px' }} />
              暖心提醒
            </span>
          }
          description={
            <div>
              <p style={{ margin: 0, marginBottom: '8px' }}>
                <ExclamationCircleOutlined style={{ color: '#faad14', marginRight: '6px' }} />
                该模块当前正处于开发过程中，暂不对外使用。
              </p>
              <p style={{ margin: 0, color: '#666' }}>
                我们正在努力完善系统监控功能，包括实时性能监控、查询日志分析和智能告警等核心功能。
                预计将在下个版本中正式发布，敬请期待！
              </p>
            </div>
          }
          type="warning"
          showIcon
          style={{
            marginBottom: '24px',
            border: '1px solid #ffe7ba',
            backgroundColor: '#fffbf0'
          }}
          closable
        />

        {/* 系统指标概览 */}
        <Row gutter={[16, 16]} style={{ marginBottom: '24px' }}>
          <Col span={6}>
            <Card>
              <Statistic
                title="CPU使用率"
                value={metrics?.cpu_usage || 0}
                suffix="%"
                valueStyle={{ color: getProgressColor(metrics?.cpu_usage || 0) }}
              />
              <Progress
                percent={metrics?.cpu_usage || 0}
                strokeColor={getProgressColor(metrics?.cpu_usage || 0)}
                showInfo={false}
                size="small"
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="内存使用率"
                value={metrics?.memory_usage || 0}
                suffix="%"
                valueStyle={{ color: getProgressColor(metrics?.memory_usage || 0) }}
              />
              <Progress
                percent={metrics?.memory_usage || 0}
                strokeColor={getProgressColor(metrics?.memory_usage || 0)}
                showInfo={false}
                size="small"
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="查询速率"
                value={metrics?.query_rate || 0}
                suffix="/min"
                prefix={<ThunderboltOutlined />}
                valueStyle={{ color: '#1890ff' }}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="平均响应时间"
                value={metrics?.avg_response_time || 0}
                suffix="ms"
                prefix={<ClockCircleOutlined />}
                valueStyle={{ color: getProgressColor(metrics?.avg_response_time || 0, { warning: 500, danger: 1000 }) }}
              />
            </Card>
          </Col>
        </Row>

        {/* 告警信息 */}
        {alerts.filter(a => !a.resolved).length > 0 && (
          <Alert
            message={`系统告警 (${alerts.filter(a => !a.resolved).length})`}
            description={
              <Space direction="vertical" style={{ width: '100%' }}>
                {alerts.filter(a => !a.resolved).slice(0, 3).map(alert => (
                  <div key={alert.id} style={{ display: 'flex', alignItems: 'center' }}>
                    {getAlertIcon(alert.type)}
                    <Text style={{ marginLeft: 8 }}>{alert.title}</Text>
                    <Text type="secondary" style={{ marginLeft: 'auto', fontSize: '12px' }}>
                      {new Date(alert.timestamp).toLocaleString()}
                    </Text>
                  </div>
                ))}
              </Space>
            }
            type="warning"
            showIcon
            style={{ marginBottom: '24px' }}
            action={
              <Button size="small" type="link">
                查看全部
              </Button>
            }
          />
        )}

        <Tabs defaultActiveKey="performance">
          <TabPane tab="性能监控" key="performance">
            <Row gutter={[16, 16]}>
              <Col span={12}>
                <Card title="系统资源使用" extra={<Button icon={<LineChartOutlined />} type="link">详细图表</Button>}>
                  <Space direction="vertical" style={{ width: '100%' }}>
                    <div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                        <Text>CPU使用率</Text>
                        <Text>{metrics?.cpu_usage || 0}%</Text>
                      </div>
                      <Progress
                        percent={metrics?.cpu_usage || 0}
                        strokeColor={getProgressColor(metrics?.cpu_usage || 0)}
                        showInfo={false}
                      />
                    </div>
                    <div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                        <Text>内存使用率</Text>
                        <Text>{metrics?.memory_usage || 0}%</Text>
                      </div>
                      <Progress
                        percent={metrics?.memory_usage || 0}
                        strokeColor={getProgressColor(metrics?.memory_usage || 0)}
                        showInfo={false}
                      />
                    </div>
                    <div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                        <Text>磁盘使用率</Text>
                        <Text>{metrics?.disk_usage || 0}%</Text>
                      </div>
                      <Progress
                        percent={metrics?.disk_usage || 0}
                        strokeColor={getProgressColor(metrics?.disk_usage || 0)}
                        showInfo={false}
                      />
                    </div>
                  </Space>
                </Card>
              </Col>
              <Col span={12}>
                <Card title="服务状态" extra={<Button icon={<PieChartOutlined />} type="link">状态分布</Button>}>
                  <Space direction="vertical" style={{ width: '100%' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <Text>系统运行时间</Text>
                      <Tag color="green">{metrics?.uptime || '0天'}</Tag>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <Text>错误率</Text>
                      <Text style={{ color: getProgressColor(metrics?.error_rate || 0, { warning: 1, danger: 5 }) }}>
                        {metrics?.error_rate || 0}%
                      </Text>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <Text>网络I/O</Text>
                      <Text>{metrics?.network_io || 0} MB/s</Text>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <Text>活跃连接</Text>
                      <Text>128</Text>
                    </div>
                  </Space>
                </Card>
              </Col>
            </Row>
          </TabPane>

          <TabPane tab="查询日志" key="logs">
            <Card>
              <div style={{ marginBottom: '16px', display: 'flex', justifyContent: 'space-between' }}>
                <Space>
                  <Text>显示最近 {timeRange} 的查询记录</Text>
                  <Tag color="blue">总计: {queryLogs.length}</Tag>
                  <Tag color="green">成功: {queryLogs.filter(log => log.status === 'success').length}</Tag>
                  <Tag color="red">失败: {queryLogs.filter(log => log.status === 'error').length}</Tag>
                </Space>
                <Space>
                  <Button icon={<DownloadOutlined />}>导出日志</Button>
                  <Button icon={<ReloadOutlined />} onClick={loadQueryLogs}>
                    刷新
                  </Button>
                </Space>
              </div>

              <Table
                columns={queryColumns}
                dataSource={queryLogs}
                rowKey="id"
                loading={loading}
                pagination={{
                  pageSize: 20,
                  showSizeChanger: true,
                  showQuickJumper: true,
                  showTotal: (total) => `共 ${total} 条记录`,
                }}
              />
            </Card>
          </TabPane>

          <TabPane tab="告警管理" key="alerts">
            <Card>
              <div style={{ marginBottom: '16px', display: 'flex', justifyContent: 'space-between' }}>
                <Space>
                  <Text>系统告警</Text>
                  <Tag color="orange">未解决: {alerts.filter(a => !a.resolved).length}</Tag>
                  <Tag color="green">已解决: {alerts.filter(a => a.resolved).length}</Tag>
                </Space>
                <Button icon={<ReloadOutlined />} onClick={loadAlerts}>
                  刷新
                </Button>
              </div>

              <Timeline>
                {alerts.map(alert => (
                  <Timeline.Item
                    key={alert.id}
                    dot={getAlertIcon(alert.type)}
                    color={alert.resolved ? 'gray' : alert.type === 'error' ? 'red' : 'orange'}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div>
                        <Text strong style={{ opacity: alert.resolved ? 0.6 : 1 }}>
                          {alert.title}
                        </Text>
                        <br />
                        <Text type="secondary" style={{ fontSize: '12px' }}>
                          {alert.description}
                        </Text>
                        <br />
                        <Text type="secondary" style={{ fontSize: '12px' }}>
                          {new Date(alert.timestamp).toLocaleString()}
                        </Text>
                      </div>
                      {!alert.resolved && (
                        <Button size="small" type="link">
                          标记已解决
                        </Button>
                      )}
                    </div>
                  </Timeline.Item>
                ))}
              </Timeline>
            </Card>
          </TabPane>
        </Tabs>
      </div>
    </PageLayout>
  );
};

export default SystemMonitoring;
