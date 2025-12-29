import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/useAuth';
import {
  Box,
  Button,
  Container,
  CssBaseline,
  Paper,
  TextField,
  Typography,
  ThemeProvider,
  createTheme,
  Alert,
  Avatar,
  Chip,
} from '@mui/material';
import { VpnKey as VpnKeyIcon } from '@mui/icons-material';
import { z } from 'zod';

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

const passwordSchema = z.object({
  oldPassword: z.string().min(1, '旧密码不能为空'),
  newPassword: z.string().min(6, '新密码至少6个字符'),
  confirmPassword: z.string().min(1, '请确认新密码'),
}).refine((data) => data.newPassword === data.confirmPassword, {
  message: '两次输入的密码不一致',
  path: ['confirmPassword'],
});

const ChangePassword: React.FC = () => {
  const { changePassword, isDemo } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [formData, setFormData] = useState({
    oldPassword: '',
    newPassword: '',
    confirmPassword: '',
  });

  const handleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = event.target;
    setFormData(prev => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setSuccess(false);
    
    const validation = passwordSchema.safeParse({
      oldPassword: formData.oldPassword,
      newPassword: formData.newPassword,
      confirmPassword: formData.confirmPassword,
    });

    if (!validation.success) {
      setError(validation.error.issues[0].message);
      return;
    }

    setLoading(true);

    try {
      const result = await changePassword(formData.oldPassword, formData.newPassword);
      if (result) {
        setSuccess(true);
        setFormData({
          oldPassword: '',
          newPassword: '',
          confirmPassword: '',
        });
      } else {
        setError('密码修改失败，请检查旧密码是否正确');
      }
    } catch (err) {
      setError('密码修改失败，请稍后重试');
      console.error('修改密码错误:', err);
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
                  bgcolor: 'primary.main',
                  boxShadow: '0 4px 12px rgba(25, 118, 210, 0.3)',
                  mb: 2,
                }}
              >
                <VpnKeyIcon sx={{ fontSize: 36 }} />
              </Avatar>
              <Typography component="h1" variant="h4" sx={{ fontWeight: 600 }}>
                修改密码
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                为了账户安全，请定期修改密码
              </Typography>
            </Box>

            <Box sx={{ display: 'flex', gap: 1, mb: 3, justifyContent: 'center' }}>
              <Chip label="安全设置" color="primary" size="small" />
              <Chip label="账户管理" color="secondary" size="small" />
            </Box>

            {isDemo && (
              <Alert severity="warning" sx={{ marginBottom: 3, width: '100%', borderRadius: 2 }}>
                Demo模式下不允许修改密码
              </Alert>
            )}

            {error && (
              <Alert severity="error" sx={{ marginBottom: 3, width: '100%', borderRadius: 2 }}>
                {error}
              </Alert>
            )}

            {success && (
              <Alert severity="success" sx={{ marginBottom: 3, width: '100%', borderRadius: 2 }}>
                密码修改成功！
              </Alert>
            )}

            <Box component="form" onSubmit={handleSubmit} sx={{ mt: 1, width: '100%' }}>
              <TextField
                margin="normal"
                required
                fullWidth
                id="oldPassword"
                label="旧密码"
                name="oldPassword"
                type="password"
                autoComplete="current-password"
                value={formData.oldPassword}
                onChange={handleChange}
                disabled={isDemo}
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
                id="newPassword"
                label="新密码"
                name="newPassword"
                type="password"
                autoComplete="new-password"
                value={formData.newPassword}
                onChange={handleChange}
                disabled={isDemo}
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
                id="confirmPassword"
                label="确认新密码"
                name="confirmPassword"
                type="password"
                autoComplete="new-password"
                value={formData.confirmPassword}
                onChange={handleChange}
                disabled={isDemo}
                sx={{
                  '& .MuiOutlinedInput-root': {
                    borderRadius: 2,
                  },
                }}
              />

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
                disabled={loading || isDemo}
              >
                {loading ? '修改中...' : '修改密码'}
              </Button>

              <Button
                fullWidth
                variant="outlined"
                sx={{
                  mt: 1,
                  borderRadius: 2,
                  textTransform: 'none',
                }}
                onClick={() => navigate('/dashboard')}
              >
                返回仪表盘
              </Button>
            </Box>
          </Paper>
        </Box>
      </Container>
    </ThemeProvider>
  );
};

export default ChangePassword;
