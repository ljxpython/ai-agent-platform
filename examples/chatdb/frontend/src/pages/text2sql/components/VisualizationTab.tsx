import React, { useEffect, useRef } from 'react';
import { FormattedOutput as OutputFormatter } from '../utils';

interface VisualizationTabProps {
  dataResult: any[] | null;
  visualizationResult: {
    type: string;
    config: any;
  } | null;
  dataStreaming: boolean;
  visualizationStreaming: boolean;
  dataHasContent: boolean;
  visualizationHasContent: boolean;
  currentPage: number;
  pageSize: number;
  handlePageChange: (page: number) => void;
  getTotalPages: () => number;
  getCurrentPageData: () => any[];
  convertToCSV: (data: any[]) => string;
  promptInfo?: string; // 服务器端返回的提示信息
}

/**
 * 可视化图表标签内容组件
 */
const VisualizationTab: React.FC<VisualizationTabProps> = ({
  dataResult,
  visualizationResult,
  dataStreaming,
  visualizationStreaming,
  dataHasContent,
  visualizationHasContent,
  currentPage,
  pageSize,
  handlePageChange,
  getTotalPages,
  getCurrentPageData,
  convertToCSV,
  promptInfo
}) => {
  const chartRef = useRef<HTMLCanvasElement>(null);

  // 图表渲染逻辑
  useEffect(() => {
    if (visualizationResult && dataResult && dataResult.length > 0 && chartRef.current) {
      // 添加一个标记，避免重复渲染
      if (chartRef.current.dataset.rendered === 'true') {
        return;
      }

      // 如果可视化类型是表格，跳过图表渲染
      if (visualizationResult.type === 'table') {
        console.log('表格类型可视化，跳过图表渲染');
        // 标记为已渲染，避免重复处理
        chartRef.current.dataset.rendered = 'true';
        return;
      }

      // 使用动态导入引入Chart.js
      import('chart.js/auto').then((ChartModule) => {
        const Chart = ChartModule.default;

        // 获取画布上下文
        const canvas = chartRef.current;
        if (!canvas) return;

        // 销毁现有图表
        try {
          const chartInstance = Chart.getChart(canvas);
          if (chartInstance) {
            chartInstance.destroy();
          }
        } catch (e) {
          console.log('No existing chart to destroy');
        }

        // 准备图表数据
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        try {
          // 标记为已渲染，避免重复渲染
          canvas.dataset.rendered = 'true';

          const chartType = visualizationResult.type as 'bar' | 'line' | 'pie' | 'scatter';
          const config = prepareChartConfig(chartType, visualizationResult.config, dataResult);
          new Chart(ctx, config);
        } catch (error) {
          console.error('图表渲染错误:', error);
        }
      });
    }

    // 清理函数
    return () => {
      if (chartRef.current) {
        // 重置已渲染标记
        chartRef.current.dataset.rendered = 'false';

        // 动态导入Chart.js并清理图表
        import('chart.js/auto').then((ChartModule) => {
          const Chart = ChartModule.default;
          try {
            const chartInstance = Chart.getChart(chartRef.current!);
            if (chartInstance) {
              chartInstance.destroy();
            }
          } catch (e) {
            console.log('Error cleaning up chart:', e);
          }
        }).catch(err => {
          console.error('清理图表时出错:', err);
        });
      }
    };
  }, [visualizationResult, dataResult]);

  // 准备图表配置
  const prepareChartConfig = (
    type: 'bar' | 'line' | 'pie' | 'scatter',
    config: any,
    data: any[]
  ) => {
    // 提取数据点
    const labels = data.map(item => {
      // 尝试获取X轴字段值
      const xField = config.xAxis || Object.keys(item)[0];
      return item[xField];
    });

    // 提取数据系列
    const yField = config.yAxis || Object.keys(data[0])[1];
    const dataPoints = data.map(item => item[yField]);

    // 生成配置
    return {
      type, // 使用正确的类型
      data: {
        labels: labels,
        datasets: [{
          label: config.title || '数据系列',
          data: dataPoints,
          backgroundColor: type === 'pie' ?
            ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40'] :
            'rgba(54, 162, 235, 0.5)',
          borderColor: 'rgba(54, 162, 235, 1)',
          borderWidth: 1
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          title: {
            display: !!config.title,
            text: config.title || ''
          },
          tooltip: {
            enabled: true
          },
          legend: {
            display: type === 'pie'
          }
        }
      }
    };
  };

  return (
    <div className="text2sql-visualization-tab">
      {/* 数据表格部分 */}
      {(dataResult && dataHasContent) && (
        <div className="text2sql-card mb-4">
          <div className="text2sql-card-header" style={{ background: 'linear-gradient(135deg, rgba(139, 92, 246, 0.1) 0%, rgba(59, 130, 246, 0.1) 100%)' }}>
            <div className="text2sql-card-title">
              <div className="text2sql-card-icon" style={{ background: 'linear-gradient(135deg, rgba(139, 92, 246, 0.2) 0%, rgba(59, 130, 246, 0.2) 100%)' }}>
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  style={{ color: '#8b5cf6' }}
                >
                  <ellipse cx="12" cy="5" rx="9" ry="3"></ellipse>
                  <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"></path>
                  <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"></path>
                </svg>
              </div>
              <span>
                查询结果
                {dataStreaming ?
                  <span className="ml-2 text-xs text-purple-500 animate-pulse">查询中...</span> :
                  dataResult ? <span className="ml-2 text-xs text-green-500">已完成</span> : null
                }
                {dataResult && (
                  <span className="ml-3 text-xs text-gray-500">
                    共 {dataResult.length} 条记录
                  </span>
                )}
              </span>
            </div>
            <div className="flex items-center space-x-2">
              {/* 导出按钮 */}
              {dataResult && (
                <button
                  className="rounded-full p-1.5 text-purple-500 hover:bg-purple-50 transition-colors"
                  onClick={() => {
                    // 将数据转换为CSV格式
                    const csvContent = convertToCSV(dataResult);
                    // 创建BLOB对象
                    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
                    // 创建下载链接
                    const link = document.createElement("a");
                    const url = URL.createObjectURL(blob);
                    link.setAttribute("href", url);
                    link.setAttribute("download", "query_result.csv");
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                  }}
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                    <polyline points="7 10 12 15 17 10" />
                    <line x1="12" y1="15" x2="12" y2="3" />
                  </svg>
                </button>
              )}
            </div>
          </div>

          {/* 数据表格内容 */}
          <div className="text2sql-card-content">
            {dataResult && dataResult.length > 0 ? (
              <>
                <table className="text2sql-table">
                  <thead>
                    <tr className="bg-gray-50 dark:bg-gray-800">
                      {Object.keys(dataResult[0]).map((key) => (
                        <th key={key} className="px-4 py-3 text-left text-sm font-medium text-gray-700 dark:text-gray-300">
                          {key.replace(/_/g, ' ')}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {getCurrentPageData().map((row, i) => (
                      <tr key={i} className={`border-t border-gray-100 dark:border-gray-800 ${i % 2 === 0 ? 'bg-white dark:bg-neutral-900' : 'bg-gray-50/50 dark:bg-gray-800/50'}`}>
                        {Object.values(row).map((value, j) => (
                          <td key={j} className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">
                            {typeof value === 'number'
                              ? value.toLocaleString('zh-CN')
                              : String(value)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>

                {/* 分页控件 */}
                {dataResult.length > pageSize && (
                  <div className="flex items-center justify-between border-t border-gray-200 dark:border-gray-700 px-4 py-3 mt-2">
                    {/* 移动端分页控件 */}
                    <div className="flex-1 flex justify-between sm:hidden">
                      <button
                        onClick={() => handlePageChange(currentPage > 1 ? currentPage - 1 : 1)}
                        disabled={currentPage === 1}
                        className="relative inline-flex items-center px-4 py-2 border border-gray-300 dark:border-gray-600 text-sm font-medium rounded-md text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        上一页
                      </button>
                      <button
                        onClick={() => handlePageChange(currentPage < getTotalPages() ? currentPage + 1 : getTotalPages())}
                        disabled={currentPage === getTotalPages()}
                        className="ml-3 relative inline-flex items-center px-4 py-2 border border-gray-300 dark:border-gray-600 text-sm font-medium rounded-md text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        下一页
                      </button>
                    </div>

                    {/* 桌面端分页控件 */}
                    <div className="hidden sm:flex sm:flex-1 sm:items-center sm:justify-between">
                      <div>
                        <p className="text2sql-pagination-info">
                          显示第 <span className="font-medium">{(currentPage - 1) * pageSize + 1}</span> 至 <span className="font-medium">{Math.min(currentPage * pageSize, dataResult.length)}</span> 条，共 <span className="font-medium">{dataResult.length}</span> 条
                        </p>
                      </div>
                      <div>
                        <nav className="text2sql-pagination-nav" aria-label="Pagination">
                          {/* 首页按钮 */}
                          <button
                            onClick={() => handlePageChange(1)}
                            disabled={currentPage === 1}
                            className={`text2sql-pagination-button first-page ${currentPage === 1 ? 'opacity-50' : ''}`}
                            title="首页"
                          >
                            <svg className="h-4 w-4" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                              <path fillRule="evenodd" d="M12.79 5.23a.75.75 0 01-.02 1.06L8.832 10l3.938 3.71a.75.75 0 11-1.04 1.08l-4.5-4.25a.75.75 0 010-1.08l4.5-4.25a.75.75 0 011.06.02z" clipRule="evenodd" />
                              <path fillRule="evenodd" d="M12.79 5.23a.75.75 0 01-.02 1.06L8.832 10l3.938 3.71a.75.75 0 11-1.04 1.08l-4.5-4.25a.75.75 0 010-1.08l4.5-4.25a.75.75 0 011.06.02z" clipRule="evenodd" />
                            </svg>
                          </button>

                          {/* 上一页按钮 */}
                          <button
                            onClick={() => handlePageChange(currentPage > 1 ? currentPage - 1 : 1)}
                            disabled={currentPage === 1}
                            className={`text2sql-pagination-button ${currentPage === 1 ? 'opacity-50' : ''}`}
                            title="上一页"
                          >
                            <svg className="h-4 w-4" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                              <path fillRule="evenodd" d="M12.79 5.23a.75.75 0 01-.02 1.06L8.832 10l3.938 3.71a.75.75 0 11-1.04 1.08l-4.5-4.25a.75.75 0 010-1.08l4.5-4.25a.75.75 0 011.06.02z" clipRule="evenodd" />
                            </svg>
                          </button>

                          {/* 页码按钮 */}
                          {Array.from({ length: getTotalPages() }).map((_, i) => {
                            // 只显示当前页附近的页码
                            if (
                              i + 1 === 1 || // 首页
                              i + 1 === getTotalPages() || // 尾页
                              (i + 1 >= currentPage - 1 && i + 1 <= currentPage + 1) // 当前页及其前后页
                            ) {
                              return (
                                <button
                                  key={i}
                                  onClick={() => handlePageChange(i + 1)}
                                  className={`text2sql-pagination-button ${currentPage === i + 1 ? 'text2sql-pagination-button-active' : ''}`}
                                >
                                  {i + 1}
                                </button>
                              );
                            } else if (
                              (i + 1 === 2 && currentPage > 3) ||
                              (i + 1 === getTotalPages() - 1 && currentPage < getTotalPages() - 2)
                            ) {
                              // 显示省略号
                              return (
                                <span
                                  key={i}
                                  className="text2sql-pagination-button"
                                >
                                  ...
                                </span>
                              );
                            }
                            return null;
                          })}

                          {/* 下一页按钮 */}
                          <button
                            onClick={() => handlePageChange(currentPage < getTotalPages() ? currentPage + 1 : getTotalPages())}
                            disabled={currentPage === getTotalPages()}
                            className={`text2sql-pagination-button ${currentPage === getTotalPages() ? 'opacity-50' : ''}`}
                            title="下一页"
                          >
                            <svg className="h-4 w-4" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                              <path fillRule="evenodd" d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z" clipRule="evenodd" />
                            </svg>
                          </button>

                          {/* 尾页按钮 */}
                          <button
                            onClick={() => handlePageChange(getTotalPages())}
                            disabled={currentPage === getTotalPages()}
                            className={`text2sql-pagination-button last-page ${currentPage === getTotalPages() ? 'opacity-50' : ''}`}
                            title="尾页"
                          >
                            <svg className="h-4 w-4" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                              <path fillRule="evenodd" d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z" clipRule="evenodd" />
                              <path fillRule="evenodd" d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z" clipRule="evenodd" />
                            </svg>
                          </button>
                        </nav>
                      </div>
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="animate-pulse flex space-x-4">
                <div className="flex-1 space-y-3 py-1">
                  <div className="h-4 bg-gray-200 rounded dark:bg-gray-700"></div>
                  <div className="h-4 bg-gray-200 rounded dark:bg-gray-700 w-5/6"></div>
                  <div className="h-4 bg-gray-200 rounded dark:bg-gray-700 w-4/6"></div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 可视化图表部分 */}
      {(visualizationResult && visualizationHasContent) && (
        <div className="text2sql-card">
          <div className="text2sql-card-header" style={{ background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(16, 185, 129, 0.1) 100%)' }}>
            <div className="text2sql-card-title">
              <div className="text2sql-card-icon" style={{ background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.2) 0%, rgba(16, 185, 129, 0.2) 100%)' }}>
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  style={{ color: '#10b981' }}
                >
                  <line x1="12" y1="20" x2="12" y2="10"></line>
                  <line x1="18" y1="20" x2="18" y2="4"></line>
                  <line x1="6" y1="20" x2="6" y2="16"></line>
                </svg>
              </div>
              <span>
                数据可视化 {visualizationResult?.type ?
                  (visualizationResult.type === 'table' ? '- 表格' : `- ${visualizationResult.type}`) : ''}
                {visualizationStreaming ?
                  <span className="ml-2 text-xs text-green-500 animate-pulse">生成中...</span> :
                  visualizationResult ? <span className="ml-2 text-xs text-green-500">已完成</span> : null
                }
              </span>
            </div>
            <div className="flex items-center space-x-2">
              {/* 导出按钮 */}
              {visualizationResult && (
                <button
                  className="rounded-full p-1.5 text-green-500 hover:bg-green-50 transition-colors"
                  onClick={() => {
                    // 导出图表逻辑
                  }}
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                    <polyline points="7 10 12 15 17 10" />
                    <line x1="12" y1="15" x2="12" y2="3" />
                  </svg>
                </button>
              )}
            </div>
          </div>

          {/* 提示信息显示区域 */}
          {promptInfo && (
            <div className="px-4 py-2 bg-blue-50 dark:bg-blue-900/20 border-b border-blue-100 dark:border-blue-800">
              <div className="flex items-start">
                <div className="flex-shrink-0 mt-0.5">
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-blue-500">
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="12" y1="16" x2="12" y2="12"></line>
                    <line x1="12" y1="8" x2="12.01" y2="8"></line>
                  </svg>
                </div>
                <div className="ml-2 text-sm text-blue-700 dark:text-blue-300">
                  <p className="font-medium">提示信息</p>
                  <p className="mt-1">{promptInfo}</p>
                </div>
              </div>
            </div>
          )}

          {/* 图表或表格显示 */}
          <div className="text2sql-card-content">
            {/* 表格类型可视化 */}
            {visualizationResult && visualizationResult.type === 'table' && dataResult ? (
              <div className="rounded-lg border border-gray-200 dark:border-gray-700">
                {visualizationResult.config && visualizationResult.config.title && (
                  <div className="p-3 border-b border-gray-200 dark:border-gray-700 text-center font-medium">
                    {visualizationResult.config.title}
                  </div>
                )}
                <div className="overflow-x-auto">
                  <table className="text2sql-table">
                    <thead>
                      <tr className="bg-gray-50 dark:bg-gray-800">
                        {visualizationResult.config && visualizationResult.config.columns ?
                          visualizationResult.config.columns.map((column: string) => (
                            <th key={column} className="px-4 py-3 text-left text-sm font-medium text-gray-700 dark:text-gray-300">
                              {column}
                            </th>
                          )) :
                          dataResult && dataResult.length > 0 && Object.keys(dataResult[0]).map((key) => (
                            <th key={key} className="px-4 py-3 text-left text-sm font-medium text-gray-700 dark:text-gray-300">
                              {key}
                            </th>
                          ))
                        }
                      </tr>
                    </thead>
                    <tbody>
                      {dataResult && dataResult.map((row, i) => (
                        <tr key={i} className={`border-t border-gray-100 dark:border-gray-800 ${i % 2 === 0 ? 'bg-white dark:bg-neutral-900' : 'bg-gray-50/50 dark:bg-gray-800/50'}`}>
                          {visualizationResult.config && visualizationResult.config.columns ?
                            visualizationResult.config.columns.map((column: string) => (
                              <td key={`${i}-${column}`} className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">
                                {typeof row[column] === 'number'
                                  ? row[column].toLocaleString('zh-CN')
                                  : String(row[column])}
                              </td>
                            )) :
                            Object.values(row).map((value, j) => (
                              <td key={j} className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">
                                {typeof value === 'number'
                                  ? value.toLocaleString('zh-CN')
                                  : String(value)}
                              </td>
                            ))
                          }
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : (
              <div className="h-80 rounded-lg border border-dashed flex items-center justify-center bg-gray-50/50 dark:bg-gray-800/50 relative overflow-hidden">
                {/* 图表容器，将使用useRef引用 */}
                <canvas
                  id="resultChart"
                  ref={chartRef}
                  className="w-full h-full z-10"
                ></canvas>

                {/* 加载指示器，只在生成中显示 */}
                {!visualizationResult && (visualizationStreaming) && (
                  <div className="absolute inset-0 flex flex-col items-center justify-center bg-gray-50/80 dark:bg-gray-800/80 z-20">
                    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mb-2"></div>
                    <p className="text-sm text-gray-500 dark:text-gray-400">生成可视化中...</p>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default VisualizationTab;
