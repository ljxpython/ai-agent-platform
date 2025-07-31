import React from 'react';

interface ErrorMessageProps {
  error: string | null;
}

/**
 * 错误消息组件
 */
const ErrorMessage: React.FC<ErrorMessageProps> = ({ error }) => {
  if (!error) return null;

  return (
    <div className="text2sql-card" style={{ borderColor: '#fee2e2', backgroundColor: '#fef2f2' }}>
      <div className="text2sql-card-header" style={{ borderColor: '#fee2e2', backgroundColor: '#fff1f2' }}>
        <div className="text2sql-card-title">
          <div className="text2sql-card-icon" style={{ backgroundColor: 'rgba(239, 68, 68, 0.1)' }}>
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
              style={{ color: '#ef4444' }}
            >
              <circle cx="12" cy="12" r="10"></circle>
              <line x1="12" y1="8" x2="12" y2="12"></line>
              <line x1="12" y1="16" x2="12" y2="16"></line>
            </svg>
          </div>
          <span style={{ color: '#b91c1c' }}>请求处理出错</span>
        </div>
      </div>
      <div className="text2sql-card-content">
        <p className="mb-3" style={{ color: '#b91c1c' }}>{error}</p>
        <p className="text-sm" style={{ color: '#ef4444' }}>
          请检查网络连接或稍后再试。如果问题持续存在，请联系管理员。
        </p>
      </div>
    </div>
  );
};

export default ErrorMessage;
