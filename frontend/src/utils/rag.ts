import { type ClassValue, clsx } from 'clsx';
import { v5 as uuidv5 } from 'uuid';

// Utility function for combining class names (replacing Tailwind's cn function)
export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}

// Status color mapping for Ant Design
export const getStatusColor = (status: string): string => {
  switch (status.toLowerCase()) {
    case 'success':
      return 'success';
    case 'failed':
    case 'error':
      return 'error';
    case 'pending':
    case 'processing':
      return 'processing';
    case 'warning':
      return 'warning';
    default:
      return 'default';
  }
};

// Status tag color mapping
export const getStatusTagColor = (status: string): string => {
  switch (status.toLowerCase()) {
    case 'success':
      return 'green';
    case 'failed':
    case 'error':
      return 'red';
    case 'pending':
      return 'orange';
    case 'processing':
      return 'blue';
    case 'warning':
      return 'yellow';
    default:
      return 'default';
  }
};

// URL validation
export const isValidUrl = (value: string): boolean => {
  const urlPattern = new RegExp(
    '^https?:\\/\\/' + // must start with http:// or https://
      '((([a-zA-Z0-9-_]+\\.)+[a-zA-Z]{2,})|((\\d{1,3}\\.){3}\\d{1,3}))' + // domain name or IP address
      '(\\:\\d+)?' + // optional port
      '(\\/.*)?' + // optional path
      '$' // end of string
  );
  return urlPattern.test(value);
};

// String utilities
export const capitalizeFirstLetter = (string: string): string => {
  if (!string) {
    return string;
  }
  return string.charAt(0).toUpperCase() + string.slice(1);
};

// Generate ID from label
export function generateIdFromLabel(label: string): string {
  const NAMESPACE_DNS = '6ba7b810-9dad-11d1-80b4-00c04fd430c8'; // UUID for DNS namespace
  return uuidv5(label, NAMESPACE_DNS);
}

// Format file size
export function formatFileSize(bytes: number | undefined): string {
  if (bytes === undefined || isNaN(bytes)) {
    return 'N/A';
  }

  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let size = bytes;
  let unitIndex = 0;

  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex++;
  }

  return `${size.toFixed(2)} ${units[unitIndex]}`;
}

// Format date
export function formatDate(dateString: string): string {
  try {
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
  } catch {
    return dateString;
  }
}

// Format relative time
export function formatRelativeTime(dateString: string): string {
  try {
    const date = new Date(dateString);
    const now = new Date();
    const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);

    if (diffInSeconds < 60) {
      return `${diffInSeconds}秒前`;
    } else if (diffInSeconds < 3600) {
      return `${Math.floor(diffInSeconds / 60)}分钟前`;
    } else if (diffInSeconds < 86400) {
      return `${Math.floor(diffInSeconds / 3600)}小时前`;
    } else {
      return `${Math.floor(diffInSeconds / 86400)}天前`;
    }
  } catch {
    return dateString;
  }
}

// Debounce function
export function debounce<T extends (...args: any[]) => any>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: NodeJS.Timeout;
  return (...args: Parameters<T>) => {
    clearTimeout(timeout);
    timeout = setTimeout(() => func(...args), wait);
  };
}

// Throttle function
export function throttle<T extends (...args: any[]) => any>(
  func: T,
  limit: number
): (...args: Parameters<T>) => void {
  let inThrottle: boolean;
  return (...args: Parameters<T>) => {
    if (!inThrottle) {
      func(...args);
      inThrottle = true;
      setTimeout(() => (inThrottle = false), limit);
    }
  };
}

// Parse JSON safely
export function safeJsonParse(jsonString: string, defaultValue: any = null): any {
  try {
    return JSON.parse(jsonString);
  } catch {
    return defaultValue;
  }
}

// Truncate text
export function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) {
    return text;
  }
  return text.substring(0, maxLength) + '...';
}

// Generate random color
export function generateRandomColor(): string {
  const colors = [
    '#1890ff', '#52c41a', '#faad14', '#f5222d', '#722ed1',
    '#13c2c2', '#eb2f96', '#fa541c', '#a0d911', '#2f54eb'
  ];
  return colors[Math.floor(Math.random() * colors.length)];
}

// Validate email
export function isValidEmail(email: string): boolean {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
}

// Extract file extension
export function getFileExtension(filename: string): string {
  return filename.split('.').pop()?.toLowerCase() || '';
}

// Check if file type is supported
export function isSupportedFileType(filename: string): boolean {
  const supportedTypes = ['pdf', 'txt', 'doc', 'docx', 'md', 'html', 'csv', 'json'];
  const extension = getFileExtension(filename);
  return supportedTypes.includes(extension);
}

// Format number with commas
export function formatNumber(num: number): string {
  return num.toLocaleString();
}

// Generate UUID
export function generateUUID(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    const r = Math.random() * 16 | 0;
    const v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}

// Deep clone object
export function deepClone<T>(obj: T): T {
  if (obj === null || typeof obj !== 'object') {
    return obj;
  }

  if (obj instanceof Date) {
    return new Date(obj.getTime()) as unknown as T;
  }

  if (obj instanceof Array) {
    return obj.map(item => deepClone(item)) as unknown as T;
  }

  if (typeof obj === 'object') {
    const clonedObj = {} as T;
    for (const key in obj) {
      if (obj.hasOwnProperty(key)) {
        clonedObj[key] = deepClone(obj[key]);
      }
    }
    return clonedObj;
  }

  return obj;
}

// Check if object is empty
export function isEmpty(obj: any): boolean {
  if (obj === null || obj === undefined) {
    return true;
  }

  if (typeof obj === 'string' || Array.isArray(obj)) {
    return obj.length === 0;
  }

  if (typeof obj === 'object') {
    return Object.keys(obj).length === 0;
  }

  return false;
}

// Convert bytes to human readable format
export function bytesToSize(bytes: number): string {
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
  if (bytes === 0) return '0 Byte';
  const i = parseInt(Math.floor(Math.log(bytes) / Math.log(1024)).toString());
  return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i];
}

// Sleep function
export function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}
