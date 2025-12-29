import React, { useState, useEffect } from 'react';
import type { ReactNode } from 'react';
import { AuthContext } from './AuthContextValue';

export interface User {
  username: string;
  email?: string;
  // 可以添加更多用户字段
}

export interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isDemo: boolean;
  login: (username: string, password: string, remember?: boolean) => Promise<boolean>;
  logout: () => void;
  changePassword: (oldPassword: string, newPassword: string) => Promise<boolean>;
}


interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isDemo, setIsDemo] = useState(false);

  const API_URL = import.meta.env.VITE_API_URL || '';

  // 检查本地存储中的用户信息
  useEffect(() => {
    const storedUser = localStorage.getItem('user');
    const storedToken = localStorage.getItem('token');
    
    if (storedUser && storedToken) {
      const userData = JSON.parse(storedUser);
      // 使用 setTimeout 避免同步调用 setState
      setTimeout(() => {
        setUser(userData);
        setIsAuthenticated(true);
      }, 0);
    }
    
    // 获取Demo模式状态
    const fetchConfig = async () => {
      try {
        const response = await fetch(`${API_URL}/api/config`);
        const data = await response.json();
        if (data.status === 'success') {
          setIsDemo(data.data.demo);
        }
      } catch (error) {
        console.error('获取配置失败:', error);
      }
    };
    
    // 使用 setTimeout 避免同步调用 setState
    setTimeout(() => {
      fetchConfig();
    }, 0);
  }, [API_URL]);

  const login = async (username: string, _password: string, remember: boolean = false): Promise<boolean> => {
    try {
      const response = await fetch(`${API_URL}/api/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username, password: _password }),
      });
      
      const data = await response.json();
      
      if (data.status === 'success') {
        const userData: User = { username: data.data.username };
        localStorage.setItem('user', JSON.stringify(userData));
        localStorage.setItem('token', data.data.access_token);
        
        setUser(userData);
        setIsAuthenticated(true);
        
        // 如果勾选了记住密码，保存凭证
        if (remember) {
          localStorage.setItem('remembered_credentials', JSON.stringify({ username, password: _password }));
        } else {
          // 如果没有勾选记住密码，清除之前保存的凭证
          localStorage.removeItem('remembered_credentials');
        }
        
        return true;
      }
      
      return false;
    } catch (error) {
      console.error('登录失败:', error);
      return false;
    }
  };

  const changePassword = async (oldPassword: string, newPassword: string): Promise<boolean> => {
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/api/change-password`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
      });
      
      const data = await response.json();
      return data.status === 'success';
    } catch (error) {
      console.error('修改密码失败:', error);
      return false;
    }
  };

  const logout = () => {
    localStorage.removeItem('user');
    localStorage.removeItem('token');
    localStorage.removeItem('remembered_credentials');
    setUser(null);
    setIsAuthenticated(false);
  };

  return (
    <AuthContext.Provider value={{ user, isAuthenticated, isDemo, login, logout, changePassword }}>
      {children}
    </AuthContext.Provider>
  );
};

