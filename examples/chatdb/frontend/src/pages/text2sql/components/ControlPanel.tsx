import React from 'react';
import { Switch, Tooltip, Dropdown, Menu } from 'antd';
import { BulbOutlined, DatabaseOutlined, DownOutlined } from '@ant-design/icons';

interface Connection {
  id: number;
  name: string;
  type: string;
  host: string;
  port: number;
  username: string;
  database: string;
  created_at: string;
  updated_at: string;
}

interface ControlPanelProps {
  query: string;
  setQuery: (query: string) => void;
  loading: boolean;
  handleSearch: () => void;
  handleKeyDown: (e: React.KeyboardEvent<HTMLInputElement>) => void;
  selectedConnectionId: number | null;
  onShowExamples?: () => void;
  hybridRetrievalEnabled?: boolean;
  // 新增的props
  connections: Connection[];
  setSelectedConnectionId: (id: number) => void;
  loadingConnections: boolean;
  setHybridRetrievalEnabled: (enabled: boolean) => void;
}

/**
 * 底部控制面板组件
 */
const ControlPanel: React.FC<ControlPanelProps> = ({
  query,
  setQuery,
  loading,
  selectedConnectionId,
  handleSearch,
  handleKeyDown,
  onShowExamples,
  hybridRetrievalEnabled = true,
  connections,
  setSelectedConnectionId,
  loadingConnections,
  setHybridRetrievalEnabled,
}) => {
  // 获取当前选中的连接信息
  const selectedConnection = connections.find(conn => conn.id === selectedConnectionId);

  // 数据库连接下拉菜单
  const connectionMenu = (
    <Menu
      onClick={({ key }) => setSelectedConnectionId(Number(key))}
      selectedKeys={selectedConnectionId ? [selectedConnectionId.toString()] : []}
    >
      {connections.map(connection => (
        <Menu.Item key={connection.id}>
          <div className="connection-menu-item">
            <DatabaseOutlined style={{ marginRight: 8, color: '#1a73e8' }} />
            <div>
              <div className="connection-name">{connection.name}</div>
              <div className="connection-info">{connection.type} - {connection.host}</div>
            </div>
          </div>
        </Menu.Item>
      ))}
    </Menu>
  );
  return (
    <div className="gemini-input-container">
      <div className="gemini-input-box">
        {/* 左侧控制按钮组 */}
        <div className="left-controls">
          {/* 智能推荐按钮 */}
          <Tooltip title={hybridRetrievalEnabled ? "智能推荐已启用" : "智能推荐已禁用"}>
            <button
              className={`control-button ${hybridRetrievalEnabled ? 'active' : ''}`}
              onClick={() => setHybridRetrievalEnabled(!hybridRetrievalEnabled)}
              disabled={loading}
            >
              <BulbOutlined />
            </button>
          </Tooltip>
        </div>

        {/* 输入框 */}
        <div className="input-wrapper">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="向佳欣智能提问"
            className="gemini-input"
            disabled={loading}
          />
        </div>

        {/* 右侧按钮组 */}
        <div className="right-controls">
          {/* 智能示例按钮 */}
          {hybridRetrievalEnabled && onShowExamples && (
            <Tooltip title="查看智能推荐示例">
              <button
                onClick={onShowExamples}
                disabled={loading || query.trim() === '' || !selectedConnectionId}
                className="control-button"
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M9 11H5a2 2 0 0 0-2 2v3a2 2 0 0 0 2 2h4"/>
                  <path d="M15 11h4a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2h-4"/>
                  <path d="M12 2v20"/>
                  <circle cx="12" cy="8" r="2"/>
                </svg>
              </button>
            </Tooltip>
          )}

          {/* 发送按钮 */}
          <Tooltip title="发送查询">
            <button
              onClick={handleSearch}
              disabled={loading || query.trim() === '' || !selectedConnectionId}
              className="send-button"
            >
              {loading ? (
                <svg className="animate-spin" width="20" height="20" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
              ) : (
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="m22 2-7 20-4-9-9-4Z"/>
                  <path d="M22 2 11 13"/>
                </svg>
              )}
            </button>
          </Tooltip>
        </div>
      </div>
    </div>
  );
};

export default ControlPanel;
