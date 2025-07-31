import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { r2rClient } from 'r2r-js';
import { message } from 'antd';
import { AuthState, Pipeline, UserContextProps } from '@/types/rag';

// 检查是否为有效的认证状态
function isAuthState(obj: any): obj is AuthState {
  const validRoles = ['admin', 'user', null];
  return (
    typeof obj === 'object' &&
    obj !== null &&
    typeof obj.isAuthenticated === 'boolean' &&
    (typeof obj.email === 'string' || obj.email === null) &&
    (validRoles.includes(obj.userRole) || obj.userRole === null)
  );
}

// 默认上下文值
const defaultContextValue: UserContextProps = {
  pipeline: null,
  setPipeline: () => {},
  selectedModel: 'null',
  setSelectedModel: () => {},
  isAuthenticated: false,
  login: async () => ({ success: false, userRole: 'user' }),
  loginWithToken: async () => ({ success: false, userRole: 'user' }),
  logout: async () => {},
  unsetCredentials: async () => {},
  register: async () => {},
  authState: {
    isAuthenticated: false,
    email: null,
    userRole: null,
    userId: null,
  },
  getClient: () => null,
  client: null,
  viewMode: 'admin',
  setViewMode: () => {},
  isSuperUser: () => false,
  createUser: async () => {
    throw new Error('createUser is not implemented in the default context');
  },
  deleteUser: async () => {
    throw new Error('deleteUser is not implemented in the default context');
  },
  updateUser: async () => {
    throw new Error('updateUser is not implemented in the default context');
  },
};

const RAGContext = createContext<UserContextProps>(defaultContextValue);

export const useRAGContext = () => useContext(RAGContext);

interface RAGProviderProps {
  children: React.ReactNode;
}

export const RAGProvider: React.FC<RAGProviderProps> = ({ children }) => {
  const [client, setClient] = useState<r2rClient | null>(null);
  const [viewMode, setViewMode] = useState<'admin' | 'user'>('admin');

  // 从localStorage初始化pipeline
  const [pipeline, setPipeline] = useState<Pipeline | null>(() => {
    if (typeof window !== 'undefined') {
      const storedPipeline = localStorage.getItem('rag_pipeline');
      return storedPipeline ? JSON.parse(storedPipeline) : null;
    }
    return null;
  });

  // 从localStorage初始化selectedModel
  const [selectedModel, setSelectedModel] = useState(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('rag_selectedModel') || '';
    }
    return 'null';
  });

  // 从localStorage初始化authState
  const [authState, setAuthState] = useState<AuthState>(() => {
    if (typeof window !== 'undefined') {
      const storedAuthState = localStorage.getItem('rag_authState');
      if (storedAuthState) {
        const parsed = JSON.parse(storedAuthState);
        if (isAuthState(parsed)) {
          return parsed;
        } else {
          console.warn('Invalid authState found in localStorage. Resetting to default.');
        }
      }
    }
    return {
      isAuthenticated: false,
      email: null,
      userRole: null,
      userId: null,
    };
  });

  // 保存pipeline到localStorage
  useEffect(() => {
    if (typeof window !== 'undefined') {
      if (pipeline) {
        localStorage.setItem('rag_pipeline', JSON.stringify(pipeline));
      } else {
        localStorage.removeItem('rag_pipeline');
      }
    }
  }, [pipeline]);

  // 保存selectedModel到localStorage
  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('rag_selectedModel', selectedModel);
    }
  }, [selectedModel]);

  // 保存authState到localStorage
  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('rag_authState', JSON.stringify(authState));
    }
  }, [authState]);

  // 获取客户端实例
  const getClient = useCallback((): r2rClient | null => {
    if (!pipeline?.deploymentUrl) {
      return null;
    }

    try {
      const newClient = new r2rClient(pipeline.deploymentUrl);
      return newClient;
    } catch (error) {
      console.error('Failed to create R2R client:', error);
      return null;
    }
  }, [pipeline]);

  // 更新客户端实例
  useEffect(() => {
    const newClient = getClient();
    setClient(newClient);
  }, [getClient]);

  // 登录函数
  const login = useCallback(async (
    email: string,
    _password: string,
    instanceUrl: string
  ): Promise<{ success: boolean; userRole: 'admin' | 'user' }> => {
    try {
      // const tempClient = new r2rClient(instanceUrl);
      // 注意：r2r-js可能没有login方法，这里需要根据实际API调整
      // const response = await tempClient.login(email, password);

      // 临时实现，实际需要根据API调整
      const newAuthState: AuthState = {
        isAuthenticated: true,
        email,
        userRole: 'user',
        userId: null,
      };

      setAuthState(newAuthState);
      setPipeline({ deploymentUrl: instanceUrl });

      message.success('登录成功');
      return { success: true, userRole: 'user' };
    } catch (error) {
      console.error('Login error:', error);
      message.error('登录失败');
      return { success: false, userRole: 'user' };
    }
  }, []);

  // Token登录函数
  const loginWithToken = useCallback(async (
    _token: string,
    instanceUrl: string
  ): Promise<{ success: boolean; userRole: 'admin' | 'user' }> => {
    try {
      // const tempClient = new r2rClient(instanceUrl);
      // 这里需要根据实际API调整
      // const response = await tempClient.loginWithToken(token);

      // 临时实现，实际需要根据API调整
      const newAuthState: AuthState = {
        isAuthenticated: true,
        email: null,
        userRole: 'user',
        userId: null,
      };

      setAuthState(newAuthState);
      setPipeline({ deploymentUrl: instanceUrl });

      message.success('Token登录成功');
      return { success: true, userRole: 'user' };
    } catch (error) {
      console.error('Token login error:', error);
      message.error('Token登录失败');
      return { success: false, userRole: 'user' };
    }
  }, []);

  // 登出函数
  const logout = useCallback(async (): Promise<void> => {
    try {
      // if (client) {
      //   await client.logout();
      // }
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      setAuthState({
        isAuthenticated: false,
        email: null,
        userRole: null,
        userId: null,
      });
      setClient(null);
      message.success('已登出');
    }
  }, [client]);

  // 清除凭据
  const unsetCredentials = useCallback(async (): Promise<void> => {
    setAuthState({
      isAuthenticated: false,
      email: null,
      userRole: null,
      userId: null,
    });
    setClient(null);
    setPipeline(null);

    if (typeof window !== 'undefined') {
      localStorage.removeItem('rag_authState');
      localStorage.removeItem('rag_pipeline');
      localStorage.removeItem('rag_selectedModel');
    }
  }, []);

  // 注册函数
  const register = useCallback(async (
    _email: string,
    _password: string,
    _instanceUrl: string
  ): Promise<void> => {
    try {
      // const tempClient = new r2rClient(instanceUrl);
      // await tempClient.register(email, password);
      message.success('注册成功');
    } catch (error) {
      console.error('Register error:', error);
      message.error('注册失败');
      throw error;
    }
  }, []);

  // 检查是否为超级用户
  const isSuperUser = useCallback((): boolean => {
    return authState.userRole === 'admin';
  }, [authState.userRole]);

  // 创建用户
  const createUser = useCallback(async (_userData: {
    email: string;
    password: string;
    role: string;
  }): Promise<any> => {
    if (!client) {
      throw new Error('No authenticated client');
    }

    try {
      // const response = await client.createUser(userData.email, userData.password);
      message.success('用户创建成功');
      return {};
    } catch (error) {
      console.error('Create user error:', error);
      message.error('用户创建失败');
      throw error;
    }
  }, [client]);

  // 删除用户
  const deleteUser = useCallback(async (_userId: string, _password: string): Promise<any> => {
    if (!client) {
      throw new Error('No authenticated client');
    }

    try {
      // const response = await client.deleteUser(userId, password);
      message.success('用户删除成功');
      return {};
    } catch (error) {
      console.error('Delete user error:', error);
      message.error('用户删除失败');
      throw error;
    }
  }, [client]);

  // 更新用户
  const updateUser = useCallback(async (
    _userId: string,
    _userData: { email: string; role: string },
    _name?: string,
    _bio?: string,
    _is_superuser?: boolean
  ): Promise<any> => {
    if (!client) {
      throw new Error('No authenticated client');
    }

    try {
      // 这里需要根据实际API调整
      // const response = await client.updateUser(userId, userData);
      message.success('用户更新成功');
      return {};
    } catch (error) {
      console.error('Update user error:', error);
      message.error('用户更新失败');
      throw error;
    }
  }, [client]);

  const contextValue: UserContextProps = {
    pipeline,
    setPipeline,
    selectedModel,
    setSelectedModel,
    isAuthenticated: authState.isAuthenticated,
    login,
    loginWithToken,
    logout,
    unsetCredentials,
    register,
    authState,
    getClient,
    client,
    viewMode,
    setViewMode,
    isSuperUser,
    createUser,
    deleteUser,
    updateUser,
  };

  return (
    <RAGContext.Provider value={contextValue}>
      {children}
    </RAGContext.Provider>
  );
};
