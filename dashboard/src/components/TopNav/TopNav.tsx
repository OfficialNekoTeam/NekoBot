import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AppBar,
  Box,
  Toolbar,
  IconButton,
  Typography,
  Menu,
  MenuItem,
  Avatar,
  Tooltip,
  ListItemText,
} from '@mui/material';
import {
  DarkMode as DarkModeIcon,
  LightMode as LightModeIcon,
  Notifications as NotificationsIcon,
  Language as LanguageIcon,
  Update as UpdateIcon,
} from '@mui/icons-material';
import { useAuth } from '../../context/useAuth';

interface TopNavProps {
  darkMode?: boolean;
  onDarkModeChange?: (darkMode: boolean) => void;
}

const TopNav: React.FC<TopNavProps> = ({ darkMode = true, onDarkModeChange }) => {
  const { user, logout, isDemo } = useAuth();
  const navigate = useNavigate();

  const [anchorElUser, setAnchorElUser] = React.useState<null | HTMLElement>(null);
  const [anchorElLanguage, setAnchorElLanguage] = React.useState<null | HTMLElement>(null);
  const [updateAvailable, setUpdateAvailable] = React.useState(false);

  React.useEffect(() => {
    setUpdateAvailable(true);
  }, []);

  const handleOpenUserMenu = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorElUser(event.currentTarget);
  };

  const handleOpenLanguageMenu = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorElLanguage(event.currentTarget);
  };

  const handleCloseUserMenu = () => {
    setAnchorElUser(null);
  };

  const handleCloseLanguageMenu = () => {
    setAnchorElLanguage(null);
  };

  const handleLogout = () => {
    logout();
    handleCloseUserMenu();
    navigate('/auth/login');
  };

  const handleChangePassword = () => {
    handleCloseUserMenu();
    navigate('/dashboard/change-password');
  };

  const handleDarkModeChange = () => {
    if (onDarkModeChange) {
      onDarkModeChange(!darkMode);
    }
  };

  return (
    <AppBar position="fixed" sx={{ zIndex: (theme) => theme.zIndex.drawer + 1 }}>
      <Toolbar>
        <Typography variant="h6" noWrap component="div" sx={{ flexGrow: 1, display: { xs: 'none', sm: 'block' } }}>
          NekoBot Dashboard
        </Typography>

        <Tooltip title="检查更新">
          <IconButton color="inherit">
            <UpdateIcon sx={updateAvailable ? { animation: 'pulse 2s infinite' } : {}} />
          </IconButton>
        </Tooltip>

        <Tooltip title="通知">
          <IconButton color="inherit">
            <NotificationsIcon />
          </IconButton>
        </Tooltip>

        <Tooltip title={darkMode ? "切换到浅色模式" : "切换到深色模式"}>
          <IconButton
            color="inherit"
            onClick={handleDarkModeChange}
            sx={{ p: 0.5 }}
          >
            {darkMode ? <LightModeIcon /> : <DarkModeIcon />}
          </IconButton>
        </Tooltip>

        <Tooltip title="语言">
          <IconButton onClick={handleOpenLanguageMenu} color="inherit">
            <LanguageIcon />
          </IconButton>
        </Tooltip>
        <Menu
          sx={{ mt: '45px' }}
          id="menu-appbar"
          anchorEl={anchorElLanguage}
          anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
          keepMounted
          transformOrigin={{ vertical: 'top', horizontal: 'right' }}
          open={Boolean(anchorElLanguage)}
          onClose={handleCloseLanguageMenu}
        >
          <MenuItem onClick={handleCloseLanguageMenu}>
            <ListItemText primary="中文" />
          </MenuItem>
          <MenuItem onClick={handleCloseLanguageMenu}>
            <ListItemText primary="English" />
          </MenuItem>
        </Menu>

        <Box sx={{ flexGrow: 0, ml: 2 }}>
          <Tooltip title="打开用户菜单">
            <IconButton onClick={handleOpenUserMenu} sx={{ p: 0 }}>
              <Avatar sx={{ bgcolor: darkMode ? '#6366f1' : '#6366f1' }}>
                {user?.username.charAt(0).toUpperCase()}
              </Avatar>
            </IconButton>
          </Tooltip>
          <Menu
            sx={{ mt: '45px' }}
            id="menu-appbar"
            anchorEl={anchorElUser}
            anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
            keepMounted
            transformOrigin={{ vertical: 'top', horizontal: 'right' }}
            open={Boolean(anchorElUser)}
            onClose={handleCloseUserMenu}
          >
            <MenuItem onClick={handleCloseUserMenu}>
              <ListItemText primary="个人信息" />
            </MenuItem>
            <MenuItem 
              onClick={handleChangePassword}
              disabled={isDemo}
              sx={isDemo ? { opacity: 0.5 } : {}}
            >
              <ListItemText primary="修改密码" />
            </MenuItem>
            <MenuItem onClick={handleLogout}>
              <ListItemText primary="退出登录" />
            </MenuItem>
            {isDemo && (
              <MenuItem disabled>
                <ListItemText 
                  primary="Demo模式" 
                  primaryTypographyProps={{ 
                    color: 'warning.main',
                    variant: 'caption' 
                  }} 
                />
              </MenuItem>
            )}
          </Menu>
        </Box>
      </Toolbar>
    </AppBar>
  );
};

export default TopNav;
