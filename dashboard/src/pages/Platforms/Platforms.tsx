import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Switch,
  Button,
  IconButton,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Alert,
  CircularProgress,
  Avatar,
  Chip,
  Grid,
} from '@mui/material';
import {
  Edit as EditIcon,
  Check as CheckIcon,
  Close as CloseIcon,
  Settings as SettingsIcon,
  Refresh as RefreshIcon,
  Info as InfoIcon,
  Hub as HubIcon,
} from '@mui/icons-material';
import { apiClient, type ApiResponse } from '../../utils/api';

// 平台适配器类型定义
interface PlatformAdapter {
  id: string;
  name: string;
  type: string;
  enabled: boolean;
  status: 'online' | 'offline' | 'error';
  description: string;
  config: {
    host: string;
    port: number;
    token?: string;
    commandPrefix: string;
  };
  messageStats: {
    sent: number;
    received: number;
    error: number;
  };
}

interface PlatformStats {
  [platformId: string]: {
    name?: string;
    display_name?: string;
    type: string;
    enabled?: boolean;
    status: 'online' | 'offline' | 'error';
    description?: string;
    config: {
      host: string;
      port: number;
      token?: string;
      commandPrefix: string;
    };
    messageStats: {
      sent: number;
      received: number;
      error: number;
    };
  };
}

const Platforms: React.FC = () => {
  // 平台列表状态
  const [platforms, setPlatforms] = useState<PlatformAdapter[]>([]);
  // 编辑对话框状态
  const [openEditDialog, setOpenEditDialog] = useState(false);
  // 当前编辑的平台
  const [currentPlatform, setCurrentPlatform] = useState<PlatformAdapter | null>(null);
  // 编辑表单数据
  const [formData, setFormData] = useState<Partial<PlatformAdapter>>({});
  // 加载状态
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 获取平台列表数据
  useEffect(() => {
    const fetchPlatforms = async () => {
      setLoading(true);
      setError(null);
      try {
        const response: ApiResponse<PlatformStats> = await apiClient.get('/api/platform/stats');
        if (response.status === 'success' && response.data) {
          const platformList = Object.entries(response.data).map(([id, p]) => ({
            id,
            name: p.name || p.display_name || `Platform ${id}`,
            type: p.type || 'unknown',
            enabled: p.enabled ?? true,
            status: p.status || 'offline',
            description: p.description || '',
            config: p.config || { host: '', port: 0, commandPrefix: '' },
            messageStats: p.messageStats || { sent: 0, received: 0, error: 0 },
          })) as PlatformAdapter[];
          setPlatforms(platformList);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : '获取平台列表失败');
      } finally {
        setLoading(false);
      }
    };

    fetchPlatforms();
  }, []);

  // 处理平台启用/禁用
  const handleTogglePlatform = (platformId: string) => {
    setPlatforms(prev => prev.map(platform => 
      platform.id === platformId 
        ? { ...platform, enabled: !platform.enabled }
        : platform
    ));
  };

  // 处理编辑平台
  const handleEditPlatform = (platform: PlatformAdapter) => {
    setCurrentPlatform(platform);
    setFormData({ ...platform });
    setOpenEditDialog(true);
  };

  // 处理关闭编辑对话框
  const handleCloseEditDialog = () => {
    setOpenEditDialog(false);
    setCurrentPlatform(null);
    setFormData({});
  };

  // 处理表单字段变化
  const handleFormChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setFormData(prev => {
      const updatedData = { ...prev };
      
      // 如果是config字段，更新到config对象中
      if (name === 'host' || name === 'port' || name === 'commandPrefix' || name === 'token') {
        updatedData.config = {
          ...(prev.config || { host: '', port: 0, commandPrefix: '' }),
          [name]: name === 'port' ? parseInt(value, 10) : value,
        };
      } else {
        // 否则更新到根对象中
        if (value !== undefined) {
          (updatedData as Record<string, unknown>)[name] = value;
        }
      }
      
      return updatedData;
    });
  };

  // 处理保存平台配置
  const handleSavePlatform = () => {
    if (currentPlatform && formData) {
      setPlatforms(prev => prev.map(platform => 
        platform.id === currentPlatform.id 
          ? { ...platform, ...formData as PlatformAdapter }
          : platform
      ));
      handleCloseEditDialog();
    }
  };

  // 渲染平台状态指示器
  const renderStatusIndicator = (status: string) => {
    switch (status) {
      case 'online':
        return <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: 'success.main', mr: 1 }} />;
      case 'offline':
        return <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: 'warning.main', mr: 1 }} />;
      case 'error':
        return <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: 'error.main', mr: 1 }} />;
      default:
        return <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: 'grey.main', mr: 1 }} />;
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
            消息平台适配器
          </Typography>
          <Typography variant="body1" color="text.secondary">
            管理和配置消息平台适配器，实时监控平台状态
          </Typography>
        </Box>
        <Avatar
          sx={{
            width: 56,
            height: 56,
            bgcolor: 'success.main',
            boxShadow: '0 4px 12px rgba(76, 175, 80, 0.3)',
          }}
        >
          <HubIcon sx={{ fontSize: 32 }} />
        </Avatar>
      </Stack>

      <Box sx={{ display: 'flex', gap: 1, mb: 3 }}>
        <Chip label="平台管理" color="primary" />
        <Chip label="实时监控" color="secondary" />
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h6">
          平台统计
        </Typography>
        <Button
          variant="outlined"
          startIcon={<RefreshIcon />}
          onClick={() => window.location.reload()}
          sx={{
            borderRadius: 2,
            textTransform: 'none',
          }}
        >
          刷新列表
        </Button>
      </Stack>

      {/* 平台统计卡片 */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Paper
            sx={{
              p: 3,
              borderRadius: 2,
              border: '1px solid',
              borderColor: 'divider',
              boxShadow: '0 2px 14px 0 rgb(32 40 45 / 8%)',
              '&:hover': {
                boxShadow: '0 4px 20px 0 rgb(32 40 45 / 12%)',
              },
            }}
          >
            <Stack spacing={1}>
              <Typography variant="body2" color="text.secondary">
                总平台数
              </Typography>
              <Typography variant="h4" sx={{ fontWeight: 600 }}>
                {platforms.length}
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', mt: 1 }}>
                <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: 'success.main', mr: 1 }} />
                <Typography variant="body2" color="text.secondary">
                  {platforms.filter(p => p.enabled).length} 个平台已启用
                </Typography>
              </Box>
            </Stack>
          </Paper>
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Paper
            sx={{
              p: 3,
              borderRadius: 2,
              border: '1px solid',
              borderColor: 'divider',
              boxShadow: '0 2px 14px 0 rgb(32 40 45 / 8%)',
              '&:hover': {
                boxShadow: '0 4px 20px 0 rgb(32 40 45 / 12%)',
              },
            }}
          >
            <Stack spacing={1}>
              <Typography variant="body2" color="text.secondary">
                在线平台
              </Typography>
              <Typography variant="h4" sx={{ fontWeight: 600, color: 'success.main' }}>
                {platforms.filter(p => p.status === 'online').length}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                实时在线状态
              </Typography>
            </Stack>
          </Paper>
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Paper
            sx={{
              p: 3,
              borderRadius: 2,
              border: '1px solid',
              borderColor: 'divider',
              boxShadow: '0 2px 14px 0 rgb(32 40 45 / 8%)',
              '&:hover': {
                boxShadow: '0 4px 20px 0 rgb(32 40 45 / 12%)',
              },
            }}
          >
            <Stack spacing={1}>
              <Typography variant="body2" color="text.secondary">
                消息总数
              </Typography>
              <Typography variant="h4" sx={{ fontWeight: 600 }}>
                {platforms.reduce((sum, p) => sum + (p.messageStats?.sent ?? 0) + (p.messageStats?.received ?? 0), 0)}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                所有平台消息统计
              </Typography>
            </Stack>
          </Paper>
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Paper
            sx={{
              p: 3,
              borderRadius: 2,
              border: '1px solid',
              borderColor: 'divider',
              boxShadow: '0 2px 14px 0 rgb(32 40 45 / 8%)',
              '&:hover': {
                boxShadow: '0 4px 20px 0 rgb(32 40 45 / 12%)',
              },
            }}
          >
            <Stack spacing={1}>
              <Typography variant="body2" color="text.secondary">
                错误率
              </Typography>
              <Typography variant="h4" sx={{ fontWeight: 600, color: 'error.main' }}>
                {platforms.length > 0 ?
                  `${((platforms.reduce((sum, p) => sum + (p.messageStats?.error ?? 0), 0) /
                    platforms.reduce((sum, p) => sum + (p.messageStats?.sent ?? 0) + (p.messageStats?.received ?? 0), 1)) * 100).toFixed(2)}%` : '0%'}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                消息处理错误率
              </Typography>
            </Stack>
          </Paper>
        </Grid>
      </Grid>

      <Typography variant="h6" sx={{ mb: 3 }}>
        平台适配器列表 ({platforms.length})
      </Typography>

      {/* 平台列表表格 */}
      <Paper
        sx={{
          borderRadius: 2,
          overflow: 'hidden',
          border: '1px solid',
          borderColor: 'divider',
          boxShadow: '0 2px 14px 0 rgb(32 40 45 / 8%)',
        }}
      >
        <TableContainer>
          <Table sx={{ minWidth: 650 }}>
            <TableHead>
              <TableRow sx={{ '& th': { fontWeight: 600, bgcolor: 'background.paper', borderBottom: 2, borderColor: 'divider' } }}>
                <TableCell sx={{ pl: 3 }}>平台信息</TableCell>
                <TableCell>类型</TableCell>
                <TableCell>状态</TableCell>
                <TableCell>消息统计</TableCell>
                <TableCell sx={{ pr: 3, textAlign: 'right' }}>操作</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {platforms.map((platform) => (
                <TableRow
                  key={platform.id}
                  sx={{
                    '&:last-child td, &:last-child th': { border: 0 },
                    '&:hover': { bgcolor: 'background.default' },
                    transition: 'background-color 0.2s ease',
                  }}
                >
                  <TableCell sx={{ pl: 3, py: 2.5 }}>
                    <Stack direction="row" alignItems="center" spacing={2}>
                      <Box sx={{ 
                        width: 40, 
                        height: 40, 
                        borderRadius: '50%', 
                        bgcolor: 'primary.main', 
                        display: 'flex', 
                        alignItems: 'center', 
                        justifyContent: 'center',
                        color: 'white',
                        fontWeight: 600,
                      }}>
                        {platform.name?.charAt(0) || '?'}
                      </Box>
                      <Stack>
                        <Typography variant="body1" sx={{ fontWeight: 600 }}>
                          {platform.name || 'Unknown'}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          {platform.description || '暂无描述'}
                        </Typography>
                      </Stack>
                    </Stack>
                  </TableCell>
                  <TableCell sx={{ py: 2.5 }}>
                    <Box sx={{ 
                      display: 'inline-block', 
                      px: 2, 
                      py: 0.5, 
                      borderRadius: 1, 
                      bgcolor: 'primary.light', 
                      color: 'primary.dark',
                      fontSize: '0.75rem',
                      fontWeight: 600,
                    }}>
                      {platform.type || 'unknown'}
                    </Box>
                  </TableCell>
                  <TableCell sx={{ py: 2.5 }}>
                    <Stack direction="row" alignItems="center" spacing={1}>
                      {renderStatusIndicator(platform.status)}
                      <Typography variant="body2" sx={{ fontWeight: 500 }}>
                        {platform.status === 'online' ? '在线' : platform.status === 'offline' ? '离线' : '错误'}
                      </Typography>
                      <Box sx={{ ml: 2 }}>
                        <Switch
                          checked={platform.enabled}
                          onChange={() => handleTogglePlatform(platform.id)}
                          size="small"
                        />
                      </Box>
                    </Stack>
                  </TableCell>
                  <TableCell sx={{ py: 2.5 }}>
                    <Stack direction="row" spacing={3}>
                      <Box sx={{ textAlign: 'center' }}>
                        <Typography variant="body2" color="text.secondary">发送</Typography>
                        <Typography variant="body1" sx={{ fontWeight: 600 }}>{platform.messageStats?.sent ?? 0}</Typography>
                      </Box>
                      <Box sx={{ textAlign: 'center' }}>
                        <Typography variant="body2" color="text.secondary">接收</Typography>
                        <Typography variant="body1" sx={{ fontWeight: 600 }}>{platform.messageStats?.received ?? 0}</Typography>
                      </Box>
                      <Box sx={{ textAlign: 'center' }}>
                        <Typography variant="body2" color="text.secondary">错误</Typography>
                        <Typography variant="body1" sx={{ fontWeight: 600, color: 'error.main' }}>{platform.messageStats?.error ?? 0}</Typography>
                      </Box>
                    </Stack>
                  </TableCell>
                  <TableCell sx={{ pr: 3, py: 2.5, textAlign: 'right' }}>
                    <Stack direction="row" justifyContent="flex-end" spacing={1}>
                      <Tooltip title="查看详情">
                        <IconButton size="small" color="info">
                          <InfoIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="配置">
                        <IconButton size="small" color="primary" onClick={() => handleEditPlatform(platform)}>
                          <SettingsIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="编辑">
                        <IconButton size="small" color="warning" onClick={() => handleEditPlatform(platform)}>
                          <EditIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </Stack>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>

      {/* 编辑平台对话框 */}
      <Dialog
        open={openEditDialog}
        onClose={handleCloseEditDialog}
        maxWidth="md"
        fullWidth
        PaperProps={{
          sx: {
            borderRadius: 2,
          },
        }}
      >
        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontWeight: 600 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <EditIcon fontSize="small" />
            编辑平台配置
          </Box>
          <IconButton
            onClick={handleCloseEditDialog}
            sx={{ p: 0.5, color: 'text.secondary' }}
          >
            <CloseIcon fontSize="small" />
          </IconButton>
        </DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)' }, gap: 3, mt: 1 }}>
            <Box>
              <TextField
                fullWidth
                label="平台名称"
                name="name"
                value={formData.name || ''}
                onChange={handleFormChange}
                sx={{ mb: 2 }}
              />
              <TextField
                fullWidth
                label="平台类型"
                name="type"
                value={formData.type || ''}
                onChange={handleFormChange}
                disabled
                sx={{ mb: 2 }}
              />
              <TextField
                fullWidth
                label="描述"
                name="description"
                value={formData.description || ''}
                onChange={handleFormChange}
                multiline
                rows={3}
              />
            </Box>
            <Box>
              <TextField
                fullWidth
                label="主机地址"
                name="host"
                value={formData.config?.host || ''}
                onChange={handleFormChange}
                sx={{ mb: 2 }}
              />
              <TextField
                fullWidth
                label="端口"
                name="port"
                type="number"
                value={formData.config?.port || ''}
                onChange={handleFormChange}
                sx={{ mb: 2 }}
              />
              <TextField
                fullWidth
                label="命令前缀"
                name="commandPrefix"
                value={formData.config?.commandPrefix || ''}
                onChange={handleFormChange}
              />
            </Box>
          </Box>
        </DialogContent>
        <DialogActions sx={{ p: 2, borderTop: 1, borderColor: 'divider', justifyContent: 'space-between' }}>
          <Button onClick={handleCloseEditDialog} color="inherit">
            取消
          </Button>
          <Button onClick={handleSavePlatform} variant="contained" startIcon={<CheckIcon />}>
            保存配置
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default Platforms;
