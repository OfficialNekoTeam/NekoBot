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
import ExtensionIcon from '@mui/icons-material/Extension';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';
import { apiClient, type ApiResponse, type McpConfig } from '../../utils/api';

const MCP: React.FC = () => {
  const [mcpList, setMcpList] = useState<McpConfig[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingMcp, setEditingMcp] = useState<Partial<McpConfig>>({
    name: '',
    type: '',
    config: {},
    enabled: true,
  });

  useEffect(() => {
    loadMcpList();
  }, []);

  const loadMcpList = async () => {
    setLoading(true);
    setError(null);
    try {
      const response: ApiResponse<{ mcps: McpConfig[] }> = await apiClient.get('/api/mcp/list');
      if (response.status === 'success' && response.data) {
        setMcpList(response.data.mcps);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载MCP列表失败');
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = () => {
    setEditingMcp({
      name: '',
      type: '',
      config: {},
      enabled: true,
    });
    setDialogOpen(true);
  };

  const handleEdit = (mcp: McpConfig) => {
    setEditingMcp(mcp);
    setDialogOpen(true);
  };

  const handleDelete = async (id: string) => {
    setError(null);
    setSuccess(false);
    try {
      const response: ApiResponse<null> = await apiClient.post('/api/mcp/delete', {
        id,
      });
      if (response.status === 'success') {
        setSuccess(true);
        setTimeout(() => setSuccess(false), 3000);
        await loadMcpList();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除失败');
    }
  };

  const handleSave = async () => {
    if (!editingMcp.name || !editingMcp.type) return;

    setError(null);
    setSuccess(false);
    try {
      if (editingMcp.id) {
        const response: ApiResponse<null> = await apiClient.post('/api/mcp/update', {
          id: editingMcp.id,
          name: editingMcp.name,
          type: editingMcp.type,
          config: editingMcp.config,
          enabled: editingMcp.enabled,
        });
        if (response.status === 'success') {
          setSuccess(true);
          setTimeout(() => setSuccess(false), 3000);
          await loadMcpList();
        }
      } else {
        const response: ApiResponse<{ id: string }> = await apiClient.post('/api/mcp/add', {
          name: editingMcp.name,
          type: editingMcp.type,
          config: editingMcp.config,
          enabled: editingMcp.enabled,
        });
        if (response.status === 'success') {
          setSuccess(true);
          setTimeout(() => setSuccess(false), 3000);
          await loadMcpList();
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
            MCP 配置
          </Typography>
          <Typography variant="body1" color="text.secondary">
            配置MCP工具和服务
          </Typography>
        </Box>
        <Avatar
          sx={{
            width: 56,
            height: 56,
            bgcolor: 'warning.main',
            boxShadow: '0 4px 12px rgba(255, 193, 7, 0.3)',
          }}
        >
          <ExtensionIcon sx={{ fontSize: 32 }} />
        </Avatar>
      </Stack>

      <Box sx={{ display: 'flex', gap: 1, mb: 3 }}>
        <Chip label="MCP配置" color="primary" />
        <Chip label="组件管理" color="secondary" />
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
          MCP 列表 ({mcpList.length})
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
          添加MCP
        </Button>
      </Stack>

      <Grid container spacing={3}>
        {mcpList.map((mcp) => (
          <Grid size={{ xs: 12, sm: 6, md: 4 }} key={mcp.id}>
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
                      bgcolor: mcp.enabled ? 'success.light' : 'grey.200',
                      color: mcp.enabled ? 'success.dark' : 'grey.500',
                    }}
                  >
                    {mcp.enabled ? <CheckCircleIcon /> : <CancelIcon />}
                  </Avatar>
                  <Chip
                    label={mcp.type}
                    size="small"
                    color={mcp.enabled ? 'success' : 'default'}
                  />
                </Stack>

                <Typography variant="h6" gutterBottom>
                  {mcp.name}
                </Typography>

                <Divider sx={{ my: 2 }} />

                <Box>
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                    配置
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
                    {typeof mcp.config === 'string' ? mcp.config : JSON.stringify(mcp.config, null, 2)}
                  </Typography>
                </Box>
              </CardContent>

              <Divider />

              <Box sx={{ p: 2 }}>
                <Stack direction="row" sx={{ alignItems: 'center', justifyContent: 'space-between' }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Switch
                      checked={mcp.enabled}
                      onChange={(e) => {
                        const updated = { ...mcp, enabled: e.target.checked };
                        handleEdit(updated);
                      }}
                      color="success"
                      size="small"
                    />
                    <Typography variant="caption" color="text.secondary">
                      {mcp.enabled ? '已启用' : '已禁用'}
                    </Typography>
                  </Box>
                  <Box sx={{ display: 'flex', gap: 0.5 }}>
                    <IconButton
                      size="small"
                      onClick={() => handleEdit(mcp)}
                      sx={{ color: 'primary.main' }}
                    >
                      <EditIcon fontSize="small" />
                    </IconButton>
                    <IconButton
                      size="small"
                      onClick={() => handleDelete(mcp.id)}
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
          {editingMcp.id ? '编辑MCP' : '添加MCP'}
        </DialogTitle>
        <DialogContent>
          <Stack spacing={3} sx={{ mt: 1 }}>
            <TextField
              autoFocus
              label="名称"
              fullWidth
              value={editingMcp.name}
              onChange={(e) => setEditingMcp({ ...editingMcp, name: e.target.value })}
              sx={{
                '& .MuiOutlinedInput-root': {
                  borderRadius: 2,
                },
              }}
            />
            <Select
              value={editingMcp.type}
              onChange={(e) => setEditingMcp({ ...editingMcp, type: e.target.value })}
              label="类型"
              fullWidth
              sx={{
                '& .MuiOutlinedInput-root': {
                  borderRadius: 2,
                },
              }}
            >
              <MenuItem value="function">函数工具</MenuItem>
              <MenuItem value="service">服务</MenuItem>
              <MenuItem value="resource">资源</MenuItem>
            </Select>
            <TextField
              label="配置 (JSON)"
              fullWidth
              multiline
              rows={6}
              value={typeof editingMcp.config === 'string' ? editingMcp.config : JSON.stringify(editingMcp.config, null, 2)}
              onChange={(e) => {
                try {
                  const config = JSON.parse(e.target.value);
                  setEditingMcp({ ...editingMcp, config });
                } catch {
                  // 保持原始字符串值，但类型转换为 Record<string, any>
                  setEditingMcp({ ...editingMcp, config: {} });
                }
              }}
              sx={{
                '& .MuiOutlinedInput-root': {
                  borderRadius: 2,
                },
              }}
            />
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', p: 2, bgcolor: 'background.default', borderRadius: 2 }}>
              <Box>
                <Typography variant="subtitle1" sx={{ fontWeight: 500 }}>
                  启用此MCP
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  启用后将可用于MCP服务
                </Typography>
              </Box>
              <Switch
                checked={editingMcp.enabled}
                onChange={(e) => setEditingMcp({ ...editingMcp, enabled: e.target.checked })}
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

export default MCP;
