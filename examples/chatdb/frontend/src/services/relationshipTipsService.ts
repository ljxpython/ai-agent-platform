import { API_BASE_URL } from '../config';

/**
 * 获取关系类型提示信息
 * @returns 关系类型提示信息
 */
export const getRelationshipTips = async () => {
  try {
    const response = await fetch(`${API_BASE_URL}/relationship-tips/`);
    if (!response.ok) {
      throw new Error(`获取关系类型提示信息失败: ${response.statusText}`);
    }
    return await response.json();
  } catch (error) {
    console.error('获取关系类型提示信息出错:', error);
    return {};
  }
};
