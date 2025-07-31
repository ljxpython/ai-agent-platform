import React from 'react';
import '../../../styles/ConnectionSelector.css';

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

interface ConnectionSelectorProps {
  connections: Connection[];
  selectedConnectionId: number | null;
  setSelectedConnectionId: (id: number | null) => void;
  loadingConnections: boolean;
  disabled?: boolean;
  userFeedbackEnabled?: boolean;
  setUserFeedbackEnabled?: (enabled: boolean) => void;
}

/**
 * 数据库连接选择器组件 - 用于页面右上角
 */
const ConnectionSelector: React.FC<ConnectionSelectorProps> = ({
  connections,
  selectedConnectionId,
  setSelectedConnectionId,
  loadingConnections,
  disabled = false,
  userFeedbackEnabled = false,
  setUserFeedbackEnabled
}) => {
  return (
    <div className="text2sql-connection-selector">
      <div className="text2sql-db-select-wrapper">
        <div className="text2sql-db-select-icon">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <ellipse cx="12" cy="5" rx="9" ry="3"></ellipse>
            <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"></path>
            <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"></path>
          </svg>
        </div>
        <select
          value={selectedConnectionId || ''}
          onChange={(e) => setSelectedConnectionId(e.target.value ? Number(e.target.value) : null)}
          className="text2sql-db-select"
          disabled={disabled || loadingConnections}
        >
          <option value="">请选择数据库连接</option>
          {connections.map(conn => (
            <option key={conn.id} value={conn.id}>{conn.name} ({conn.type} - {conn.database})</option>
          ))}
        </select>
        <div className="text2sql-db-select-arrow">
          <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="6 9 12 15 18 9"></polyline>
          </svg>
        </div>
        {loadingConnections && <div className="text-xs text-gray-500 absolute -bottom-5 left-0">加载中...</div>}
      </div>

      {/* 用户反馈复选框 */}
      {setUserFeedbackEnabled && (
        <div className="text2sql-feedback-checkbox">
          <label className="feedback-checkbox-label">
            <input
              type="checkbox"
              checked={userFeedbackEnabled}
              onChange={(e) => setUserFeedbackEnabled(e.target.checked)}
              disabled={disabled}
              className="feedback-checkbox-input"
            />
            <span className="feedback-checkbox-text">用户反馈</span>
          </label>
        </div>
      )}
    </div>
  );
};

export default ConnectionSelector;
