import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/useAuth';
import {
  Box,
  Button,
  Container,
  CssBaseline,
  FormControlLabel,
  IconButton,
  InputAdornment,
  Paper,
  TextField,
  Typography,
  ThemeProvider,
  createTheme,
  Link,
  Alert,
  Stack,
  Avatar,
  Chip,
} from '@mui/material';
import {
  Visibility,
  VisibilityOff,
} from '@mui/icons-material';
import { z } from 'zod';

// 创建主题
const theme = createTheme({
  palette: {
    primary: {
      main: '#1976d2',
    },
    secondary: {
      main: '#dc004e',
    },
    mode: 'dark',
  },
});

// 登录表单验证Schema
const loginSchema = z.object({
  username: z.string().min(1, '用户名不能为空'),
  password: z.string().min(1, '密码不能为空'),
});

const Login: React.FC = () => {
  const { login, isDemo } = useAuth();
  const navigate = useNavigate();
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [formData, setFormData] = useState({
    username: '',
    password: '',
    remember: false,
  });

  // 加载记住的登录凭证
  useEffect(() => {
    try {
      const remembered = localStorage.getItem('remembered_credentials');
      if (remembered) {
        const credentials = JSON.parse(remembered);
        setFormData(prev => ({
          ...prev,
          username: credentials.username || '',
          password: credentials.password || '',
          remember: true,
        }));
      }
    } catch (error) {
      console.error('加载记住的凭证失败:', error);
    }
  }, []);

  const handleClickShowPassword = () => {
    setShowPassword(!showPassword);
  };

  const handleMouseDownPassword = (event: React.MouseEvent<HTMLButtonElement>) => {
    event.preventDefault();
  };

  const handleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value, type, checked } = event.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value,
    }));
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    
    // 验证表单
    const validation = loginSchema.safeParse({
      username: formData.username,
      password: formData.password,
    });

    if (!validation.success) {
      setError(validation.error.issues[0].message);
      return;
    }

    setLoading(true);

    try {
      const success = await login(formData.username, formData.password, formData.remember);
      if (success) {
        // 登录成功，跳转到仪表盘
        navigate('/dashboard');
      } else {
        setError('用户名或密码错误');
      }
    } catch (err) {
      setError('登录失败，请稍后重试');
      console.error('登录错误:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <ThemeProvider theme={theme}>
      <Container component="main" maxWidth="sm">
        <CssBaseline />
        <Box
          sx={{
            minHeight: '100vh',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            py: 4,
          }}
        >
          <Paper
            elevation={0}
            sx={{
              padding: 4,
              width: '100%',
              border: '1px solid',
              borderColor: 'divider',
              boxShadow: '0 2px 14px 0 rgb(32 40 45 / 8%)',
              borderRadius: 3,
            }}
          >
            <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', marginBottom: 3 }}>
              <Avatar
                sx={{
                  width: 64,
                  height: 64,
                  boxShadow: '0 4px 12px rgba(25, 118, 210, 0.3)',
                  mb: 2,
                }}
              >
                <img src="/logo.svg" alt="NekoBot" style={{ width: '100%', height: '100%' }} />
              </Avatar>
              <Typography component="h1" variant="h4" sx={{ fontWeight: 600 }}>
                NekoBot 登录
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                欢迎回来，请输入您的凭据
              </Typography>
            </Box>

            <Box sx={{ display: 'flex', gap: 1, mb: 3, justifyContent: 'center' }}>
              <Chip label="安全登录" color="primary" size="small" />
              <Chip label="快速访问" color="secondary" size="small" />
            </Box>

            {isDemo && (
              <Alert severity="warning" sx={{ marginBottom: 3, width: '100%', borderRadius: 2 }}>
                当前为 Demo 模式，默认密码为 nekobot，不允许修改密码、安装插件、创建适配器、重启等敏感操作
              </Alert>
            )}

            {error && (
              <Alert severity="error" sx={{ marginBottom: 3, width: '100%', borderRadius: 2 }}>
                {error}
              </Alert>
            )}

            <Box component="form" onSubmit={handleSubmit} sx={{ mt: 1, width: '100%' }}>
              <TextField
                margin="normal"
                required
                fullWidth
                id="username"
                label="用户名"
                name="username"
                autoComplete="username"
                autoFocus
                value={formData.username}
                onChange={handleChange}
                sx={{
                  '& .MuiOutlinedInput-root': {
                    borderRadius: 2,
                  },
                }}
              />
              
              <TextField
                margin="normal"
                required
                fullWidth
                id="password"
                label="密码"
                name="password"
                type={showPassword ? 'text' : 'password'}
                value={formData.password}
                onChange={handleChange}
                autoComplete="current-password"
                InputProps={{
                  endAdornment: (
                    <InputAdornment position="end">
                      <IconButton
                        aria-label="切换密码可见性"
                        onClick={handleClickShowPassword}
                        onMouseDown={handleMouseDownPassword}
                        edge="end"
                      >
                        {showPassword ? <VisibilityOff /> : <Visibility />}
                      </IconButton>
                    </InputAdornment>
                  ),
                }}
                sx={{
                  '& .MuiOutlinedInput-root': {
                    borderRadius: 2,
                  },
                }}
              />

              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mt: 2 }}>
                <FormControlLabel
                  control={
                    <input
                      type="checkbox"
                      name="remember"
                      checked={formData.remember}
                      onChange={handleChange}
                    />
                  }
                  label="记住密码"
                />
                <Link href="#" variant="body2" sx={{ fontWeight: 500 }}>
                  忘记密码?
                </Link>
              </Box>

              <Button
                type="submit"
                fullWidth
                variant="contained"
                sx={{
                  mt: 3,
                  mb: 2,
                  py: 1.5,
                  fontSize: '1rem',
                  fontWeight: 600,
                  borderRadius: 2,
                  textTransform: 'none',
                }}
                disabled={loading}
              >
                {loading ? '登录中...' : '登录'}
              </Button>

              <Stack direction="row" sx={{ justifyContent: 'center', alignItems: 'center', mt: 2 }}>
                <Typography variant="body2" color="text.secondary">
                  © {new Date().getFullYear()} NekoBotTeam
                </Typography>
              </Stack>
            </Box>
          </Paper>
        </Box>
      </Container>
    </ThemeProvider>
  );
};

export default Login;
