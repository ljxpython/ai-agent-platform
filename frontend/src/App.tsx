import React from 'react';
import { BrowserRouter as Router, Routes, Route, useLocation, Navigate } from 'react-router-dom';
import SideNavigation from '@/components/SideNavigation';
import HomePage from '@/pages/HomePage';
import ChatPage from '@/pages/ChatPage';
import RAGManagePage from '@/pages/RAGManagePage';
import TestCasePage from '@/pages/TestCasePage';
import MidscenePage from '@/pages/MidscenePage';
import UITestScriptPage from '@/pages/UITestScriptPage';
import ScrollTestPage from '@/pages/ScrollTestPage';
import LoginPage from '@/pages/LoginPage';
import UserProfilePage from '@/pages/UserProfilePage';
import UserManagePage from '@/pages/system/UserManagePage';
import RoleManagePage from '@/pages/system/RoleManagePage';
import DepartmentManagePage from '@/pages/system/DepartmentManagePage';
import ApiManagePage from '@/pages/system/ApiManagePage';
// RAG管理页面
import RAGDashboard from '@/pages/rag/RAGDashboard';
import DocumentManagement from '@/pages/rag/DocumentManagement';
import VectorManagement from '@/pages/rag/VectorManagement';
import SystemMonitoring from '@/pages/rag/SystemMonitoring';
import ConfigManagement from '@/pages/rag/ConfigManagement';
import CollectionManagement from './pages/rag/CollectionManagement';
import { isAuthenticated } from '@/services/auth';

// 认证保护组件
const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return isAuthenticated() ? <>{children}</> : <Navigate to="/login" replace />;
};

const AppContent: React.FC = () => {
  const location = useLocation();
  const isHomePage = location.pathname === '/';
  const isLoginPage = location.pathname === '/login';

  // 登录页面独立显示
  if (isLoginPage) {
    return (
      <Routes>
        <Route path="/login" element={<LoginPage />} />
      </Routes>
    );
  }

  // 首页不显示侧边栏，其他页面显示
  if (isHomePage) {
    return (
      <Routes>
        <Route path="/" element={
          <ProtectedRoute>
            <HomePage />
          </ProtectedRoute>
        } />
      </Routes>
    );
  }

  return (
    <ProtectedRoute>
      <SideNavigation>
        <Routes>
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/rag-manage" element={<RAGManagePage />} />
          <Route path="/testcase" element={<TestCasePage />} />
          <Route path="/midscene" element={<MidscenePage />} />
          <Route path="/ui-test-script" element={<UITestScriptPage />} />
          <Route path="/scroll-test" element={<ScrollTestPage />} />
          <Route path="/profile" element={<UserProfilePage />} />
          <Route path="/system/users" element={<UserManagePage />} />
          <Route path="/system/roles" element={<RoleManagePage />} />
          <Route path="/system/departments" element={<DepartmentManagePage />} />
          <Route path="/system/apis" element={<ApiManagePage />} />
          {/* RAG管理路由 */}
          <Route path="/rag" element={<RAGDashboard />} />
          <Route path="/rag/dashboard" element={<RAGDashboard />} />
          <Route path="/rag/documents" element={<DocumentManagement />} />
          <Route path="/rag/vectors" element={<VectorManagement />} />
          <Route path="/rag/monitoring" element={<SystemMonitoring />} />
          <Route path="/rag/config" element={<ConfigManagement />} />
          <Route path="/rag/collections" element={<CollectionManagement />} />
        </Routes>
      </SideNavigation>
    </ProtectedRoute>
  );
};

const App: React.FC = () => {
  return (
    <Router>
      <AppContent />
    </Router>
  );
};

export default App;
