import React from 'react';

interface TabPanelProps {
  children: React.ReactNode;
  value: number;
  index: number;
}

/**
 * 标签面板组件，用于在标签切换时显示/隐藏内容
 */
const TabPanel: React.FC<TabPanelProps> = ({ children, value, index }) => {
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`tabpanel-${index}`}
      aria-labelledby={`tab-${index}`}
      className={`text2sql-tabpanel ${value === index ? 'active' : ''}`}
      style={{
        display: value === index ? 'block' : 'none',
        height: '100%',
        overflow: 'auto'
      }}
    >
      {value === index && children}
    </div>
  );
};

export default TabPanel;
