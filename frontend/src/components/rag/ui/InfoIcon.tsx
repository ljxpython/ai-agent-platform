import React from 'react';
import { InfoCircleOutlined } from '@ant-design/icons';
import { Tooltip } from 'antd';

interface InfoIconProps {
  tooltip?: string;
  size?: number;
  className?: string;
  color?: string;
}

export const InfoIcon: React.FC<InfoIconProps> = ({
  tooltip,
  size = 16,
  className = '',
  color = '#1890ff',
}) => {
  const icon = (
    <InfoCircleOutlined
      style={{
        fontSize: size,
        color,
        cursor: tooltip ? 'help' : 'default'
      }}
      className={className}
    />
  );

  if (tooltip) {
    return (
      <Tooltip title={tooltip}>
        {icon}
      </Tooltip>
    );
  }

  return icon;
};
