/**
 * 纯函数：清洗终端 ANSI 转义字符与回车控制符
 * 用于将 Docker 容器后台任务的 stdout/stderr 日志安全转换为干净的纯文本
 */

// 匹配 CSI (\u001b[...m) 及各类标准 ANSI 转义码
const ANSI_REGEX =
  // eslint-disable-next-line no-control-regex
  /\u001b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])/g;

/**
 * 剥除 ANSI 转义序列，并将单独的 \r 回车符清洗
 */
export function stripAnsi(text: string): string {
  if (!text) return "";
  return text
    .replace(ANSI_REGEX, "")
    .replace(/\r\n/g, "\n")
    .replace(/\r/g, "\n");
}
