import api from './api'

export const authApi = {
  // 用户登录
  login: (username: string, password: string) => {
    const formData = new FormData()
    formData.append('username', username)
    formData.append('password', password)
    return api.post('/users/login', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
  },

  // 用户注册
  register: (email: string, username: string, password: string, fullName?: string) => {
    return api.post('/users/register', {
      email,
      username,
      password,
      full_name: fullName,
    })
  },

  // 获取当前用户信息
  getCurrentUser: () => {
    return api.get('/users/me')
  },

  // 更新用户信息
  updateCurrentUser: (data: {
    email?: string
    full_name?: string
    password?: string
  }) => {
    return api.put('/users/me', data)
  },
}
