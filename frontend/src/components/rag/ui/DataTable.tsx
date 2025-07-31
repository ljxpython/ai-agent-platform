import React, { useState, useMemo } from 'react';
import { Table, Input, Button, Space, Pagination } from 'antd';
import { SearchOutlined, FilterOutlined } from '@ant-design/icons';
import type { ColumnsType, TableProps } from 'antd/es/table';
import { SortCriteria, FilterCriteria, TableProps as CustomTableProps } from '@/types/rag';

interface DataTableProps<T extends Record<string, any>> extends CustomTableProps<T> {
  loading?: boolean;
  rowKey?: string | ((record: T) => string);
  size?: 'small' | 'middle' | 'large';
  bordered?: boolean;
  showHeader?: boolean;
  scroll?: { x?: number; y?: number };
  expandable?: TableProps<T>['expandable'];
}

export function DataTable<T extends Record<string, any>>({
  data,
  columns,
  initialSort,
  initialFilters = {},
  onRowSelect,
  pagination,
  loading = false,
  rowKey = 'id',
  size = 'middle',
  bordered = false,
  showHeader = true,
  scroll,
  expandable,
}: DataTableProps<T>) {
  const [sortCriteria, setSortCriteria] = useState<SortCriteria<T> | null>(initialSort || null);
  const [filters, setFilters] = useState<FilterCriteria>(initialFilters);
  const [searchText, setSearchText] = useState('');
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);
  const [currentPage, setCurrentPage] = useState(pagination?.initialPage || 1);

  // 处理搜索
  const filteredData = useMemo(() => {
    let result = [...data];

    // 全局搜索
    if (searchText) {
      result = result.filter(item =>
        Object.values(item).some(value =>
          String(value).toLowerCase().includes(searchText.toLowerCase())
        )
      );
    }

    // 列过滤
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        result = result.filter(item => {
          const itemValue = item[key];
          if (typeof value === 'string') {
            return String(itemValue).toLowerCase().includes(value.toLowerCase());
          }
          return itemValue === value;
        });
      }
    });

    return result;
  }, [data, searchText, filters]);

  // 处理排序
  const sortedData = useMemo(() => {
    if (!sortCriteria) return filteredData;

    return [...filteredData].sort((a, b) => {
      const aValue = a[sortCriteria.key];
      const bValue = b[sortCriteria.key];

      if (aValue === bValue) return 0;

      let comparison = 0;
      if (aValue > bValue) comparison = 1;
      if (aValue < bValue) comparison = -1;

      return sortCriteria.order === 'desc' ? -comparison : comparison;
    });
  }, [filteredData, sortCriteria]);

  // 分页数据
  const paginatedData = useMemo(() => {
    if (!pagination) return sortedData;

    const { itemsPerPage } = pagination;
    const startIndex = (currentPage - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;

    return sortedData.slice(startIndex, endIndex);
  }, [sortedData, currentPage, pagination]);

  // 转换列定义
  const antdColumns: ColumnsType<T> = useMemo(() => {
    return columns.map(column => ({
      title: column.label,
      dataIndex: column.key as string,
      key: column.key as string,
      sorter: column.sortable ? {
        compare: (a: T, b: T) => {
          const aValue = a[column.key];
          const bValue = b[column.key];
          if (aValue === bValue) return 0;
          return aValue > bValue ? 1 : -1;
        },
      } : false,
      sortOrder: sortCriteria?.key === column.key ?
        (sortCriteria.order === 'asc' ? 'ascend' : 'descend') : null,
      filterDropdown: column.filterable ? ({ setSelectedKeys, selectedKeys, confirm, clearFilters }) => (
        <div style={{ padding: 8 }}>
          <Input
            placeholder={`搜索 ${column.label}`}
            value={selectedKeys[0]}
            onChange={e => setSelectedKeys(e.target.value ? [e.target.value] : [])}
            onPressEnter={() => confirm()}
            style={{ marginBottom: 8, display: 'block' }}
          />
          <Space>
            <Button
              type="primary"
              onClick={() => confirm()}
              icon={<SearchOutlined />}
              size="small"
              style={{ width: 90 }}
            >
              搜索
            </Button>
            <Button
              onClick={() => {
                clearFilters?.();
                setFilters((prev: FilterCriteria) => ({ ...prev, [column.key]: undefined }));
              }}
              size="small"
              style={{ width: 90 }}
            >
              重置
            </Button>
          </Space>
        </div>
      ) : undefined,
      filterIcon: column.filterable ? (filtered: boolean) => (
        <FilterOutlined style={{ color: filtered ? '#1890ff' : undefined }} />
      ) : undefined,
      onFilter: column.filterable ? (value, record) => {
        const recordValue = record[column.key];
        return String(recordValue).toLowerCase().includes(String(value).toLowerCase());
      } : undefined,
      render: column.render ? (_value: any, record: T) =>
        column.render!(record) : undefined,
    }));
  }, [columns, sortCriteria, filters]);

  // 行选择配置
  const rowSelection = onRowSelect ? {
    selectedRowKeys,
    onChange: (newSelectedRowKeys: React.Key[]) => {
      setSelectedRowKeys(newSelectedRowKeys);
      onRowSelect(newSelectedRowKeys.map(key => String(key)));
    },
    onSelectAll: (selected: boolean) => {
      const keys = selected ?
        data.map(item => typeof rowKey === 'function' ? rowKey(item) : item[rowKey]) :
        [];
      setSelectedRowKeys(keys);
      onRowSelect(keys.map(key => String(key)));
    },
  } : undefined;

  // 处理表格变化
  const handleTableChange = (_paginationInfo: any, filters: any, sorter: any) => {
    // 处理排序
    if (sorter.order) {
      setSortCriteria({
        key: sorter.field,
        order: sorter.order === 'ascend' ? 'asc' : 'desc',
      });
    } else {
      setSortCriteria(null);
    }

    // 处理过滤
    const newFilters: FilterCriteria = {};
    Object.entries(filters).forEach(([key, value]) => {
      if (value && Array.isArray(value) && value.length > 0) {
        newFilters[key] = value[0];
      }
    });
    setFilters(newFilters);
  };

  return (
    <div>
      {/* 全局搜索 */}
      <div style={{ marginBottom: 16 }}>
        <Input.Search
          placeholder="全局搜索..."
          value={searchText}
          onChange={e => setSearchText(e.target.value)}
          onSearch={setSearchText}
          style={{ width: 300 }}
          allowClear
        />
      </div>

      {/* 表格 */}
      <Table<T>
        columns={antdColumns}
        dataSource={pagination ? paginatedData : sortedData}
        rowKey={rowKey}
        rowSelection={rowSelection}
        loading={loading}
        size={size}
        bordered={bordered}
        showHeader={showHeader}
        scroll={scroll}
        expandable={expandable}
        pagination={false} // 使用自定义分页
        onChange={handleTableChange}
      />

      {/* 自定义分页 */}
      {pagination && (
        <div style={{ marginTop: 16, textAlign: 'right' }}>
          <Pagination
            current={currentPage}
            pageSize={pagination.itemsPerPage}
            total={sortedData.length}
            onChange={setCurrentPage}
            showSizeChanger={false}
            showQuickJumper
            showTotal={(total, range) =>
              `第 ${range[0]}-${range[1]} 条，共 ${total} 条`
            }
          />
        </div>
      )}

      {/* 选择信息 */}
      {onRowSelect && selectedRowKeys.length > 0 && (
        <div style={{ marginTop: 8 }}>
          已选择 {selectedRowKeys.length} 项
          <Button
            type="link"
            size="small"
            onClick={() => {
              setSelectedRowKeys([]);
              onRowSelect([]);
            }}
          >
            清空选择
          </Button>
        </div>
      )}
    </div>
  );
}
