'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { login } from '@/services/auth'
import { showToast } from '@/components/Toast'

export default function LoginPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const router = useRouter()

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    try {
      const res = await login(username, password)

      // 存 cookie（有效期 1 天）
      document.cookie = `token=${res.access_token}; path=/; max-age=${24 * 60 * 60}`
      debugger
      showToast('登录成功')
      router.push('/') // 首页路径
    } catch (err) {
      showToast('用户名或密码错误')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <form
        onSubmit={handleLogin}
        className="bg-white shadow-xl rounded-2xl p-8 w-80 border border-gray-100"
      >
        <h1 className="text-2xl font-semibold text-center mb-6 text-gray-800">系统登录</h1>
        <input
          className="w-full border rounded-lg px-3 py-2 mb-4 text-gray-700 focus:ring focus:ring-indigo-100"
          placeholder="用户名"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />
        <input
          type="password"
          className="w-full border rounded-lg px-3 py-2 mb-6 text-gray-700 focus:ring focus:ring-indigo-100"
          placeholder="密码"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <button
          disabled={loading}
          className="w-full bg-indigo-600 text-white py-2 rounded-lg hover:bg-indigo-700 transition"
        >
          {loading ? '登录中...' : '登录'}
        </button>
      </form>
    </div>
  )
}
