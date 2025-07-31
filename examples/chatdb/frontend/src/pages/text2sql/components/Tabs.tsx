import React from 'react';

interface TabsProps {
  value: number;
  onChange: (newValue: number) => void;
  tabs: {
    label: string;
    icon: React.ReactNode;
    hasContent: boolean;
    isStreaming?: boolean;
  }[];
}

/**
 * 标签组件
 */
const Tabs: React.FC<TabsProps> = ({ value, onChange, tabs }) => {
  return (
    <div className="text2sql-tabs">
      <div className="text2sql-tabs-list">
        {tabs.map((tab, index) => (
          <button
            key={index}
            className={`text2sql-tab ${value === index ? 'text2sql-tab-active' : ''} ${tab.hasContent ? 'text2sql-tab-has-content' : ''}`}
            onClick={() => onChange(index)}
            role="tab"
            aria-selected={value === index}
            id={`tab-${index}`}
            aria-controls={`tabpanel-${index}`}
          >
            <span className="text2sql-tab-icon">{tab.icon}</span>
            <span className="text2sql-tab-label">{tab.label}</span>
            {tab.isStreaming && (
              <span className="text2sql-tab-streaming-indicator"></span>
            )}
          </button>
        ))}
      </div>
    </div>
  );
};

export default Tabs;
