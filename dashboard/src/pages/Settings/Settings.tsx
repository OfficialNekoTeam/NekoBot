import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Chip,
  Button,
  Switch,
  Select,
  MenuItem,
  Alert,
  CircularProgress,
  Stack,
  Avatar,
  Divider,
  Grid,
} from '@mui/material';
import SettingsIcon from '@mui/icons-material/Settings';
import SaveIcon from '@mui/icons-material/Save';
import RestartAltIcon from '@mui/icons-material/RestartAlt';
import UpdateIcon from '@mui/icons-material/Update';
import DarkModeIcon from '@mui/icons-material/DarkMode';
import LanguageIcon from '@mui/icons-material/Language';
import NotificationsIcon from '@mui/icons-material/Notifications';
import { apiClient, type ApiResponse, type Settings } from '../../utils/api';

const SettingsPage: React.FC = () => {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    setLoading(true);
    setError(null);
    try {
      const response: ApiResponse<{ settings: Settings }> = await apiClient.get('/api/settings');
      if (response.status === 'success' && response.data) {
        setSettings(response.data.settings);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载设置失败');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!settings) return;

    setLoading(true);
    setError(null);
    setSuccess(false);
    try {
      const response: ApiResponse<null> = await apiClient.post('/api/settings', {
        settings: settings,
      });
      if (response.status === 'success') {
        setSuccess(true);
        setTimeout(() => setSuccess(false), 3000);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存设置失败');
    } finally {
      setLoading(false);
    }
  };

  const handleRestart = async () => {
    setError(null);
    setSuccess(false);
    try {
      const response: ApiResponse<null> = await apiClient.post('/api/settings/restart', {});
      if (response.status === 'success') {
        setSuccess(true);
        setTimeout(() => setSuccess(false), 3000);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '重启服务失败');
    }
  };

  const handleCheckUpdate = async () => {
    setError(null);
    setSuccess(false);
    try {
      const response: ApiResponse<{ has_update: boolean; latest_version: string }> = await apiClient.get('/api/settings/update');
      if (response.status === 'success' && response.data) {
        const { has_update, latest_version } = response.data;
        if (has_update) {
          setError(`发现新版本: ${latest_version}`);
        } else {
          setSuccess(true);
          setTimeout(() => setSuccess(false), 3000);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '检查更新失败');
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ flexGrow: 1 }}>
      <Stack direction="row" sx={{ alignItems: 'center', justifyContent: 'space-between', mb: 3 }}>
        <Box>
          <Typography variant="h4" component="h1" gutterBottom>
            更多设置
          </Typography>
          <Typography variant="body1" color="text.secondary">
            配置和管理系统设置
          </Typography>
        </Box>
        <Avatar
          sx={{
            width: 56,
            height: 56,
            bgcolor: 'error.main',
            boxShadow: '0 4px 12px rgba(244, 67, 54, 0.3)',
          }}
        >
          <SettingsIcon sx={{ fontSize: 32 }} />
        </Avatar>
      </Stack>

      <Box sx={{ display: 'flex', gap: 1, mb: 3 }}>
        <Chip label="系统设置" color="primary" />
        <Chip label="更多设置" color="secondary" />
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {success && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess(false)}>
          操作成功
        </Alert>
      )}

      <Grid container spacing={3}>
        <Grid size={{ xs: 12, md: 8 }}>
          <Card
            sx={{
              border: '1px solid',
              borderColor: 'divider',
              boxShadow: '0 2px 14px 0 rgb(32 40 45 / 8%)',
              '&:hover': {
                boxShadow: '0 4px 20px 0 rgb(32 40 45 / 12%)',
              },
            }}
          >
            <CardContent>
              <Stack direction="row" sx={{ alignItems: 'center', justifyContent: 'space-between', mb: 3 }}>
                <Typography variant="h5" component="h2">
                  系统设置
                </Typography>
                <Avatar
                  sx={{
                    width: 40,
                    height: 40,
                    bgcolor: 'error.light',
                    color: 'error.dark',
                  }}
                >
                  <SettingsIcon />
                </Avatar>
              </Stack>

              <Divider sx={{ mb: 3 }} />

              <Stack spacing={3}>
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', p: 2, bgcolor: 'background.default', borderRadius: 2 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                    <Avatar sx={{ bgcolor: 'primary.light', color: 'primary.dark' }}>
                      <DarkModeIcon />
                    </Avatar>
                    <Box>
                      <Typography variant="subtitle1" sx={{ fontWeight: 500 }}>
                        主题设置
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        选择界面主题
                      </Typography>
                    </Box>
                  </Box>
                  <Select
                    value={settings?.theme || 'dark'}
                    onChange={(e) => setSettings({
                      ...settings!,
                      theme: e.target.value
                    })}
                    sx={{
                      minWidth: 120,
                      '& .MuiOutlinedInput-root': {
                        borderRadius: 2,
                      },
                    }}
                  >
                    <MenuItem value="dark">深色</MenuItem>
                    <MenuItem value="light">浅色</MenuItem>
                  </Select>
                </Box>

                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', p: 2, bgcolor: 'background.default', borderRadius: 2 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                    <Avatar sx={{ bgcolor: 'info.light', color: 'info.dark' }}>
                      <LanguageIcon />
                    </Avatar>
                    <Box>
                      <Typography variant="subtitle1" sx={{ fontWeight: 500 }}>
                        语言设置
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        选择界面语言
                      </Typography>
                    </Box>
                  </Box>
                  <Select
                    value={settings?.language || 'zh-CN'}
                    onChange={(e) => setSettings({
                      ...settings!,
                      language: e.target.value
                    })}
                    sx={{
                      minWidth: 120,
                      '& .MuiOutlinedInput-root': {
                        borderRadius: 2,
                      },
                    }}
                  >
                    <MenuItem value="zh-CN">简体中文</MenuItem>
                    <MenuItem value="en-US">English</MenuItem>
                  </Select>
                </Box>

                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', p: 2, bgcolor: 'background.default', borderRadius: 2 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                    <Avatar sx={{ bgcolor: 'warning.light', color: 'warning.dark' }}>
                      <NotificationsIcon />
                    </Avatar>
                    <Box>
                      <Typography variant="subtitle1" sx={{ fontWeight: 500 }}>
                        通知设置
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        启用系统通知
                      </Typography>
                    </Box>
                  </Box>
                  <Switch
                    checked={settings?.notifications?.enabled || false}
                    onChange={(e) => setSettings({
                      ...settings!,
                      notifications: {
                        enabled: e.target.checked,
                        types: settings!.notifications.types
                      }
                    })}
                    color="primary"
                  />
                </Box>

                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', p: 2, bgcolor: 'background.default', borderRadius: 2 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                    <Avatar sx={{ bgcolor: 'success.light', color: 'success.dark' }}>
                      <RestartAltIcon />
                    </Avatar>
                    <Box>
                      <Typography variant="subtitle1" sx={{ fontWeight: 500 }}>
                        自动重启
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        启用自动重启功能
                      </Typography>
                    </Box>
                  </Box>
                  <Switch
                    checked={settings?.auto_restart || false}
                    onChange={(e) => setSettings({
                      ...settings!,
                      auto_restart: e.target.checked
                    })}
                    color="primary"
                  />
                </Box>
              </Stack>
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, md: 4 }}>
          <Stack spacing={3}>
            <Card
              sx={{
                border: '1px solid',
                borderColor: 'divider',
                boxShadow: '0 2px 14px 0 rgb(32 40 45 / 8%)',
              }}
            >
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  系统操作
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                  执行系统级别的操作
                </Typography>

                <Stack spacing={2}>
                  <Button
                    variant="contained"
                    color="primary"
                    onClick={handleSave}
                    disabled={loading}
                    startIcon={<SaveIcon />}
                    fullWidth
                    sx={{
                      borderRadius: 2,
                      textTransform: 'none',
                      py: 1.5,
                    }}
                  >
                    {loading ? '保存中...' : '保存设置'}
                  </Button>
                  <Button
                    variant="outlined"
                    onClick={handleRestart}
                    startIcon={<RestartAltIcon />}
                    fullWidth
                    sx={{
                      borderRadius: 2,
                      textTransform: 'none',
                      py: 1.5,
                    }}
                  >
                    重启服务
                  </Button>
                  <Button
                    variant="outlined"
                    onClick={handleCheckUpdate}
                    startIcon={<UpdateIcon />}
                    fullWidth
                    sx={{
                      borderRadius: 2,
                      textTransform: 'none',
                      py: 1.5,
                    }}
                  >
                    检查更新
                  </Button>
                </Stack>
              </CardContent>
            </Card>

            <Card
              sx={{
                border: '1px solid',
                borderColor: 'divider',
                boxShadow: '0 2px 14px 0 rgb(32 40 45 / 8%)',
              }}
            >
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  系统信息
                </Typography>
                <Stack spacing={2}>
                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      当前版本
                    </Typography>
                    <Typography variant="body1" sx={{ fontWeight: 500 }}>
                      1.0.0
                    </Typography>
                  </Box>
                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      运行时间
                    </Typography>
                    <Typography variant="body1" sx={{ fontWeight: 500 }}>
                      正常运行
                    </Typography>
                  </Box>
                </Stack>
              </CardContent>
            </Card>
          </Stack>
        </Grid>
      </Grid>
    </Box>
  );
};

export default SettingsPage;
