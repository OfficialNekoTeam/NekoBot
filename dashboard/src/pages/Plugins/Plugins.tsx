import React, { useState, useEffect, useRef } from 'react';
import {
  Box,
  Typography,
  Chip,
  Button,
  Switch,
  Alert,
  CircularProgress,
  Paper,
  Tooltip,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  MenuItem,
  Select,
  InputLabel,
  FormControl,
  Tab,
  Tabs,
} from '@mui/material';
import {
  Extension as ExtensionIcon,
  Refresh as RefreshIcon,
  CloudUpload as CloudUploadIcon,
  Delete as DeleteIcon,
  Settings as SettingsIcon,
  Close as CloseIcon,
  Link as LinkIcon,
  GitHub as GitHubIcon,
} from '@mui/icons-material';
import { apiClient, type ApiResponse, type PluginInfo } from '../../utils/api';

// GitHub 代理列表
const GITHUB_PROXIES = [
  { label: '不使用代理', value: '' },
  { label: 'GitHub Proxy (ghproxy.com)', value: 'https://ghproxy.com/' },
  { label: 'GitHub Proxy (ghproxy.cn)', value: 'https://ghproxy.cn/' },
  { label: 'Moeyy (moeyy.cn)', value: 'https://gh.moeyy.cn/' },
  { label: 'FastGit (fastgit.org)', value: 'https://hub.fastgit.xyz/' },
  { label: 'GitClone (gitclone.com)', value: 'https://gitclone.com/' },
];

const Plugins: React.FC = () => {
  const [plugins, setPlugins] = useState<Record<string, PluginInfo>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [configDialogOpen, setConfigDialogOpen] = useState(false);
  const [configPlugin, setConfigPlugin] = useState<string | null>(null);
  const [pluginConfig, setPluginConfig] = useState<Record<string, unknown>>({});
  const [configSchema, setConfigSchema] = useState<Record<string, unknown> | null>(null);
  const [installDialogOpen, setInstallDialogOpen] = useState(false);
  const [installUrl, setInstallUrl] = useState('');
  const [installProxy, setInstallProxy] = useState('');
  const [installing, setInstalling] = useState(false);
  const [installTab, setInstallTab] = useState(0);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    loadPlugins();
  }, []);

  const loadPlugins = async () => {
    setLoading(true);
    setError(null);
    try {
      const response: ApiResponse<Record<string, PluginInfo>> = await apiClient.get('/api/plugins/list');
      if (response.status === 'success' && response.data) {
        setPlugins(response.data);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载插件列表失败');
    } finally {
      setLoading(false);
    }
  };

  const handleTogglePlugin = async (pluginName: string, enable: boolean) => {
    setError(null);
    setSuccess(false);
    try {
      const endpoint = enable ? '/api/plugins/enable' : '/api/plugins/disable';
      const response: ApiResponse<null> = await apiClient.post(endpoint, {
        name: pluginName,
      });
      if (response.status === 'success') {
        setSuccess(true);
        setTimeout(() => setSuccess(false), 3000);
        await loadPlugins();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '操作失败');
    }
  };

  const handleReloadPlugin = async (pluginName: string) => {
    setError(null);
    setSuccess(false);
    try {
      const response: ApiResponse<null> = await apiClient.post('/api/plugins/reload', {
        name: pluginName,
      });
      if (response.status === 'success') {
        setSuccess(true);
        setTimeout(() => setSuccess(false), 3000);
        await loadPlugins();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '重载失败');
    }
  };

  const handleUploadPlugin = async () => {
    if (!uploadFile) {
      setError('请选择要上传的插件文件');
      return;
    }

    setError(null);
    setSuccess(false);
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', uploadFile);

      const response = await fetch(`${apiClient['baseUrl']}/api/plugins/upload`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${apiClient['token']}`,
        },
        body: formData,
      });

      const result = await response.json();

      if (result.status === 'success') {
        setSuccess(true);
        setTimeout(() => setSuccess(false), 3000);
        setUploadDialogOpen(false);
        setUploadFile(null);
        await loadPlugins();
      } else {
        setError(result.message || '上传失败');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '上传失败');
    } finally {
      setUploading(false);
    }
  };

  const handleDeletePlugin = async (pluginName: string) => {
    if (!confirm(`确定要删除插件 "${pluginName}" 吗？此操作不可恢复。`)) {
      return;
    }

    setError(null);
    setSuccess(false);
    try {
      const response: ApiResponse<null> = await apiClient.post('/api/plugins/delete', {
        name: pluginName,
      });
      if (response.status === 'success') {
        setSuccess(true);
        setTimeout(() => setSuccess(false), 3000);
        await loadPlugins();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除失败');
    }
  };

  const handleOpenConfig = async (pluginName: string) => {
    setError(null);
    try {
      const response: ApiResponse<{ config: Record<string, unknown>; schema: Record<string, unknown> | null }> = 
        await apiClient.get(`/api/plugins/config?name=${pluginName}`);
      
      if (response.status === 'success' && response.data) {
        setPluginConfig(response.data.config);
        setConfigSchema(response.data.schema);
        setConfigPlugin(pluginName);
        setConfigDialogOpen(true);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取配置失败');
    }
  };

  const handleSaveConfig = async () => {
    if (!configPlugin) return;

    setError(null);
    setSuccess(false);
    try {
      const response: ApiResponse<null> = await apiClient.post('/api/plugins/config', {
        name: configPlugin,
        config: pluginConfig,
      });
      if (response.status === 'success') {
        setSuccess(true);
        setTimeout(() => setSuccess(false), 3000);
        setConfigDialogOpen(false);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存配置失败');
    }
  };

  const handleInstallFromUrl = async () => {
    if (!installUrl.trim()) {
      setError('请输入插件 URL');
      return;
    }

    setError(null);
    setSuccess(false);
    setInstalling(true);
    try {
      const response: ApiResponse<{ plugin_name: string }> = await apiClient.post('/api/plugins/install', {
        url: installUrl.trim(),
        proxy: installProxy || undefined,
      });
      if (response.status === 'success') {
        setSuccess(true);
        setTimeout(() => setSuccess(false), 3000);
        setInstallDialogOpen(false);
        setInstallUrl('');
        setInstallProxy('');
        await loadPlugins();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '安装失败');
    } finally {
      setInstalling(false);
    }
  };

  const handleInstallFromGitHub = async () => {
    if (!installUrl.trim()) {
      setError('请输入 GitHub 仓库链接');
      return;
    }

    // 验证 GitHub 链接格式
    const githubRegex = /github\.com\/([^/]+)\/([^/]+)/;
    const match = installUrl.match(githubRegex);
    if (!match) {
      setError('GitHub 仓库链接格式不正确，应为: https://github.com/user/repo');
      return;
    }

    setError(null);
    setSuccess(false);
    setInstalling(true);
    try {
      const response: ApiResponse<{ plugin_name: string }> = await apiClient.post('/api/plugins/install', {
        url: installUrl.trim(),
        proxy: installProxy || undefined,
      });
      if (response.status === 'success') {
        setSuccess(true);
        setTimeout(() => setSuccess(false), 3000);
        setInstallDialogOpen(false);
        setInstallUrl('');
        setInstallProxy('');
        await loadPlugins();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '安装失败');
    } finally {
      setInstalling(false);
    }
  };

  const pluginsList = Object.values(plugins);
  const enabledCount = pluginsList.filter(p => p.enabled).length;
  const totalCount = pluginsList.length;

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ flexGrow: 1, p: 3 }}>
      {/* 页面标题 */}
      <Box sx={{ mb: 4, className: 'fade-in' }}>
        <Typography
          variant="h3"
          component="h1"
          gutterBottom
          sx={{
            fontWeight: 700,
            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            backgroundClip: 'text',
          }}
        >
          插件管理
        </Typography>
        <Typography variant="body1" color="text.secondary" sx={{ mt: 1 }}>
          管理本地插件和在线插件市场
        </Typography>
      </Box>

      {/* 统计卡片 */}
      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)' }, gap: 3, mb: 4 }}>
        <Paper
          className="glass-card card-hover"
          sx={{
            p: 3,
            display: 'flex',
            alignItems: 'center',
            gap: 3,
          }}
        >
          <Box
            sx={{
              p: 2.5,
              borderRadius: '16px',
              background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
              color: 'white',
              boxShadow: '0 8px 16px -4px rgba(102, 126, 234, 0.3)',
            }}
          >
            <ExtensionIcon fontSize="large" />
          </Box>
          <Box>
            <Typography variant="body2" color="text.secondary" gutterBottom sx={{ fontWeight: 500 }}>
              已启用插件
            </Typography>
            <Typography variant="h3" component="span" sx={{ fontWeight: 700 }}>
              {enabledCount}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ ml: 1 }}>
              / {totalCount}
            </Typography>
          </Box>
        </Paper>

        <Paper
          className="glass-card card-hover"
          sx={{
            p: 3,
            display: 'flex',
            alignItems: 'center',
            gap: 3,
          }}
        >
          <Box
            sx={{
              p: 2.5,
              borderRadius: '16px',
              background: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
              color: 'white',
              boxShadow: '0 8px 16px -4px rgba(0, 242, 254, 0.3)',
            }}
          >
            <CloudUploadIcon fontSize="large" />
          </Box>
          <Box>
            <Typography variant="body2" color="text.secondary" gutterBottom sx={{ fontWeight: 500 }}>
              在线市场
            </Typography>
            <Typography variant="h3" component="span" sx={{ fontWeight: 700 }}>
              即将推出
            </Typography>
          </Box>
        </Paper>
      </Box>

      {/* 操作按钮 */}
      <Box sx={{ display: 'flex', gap: 2, mb: 3 }}>
        <Button
          variant="contained"
          startIcon={<RefreshIcon />}
          onClick={loadPlugins}
          disabled={loading}
          sx={{
            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            '&:hover': {
              background: 'linear-gradient(135deg, #5a6fd6 0%, #6a4190 100%)',
            },
          }}
        >
          刷新列表
        </Button>
        <Button
          variant="outlined"
          startIcon={<CloudUploadIcon />}
          onClick={() => setUploadDialogOpen(true)}
          sx={{
            borderColor: 'rgba(102, 126, 234, 0.5)',
            color: 'rgba(102, 126, 234, 1)',
            '&:hover': {
              borderColor: 'rgba(102, 126, 234, 1)',
              backgroundColor: 'rgba(102, 126, 234, 0.05)',
            },
          }}
        >
          上传插件
        </Button>
        <Button
          variant="outlined"
          startIcon={<LinkIcon />}
          onClick={() => setInstallDialogOpen(true)}
          sx={{
            borderColor: 'rgba(102, 126, 234, 0.5)',
            color: 'rgba(102, 126, 234, 1)',
            '&:hover': {
              borderColor: 'rgba(102, 126, 234, 1)',
              backgroundColor: 'rgba(102, 126, 234, 0.05)',
            },
          }}
        >
          URL 安装
        </Button>
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

      {/* 插件列表 */}
      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: 'repeat(2, 1fr)' }, gap: 3 }}>
        {pluginsList.map((plugin) => (
          <Paper
            key={plugin.name}
            className="glass-card card-hover"
            sx={{
              p: 3,
              height: '100%',
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            {/* 插件头部 */}
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
              <Box sx={{ display: 'flex', gap: 2, alignItems: 'flex-start' }}>
                <Box
                  sx={{
                    p: 2,
                    borderRadius: '12px',
                    background: plugin.enabled
                      ? 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
                      : 'linear-gradient(135deg, #a8a8a8 0%, #6e6e6e 100%)',
                    color: 'white',
                    boxShadow: plugin.enabled
                      ? '0 8px 16px -4px rgba(102, 126, 234, 0.3)'
                      : '0 8px 16px -4px rgba(110, 110, 110, 0.3)',
                  }}
                >
                  <ExtensionIcon />
                </Box>
                <Box>
                  <Typography variant="h6" sx={{ fontWeight: 600, mb: 0.5 }}>
                    {plugin.name}
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                    <Chip
                      label={`v${plugin.version}`}
                      size="small"
                      sx={{
                        background: 'rgba(102, 126, 234, 0.1)',
                        color: 'rgba(102, 126, 234, 1)',
                        fontWeight: 500,
                      }}
                    />
                    {plugin.is_official && (
                      <Chip
                        label="官方"
                        size="small"
                        color="primary"
                        sx={{ fontWeight: 500 }}
                      />
                    )}
                  </Box>
                </Box>
              </Box>
              <Switch
                checked={plugin.enabled}
                onChange={(e) => handleTogglePlugin(plugin.name, e.target.checked)}
                color="primary"
              />
            </Box>

            {/* 插件信息 */}
            <Box sx={{ mb: 2, flexGrow: 1 }}>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                {plugin.description}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                作者: {plugin.author}
              </Typography>
            </Box>

            {/* 插件命令 */}
            {plugin.commands && plugin.commands.length > 0 && (
              <Box sx={{ mb: 2 }}>
                <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600, mb: 1, display: 'block' }}>
                  可用命令:
                </Typography>
                <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                  {plugin.commands.map((cmd) => (
                    <Chip
                      key={cmd}
                      label={`/${cmd}`}
                      size="small"
                      variant="outlined"
                      sx={{
                        fontSize: '0.75rem',
                        height: 24,
                      }}
                    />
                  ))}
                </Box>
              </Box>
            )}

            {/* 操作按钮 */}
            <Box sx={{ display: 'flex', gap: 1, justifyContent: 'flex-end', pt: 2, borderTop: 1, borderColor: 'divider' }}>
              <Tooltip title="重载插件">
                <IconButton
                  size="small"
                  onClick={() => handleReloadPlugin(plugin.name)}
                  sx={{
                    color: 'text.secondary',
                    '&:hover': {
                      color: 'primary.main',
                      backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    },
                  }}
                >
                  <RefreshIcon fontSize="small" />
                </IconButton>
              </Tooltip>
              <Tooltip title="插件配置">
                <IconButton
                  size="small"
                  onClick={() => handleOpenConfig(plugin.name)}
                  sx={{
                    color: 'text.secondary',
                    '&:hover': {
                      color: 'primary.main',
                      backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    },
                  }}
                >
                  <SettingsIcon fontSize="small" />
                </IconButton>
              </Tooltip>
              <Tooltip title="删除插件">
                <IconButton
                  size="small"
                  onClick={() => handleDeletePlugin(plugin.name)}
                  sx={{
                    color: 'text.secondary',
                    '&:hover': {
                      color: 'error.main',
                      backgroundColor: 'rgba(211, 47, 47, 0.1)',
                    },
                  }}
                >
                  <DeleteIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            </Box>
          </Paper>
        ))}
      </Box>

      {pluginsList.length === 0 && (
        <Paper
          className="glass-card"
          sx={{
            p: 6,
            textAlign: 'center',
          }}
        >
          <Box
            sx={{
              p: 3,
              borderRadius: '50%',
              background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
              color: 'white',
              display: 'inline-flex',
              mb: 2,
            }}
          >
            <ExtensionIcon sx={{ fontSize: 48 }} />
          </Box>
          <Typography variant="h6" gutterBottom>
            暂无插件
          </Typography>
          <Typography variant="body2" color="text.secondary">
            请上传插件或从在线市场安装
          </Typography>
        </Paper>
      )}

      {/* 上传插件对话框 */}
      <Dialog
        open={uploadDialogOpen}
        onClose={() => setUploadDialogOpen(false)}
        maxWidth="sm"
        fullWidth
        PaperProps={{
          className: 'glass-card',
        }}
      >
        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="h6" sx={{ fontWeight: 600 }}>
            上传插件
          </Typography>
          <IconButton onClick={() => setUploadDialogOpen(false)} size="small">
            <CloseIcon />
          </IconButton>
        </DialogTitle>
        <DialogContent>
          <Box
            sx={{
              border: 2,
              borderColor: 'divider',
              borderRadius: 2,
              p: 4,
              textAlign: 'center',
              cursor: 'pointer',
              '&:hover': {
                borderColor: 'primary.main',
                backgroundColor: 'rgba(102, 126, 234, 0.05)',
              },
            }}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              type="file"
              ref={fileInputRef}
              style={{ display: 'none' }}
              accept=".zip"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) {
                  setUploadFile(file);
                }
              }}
            />
            <CloudUploadIcon sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
            <Typography variant="body1" gutterBottom>
              {uploadFile ? uploadFile.name : '点击或拖拽上传插件包'}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              支持 .zip 格式的插件包
            </Typography>
          </Box>
        </DialogContent>
        <DialogActions sx={{ p: 3 }}>
          <Button onClick={() => setUploadDialogOpen(false)} disabled={uploading}>
            取消
          </Button>
          <Button
            variant="contained"
            onClick={handleUploadPlugin}
            disabled={!uploadFile || uploading}
            sx={{
              background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
              '&:hover': {
                background: 'linear-gradient(135deg, #5a6fd6 0%, #6a4190 100%)',
              },
            }}
          >
            {uploading ? <CircularProgress size={20} sx={{ mr: 1 }} /> : null}
            {uploading ? '上传中...' : '上传'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* 插件配置对话框 */}
      <Dialog
        open={configDialogOpen}
        onClose={() => setConfigDialogOpen(false)}
        maxWidth="md"
        fullWidth
        PaperProps={{
          className: 'glass-card',
        }}
      >
        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="h6" sx={{ fontWeight: 600 }}>
            插件配置 - {configPlugin}
          </Typography>
          <IconButton onClick={() => setConfigDialogOpen(false)} size="small">
            <CloseIcon />
          </IconButton>
        </DialogTitle>
        <DialogContent>
          {configSchema && Object.keys(configSchema).length > 0 ? (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              {Object.entries(configSchema).map(([key, schema]: [string, unknown]) => {
                const fieldSchema = schema as { type: string; title: string; description: string; default: unknown };
                return (
                  <Box key={key}>
                    <Typography variant="subtitle2" gutterBottom sx={{ fontWeight: 600 }}>
                      {fieldSchema.title || key}
                    </Typography>
                    {fieldSchema.description && (
                      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
                        {fieldSchema.description}
                      </Typography>
                    )}
                    <TextField
                      fullWidth
                      value={(pluginConfig[key] as string) || ''}
                      onChange={(e) => setPluginConfig({ ...pluginConfig, [key]: e.target.value })}
                      placeholder={String(fieldSchema.default || '')}
                      variant="outlined"
                      size="small"
                    />
                  </Box>
                );
              })}
            </Box>
          ) : (
            <Typography variant="body2" color="text.secondary">
              该插件没有可配置的选项
            </Typography>
          )}
        </DialogContent>
        <DialogActions sx={{ p: 3 }}>
          <Button onClick={() => setConfigDialogOpen(false)}>
            取消
          </Button>
          <Button
            variant="contained"
            onClick={handleSaveConfig}
            sx={{
              background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
              '&:hover': {
                background: 'linear-gradient(135deg, #5a6fd6 0%, #6a4190 100%)',
              },
            }}
          >
            保存配置
          </Button>
        </DialogActions>
      </Dialog>

      {/* URL/GitHub 安装对话框 */}
      <Dialog
        open={installDialogOpen}
        onClose={() => setInstallDialogOpen(false)}
        maxWidth="md"
        fullWidth
        PaperProps={{
          className: 'glass-card',
        }}
      >
        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="h6" sx={{ fontWeight: 600 }}>
            安装插件
          </Typography>
          <IconButton onClick={() => setInstallDialogOpen(false)} size="small">
            <CloseIcon />
          </IconButton>
        </DialogTitle>
        <DialogContent>
          <Tabs
            value={installTab}
            onChange={(_, newValue) => setInstallTab(newValue)}
            sx={{ mb: 3 }}
          >
            <Tab label="URL 安装" />
            <Tab label="GitHub 仓库" />
          </Tabs>

          {installTab === 0 && (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
              <Box>
                <Typography variant="subtitle2" gutterBottom sx={{ fontWeight: 600 }}>
                  插件 URL
                </Typography>
                <TextField
                  fullWidth
                  placeholder="https://example.com/plugin.zip"
                  value={installUrl}
                  onChange={(e) => setInstallUrl(e.target.value)}
                  variant="outlined"
                  size="small"
                  InputProps={{
                    startAdornment: <LinkIcon sx={{ mr: 1, color: 'text.secondary' }} />,
                  }}
                />
                <Typography variant="caption" color="text.secondary" sx={{ mt: 1 }}>
                  输入插件的直接下载链接
                </Typography>
              </Box>

              <Box>
                <Typography variant="subtitle2" gutterBottom sx={{ fontWeight: 600 }}>
                  GitHub 代理（可选）
                </Typography>
                <FormControl fullWidth size="small">
                  <InputLabel>选择代理</InputLabel>
                  <Select
                    value={installProxy}
                    onChange={(e) => setInstallProxy(e.target.value)}
                    label="选择代理"
                  >
                    {GITHUB_PROXIES.map((proxy) => (
                      <MenuItem key={proxy.value} value={proxy.value}>
                        {proxy.label}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
                <Typography variant="caption" color="text.secondary" sx={{ mt: 1 }}>
                  如果下载速度慢，可以选择使用 GitHub 代理
                </Typography>
              </Box>
            </Box>
          )}

          {installTab === 1 && (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
              <Box>
                <Typography variant="subtitle2" gutterBottom sx={{ fontWeight: 600 }}>
                  GitHub 仓库链接
                </Typography>
                <TextField
                  fullWidth
                  placeholder="https://github.com/user/repo"
                  value={installUrl}
                  onChange={(e) => setInstallUrl(e.target.value)}
                  variant="outlined"
                  size="small"
                  InputProps={{
                    startAdornment: <GitHubIcon sx={{ mr: 1, color: 'text.secondary' }} />,
                  }}
                />
                <Typography variant="caption" color="text.secondary" sx={{ mt: 1 }}>
                  输入 GitHub 仓库链接，格式: https://github.com/user/repo
                </Typography>
              </Box>

              <Box>
                <Typography variant="subtitle2" gutterBottom sx={{ fontWeight: 600 }}>
                  GitHub 代理（可选）
                </Typography>
                <FormControl fullWidth size="small">
                  <InputLabel>选择代理</InputLabel>
                  <Select
                    value={installProxy}
                    onChange={(e) => setInstallProxy(e.target.value)}
                    label="选择代理"
                  >
                    {GITHUB_PROXIES.map((proxy) => (
                      <MenuItem key={proxy.value} value={proxy.value}>
                        {proxy.label}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
                <Typography variant="caption" color="text.secondary" sx={{ mt: 1 }}>
                  如果下载速度慢，可以选择使用 GitHub 代理
                </Typography>
              </Box>
            </Box>
          )}
        </DialogContent>
        <DialogActions sx={{ p: 3 }}>
          <Button onClick={() => setInstallDialogOpen(false)} disabled={installing}>
            取消
          </Button>
          <Button
            variant="contained"
            onClick={installTab === 0 ? handleInstallFromUrl : handleInstallFromGitHub}
            disabled={!installUrl.trim() || installing}
            sx={{
              background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
              '&:hover': {
                background: 'linear-gradient(135deg, #5a6fd6 0%, #6a4190 100%)',
              },
            }}
          >
            {installing ? <CircularProgress size={20} sx={{ mr: 1 }} /> : null}
            {installing ? '安装中...' : '安装'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default Plugins;
