import { useState } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import Layout from './components/Layout/Layout';
import Login from './pages/Login/Login';
import Dashboard from './pages/Dashboard/Dashboard';
import ChangePassword from './pages/ChangePassword/ChangePassword';
import Platforms from './pages/Platforms/Platforms';
import BotSettings from './pages/BotSettings/BotSettings';
import LLM from './pages/LLM/LLM';
import Plugins from './pages/Plugins/Plugins';
import Logs from './pages/Logs/Logs';
import Personalities from './pages/Personalities/Personalities';
import MCP from './pages/MCP/MCP';
import Settings from './pages/Settings/Settings';

function App() {
  const [darkMode, setDarkMode] = useState(true);

  return (
    <AuthProvider>
      <Router>
        <Routes>
          {/* 登录页面 - 无需布局 */}
          <Route path="/auth/login" element={<Login />} />
          
          {/* 仪表盘路由 - 使用主布局 */}
          <Route
            path="/dashboard"
            element={<Layout darkMode={darkMode} onDarkModeChange={setDarkMode} />}
          >
            {/* 仪表盘首页 */}
            <Route index element={<Dashboard />} />
            {/* 消息平台适配器 */}
            <Route path="platforms" element={<Platforms />} />
            {/* 机器人基础配置 */}
            <Route path="bot" element={<BotSettings />} />
            {/* 插件管理 */}
            <Route path="plugins" element={<Plugins />} />
            {/* LLM/TTL 服务提供商配置 */}
            <Route path="llm" element={<LLM />} />
            {/* 人设/提示词 */}
            <Route path="personalities" element={<Personalities />} />
            {/* MCP 配置 */}
            <Route path="mcp" element={<MCP />} />
            {/* 日志管理 */}
            <Route path="logs" element={<Logs />} />
            {/* 修改密码 */}
            <Route path="change-password" element={<ChangePassword />} />
            {/* 更多设置 */}
            <Route path="settings" element={<Settings />} />
          </Route>
          
          {/* 根路径重定向到仪表盘 */}
          <Route path="/" element={<Layout darkMode={darkMode} onDarkModeChange={setDarkMode} />}>
            <Route index element={<Dashboard />} />
          </Route>
        </Routes>
      </Router>
    </AuthProvider>
  );
}



export default App;
