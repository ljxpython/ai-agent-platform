import React from 'react';
import { Routes, Route, Link, useLocation } from 'react-router-dom';
import { Layout, Menu, theme } from 'antd';
import type { MenuProps } from 'antd';
import {
  DatabaseOutlined,
  TableOutlined,
  SwapOutlined,
  HomeOutlined,
  ApiOutlined,
  ShareAltOutlined,
  BulbOutlined
} from '@ant-design/icons';

import './styles/Header.css';
import './styles/global-styles.css';
import './styles/layout-fix.css';

import ConnectionsPage from './pages/ConnectionsPage';
import SchemaManagementPage from './pages/SchemaManagementPage';
import IntelligentQueryPage from './pages/IntelligentQueryPage';
import ValueMappingsPage from './pages/ValueMappingsPage';
import GraphVisualizationPage from './pages/GraphVisualizationPage';
import Text2SQL from './pages/text2sql/page';
import HybridQAPage from './pages/HybridQA';
import MarkdownTest from './pages/text2sql/components/MarkdownTest';

const { Header, Content } = Layout;

const App: React.FC = () => {
  const location = useLocation();

  const {
    token: { colorBgContainer },
  } = theme.useToken();

  // 子菜单项
  const items: MenuProps['items'] = [
    {
      key: '/text2sql',
      icon: <HomeOutlined />,
      label: <Link to="/text2sql">智能查询</Link>,
    },
    {
      key: '/hybrid-qa',
      icon: <BulbOutlined />,
      label: <Link to="/hybrid-qa">智能问答</Link>,
    },
    {
      key: '/schema',
      icon: <TableOutlined />,
      label: <Link to="/schema">数据建模</Link>,
    },
    {
      key: '/graph-visualization',
      icon: <ShareAltOutlined />,
      label: <Link to="/graph-visualization">图数据可视化</Link>,
    },
    {
      key: '/connections',
      icon: <DatabaseOutlined />,
      label: <Link to="/connections">连接管理</Link>,
    },
    {
      key: '/value-mappings',
      icon: <SwapOutlined />,
      label: <Link to="/value-mappings">数据映射</Link>,
    },
  ];

  return (
    <Layout style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Header className="app-header">
        <ApiOutlined style={{ fontSize: '28px', color: '#1890ff', marginRight: '16px' }} />
        <div className="app-title">
          佳欣智能数据分析系统
        </div>
        <Menu
          className="app-menu"
          theme="dark"
          mode="horizontal"
          selectedKeys={[location.pathname === '/' ? '/text2sql' : location.pathname]}
          items={items}
        />
      </Header>
      <Content style={{
        padding: '0 50px',
        marginTop: 16,
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden' // 防止内容区域产生额外滚动条
      }}>
        <div style={{
          padding: 24,
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          background: colorBgContainer,
          borderRadius: '2px',
          overflow: 'auto', // 允许内容区域滚动
          minHeight: 0 // 确保flex子元素可以收缩
        }}>
          <Routes>
            <Route path="/" element={<Text2SQL />} />
            <Route path="/text2sql" element={<Text2SQL />} />
            <Route path="/hybrid-qa" element={<HybridQAPage />} />
            <Route path="/connections" element={<ConnectionsPage />} />
            <Route path="/schema" element={<SchemaManagementPage />} />
            <Route path="/graph-visualization" element={<GraphVisualizationPage />} />
            <Route path="/query" element={<IntelligentQueryPage />} />
            <Route path="/value-mappings" element={<ValueMappingsPage />} />
            <Route path="/markdown-test" element={<MarkdownTest />} />
          </Routes>
        </div>
      </Content>
    </Layout>
  );
};

export default App;
