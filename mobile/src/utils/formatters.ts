// mobile/src/utils/formatters.ts
// 格式化工具函数

import { ColorScheme } from '../theme';
import { Task, WorkflowRun } from '../types';

/**
 * 格式化日期
 */
export const formatDate = (date: Date | string): string => {
  const d = typeof date === 'string' ? new Date(date) : date;
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  if (d.toDateString() === today.toDateString()) {
    return d.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  if (d.toDateString() === yesterday.toDateString()) {
    return 'Yesterday';
  }

  return d.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  });
};

/**
 * 格式化时间差
 */
export const formatTimeAgo = (date: Date | string): string => {
  const d = typeof date === 'string' ? new Date(date) : date;
  const now = new Date();
  const seconds = Math.floor((now.getTime() - d.getTime()) / 1000);

  if (seconds < 60) {
    return 'just now';
  }

  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) {
    return `${minutes}m ago`;
  }

  const hours = Math.floor(minutes / 60);
  if (hours < 24) {
    return `${hours}h ago`;
  }

  const days = Math.floor(hours / 24);
  if (days < 7) {
    return `${days}d ago`;
  }

  return d.toLocaleDateString();
};

/**
 * 格式化持续时间
 */
export const formatDuration = (milliseconds: number): string => {
  const seconds = Math.floor(milliseconds / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);

  if (hours > 0) {
    return `${hours}h ${minutes % 60}m`;
  }

  if (minutes > 0) {
    return `${minutes}m ${seconds % 60}s`;
  }

  return `${seconds}s`;
};

/**
 * 获取状态颜色
 */
export const getStatusColor = (
  status: Task['status'] | WorkflowRun['status'],
  theme: ColorScheme
): string => {
  switch (status) {
    case 'pending':
      return theme.warning;
    case 'running':
      return theme.info;
    case 'completed':
      return theme.success;
    case 'failed':
      return theme.error;
    default:
      return theme.textTertiary;
  }
};

/**
 * 获取优先级颜色
 */
export const getPriorityColor = (
  priority: Task['priority'],
  theme: ColorScheme
): string => {
  switch (priority) {
    case 'high':
      return theme.error;
    case 'medium':
      return theme.warning;
    case 'low':
      return theme.success;
    default:
      return theme.textTertiary;
  }
};

/**
 * 格式化文件大小
 */
export const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 B';

  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
};

/**
 * 格式化百分比
 */
export const formatPercentage = (value: number, decimals: number = 0): string => {
  return (Math.round(value * Math.pow(10, decimals)) / Math.pow(10, decimals)).toFixed(
    decimals
  ) + '%';
};

/**
 * 截断文本
 */
export const truncateText = (text: string, maxLength: number): string => {
  if (text.length <= maxLength) {
    return text;
  }
  return text.substring(0, maxLength - 3) + '...';
};

/**
 * 首字母大写
 */
export const capitalize = (text: string): string => {
  return text.charAt(0).toUpperCase() + text.slice(1);
};

/**
 * 格式化JSON
 */
export const formatJSON = (obj: any, indent: number = 2): string => {
  try {
    return JSON.stringify(obj, null, indent);
  } catch (error) {
    return 'Invalid JSON';
  }
};

/**
 * 解析JSON
 */
export const parseJSON = <T = any>(json: string, defaultValue?: T): T | undefined => {
  try {
    return JSON.parse(json);
  } catch (error) {
    return defaultValue;
  }
};

/**
 * 格式化错误消息
 */
export const formatErrorMessage = (error: any): string => {
  if (typeof error === 'string') {
    return error;
  }

  if (error?.message) {
    return error.message;
  }

  if (error?.error?.message) {
    return error.error.message;
  }

  return 'An unknown error occurred';
};

/**
 * 格式化API响应
 */
export const formatApiResponse = (response: any): string => {
  if (response?.data?.message) {
    return response.data.message;
  }

  if (response?.message) {
    return response.message;
  }

  return 'Request completed';
};
