/**
 * 系统管理API
 */

import { request } from '@/utils/request';

// ==================== 用户管理 ====================

export interface User {
  id: number;
  username: string;
  email: string;
  full_name?: string;
  is_active: boolean;
  is_superuser: boolean;
  last_login?: string;
  created_at: string;
  updated_at: string;
  dept?: {
    id: number;
    name: string;
  };
  roles: Array<{
    id: number;
    name: string;
  }>;
}

export interface UserCreateRequest {
  username: string;
  email: string;
  password: string;
  full_name?: string;
  is_active: boolean;
  dept_id?: number;
  role_ids: number[];
}

export interface UserUpdateRequest {
  username: string;
  email: string;
  full_name?: string;
  is_active: boolean;
  dept_id?: number;
  role_ids: number[];
}

export interface UserListParams {
  page?: number;
  page_size?: number;
  username?: string;
  email?: string;
  dept_id?: number;
}

// ==================== 角色管理 ====================

export interface Role {
  id: number;
  name: string;
  description?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  apis: Array<{
    id: number;
    path: string;
    method: string;
  }>;
}

export interface RoleCreateRequest {
  name: string;
  description?: string;
  is_active: boolean;
}

export interface RoleUpdateRequest {
  name: string;
  description?: string;
  is_active: boolean;
}

export interface RoleListParams {
  page?: number;
  page_size?: number;
  name?: string;
}

// ==================== 部门管理 ====================

export interface Department {
  id: number;
  name: string;
  description?: string;
  parent_id?: number;
  sort_order: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  children?: Department[];
  users_count: number;
}

export interface DepartmentCreateRequest {
  name: string;
  description?: string;
  parent_id?: number;
  sort_order: number;
  is_active: boolean;
}

export interface DepartmentUpdateRequest {
  name: string;
  description?: string;
  parent_id?: number;
  sort_order: number;
  is_active: boolean;
}

export interface DepartmentListParams {
  page?: number;
  page_size?: number;
  name?: string;
}

// ==================== API管理 ====================

export interface Api {
  id: number;
  path: string;
  method: string;
  summary?: string;
  description?: string;
  tags?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ApiCreateRequest {
  path: string;
  method: string;
  summary?: string;
  description?: string;
  tags?: string;
  is_active: boolean;
}

export interface ApiUpdateRequest {
  path: string;
  method: string;
  summary?: string;
  description?: string;
  tags?: string;
  is_active: boolean;
}

export interface ApiListParams {
  page?: number;
  page_size?: number;
  path?: string;
  method?: string;
  tags?: string;
}

// ==================== API服务类 ====================

export class SystemAPI {
  // 用户管理
  static async getUserList(params: UserListParams = {}) {
    console.log('🌐 [SystemAPI] 发送用户列表请求:', params);
    const response = await request.get('/v1/system/users', { params });
    console.log('📨 [SystemAPI] 用户列表原始响应:', response);
    return response;
  }

  static async getUser(id: number) {
    const response = await request.get(`/v1/system/users/${id}`);
    return response.data;
  }

  static async createUser(data: UserCreateRequest) {
    const response = await request.post('/v1/system/users', data);
    return response.data;
  }

  static async updateUser(id: number, data: UserUpdateRequest) {
    const response = await request.put(`/v1/system/users/${id}`, data);
    return response.data;
  }

  static async deleteUser(id: number) {
    const response = await request.delete(`/v1/system/users/${id}`);
    return response.data;
  }

  static async resetUserPassword(id: number) {
    const response = await request.post(`/v1/system/users/${id}/reset-password`);
    return response.data;
  }

  // 角色管理
  static async getRoleList(params: RoleListParams = {}) {
    console.log('🌐 [SystemAPI] 发送角色列表请求:', params);
    const response = await request.get('/v1/system/roles', { params });
    console.log('📨 [SystemAPI] 角色列表原始响应:', response);
    return response;
  }

  static async getRole(id: number) {
    const response = await request.get(`/v1/system/roles/${id}`);
    return response.data;
  }

  static async createRole(data: RoleCreateRequest) {
    const response = await request.post('/v1/system/roles', data);
    return response.data;
  }

  static async updateRole(id: number, data: RoleUpdateRequest) {
    const response = await request.put(`/v1/system/roles/${id}`, data);
    return response.data;
  }

  static async deleteRole(id: number) {
    const response = await request.delete(`/v1/system/roles/${id}`);
    return response.data;
  }

  static async updateRoleApis(id: number, api_ids: number[]) {
    const response = await request.put(`/v1/system/roles/${id}/apis`, { api_ids });
    return response.data;
  }

  // 部门管理
  static async getDepartmentList(params: DepartmentListParams = {}) {
    console.log('🌐 [SystemAPI] 发送部门列表请求:', params);
    const response = await request.get('/v1/system/departments', { params });
    console.log('📨 [SystemAPI] 部门列表原始响应:', response);
    return response;
  }

  static async getDepartmentTree() {
    console.log('🌐 [SystemAPI] 发送部门树请求');
    const response = await request.get('/v1/system/departments/tree');
    console.log('📨 [SystemAPI] 部门树原始响应:', response);
    return response;
  }

  static async getDepartment(id: number) {
    const response = await request.get(`/v1/system/departments/${id}`);
    return response.data;
  }

  static async createDepartment(data: DepartmentCreateRequest) {
    const response = await request.post('/v1/system/departments', data);
    return response.data;
  }

  static async updateDepartment(id: number, data: DepartmentUpdateRequest) {
    const response = await request.put(`/v1/system/departments/${id}`, data);
    return response.data;
  }

  static async deleteDepartment(id: number) {
    const response = await request.delete(`/v1/system/departments/${id}`);
    return response.data;
  }

  // API管理
  static async getApiList(params: ApiListParams = {}) {
    console.log('🌐 [SystemAPI] 发送API列表请求:', params);
    const response = await request.get('/v1/system/apis', { params });
    console.log('📨 [SystemAPI] API列表原始响应:', response);
    return response;
  }

  static async getApi(id: number) {
    const response = await request.get(`/v1/system/apis/${id}`);
    return response.data;
  }

  static async createApi(data: ApiCreateRequest) {
    const response = await request.post('/v1/system/apis', data);
    return response.data;
  }

  static async updateApi(id: number, data: ApiUpdateRequest) {
    const response = await request.put(`/v1/system/apis/${id}`, data);
    return response.data;
  }

  static async deleteApi(id: number) {
    const response = await request.delete(`/v1/system/apis/${id}`);
    return response.data;
  }

  static async syncApis() {
    const response = await request.post('/v1/system/apis/sync');
    return response.data;
  }
}
