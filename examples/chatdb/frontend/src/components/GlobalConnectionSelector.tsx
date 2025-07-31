import React, { useState, useEffect } from 'react';
import { Select, Spin } from 'antd';
import { DatabaseOutlined } from '@ant-design/icons';
import '../styles/GlobalConnectionSelector.css';

const { Option } = Select;

interface Connection {
  id: number;
  name: string;
  type: string;
  database: string;
}

interface GlobalConnectionSelectorProps {
  selectedConnectionId: number | null;
  setSelectedConnectionId: (id: number | null) => void;
}

const GlobalConnectionSelector: React.FC<GlobalConnectionSelectorProps> = ({
  selectedConnectionId,
  setSelectedConnectionId
}) => {
  const [connections, setConnections] = useState<Connection[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  // 获取连接列表
  useEffect(() => {
    const fetchConnections = async () => {
      try {
        // 这里应该调用实际的API
        // 为了演示，我们使用setTimeout模拟API调用
        setTimeout(() => {
          // 模拟数据
          const mockConnections = [
            { id: 1, name: '测试连接1', type: 'MySQL', database: 'test_db' },
            { id: 2, name: '生产数据库', type: 'PostgreSQL', database: 'prod_db' },
            { id: 3, name: '开发环境', type: 'SQLite', database: 'dev_db' }
          ];
          setConnections(mockConnections);
          setLoading(false);
        }, 500);
      } catch (error) {
        console.error('获取连接失败:', error);
        setLoading(false);
      }
    };

    fetchConnections();
  }, []);

  return (
    <div className="global-connection-selector">
      <Select
        placeholder="选择数据库连接"
        value={selectedConnectionId || undefined}
        onChange={(value) => setSelectedConnectionId(value ? Number(value) : null)}
        loading={loading}
        style={{ width: 220 }}
        dropdownMatchSelectWidth={false}
        suffixIcon={loading ? <Spin size="small" /> : <DatabaseOutlined />}
        className="connection-select"
      >
        {connections.map(conn => (
          <Option key={conn.id} value={conn.id}>
            {conn.name} ({conn.type})
          </Option>
        ))}
      </Select>
    </div>
  );
};

export default GlobalConnectionSelector;
