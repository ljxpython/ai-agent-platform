import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
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
  Avatar,
} from 'antd';
import {
  DatabaseOutlined,
  FileTextOutlined,
  CloudOutlined,
  BarChartOutlined,
  SettingOutlined,
  SearchOutlined,
  RobotOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import PageLayout from '@/components/PageLayout';

const { Title, Text, Paragraph } = Typography;
const { TabPane } = Tabs;

interface RAGStats {
  total_collections: number;
  total_documents: number;
  total_vectors: number;
  storage_used: string;
  query_count_today: number;
  avg_response_time: number;
  system_health: 'healthy' | 'warning' | 'error';
}

interface RecentActivity {
  id: string;
  type: 'upload' | 'query' | 'collection_created' | 'model_updated';
  description: string;
  timestamp: string;
  status: 'success' | 'warning' | 'error';
}

const RAGDashboard: React.FC = () => {
  const navigate = useNavigate();
  const [stats, setStats] = useState<RAGStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [recentActivities, setRecentActivities] = useState<RecentActivity[]>([]);

  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    setLoading(true);
    try {
      // 加载统计数据
      const statsResponse = await fetch('/api/v1/rag/dashboard/stats');
      if (statsResponse.ok) {
        const statsData = await statsResponse.json();
        setStats(statsData.data);
      }

      // 加载最近活动
      const activitiesResponse = await fetch('/api/v1/rag/dashboard/activities');
      if (activitiesResponse.ok) {
        const activitiesData = await activitiesResponse.json();
        setRecentActivities(activitiesData.data || []);
      }
    } catch (error) {
      console.error('加载仪表板数据失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const getHealthColor = (health: string) => {
    switch (health) {
      case 'healthy': return '#52c41a';
      case 'warning': return '#faad14';
      case 'error': return '#ff4d4f';
      default: return '#d9d9d9';
    }
  };

  const getActivityIcon = (type: string) => {
    switch (type) {
      case 'upload': return <FileTextOutlined style={{ color: '#1890ff' }} />;
      case 'query': return <SearchOutlined style={{ color: '#52c41a' }} />;
      case 'collection_created': return <DatabaseOutlined style={{ color: '#722ed1' }} />;
      case 'model_updated': return <RobotOutlined style={{ color: '#fa8c16' }} />;
      default: return <ThunderboltOutlined />;
    }
  };

  const quickActions = [
    {
      title: '上传文档',
      description: '添加新文档到知识库',
      icon: <FileTextOutlined />,
      color: '#1890ff',
      action: () => navigate('/rag/documents'),
    },
    {
      title: '创建Collection',
      description: '创建新的知识库集合',
      icon: <DatabaseOutlined />,
      color: '#52c41a',
      action: () => navigate('/rag/collections'),
    },
    {
      title: '向量管理',
      description: '管理向量数据库',
      icon: <CloudOutlined />,
      color: '#722ed1',
      action: () => navigate('/rag/vectors'),
    },
    {
      title: '系统配置',
      description: '配置RAG系统参数',
      icon: <SettingOutlined />,
      color: '#fa8c16',
      action: () => navigate('/rag/config'),
    },
  ];

  return (
    <PageLayout>
      <div style={{ padding: '24px' }}>
        <div style={{ marginBottom: '24px' }}>
          <Title level={2}>
            <DatabaseOutlined style={{ marginRight: '8px', color: '#1890ff' }} />
            RAG知识库管理中心
          </Title>
          <Paragraph type="secondary">
            统一管理RAG知识库系统，包括文档处理、向量管理、模型配置和系统监控
          </Paragraph>
        </div>

        {/* 系统状态概览 */}
        <Row gutter={[16, 16]} style={{ marginBottom: '24px' }}>
          <Col span={6}>
            <Card>
              <Statistic
                title="知识库集合"
                value={stats?.total_collections || 0}
                prefix={<DatabaseOutlined />}
                valueStyle={{ color: '#1890ff' }}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="文档总数"
                value={stats?.total_documents || 0}
                prefix={<FileTextOutlined />}
                valueStyle={{ color: '#52c41a' }}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="向量总数"
                value={stats?.total_vectors || 0}
                prefix={<CloudOutlined />}
                valueStyle={{ color: '#722ed1' }}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="今日查询"
                value={stats?.query_count_today || 0}
                prefix={<SearchOutlined />}
                valueStyle={{ color: '#fa8c16' }}
              />
            </Card>
          </Col>
        </Row>

        {/* 系统健康状态 */}
        <Row gutter={[16, 16]} style={{ marginBottom: '24px' }}>
          <Col span={12}>
            <Card title="系统健康状态" extra={<Button icon={<BarChartOutlined />}>详细监控</Button>}>
              <Space direction="vertical" style={{ width: '100%' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <Text>系统状态</Text>
                  <Tag color={getHealthColor(stats?.system_health || 'healthy')}>
                    {stats?.system_health === 'healthy' ? '健康' :
                     stats?.system_health === 'warning' ? '警告' : '错误'}
                  </Tag>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <Text>存储使用</Text>
                  <Text>{stats?.storage_used || '0 MB'}</Text>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <Text>平均响应时间</Text>
                  <Text>{stats?.avg_response_time || 0}ms</Text>
                </div>
                <Progress
                  percent={75}
                  strokeColor={getHealthColor(stats?.system_health || 'healthy')}
                  showInfo={false}
                />
              </Space>
            </Card>
          </Col>
          <Col span={12}>
            <Card title="快速操作">
              <Row gutter={[8, 8]}>
                {quickActions.map((action, index) => (
                  <Col span={12} key={index}>
                    <Card
                      size="small"
                      hoverable
                      style={{
                        borderLeft: `4px solid ${action.color}`,
                        cursor: 'pointer'
                      }}
                      onClick={() => {
                        console.log(`执行快速操作: ${action.title}`);
                        action.action();
                      }}
                    >
                      <Space>
                        <Avatar
                          icon={action.icon}
                          style={{ backgroundColor: action.color }}
                          size="small"
                        />
                        <div>
                          <div style={{ fontWeight: 'bold', fontSize: '12px' }}>
                            {action.title}
                          </div>
                          <div style={{ fontSize: '10px', color: '#666' }}>
                            {action.description}
                          </div>
                        </div>
                      </Space>
                    </Card>
                  </Col>
                ))}
              </Row>
            </Card>
          </Col>
        </Row>

        {/* 最近活动 */}
        <Card title="最近活动" extra={<Button type="link">查看全部</Button>}>
          <List
            dataSource={recentActivities}
            renderItem={(item) => (
              <List.Item>
                <List.Item.Meta
                  avatar={getActivityIcon(item.type)}
                  title={
                    <Space>
                      <Text>{item.description}</Text>
                      <Tag color={item.status === 'success' ? 'green' : item.status === 'warning' ? 'orange' : 'red'}>
                        {item.status === 'success' ? '成功' : item.status === 'warning' ? '警告' : '失败'}
                      </Tag>
                    </Space>
                  }
                  description={new Date(item.timestamp).toLocaleString()}
                />
              </List.Item>
            )}
            locale={{ emptyText: '暂无最近活动' }}
          />
        </Card>
      </div>
    </PageLayout>
  );
};

export default RAGDashboard;
