import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
  Typography,
  Divider,
  Box,
} from '@mui/material';
import {
  Dashboard as DashboardIcon,
  Chat as ChatIcon,
  Settings as SettingsIcon,
  Extension as ExtensionIcon,
  Computer as ComputerIcon,
  Person as PersonIcon,
  Code as CodeIcon,
  Description as DescriptionIcon,
  MoreHoriz as MoreIcon,
} from '@mui/icons-material';

interface MenuItem {
  text: string;
  icon: React.ReactNode;
  path: string;
}



const Sidebar: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = React.useState(false);
  const drawerWidth = 240;

  // 定义侧边栏菜单项
  const menuItems: MenuItem[] = [
    { text: '仪表盘', icon: <DashboardIcon />, path: '/dashboard' },
    { text: '消息平台适配器', icon: <ChatIcon />, path: '/dashboard/platforms' },
    { text: '机器人基础配置', icon: <SettingsIcon />, path: '/dashboard/bot' },
    { text: '插件管理', icon: <ExtensionIcon />, path: '/dashboard/plugins' },
    { text: 'LLM/TTL 服务提供商配置', icon: <ComputerIcon />, path: '/dashboard/llm' },
    { text: '人设/提示词', icon: <PersonIcon />, path: '/dashboard/personalities' },
    { text: 'MCP 配置', icon: <CodeIcon />, path: '/dashboard/mcp' },
    { text: '日志管理', icon: <DescriptionIcon />, path: '/dashboard/logs' },
    { text: '更多设置', icon: <MoreIcon />, path: '/dashboard/settings' },
  ];

  const handleDrawerToggle = () => {
    setMobileOpen(!mobileOpen);
  };

  const handleMenuItemClick = (path: string) => {
    navigate(path);
    setMobileOpen(false); // 关闭移动端侧边栏
  };

  const drawer = (
    <div>
      <Toolbar>
        <Typography variant="h6" noWrap component="div">
          NekoBot
        </Typography>
      </Toolbar>
      <Divider />
      <List>
        {menuItems.map((item) => (
          <ListItem key={item.text} disablePadding>
            <ListItemButton
              selected={location.pathname === item.path}
              onClick={() => handleMenuItemClick(item.path)}
            >
              <ListItemIcon>
                {item.icon}
              </ListItemIcon>
              <ListItemText primary={item.text} />
            </ListItemButton>
          </ListItem>
        ))}
      </List>
      <Divider />
      <Box sx={{ p: 2 }}>
        <Typography variant="body2" color="text.secondary">
          NekoBot Dashboard v{__APP_VERSION__}
        </Typography>
      </Box>
    </div>
  );

  return (
    <Box sx={{ display: 'flex' }}>
      {/* 移动端菜单按钮 */}
      <Box component="nav" sx={{ width: { sm: drawerWidth }, flexShrink: { sm: 0 } }} aria-label="mailbox folders">
        {/* 移动端抽屉 */}
        <Drawer
          variant="temporary"
          open={mobileOpen}
          onClose={handleDrawerToggle}
          ModalProps={{
            keepMounted: true, // Better open performance on mobile.
          }}
          sx={{
            display: { xs: 'block', sm: 'none' },
            '& .MuiDrawer-paper': { boxSizing: 'border-box', width: drawerWidth },
          }}
        >
          {drawer}
        </Drawer>
        {/* 桌面端抽屉 */}
        <Drawer
          variant="permanent"
          sx={{
            display: { xs: 'none', sm: 'block' },
            '& .MuiDrawer-paper': { boxSizing: 'border-box', width: drawerWidth },
          }}
          open
        >
          {drawer}
        </Drawer>
      </Box>
    </Box>
  );
};

export default Sidebar;
