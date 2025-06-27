// 测试前端API调用的脚本
// 模拟前端的API调用逻辑

const axios = require('axios');

// 模拟前端的request配置
const request = axios.create({
  baseURL: 'http://localhost:8000/api',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  }
});

// 模拟SystemAPI.getDepartmentList方法（修复后）
async function getDepartmentList(params = {}) {
  console.log('🌐 [SystemAPI] 发送部门列表请求:', params);
  const response = await request.get('/v1/system/departments', { params });
  console.log('📨 [SystemAPI] 部门列表原始响应:', response.data);
  return response.data; // 修复后：返回完整响应
}

// 模拟SystemAPI.getApiList方法（修复后）
async function getApiList(params = {}) {
  console.log('🌐 [SystemAPI] 发送API列表请求:', params);
  const response = await request.get('/v1/system/apis', { params });
  console.log('📨 [SystemAPI] API列表原始响应:', response.data);
  return response.data; // 修复后：返回完整响应
}

// 模拟前端页面的数据处理逻辑
async function testDepartmentPage() {
  console.log('\n=== 测试部门管理页面 ===');
  try {
    const pagination = { current: 1, pageSize: 10 };
    const searchParams = { name: '' };

    const response = await getDepartmentList({
      page: pagination.current,
      page_size: pagination.pageSize,
      ...searchParams,
    });

    console.log('✅ 部门数据:', response.data);
    console.log('✅ 总数:', response.total);
    console.log('✅ 页码:', response.page);
    console.log('✅ 页大小:', response.page_size);

    // 验证数据结构
    if (response.data && Array.isArray(response.data) && typeof response.total === 'number') {
      console.log('🎉 部门管理页面数据结构正确！');
      return true;
    } else {
      console.log('❌ 部门管理页面数据结构错误！');
      return false;
    }
  } catch (error) {
    console.error('❌ 部门管理页面测试失败:', error.message);
    return false;
  }
}

async function testApiPage() {
  console.log('\n=== 测试API管理页面 ===');
  try {
    const pagination = { current: 1, pageSize: 10 };
    const searchParams = { path: '', method: '', tags: '' };

    const response = await getApiList({
      page: pagination.current,
      page_size: pagination.pageSize,
      ...searchParams,
    });

    console.log('✅ API数据:', response.data.slice(0, 2)); // 只显示前2个
    console.log('✅ 总数:', response.total);
    console.log('✅ 页码:', response.page);
    console.log('✅ 页大小:', response.page_size);

    // 验证数据结构
    if (response.data && Array.isArray(response.data) && typeof response.total === 'number') {
      console.log('🎉 API管理页面数据结构正确！');
      return true;
    } else {
      console.log('❌ API管理页面数据结构错误！');
      return false;
    }
  } catch (error) {
    console.error('❌ API管理页面测试失败:', error.message);
    return false;
  }
}

// 运行测试
async function runTests() {
  console.log('🚀 开始测试前端API修复效果...\n');

  const deptResult = await testDepartmentPage();
  const apiResult = await testApiPage();

  console.log('\n=== 测试结果汇总 ===');
  console.log(`部门管理页面: ${deptResult ? '✅ 通过' : '❌ 失败'}`);
  console.log(`API管理页面: ${apiResult ? '✅ 通过' : '❌ 失败'}`);

  if (deptResult && apiResult) {
    console.log('\n🎉 所有测试通过！前端页面应该能正常展示后端数据了！');
  } else {
    console.log('\n❌ 部分测试失败，需要进一步检查。');
  }
}

// 如果直接运行此脚本
if (require.main === module) {
  runTests().catch(console.error);
}

module.exports = {
  getDepartmentList,
  getApiList,
  testDepartmentPage,
  testApiPage,
  runTests
};
