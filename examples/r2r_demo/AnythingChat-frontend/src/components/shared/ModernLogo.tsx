import React from 'react';

interface ModernLogoProps {
  className?: string;
  size?: 'sm' | 'md' | 'lg';
}

const ModernLogo: React.FC<ModernLogoProps> = ({
  className = '',
  size = 'md',
}) => {
  const sizeClasses = {
    sm: 'w-8 h-8',
    md: 'w-12 h-12',
    lg: 'w-16 h-16',
  };

  return (
    <div className={`${sizeClasses[size]} ${className} relative`}>
      <svg
        viewBox="0 0 100 100"
        className="w-full h-full"
        xmlns="http://www.w3.org/2000/svg"
      >
        <defs>
          <linearGradient id="logoGradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#667eea" />
            <stop offset="50%" stopColor="#764ba2" />
            <stop offset="100%" stopColor="#f093fb" />
          </linearGradient>
          <filter id="glow">
            <feGaussianBlur stdDeviation="3" result="coloredBlur" />
            <feMerge>
              <feMergeNode in="coloredBlur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* 外圆环 */}
        <circle
          cx="50"
          cy="50"
          r="45"
          fill="none"
          stroke="url(#logoGradient)"
          strokeWidth="3"
          className="animate-pulse"
        />

        {/* 内部图标 - 聊天气泡 */}
        <g filter="url(#glow)">
          {/* 主聊天气泡 */}
          <path
            d="M25 35 Q25 25 35 25 L65 25 Q75 25 75 35 L75 55 Q75 65 65 65 L45 65 L35 75 L35 65 Q25 65 25 55 Z"
            fill="url(#logoGradient)"
            className="animate-pulse"
          />

          {/* 小聊天气泡 */}
          <circle
            cx="70"
            cy="70"
            r="8"
            fill="url(#logoGradient)"
            opacity="0.8"
            className="animate-bounce"
          />

          {/* 聊天点 */}
          <circle cx="40" cy="45" r="3" fill="white" opacity="0.9" />
          <circle cx="50" cy="45" r="3" fill="white" opacity="0.9" />
          <circle cx="60" cy="45" r="3" fill="white" opacity="0.9" />
        </g>
      </svg>
    </div>
  );
};

export default ModernLogo;
