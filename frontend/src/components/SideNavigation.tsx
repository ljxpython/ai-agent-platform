import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Layout, Menu, Typography } from 'antd';
import {
  HomeOutlined,
  MessageOutlined,
  FileTextOutlined,
  RobotOutlined,
  SettingOutlined,
  BugOutlined,
  ApiOutlined,
  DashboardOutlined,
  CodeOutlined,
  UserOutlined,
  TeamOutlined,
  ApartmentOutlined,
  DatabaseOutlined,
  CloudOutlined,
  BarChartOutlined,
} from '@ant-design/icons';
import TopNavigation from './TopNavigation';
import SidebarToggleButton from './FloatingToggleButton';
import './SideNavigation.css';

const { Sider } = Layout;
const { Text } = Typography;

interface SideNavigationProps {
  children: React.ReactNode;
}

const SideNavigation: React.FC<SideNavigationProps> = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [openKeys, setOpenKeys] = useState(['ai-assist']); // 默认展开AI助力模块

  // 根据当前路径确定选中的菜单项
  const getSelectedKey = () => {
    const path = location.pathname;
    if (path === '/') return 'home';
    if (path === '/chat') return 'chat';

    if (path === '/testcase') return 'testcase';
    if (path === '/midscene') return 'midscene';
    if (path === '/ui-test-script') return 'ui-test-script';
    if (path === '/api-testing') return 'api-testing';
    if (path === '/performance-testing') return 'performance-testing';
    // RAG管理路由
    if (path.startsWith('/rag')) {
      if (path === '/rag' || path === '/rag/dashboard') return 'rag-dashboard';
      if (path === '/rag/documents') return 'rag-documents';
      if (path === '/rag/collections') return 'rag-collections';
      if (path === '/rag/vectors') return 'rag-vectors';
      if (path === '/rag/monitoring') return 'rag-monitoring';
      if (path === '/rag/config') return 'rag-config';
    }
    if (path === '/system/users') return 'system-users';
    if (path === '/system/roles') return 'system-roles';
    if (path === '/system/departments') return 'system-departments';
    if (path === '/system/apis') return 'system-apis';
    return 'home';
  };

  const menuItems = [
    {
      key: 'home',
      icon: <HomeOutlined />,
      label: collapsed ? null : '首页',
    },
    {
      key: 'divider1',
      type: 'divider' as const,
    },
    {
      key: 'ai-assist',
      icon: <RobotOutlined />,
      label: collapsed ? null : 'AI助力',
      children: [
        {
          key: 'chat',
          icon: <MessageOutlined />,
          label: 'AI对话',
        },

        {
          key: 'testcase',
          icon: <FileTextOutlined />,
          label: '测试用例生成',
        },
      ],
    },
    {
      key: 'rag-management',
      icon: <DatabaseOutlined />,
      label: collapsed ? null : 'RAG知识库',
      children: [
        {
          key: 'rag-dashboard',
          icon: <DashboardOutlined />,
          label: '管理中心',
        },
        {
          key: 'rag-documents',
          icon: <FileTextOutlined />,
          label: '文档管理',
        },
        {
          key: 'rag-collections',
          icon: <DatabaseOutlined />,
          label: 'Collection管理',
        },
        {
          key: 'rag-vectors',
          icon: <CloudOutlined />,
          label: '向量管理',
        },
        {
          key: 'rag-monitoring',
          icon: <BarChartOutlined />,
          label: '系统监控',
        },
        {
          key: 'rag-config',
          icon: <SettingOutlined />,
          label: '配置管理',
        },
      ],
    },
    {
      key: 'ui-testing',
      icon: <BugOutlined />,
      label: collapsed ? null : 'UI测试',
      children: [
        {
          key: 'midscene',
          icon: <RobotOutlined />,
          label: 'Midscene智能系统介绍',
        },
        {
          key: 'ui-test-script',
          icon: <CodeOutlined />,
          label: 'UI测试脚本生成',
        },
      ],
    },
    {
      key: 'api-testing',
      icon: <ApiOutlined />,
      label: collapsed ? null : '接口测试',
      disabled: true,
    },
    {
      key: 'performance-testing',
      icon: <DashboardOutlined />,
      label: collapsed ? null : '性能测试',
      disabled: true,
    },
    {
      key: 'divider2',
      type: 'divider' as const,
    },
    {
      key: 'system-management',
      icon: <SettingOutlined />,
      label: collapsed ? null : '系统管理',
      children: [
        {
          key: 'system-users',
          icon: <UserOutlined />,
          label: '用户管理',
        },
        {
          key: 'system-roles',
          icon: <TeamOutlined />,
          label: '角色管理',
        },
        {
          key: 'system-departments',
          icon: <ApartmentOutlined />,
          label: '部门管理',
        },
        {
          key: 'system-apis',
          icon: <ApiOutlined />,
          label: 'API管理',
        },
      ],
    },
  ];

  const handleMenuClick = ({ key }: { key: string }) => {
    switch (key) {
      case 'home':
        navigate('/');
        break;
      case 'chat':
        navigate('/chat');
        break;

      case 'testcase':
        navigate('/testcase');
        break;
      case 'midscene':
        navigate('/midscene');
        break;
      case 'ui-test-script':
        navigate('/ui-test-script');
        break;
      case 'api-testing':
        // 未来功能，暂时不跳转
        console.log('接口测试功能开发中');
        break;
      case 'performance-testing':
        // 未来功能，暂时不跳转
        console.log('性能测试功能开发中');
        break;
      // RAG管理路由
      case 'rag-dashboard':
        navigate('/rag/dashboard');
        break;
      case 'rag-documents':
        navigate('/rag/documents');
        break;
      case 'rag-collections':
        navigate('/rag/collections');
        break;
      case 'rag-vectors':
        navigate('/rag/vectors');
        break;
      case 'rag-monitoring':
        navigate('/rag/monitoring');
        break;
      case 'rag-config':
        navigate('/rag/config');
        break;
      case 'system-users':
        navigate('/system/users');
        break;
      case 'system-roles':
        navigate('/system/roles');
        break;
      case 'system-departments':
        navigate('/system/departments');
        break;
      case 'system-apis':
        navigate('/system/apis');
        break;
      default:
        break;
    }
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      {/* 顶部导航栏 */}
      <TopNavigation />

      {/* 主体布局 */}
      <Layout style={{ marginTop: 64 }}>
        <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        trigger={null}
        width={240}
        collapsedWidth={48}
        className="ant-layout-sider-fixed"
        style={{
          background: '#ffffff',
          boxShadow: '2px 0 8px rgba(0,0,0,0.06)',
          position: 'fixed',
          left: 0,
          top: 64,
          height: 'calc(100vh - 64px)',
          zIndex: 1000,
          borderRight: '1px solid #f0f0f0',
          overflow: 'auto',
          userSelect: 'none',
          WebkitUserSelect: 'none',
        }}
      >
        {/* 顶部间距 */}
        <div style={{ height: 16 }} />



        {/* 导航菜单 */}
        <Menu
          theme="light"
          mode="inline"
          selectedKeys={[getSelectedKey()]}
          openKeys={collapsed ? [] : openKeys}
          onOpenChange={setOpenKeys}
          onClick={handleMenuClick}
          style={{
            background: 'transparent',
            border: 'none',
            fontSize: 14,
            padding: '0 8px',
          }}
          items={menuItems}
        />

        {/* 底部信息 */}
        {!collapsed && (
          <div
            style={{
              position: 'absolute',
              bottom: 16,
              left: 16,
              right: 16,
              padding: 12,
              background: '#fafafa',
              borderRadius: 6,
              border: '1px solid #f0f0f0',
            }}
          >
            <Text
              style={{
                color: '#8c8c8c',
                fontSize: 12,
                display: 'block',
                textAlign: 'center',
                lineHeight: 1.4,
              }}
            >
              基于 AutoGen 0.5.7
              <br />
              FastAPI + React
            </Text>
          </div>
        )}

        {/* 折叠按钮 */}
        <SidebarToggleButton
          collapsed={collapsed}
          onToggle={() => setCollapsed(!collapsed)}
        />
      </Sider>

        {/* 主内容区域 */}
        <Layout>
          <div
            className={`main-content-with-sidebar ${collapsed ? 'collapsed' : ''}`}
            style={{
              flex: 1,
              transition: 'all 0.2s',
              background: '#f5f5f5',
              minHeight: 'calc(100vh - 64px)',
              marginLeft: collapsed ? 48 : 240,
              overflow: 'auto',
              position: 'relative',
            }}
          >
            {children}
          </div>
        </Layout>
      </Layout>


    </Layout>
  );
};

export default SideNavigation;
