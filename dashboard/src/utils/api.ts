/**
 * API工具类
 *
 * 提供统一的API调用接口
 */
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:6285';

class ApiClient {
  private baseUrl: string;
  private token: string | null;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
    this.token = localStorage.getItem('token');
  }

  setToken(token: string) {
    this.token = token;
    localStorage.setItem('token', token);
  }

  clearToken() {
    this.token = null;
    localStorage.removeItem('token');
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    };

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.message || '请求失败');
    }

    return response.json();
  }

  async get<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'GET' });
  }

  async post<T>(endpoint: string, data: unknown): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async put<T>(endpoint: string, data: unknown): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async delete<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'DELETE' });
  }
}

export const apiClient = new ApiClient();

export interface ApiResponse<T = unknown> {
  status: 'success' | 'error';
  message: string;
  data?: T;
}

export interface BotConfig {
  command_prefix: string;
  server: {
    host: string;
    port: number;
  };
  jwt: {
    secret_key: string;
    algorithm: string;
    access_token_expire_minutes: number;
  };
  demo: boolean;
  platforms: Record<string, unknown>;
}

export interface PluginInfo {
  name: string;
  version: string;
  description: string;
  author: string;
  enabled: boolean;
  commands: string[];
  is_official: boolean;
}

export interface Personality {
  id: string;
  name: string;
  description: string;
  prompt: string;
  enabled: boolean;
  created_at: string;
  updated_at?: string;
}

export interface McpConfig {
  id: string;
  name: string;
  type: string;
  config: Record<string, unknown>;
  enabled: boolean;
  created_at: string;
  updated_at?: string;
}

export interface LlmProvider {
  id: string;
  name: string;
  type: string;
  api_key: string;
  base_url: string;
  model: string;
  enabled: boolean;
  created_at: string;
  updated_at?: string;
}

export interface Settings {
  theme: string;
  language: string;
  notifications: {
    enabled: boolean;
    types: string[];
  };
  auto_restart: boolean;
}

export interface LogFile {
  name: string;
  size: number;
  modified: string;
}

export interface LogContent {
  file: string;
  content: string;
  lines: number;
}

export interface SystemStats {
  cpuUsage: number;
  memoryUsage: number;
  pluginsCount: number;
  enabledPluginsCount: number;
  adaptersCount: number;
  runningAdaptersCount: number;
}

export interface MessageStat {
  platform: string;
  messages: number;
  trend: 'up' | 'down';
  change: number;
}

export interface DashboardStats {
  system: SystemStats;
  messages: MessageStat[];
}
