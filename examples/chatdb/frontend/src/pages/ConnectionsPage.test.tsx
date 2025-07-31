import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import ConnectionsPage from './ConnectionsPage';
import * as api from '../services/api';

// Extend Jest matchers for TypeScript
declare global {
  namespace jest {
    interface Matchers<R> {
      toBeInTheDocument(): R;
    }
  }
}

// Mock the API module
jest.mock('../services/api', () => ({
  getConnections: jest.fn(),
  createConnection: jest.fn(),
  updateConnection: jest.fn(),
  deleteConnection: jest.fn(),
  testConnection: jest.fn(),
}));

describe('ConnectionsPage', () => {
  beforeEach(() => {
    // Mock the API responses
    (api.getConnections as jest.Mock).mockResolvedValue({
      data: [
        {
          id: 1,
          name: 'Test Connection',
          db_type: 'mysql',
          host: 'localhost',
          port: 3306,
          username: 'root',
          database_name: 'test_db',
          created_at: '2023-01-01T00:00:00Z',
          updated_at: '2023-01-01T00:00:00Z',
        },
      ],
    });
  });

  test('renders connections table', async () => {
    render(<ConnectionsPage />);

    // 检查标题是否渲染
    expect(screen.getByText('数据库连接')).toBeInTheDocument();

    // 检查“添加连接”按钮是否渲染
    expect(screen.getByText('添加连接')).toBeInTheDocument();

    // Wait for the connections to be loaded
    await waitFor(() => {
      expect(screen.getByText('Test Connection')).toBeInTheDocument();
    });

    // 检查表头是否渲染
    expect(screen.getByText('名称')).toBeInTheDocument();
    expect(screen.getByText('类型')).toBeInTheDocument();
    expect(screen.getByText('主机')).toBeInTheDocument();
    expect(screen.getByText('端口')).toBeInTheDocument();
    expect(screen.getByText('数据库')).toBeInTheDocument();
    expect(screen.getByText('操作')).toBeInTheDocument();

    // Check if the connection data is rendered
    expect(screen.getByText('Test Connection')).toBeInTheDocument();
    expect(screen.getByText('mysql')).toBeInTheDocument();
    expect(screen.getByText('localhost')).toBeInTheDocument();
    expect(screen.getByText('3306')).toBeInTheDocument();
    expect(screen.getByText('test_db')).toBeInTheDocument();

    // 检查操作按钮是否渲染
    expect(screen.getByText('测试')).toBeInTheDocument();
    expect(screen.getByText('编辑')).toBeInTheDocument();
    expect(screen.getByText('删除')).toBeInTheDocument();
  });

  test('点击添加连接按钮时打开添加连接模态框', async () => {
    render(<ConnectionsPage />);

    // 点击“添加连接”按钮
    fireEvent.click(screen.getByText('添加连接'));

    // 检查模态框是否打开
    await waitFor(() => {
      expect(screen.getByText('添加连接')).toBeInTheDocument();
    });

    // 检查表单字段是否渲染
    expect(screen.getByLabelText('连接名称')).toBeInTheDocument();
    expect(screen.getByLabelText('数据库类型')).toBeInTheDocument();
    expect(screen.getByLabelText('主机')).toBeInTheDocument();
    expect(screen.getByLabelText('端口')).toBeInTheDocument();
    expect(screen.getByLabelText('用户名')).toBeInTheDocument();
    expect(screen.getByLabelText('密码')).toBeInTheDocument();
    expect(screen.getByLabelText('数据库名称')).toBeInTheDocument();
  });
});
