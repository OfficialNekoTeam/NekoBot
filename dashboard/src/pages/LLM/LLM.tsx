import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Chip,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Select,
  MenuItem,
  Switch,
  Alert,
  CircularProgress,
  Stack,
  Avatar,
  Divider,
  IconButton,
  Grid,
} from '@mui/material';
import PsychologyIcon from '@mui/icons-material/Psychology';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';
import { apiClient, type ApiResponse, type LlmProvider } from '../../utils/api';

const LLM: React.FC = () => {
  const [providers, setProviders] = useState<LlmProvider[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingProvider, setEditingProvider] = useState<Partial<LlmProvider>>({
    name: '',
    type: '',
    api_key: '',
    base_url: '',
    model: '',
    enabled: true,
  });

  useEffect(() => {
    loadProviders();
  }, []);

  const loadProviders = async () => {
    setLoading(true);
    setError(null);
    try {
      const response: ApiResponse<{ providers: LlmProvider[] }> = await apiClient.get('/api/llm/providers');
      if (response.status === 'success' && response.data) {
        setProviders(response.data.providers);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载服务提供商列表失败');
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = () => {
    setEditingProvider({
      name: '',
      type: '',
      api_key: '',
      base_url: '',
      model: '',
      enabled: true,
    });
    setDialogOpen(true);
  };

  const handleEdit = (provider: LlmProvider) => {
    setEditingProvider(provider);
    setDialogOpen(true);
  };

  const handleDelete = async (id: string) => {
    setError(null);
    setSuccess(false);
    try {
      const response: ApiResponse<null> = await apiClient.post('/api/llm/providers/delete', {
        id,
      });
      if (response.status === 'success') {
        setSuccess(true);
        setTimeout(() => setSuccess(false), 3000);
        await loadProviders();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除失败');
    }
  };

  const handleSave = async () => {
    if (!editingProvider.name || !editingProvider.type || !editingProvider.api_key) return;

    setError(null);
    setSuccess(false);
    try {
      if (editingProvider.id) {
        const response: ApiResponse<null> = await apiClient.post('/api/llm/providers/update', {
          id: editingProvider.id,
          name: editingProvider.name,
          type: editingProvider.type,
          api_key: editingProvider.api_key,
          base_url: editingProvider.base_url,
          model: editingProvider.model,
          enabled: editingProvider.enabled,
        });
        if (response.status === 'success') {
          setSuccess(true);
          setTimeout(() => setSuccess(false), 3000);
          await loadProviders();
        }
      } else {
        const response: ApiResponse<{ id: string }> = await apiClient.post('/api/llm/providers/add', {
          name: editingProvider.name,
          type: editingProvider.type,
          api_key: editingProvider.api_key,
          base_url: editingProvider.base_url,
          model: editingProvider.model,
          enabled: editingProvider.enabled,
        });
        if (response.status === 'success') {
          setSuccess(true);
          setTimeout(() => setSuccess(false), 3000);
          await loadProviders();
        }
      }
      setDialogOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存失败');
    }
  };

  const handleCloseDialog = () => {
    setDialogOpen(false);
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
            LLM/TTL 服务提供商配置
          </Typography>
          <Typography variant="body1" color="text.secondary">
            配置和管理LLM/TTL服务提供商
          </Typography>
        </Box>
        <Avatar
          sx={{
            width: 56,
            height: 56,
            bgcolor: 'secondary.main',
            boxShadow: '0 4px 12px rgba(103, 58, 183, 0.3)',
          }}
        >
          <PsychologyIcon sx={{ fontSize: 32 }} />
        </Avatar>
      </Stack>

      <Box sx={{ display: 'flex', gap: 1, mb: 3 }}>
        <Chip label="LLM配置" color="primary" />
        <Chip label="TTL服务" color="secondary" />
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

      <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h6">
          服务提供商列表 ({providers.length})
        </Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={handleCreate}
          sx={{
            borderRadius: 2,
            textTransform: 'none',
            px: 3,
          }}
        >
          添加提供商
        </Button>
      </Stack>

      <Grid container spacing={3}>
        {providers.map((provider) => (
          <Grid size={{ xs: 12, sm: 6, md: 4 }} key={provider.id}>
            <Card
              sx={{
                border: '1px solid',
                borderColor: 'divider',
                boxShadow: '0 2px 14px 0 rgb(32 40 45 / 8%)',
                '&:hover': {
                  boxShadow: '0 4px 20px 0 rgb(32 40 45 / 12%)',
                  transform: 'translateY(-2px)',
                },
                transition: 'all 0.3s ease',
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
              }}
            >
              <CardContent sx={{ flexGrow: 1 }}>
                <Stack direction="row" sx={{ alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
                  <Avatar
                    sx={{
                      width: 48,
                      height: 48,
                      bgcolor: provider.enabled ? 'success.light' : 'grey.200',
                      color: provider.enabled ? 'success.dark' : 'grey.500',
                    }}
                  >
                    {provider.enabled ? <CheckCircleIcon /> : <CancelIcon />}
                  </Avatar>
                  <Chip
                    label={provider.type}
                    size="small"
                    color={provider.enabled ? 'success' : 'default'}
                  />
                </Stack>

                <Typography variant="h6" gutterBottom>
                  {provider.name}
                </Typography>

                <Divider sx={{ my: 2 }} />

                <Stack spacing={1.5}>
                  <Box>
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                      模型
                    </Typography>
                    <Typography variant="body2" sx={{ fontWeight: 500 }}>
                      {provider.model || '未设置'}
                    </Typography>
                  </Box>

                  <Box>
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                      基础URL
                    </Typography>
                    <Typography
                      variant="body2"
                      sx={{
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {provider.base_url || '未设置'}
                    </Typography>
                  </Box>

                  <Box>
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                      API密钥
                    </Typography>
                    <Typography
                      variant="body2"
                      sx={{
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {provider.api_key ? '••••••••' : '未设置'}
                    </Typography>
                  </Box>
                </Stack>
              </CardContent>

              <Divider />

              <Box sx={{ p: 2 }}>
                <Stack direction="row" sx={{ alignItems: 'center', justifyContent: 'space-between' }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Switch
                      checked={provider.enabled}
                      onChange={(e) => {
                        const updated = { ...provider, enabled: e.target.checked };
                        handleEdit(updated);
                      }}
                      color="success"
                      size="small"
                    />
                    <Typography variant="caption" color="text.secondary">
                      {provider.enabled ? '已启用' : '已禁用'}
                    </Typography>
                  </Box>
                  <Box sx={{ display: 'flex', gap: 0.5 }}>
                    <IconButton
                      size="small"
                      onClick={() => handleEdit(provider)}
                      sx={{ color: 'primary.main' }}
                    >
                      <EditIcon fontSize="small" />
                    </IconButton>
                    <IconButton
                      size="small"
                      onClick={() => handleDelete(provider.id)}
                      sx={{ color: 'error.main' }}
                    >
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  </Box>
                </Stack>
              </Box>
            </Card>
          </Grid>
        ))}
      </Grid>

      <Dialog open={dialogOpen} onClose={handleCloseDialog} maxWidth="md" fullWidth>
        <DialogTitle>
          {editingProvider.id ? '编辑服务提供商' : '添加服务提供商'}
        </DialogTitle>
        <DialogContent>
          <Stack spacing={3} sx={{ mt: 1 }}>
            <TextField
              autoFocus
              label="名称"
              fullWidth
              value={editingProvider.name}
              onChange={(e) => setEditingProvider({ ...editingProvider, name: e.target.value })}
              sx={{
                '& .MuiOutlinedInput-root': {
                  borderRadius: 2,
                },
              }}
            />
            <Select
              value={editingProvider.type}
              onChange={(e) => setEditingProvider({ ...editingProvider, type: e.target.value })}
              label="类型"
              fullWidth
              sx={{
                '& .MuiOutlinedInput-root': {
                  borderRadius: 2,
                },
              }}
            >
              <MenuItem value="openai">OpenAI</MenuItem>
              <MenuItem value="anthropic">Anthropic</MenuItem>
              <MenuItem value="google">Google</MenuItem>
              <MenuItem value="azure">Azure</MenuItem>
              <MenuItem value="custom">自定义</MenuItem>
            </Select>
            <TextField
              label="API密钥"
              fullWidth
              value={editingProvider.api_key}
              onChange={(e) => setEditingProvider({ ...editingProvider, api_key: e.target.value })}
              type="password"
              sx={{
                '& .MuiOutlinedInput-root': {
                  borderRadius: 2,
                },
              }}
            />
            <TextField
              label="基础URL"
              fullWidth
              value={editingProvider.base_url}
              onChange={(e) => setEditingProvider({ ...editingProvider, base_url: e.target.value })}
              sx={{
                '& .MuiOutlinedInput-root': {
                  borderRadius: 2,
                },
              }}
            />
            <TextField
              label="模型"
              fullWidth
              value={editingProvider.model}
              onChange={(e) => setEditingProvider({ ...editingProvider, model: e.target.value })}
              sx={{
                '& .MuiOutlinedInput-root': {
                  borderRadius: 2,
                },
              }}
            />
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', p: 2, bgcolor: 'background.default', borderRadius: 2 }}>
              <Box>
                <Typography variant="subtitle1" sx={{ fontWeight: 500 }}>
                  启用此提供商
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  启用后将可用于LLM/TTL服务
                </Typography>
              </Box>
              <Switch
                checked={editingProvider.enabled}
                onChange={(e) => setEditingProvider({ ...editingProvider, enabled: e.target.checked })}
                color="primary"
              />
            </Box>
          </Stack>
        </DialogContent>
        <DialogActions sx={{ p: 3 }}>
          <Button onClick={handleCloseDialog} sx={{ borderRadius: 2, textTransform: 'none', px: 3 }}>
            取消
          </Button>
          <Button onClick={handleSave} variant="contained" sx={{ borderRadius: 2, textTransform: 'none', px: 3 }}>
            保存
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default LLM;
