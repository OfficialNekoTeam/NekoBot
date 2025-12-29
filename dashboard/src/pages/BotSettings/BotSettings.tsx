import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  TextField,
  Button,
  Switch,
  Alert,
  CircularProgress,
  Stack,
  Avatar,
  Chip,
  Divider,
} from '@mui/material';
import SettingsIcon from '@mui/icons-material/Settings';
import SaveIcon from '@mui/icons-material/Save';
import RestartAltIcon from '@mui/icons-material/RestartAlt';
import { apiClient, type ApiResponse, type BotConfig } from '../../utils/api';

const BotSettings: React.FC = () => {
  const [config, setConfig] = useState<Partial<BotConfig> | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    setLoading(true);
    setError(null);
    try {
      const response: ApiResponse<BotConfig> = await apiClient.get('/api/bot/config');
      if (response.status === 'success' && response.data) {
        setConfig(response.data);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载配置失败');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!config) return;

    setSaving(true);
    setError(null);
    setSuccess(false);
    try {
      const response: ApiResponse<null> = await apiClient.post('/api/bot/config', {
        config: config,
      });
      if (response.status === 'success') {
        setSuccess(true);
        setTimeout(() => setSuccess(false), 3000);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存配置失败');
    } finally {
      setSaving(false);
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
            机器人基础配置
          </Typography>
          <Typography variant="body1" color="text.secondary">
            配置机器人的基础设置
          </Typography>
        </Box>
        <Avatar
          sx={{
            width: 56,
            height: 56,
            bgcolor: 'primary.main',
            boxShadow: '0 4px 12px rgba(33, 150, 243, 0.3)',
          }}
        >
          <SettingsIcon sx={{ fontSize: 32 }} />
        </Avatar>
      </Stack>

      <Box sx={{ display: 'flex', gap: 1, mb: 3 }}>
        <Chip label="机器人配置" color="primary" />
        <Chip label="基础设置" color="secondary" />
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {success && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess(false)}>
          配置保存成功
        </Alert>
      )}

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
              机器人设置
            </Typography>
            <Avatar
              sx={{
                width: 40,
                height: 40,
                bgcolor: 'primary.light',
                color: 'primary.dark',
              }}
            >
              <SettingsIcon />
            </Avatar>
          </Stack>

          <Divider sx={{ mb: 3 }} />

          <Stack spacing={3}>
            <Box>
              <Typography variant="subtitle1" sx={{ mb: 1.5, fontWeight: 500 }}>
                命令前缀
              </Typography>
              <TextField
                fullWidth
                value={config?.command_prefix || '/'}
                onChange={(e) => setConfig({ ...config, command_prefix: e.target.value })}
                placeholder="/"
                sx={{
                  '& .MuiOutlinedInput-root': {
                    borderRadius: 2,
                  },
                }}
              />
            </Box>

            <Box>
              <Typography variant="subtitle1" sx={{ mb: 1.5, fontWeight: 500 }}>
                服务器地址
              </Typography>
              <TextField
                fullWidth
                value={config?.server?.host || '0.0.0.0'}
                onChange={(e) => setConfig({
                 ...config,
                 server: {
                   host: e.target.value,
                   port: config?.server?.port || 6285
                 }
               })}
                placeholder="0.0.0.0"
                sx={{
                  '& .MuiOutlinedInput-root': {
                    borderRadius: 2,
                  },
                }}
              />
            </Box>

            <Box>
              <Typography variant="subtitle1" sx={{ mb: 1.5, fontWeight: 500 }}>
                服务器端口
              </Typography>
              <TextField
                fullWidth
                type="number"
                value={config?.server?.port || 6285}
                onChange={(e) => setConfig({
                 ...config,
                 server: {
                   host: config?.server?.host || '0.0.0.0',
                   port: parseInt(e.target.value)
                 }
               })}
                placeholder="6285"
                sx={{
                  '& .MuiOutlinedInput-root': {
                    borderRadius: 2,
                  },
                }}
              />
            </Box>

            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', p: 2, bgcolor: 'background.default', borderRadius: 2 }}>
              <Box>
                <Typography variant="subtitle1" sx={{ fontWeight: 500 }}>
                  Demo 模式
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  启用后将以演示模式运行
                </Typography>
              </Box>
              <Switch
                checked={config?.demo || false}
                onChange={(e) => setConfig({ ...config, demo: e.target.checked })}
                color="primary"
              />
            </Box>

            <Divider sx={{ my: 2 }} />

            <Stack direction="row" spacing={2}>
              <Button
                variant="contained"
                color="primary"
                onClick={handleSave}
                disabled={saving}
                startIcon={<SaveIcon />}
                sx={{
                  borderRadius: 2,
                  textTransform: 'none',
                  px: 3,
                }}
              >
                {saving ? '保存中...' : '保存配置'}
              </Button>
              <Button
                variant="outlined"
                startIcon={<RestartAltIcon />}
                sx={{
                  borderRadius: 2,
                  textTransform: 'none',
                  px: 3,
                }}
              >
                重置
              </Button>
            </Stack>
          </Stack>
        </CardContent>
      </Card>
    </Box>
  );
};

export default BotSettings;
