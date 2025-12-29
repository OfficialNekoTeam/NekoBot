import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Divider,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Chip,
  CircularProgress,
  Tooltip,
  Paper,
} from '@mui/material';
import {
  Monitor as MonitorIcon,
  Memory as MemoryIcon,
  Extension as ExtensionIcon,
  Chat as ChatIcon,
  BarChart as BarChartIcon,
  ArrowUpward as ArrowUpwardIcon,
  ArrowDownward as ArrowDownwardIcon,
  TrendingUp as TrendingUpIcon,
  Speed as SpeedIcon,
  Cloud as CloudIcon,
  CheckCircle as CheckCircleIcon,
} from '@mui/icons-material';
import { apiClient, type SystemStats, type MessageStat } from '../../utils/api';

const Dashboard: React.FC = () => {
  const [systemStats, setSystemStats] = useState<SystemStats>({
    cpuUsage: 0,
    memoryUsage: 0,
    pluginsCount: 0,
    enabledPluginsCount: 0,
    adaptersCount: 0,
    runningAdaptersCount: 0,
  });
  const [messageStats, setMessageStats] = useState<MessageStat[]>([]);
  const [loading, setLoading] = useState(true);

  // 获取系统统计数据
  useEffect(() => {
    const fetchSystemStats = async () => {
      try {
        setLoading(true);
        
        // 调用真实的API获取系统统计数据
        const response = await apiClient.get<{ status: string; message: string; data: { system: SystemStats; messages: MessageStat[] } }>('/api/stats');
        
        if (response.status === 'success' && response.data) {
          // 更新系统统计数据
          setSystemStats(response.data.system);
          
          // 更新消息统计数据
          setMessageStats(response.data.messages);
        }
      } catch (error) {
        console.error('获取系统统计数据失败:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchSystemStats();
    
    // 定期更新数据，每5秒刷新一次
    const interval = setInterval(fetchSystemStats, 5000);
    return () => clearInterval(interval);
  }, []);

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
          仪表盘
        </Typography>
        <Typography variant="body1" color="text.secondary" sx={{ mt: 1 }}>
          查看系统状态和消息统计
        </Typography>
      </Box>

      {/* 系统统计卡片 */}
      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', md: 'repeat(4, 1fr)' }, gap: 3, mb: 4 }}>
        {/* CPU使用率卡片 */}
        <Paper
          className="glass-card card-hover"
          sx={{
            p: 3,
            height: '100%',
            position: 'relative',
            overflow: 'hidden',
          }}
        >
          <Box sx={{ position: 'relative', zIndex: 1 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
              <Box>
                <Typography variant="body2" color="text.secondary" gutterBottom sx={{ fontWeight: 500 }}>
                  CPU 使用率
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'baseline', mt: 1 }}>
                  {loading ? (
                    <CircularProgress size={28} />
                  ) : (
                    <>
                      <Typography variant="h3" component="span" sx={{ fontWeight: 700 }}>
                        {systemStats.cpuUsage}%
                      </Typography>
                    </>
                  )}
                </Box>
              </Box>
              <Box
                sx={{
                  p: 2.5,
                  borderRadius: '16px',
                  background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                  color: 'white',
                  boxShadow: '0 8px 16px -4px rgba(102, 126, 234, 0.3)',
                }}
              >
                <MonitorIcon fontSize="large" />
              </Box>
            </Box>
            <Box sx={{ mt: 2 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <TrendingUpIcon sx={{ fontSize: 16, color: 'success.main' }} />
                <Typography variant="caption" color="success.main" sx={{ fontWeight: 600 }}>
                  运行正常
                </Typography>
              </Box>
            </Box>
          </Box>
        </Paper>

        {/* 内存使用率卡片 */}
        <Paper
          className="glass-card card-hover"
          sx={{
            p: 3,
            height: '100%',
            position: 'relative',
            overflow: 'hidden',
          }}
        >
          <Box sx={{ position: 'relative', zIndex: 1 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
              <Box>
                <Typography variant="body2" color="text.secondary" gutterBottom sx={{ fontWeight: 500 }}>
                  内存使用率
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'baseline', mt: 1 }}>
                  {loading ? (
                    <CircularProgress size={28} />
                  ) : (
                    <>
                      <Typography variant="h3" component="span" sx={{ fontWeight: 700 }}>
                        {systemStats.memoryUsage}%
                      </Typography>
                    </>
                  )}
                </Box>
              </Box>
              <Box
                sx={{
                  p: 2.5,
                  borderRadius: '16px',
                  background: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
                  color: 'white',
                  boxShadow: '0 8px 16px -4px rgba(245, 87, 108, 0.3)',
                }}
              >
                <MemoryIcon fontSize="large" />
              </Box>
            </Box>
            <Box sx={{ mt: 2 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <SpeedIcon sx={{ fontSize: 16, color: 'info.main' }} />
                <Typography variant="caption" color="info.main" sx={{ fontWeight: 600 }}>
                  性能良好
                </Typography>
              </Box>
            </Box>
          </Box>
        </Paper>

        {/* 插件数量卡片 */}
        <Paper
          className="glass-card card-hover"
          sx={{
            p: 3,
            height: '100%',
            position: 'relative',
            overflow: 'hidden',
          }}
        >
          <Box sx={{ position: 'relative', zIndex: 1 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
              <Box>
                <Typography variant="body2" color="text.secondary" gutterBottom sx={{ fontWeight: 500 }}>
                  插件数量
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'baseline', mt: 1 }}>
                  {loading ? (
                    <CircularProgress size={28} />
                  ) : (
                    <>
                      <Typography variant="h3" component="span" sx={{ fontWeight: 700 }}>
                        {systemStats.enabledPluginsCount}
                      </Typography>
                      <Typography variant="body2" color="text.secondary" sx={{ ml: 1 }}>
                        / {systemStats.pluginsCount}
                      </Typography>
                    </>
                  )}
                </Box>
              </Box>
              <Box
                sx={{
                  p: 2.5,
                  borderRadius: '16px',
                  background: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
                  color: 'white',
                  boxShadow: '0 8px 16px -4px rgba(0, 242, 254, 0.3)',
                }}
              >
                <ExtensionIcon fontSize="large" />
              </Box>
            </Box>
            <Box sx={{ mt: 2 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <CloudIcon sx={{ fontSize: 16, color: 'success.main' }} />
                <Typography variant="caption" color="success.main" sx={{ fontWeight: 600 }}>
                  已加载
                </Typography>
              </Box>
            </Box>
          </Box>
        </Paper>

        {/* 适配器数量卡片 */}
        <Paper
          className="glass-card card-hover"
          sx={{
            p: 3,
            height: '100%',
            position: 'relative',
            overflow: 'hidden',
          }}
        >
          <Box sx={{ position: 'relative', zIndex: 1 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
              <Box>
                <Typography variant="body2" color="text.secondary" gutterBottom sx={{ fontWeight: 500 }}>
                  消息适配器
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'baseline', mt: 1 }}>
                  {loading ? (
                    <CircularProgress size={28} />
                  ) : (
                    <>
                      <Typography variant="h3" component="span" sx={{ fontWeight: 700 }}>
                        {systemStats.runningAdaptersCount}
                      </Typography>
                      <Typography variant="body2" color="text.secondary" sx={{ ml: 1 }}>
                        / {systemStats.adaptersCount}
                      </Typography>
                    </>
                  )}
                </Box>
              </Box>
              <Box
                sx={{
                  p: 2.5,
                  borderRadius: '16px',
                  background: 'linear-gradient(135deg, #fa709a 0%, #fee140 100%)',
                  color: 'white',
                  boxShadow: '0 8px 16px -4px rgba(254, 225, 64, 0.3)',
                }}
              >
                <ChatIcon fontSize="large" />
              </Box>
            </Box>
            <Box sx={{ mt: 2 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                {systemStats.runningAdaptersCount > 0 ? (
                  <>
                    <CheckCircleIcon sx={{ fontSize: 16, color: 'success.main' }} />
                    <Typography variant="caption" color="success.main" sx={{ fontWeight: 600 }}>
                      运行中
                    </Typography>
                  </>
                ) : (
                  <>
                    <TrendingUpIcon sx={{ fontSize: 16, color: 'warning.main' }} />
                    <Typography variant="caption" color="warning.main" sx={{ fontWeight: 600 }}>
                      未启动
                    </Typography>
                  </>
                )}
              </Box>
            </Box>
          </Box>
        </Paper>
      </Box>

      {/* 消息统计列表 */}
      <Paper
        className="glass-card"
        sx={{
          borderRadius: 3,
          overflow: 'hidden',
        }}
      >
        <Box sx={{ p: 3, borderBottom: 1, borderColor: 'divider' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Box
              sx={{
                p: 1.5,
                borderRadius: '12px',
                background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                color: 'white',
              }}
            >
              <BarChartIcon />
            </Box>
            <Typography variant="h6" sx={{ fontWeight: 600 }}>
              消息统计
            </Typography>
          </Box>
        </Box>
        <List sx={{ p: 0 }}>
          {loading ? (
            <ListItem>
              <CircularProgress sx={{ mx: 'auto' }} />
            </ListItem>
          ) : (
            messageStats.map((stat, index) => (
              <React.Fragment key={stat.platform}>
                <ListItem
                  sx={{
                    py: 2.5,
                    px: 3,
                    transition: 'all 0.3s ease',
                    '&:hover': {
                      backgroundColor: 'action.hover',
                    },
                  }}
                >
                  <ListItemIcon>
                    <Box
                      sx={{
                        p: 1.5,
                        borderRadius: '12px',
                        background: 'linear-gradient(135deg, #a8edea 0%, #fed6e3 100%)',
                        color: 'white',
                      }}
                    >
                      <ChatIcon />
                    </Box>
                  </ListItemIcon>
                  <ListItemText
                    primary={
                      <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                        {stat.platform}
                      </Typography>
                    }
                    secondary={`${stat.messages} 条消息`}
                  />
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                    <Typography variant="h6" sx={{ fontWeight: 700 }}>
                      {stat.messages}
                    </Typography>
                    <Tooltip title={`${stat.change}% ${stat.trend === 'up' ? '增长' : '下降'}`}>
                      <Chip
                        label={
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                            {stat.trend === 'up' ? (
                              <ArrowUpwardIcon fontSize="small" />
                            ) : (
                              <ArrowDownwardIcon fontSize="small" />
                            )}
                            {Math.abs(stat.change)}%
                          </Box>
                        }
                        size="medium"
                        sx={{
                          fontWeight: 600,
                          borderRadius: '8px',
                          px: 1.5,
                          py: 0.75,
                        }}
                        color={stat.trend === 'up' ? 'success' : 'error'}
                      />
                    </Tooltip>
                  </Box>
                </ListItem>
                {index < messageStats.length - 1 && (
                  <Divider sx={{ mx: 3 }} />
                )}
              </React.Fragment>
            ))
          )}
        </List>
      </Paper>
    </Box>
  );
};

export default Dashboard;
