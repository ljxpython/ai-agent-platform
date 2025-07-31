import React from 'react';

interface UserFeedbackProps {
  visible: boolean;
  message: string;
  promptMessage: string;
  setMessage: (message: string) => void;
  handleSubmit: () => void;
  handleApprove: () => void;
  handleCancel: () => void;
}

/**
 * 用户反馈组件
 */
const UserFeedback: React.FC<UserFeedbackProps> = ({
  visible,
  message,
  promptMessage,
  setMessage,
  handleSubmit,
  handleApprove,
  handleCancel
}) => {
  if (!visible) return null;

  return (
    <div className="text2sql-feedback-wrapper">
      <div className="text2sql-feedback-header">
        <div className="text2sql-feedback-title">
          <div className="text2sql-feedback-icon">
            <svg className="h-4 w-4" style={{ color: '#3b82f6' }} fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
            </svg>
          </div>
          <span>{promptMessage || '请提供您的反馈'}</span>
        </div>
        <button
          onClick={handleCancel}
          className="text2sql-feedback-close-button"
          aria-label="关闭"
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path>
          </svg>
        </button>
      </div>
      <div className="text2sql-feedback-content">
        <div className="text2sql-feedback-info">
          您的输入将发送到智能体进行处理。点击<strong style={{ color: '#2563eb' }}>发送</strong>提交您的自定义反馈，点击<strong style={{ color: '#059669' }}>同意</strong>快速批准操作。
        </div>
        <div className="relative">
          <div className="text2sql-input-wrapper">
            <svg className="text2sql-input-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6"></path>
            </svg>
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && e.ctrlKey) {
                  e.preventDefault();
                  handleSubmit();
                }
              }}
              placeholder="输入您的反馈... (Ctrl+Enter发送)"
              className="text2sql-feedback-input"
              autoFocus
              rows={3}
              style={{
                paddingLeft: '2.5rem',
                minHeight: '60px',
                resize: 'vertical'
              }}
            />
          </div>
        </div>
        <div className="text2sql-feedback-buttons">
          <button
            onClick={handleApprove}
            className="text2sql-feedback-button text2sql-feedback-button-approve"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path>
            </svg>
            同意
          </button>
          <button
            onClick={handleSubmit}
            disabled={!message.trim()}
            className={`text2sql-feedback-button ${
              !message.trim() ? '' : 'text2sql-feedback-button-submit'
            }`}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14 5l7 7m0 0l-7 7m7-7H3"></path>
            </svg>
            发送
          </button>
        </div>
      </div>
    </div>
  );
};

export default UserFeedback;
