export function LangGraphLogoSVG({
  className,
  width,
  height,
}: {
  width?: number;
  height?: number;
  className?: string;
}) {
  return (
    <svg
      width={width}
      height={height}
      viewBox="0 0 120 60"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      {/* 定义渐变 */}
      <defs>
        <linearGradient id="bgGradient" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" style={{ stopColor: "#1e3a8a", stopOpacity: 1 }} />
          <stop offset="100%" style={{ stopColor: "#3b82f6", stopOpacity: 1 }} />
        </linearGradient>
        <linearGradient id="accentGradient" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" style={{ stopColor: "#60a5fa", stopOpacity: 1 }} />
          <stop offset="100%" style={{ stopColor: "#3b82f6", stopOpacity: 1 }} />
        </linearGradient>
      </defs>

      {/* 主背景 */}
      <rect
        x="2"
        y="2"
        width="116"
        height="56"
        rx="28"
        fill="url(#bgGradient)"
        stroke="#1e40af"
        strokeWidth="1"
        opacity="0.95"
      />

      {/* 内层装饰边框 */}
      <rect
        x="6"
        y="6"
        width="108"
        height="48"
        rx="24"
        fill="none"
        stroke="#60a5fa"
        strokeWidth="0.5"
        opacity="0.3"
      />

      {/* 混合云图标 - 左侧云朵 */}
      <path
        d="M22 25 C19 25 17 27 17 30 C17 33 19 35 22 35 C23 35 24 34.5 24.5 34 C25.5 35 27 35 28 34 C29 33 29 31 28 30 C28 28 26.5 26.5 25 26 C25 24 23 22 21 22 C19 22 17 24 17 26 C17 28 19 30 21 30 Z"
        fill="#60a5fa"
        opacity="0.9"
      />

      {/* 边缘计算图标 - 右侧节点 */}
      <circle cx="98" cy="30" r="6" fill="none" stroke="#60a5fa" strokeWidth="2" opacity="0.9" />
      <circle cx="98" cy="30" r="2" fill="#60a5fa" opacity="0.9" />

      {/* 连接线 */}
      <line
        x1="55"
        y1="30"
        x2="85"
        y2="30"
        stroke="#60a5fa"
        strokeWidth="1"
        opacity="0.6"
        strokeDasharray="3,2"
      />

      {/* 小点装饰 */}
      <circle cx="70" cy="25" r="1" fill="#60a5fa" opacity="0.7" />
      <circle cx="70" cy="35" r="1" fill="#60a5fa" opacity="0.7" />

      {/* 中间分隔线 - 使用渐变 */}
      <line
        x1="60"
        y1="16"
        x2="60"
        y2="44"
        stroke="url(#accentGradient)"
        strokeWidth="1.5"
        opacity="0.7"
      />

      {/* 顶部装饰线 */}
      <line
        x1="30"
        y1="12"
        x2="90"
        y2="12"
        stroke="#60a5fa"
        strokeWidth="0.8"
        opacity="0.4"
      />

      {/* 底部装饰线 */}
      <line
        x1="30"
        y1="48"
        x2="90"
        y2="48"
        stroke="#60a5fa"
        strokeWidth="0.8"
        opacity="0.4"
      />
    </svg>
  );
}
// FIXME  MS8yOmFIVnBZMlhtblk3a3ZiUG1yS002VmpCQlNnPT06ODUzNTZjYjE=
