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
  Switch,
  Alert,
  CircularProgress,
  Stack,
  Avatar,
  Divider,
  IconButton,
  Grid,
} from '@mui/material';
import PersonIcon from '@mui/icons-material/Person';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';
import { apiClient, type ApiResponse, type Personality } from '../../utils/api';

const Personalities: React.FC = () => {
  const [personalities, setPersonalities] = useState<Personality[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingPersonality, setEditingPersonality] = useState<Partial<Personality>>({
    name: '',
    description: '',
    prompt: '',
    enabled: true,
  });

  useEffect(() => {
    loadPersonalities();
  }, []);

  const loadPersonalities = async () => {
    setLoading(true);
    setError(null);
    try {
      const response: ApiResponse<{ personalities: Personality[] }> = await apiClient.get('/api/personalities/list');
      if (response.status === 'success' && response.data) {
        setPersonalities(response.data.personalities);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载人设列表失败');
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = () => {
    setEditingPersonality({
      name: '',
      description: '',
      prompt: '',
      enabled: true,
    });
    setDialogOpen(true);
  };

  const handleEdit = (personality: Personality) => {
    setEditingPersonality(personality);
    setDialogOpen(true);
  };

  const handleDelete = async (id: string) => {
    setError(null);
    setSuccess(false);
    try {
      const response: ApiResponse<null> = await apiClient.post('/api/personalities/delete', {
        id,
      });
      if (response.status === 'success') {
        setSuccess(true);
        setTimeout(() => setSuccess(false), 3000);
        await loadPersonalities();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除失败');
    }
  };

  const handleSave = async () => {
    if (!editingPersonality.name || !editingPersonality.prompt) return;

    setError(null);
    setSuccess(false);
    try {
      if (editingPersonality.id) {
        const response: ApiResponse<null> = await apiClient.post('/api/personalities/update', {
          id: editingPersonality.id,
          name: editingPersonality.name,
          description: editingPersonality.description,
          prompt: editingPersonality.prompt,
          enabled: editingPersonality.enabled,
        });
        if (response.status === 'success') {
          setSuccess(true);
          setTimeout(() => setSuccess(false), 3000);
          await loadPersonalities();
        }
      } else {
        const response: ApiResponse<{ id: string }> = await apiClient.post('/api/personalities/create', {
          name: editingPersonality.name,
          description: editingPersonality.description,
          prompt: editingPersonality.prompt,
          enabled: editingPersonality.enabled,
        });
        if (response.status === 'success') {
          setSuccess(true);
          setTimeout(() => setSuccess(false), 3000);
          await loadPersonalities();
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
            人设/提示词
          </Typography>
          <Typography variant="body1" color="text.secondary">
            管理机器人的人设和提示词
          </Typography>
        </Box>
        <Avatar
          sx={{
            width: 56,
            height: 56,
            bgcolor: 'info.main',
            boxShadow: '0 4px 12px rgba(3, 169, 244, 0.3)',
          }}
        >
          <PersonIcon sx={{ fontSize: 32 }} />
        </Avatar>
      </Stack>

      <Box sx={{ display: 'flex', gap: 1, mb: 3 }}>
        <Chip label="人设管理" color="primary" />
        <Chip label="提示词配置" color="secondary" />
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
          人设列表 ({personalities.length})
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
          创建人设
        </Button>
      </Stack>

      <Grid container spacing={3}>
        {personalities.map((personality) => (
          <Grid size={{ xs: 12, sm: 6, md: 4 }} key={personality.id}>
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
                      bgcolor: personality.enabled ? 'success.light' : 'grey.200',
                      color: personality.enabled ? 'success.dark' : 'grey.500',
                    }}
                  >
                    {personality.enabled ? <CheckCircleIcon /> : <CancelIcon />}
                  </Avatar>
                  <Chip
                    label={personality.enabled ? '已启用' : '已禁用'}
                    size="small"
                    color={personality.enabled ? 'success' : 'default'}
                  />
                </Stack>

                <Typography variant="h6" gutterBottom>
                  {personality.name}
                </Typography>

                <Divider sx={{ my: 2 }} />

                <Stack spacing={1.5}>
                  <Box>
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                      描述
                    </Typography>
                    <Typography
                      variant="body2"
                      sx={{
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        display: '-webkit-box',
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: 'vertical',
                        maxHeight: 40,
                      }}
                    >
                      {personality.description || '暂无描述'}
                    </Typography>
                  </Box>

                  <Box>
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                      提示词
                    </Typography>
                    <Typography
                      variant="body2"
                      sx={{
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        display: '-webkit-box',
                        WebkitLineClamp: 3,
                        WebkitBoxOrient: 'vertical',
                        maxHeight: 60,
                      }}
                    >
                      {personality.prompt}
                    </Typography>
                  </Box>
                </Stack>
              </CardContent>

              <Divider />

              <Box sx={{ p: 2 }}>
                <Stack direction="row" sx={{ alignItems: 'center', justifyContent: 'space-between' }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Switch
                      checked={personality.enabled}
                      onChange={(e) => {
                        const updated = { ...personality, enabled: e.target.checked };
                        handleEdit(updated);
                      }}
                      color="success"
                      size="small"
                    />
                    <Typography variant="caption" color="text.secondary">
                      {personality.enabled ? '已启用' : '已禁用'}
                    </Typography>
                  </Box>
                  <Box sx={{ display: 'flex', gap: 0.5 }}>
                    <IconButton
                      size="small"
                      onClick={() => handleEdit(personality)}
                      sx={{ color: 'primary.main' }}
                    >
                      <EditIcon fontSize="small" />
                    </IconButton>
                    <IconButton
                      size="small"
                      onClick={() => handleDelete(personality.id)}
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
          {editingPersonality.id ? '编辑人设' : '创建人设'}
        </DialogTitle>
        <DialogContent>
          <Stack spacing={3} sx={{ mt: 1 }}>
            <TextField
              autoFocus
              label="名称"
              fullWidth
              value={editingPersonality.name}
              onChange={(e) => setEditingPersonality({ ...editingPersonality, name: e.target.value })}
              sx={{
                '& .MuiOutlinedInput-root': {
                  borderRadius: 2,
                },
              }}
            />
            <TextField
              label="描述"
              fullWidth
              multiline
              rows={3}
              value={editingPersonality.description}
              onChange={(e) => setEditingPersonality({ ...editingPersonality, description: e.target.value })}
              placeholder="描述此人设的特点和用途"
              sx={{
                '& .MuiOutlinedInput-root': {
                  borderRadius: 2,
                },
              }}
            />
            <TextField
              label="提示词"
              fullWidth
              multiline
              rows={8}
              value={editingPersonality.prompt}
              onChange={(e) => setEditingPersonality({ ...editingPersonality, prompt: e.target.value })}
              placeholder="输入系统提示词，用于定义机器人的行为和回复风格"
              sx={{
                '& .MuiOutlinedInput-root': {
                  borderRadius: 2,
                },
              }}
            />
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', p: 2, bgcolor: 'background.default', borderRadius: 2 }}>
              <Box>
                <Typography variant="subtitle1" sx={{ fontWeight: 500 }}>
                  启用此人设
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  启用后将可用于对话
                </Typography>
              </Box>
              <Switch
                checked={editingPersonality.enabled}
                onChange={(e) => setEditingPersonality({ ...editingPersonality, enabled: e.target.checked })}
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

export default Personalities;
