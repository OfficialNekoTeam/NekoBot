import React from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Box, ThemeProvider, createTheme } from '@mui/material';

import { useAuth } from '../../context/useAuth';
import Sidebar from '../Sidebar/Sidebar';
import TopNav from '../TopNav/TopNav';

// 创建主题
const darkTheme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#6366f1', // indigo-500 - berry风格主色
    },
    secondary: {
      main: '#8b5cf6', // purple-500 - berry风格次色
    },
    background: {
      default: '#111827', // 深色背景
      paper: '#1f2937', // 卡片背景
    },
    text: {
      primary: '#f9fafb',
      secondary: '#9ca3af',
    },
  },
  shape: {
    borderRadius: 12,
  },
  typography: {
    fontFamily: 'system-ui, Avenir, Helvetica, Arial, sans-serif',
  },
});

const lightTheme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#6366f1', // indigo-500 - berry风格主色
    },
    secondary: {
      main: '#8b5cf6', // purple-500 - berry风格次色
    },
    background: {
      default: '#f9fafb', // 浅色背景
      paper: '#ffffff', // 卡片背景
    },
    text: {
      primary: '#1f2937',
      secondary: '#6b7280',
    },
  },
  shape: {
    borderRadius: 12,
  },
  typography: {
    fontFamily: 'system-ui, Avenir, Helvetica, Arial, sans-serif',
  },
});

interface LayoutProps {
  darkMode?: boolean;
  onDarkModeChange?: (darkMode: boolean) => void;
}

const Layout: React.FC<LayoutProps> = ({ darkMode = true, onDarkModeChange }) => {
  const { isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  // 路由守卫：如果未登录且不在登录页，则跳转到登录页
  React.useEffect(() => {
    if (!isAuthenticated && location.pathname !== '/auth/login') {
      navigate('/auth/login');
    }
  }, [isAuthenticated, location.pathname, navigate]);

  return (
    <ThemeProvider theme={darkMode ? darkTheme : lightTheme}>
      <Box sx={{ display: 'flex' }}>
        {/* 顶部导航 */}
        <TopNav darkMode={darkMode} onDarkModeChange={onDarkModeChange} />
        
        {/* 侧边栏 */}
        <Sidebar />
        
        {/* 主内容区域 */}
        <Box
          component="main"
          sx={{
            flexGrow: 1,
            pt: '64px',
            px: 3,
            pb: 3,
            transition: (theme) => theme.transitions.create('margin', {
              easing: theme.transitions.easing.sharp,
              duration: theme.transitions.duration.leavingScreen,
            }),
          }}
        >
          {/* 内容区域 */}
          <Outlet />
        </Box>
      </Box>
    </ThemeProvider>
  );
};

export default Layout;
