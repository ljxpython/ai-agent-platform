import React from 'react';
import { BrowserRouter as Router, Routes, Route, useLocation, Navigate } from 'react-router-dom';
import SideNavigation from '@/components/SideNavigation';
import HomePage from '@/pages/HomePage';
import ChatPage from '@/pages/ChatPage';

import TestCasePage from '@/pages/TestCasePage';
import ScrollTestPage from '@/pages/ScrollTestPage';

// UI测试页面
import {
  OverviewPage,
  ImageUploadPage,
  TaskManagePage,
  ResultViewPage,
} from '@/pages/ui-test';
import LoginPage from '@/pages/LoginPage';
import UserProfilePage from '@/pages/UserProfilePage';
import UserManagePage from '@/pages/system/UserManagePage';
import RoleManagePage from '@/pages/system/RoleManagePage';
import DepartmentManagePage from '@/pages/system/DepartmentManagePage';
import ApiManagePage from '@/pages/system/ApiManagePage';
import ProjectManagement from '@/pages/system/ProjectManagement';
import ProjectTest from '@/pages/test/ProjectTest';
import ApiTest from '@/pages/test/ApiTest';
// RAG管理页面
import RAGDashboard from '@/pages/rag/RAGDashboard';
import DocumentManagement from '@/pages/rag/DocumentManagement';
import VectorManagement from '@/pages/rag/VectorManagement';
import SystemMonitoring from '@/pages/rag/SystemMonitoring';
import ConfigManagement from '@/pages/rag/ConfigManagement';
import CollectionManagement from './pages/rag/CollectionManagement';
import RAGChat from '@/pages/rag/Chat';
import { isAuthenticated } from '@/services/auth';
import { RAGProvider } from '@/contexts/RAGContext';

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

          <Route path="/testcase" element={<TestCasePage />} />

          {/* UI测试路由 */}
          <Route path="/ui-test" element={<OverviewPage />} />
          <Route path="/ui-test/overview" element={<OverviewPage />} />
          <Route path="/ui-test/upload" element={<ImageUploadPage />} />
          <Route path="/ui-test/tasks" element={<TaskManagePage />} />
          <Route path="/ui-test/results" element={<ResultViewPage />} />

          <Route path="/scroll-test" element={<ScrollTestPage />} />
          <Route path="/profile" element={<UserProfilePage />} />
          <Route path="/system/users" element={<UserManagePage />} />
          <Route path="/system/roles" element={<RoleManagePage />} />
          <Route path="/system/departments" element={<DepartmentManagePage />} />
          <Route path="/system/apis" element={<ApiManagePage />} />
          <Route path="/system/projects" element={<ProjectManagement />} />
          <Route path="/test/projects" element={<ProjectTest />} />
          <Route path="/test/api" element={<ApiTest />} />
          {/* RAG管理路由 */}
          <Route path="/rag" element={<RAGDashboard />} />
          <Route path="/rag/dashboard" element={<RAGDashboard />} />
          <Route path="/rag/chat" element={
            <RAGProvider>
              <RAGChat />
            </RAGProvider>
          } />
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
