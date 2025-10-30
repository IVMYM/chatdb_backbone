'use client'

import { useState, useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { getToken, clearToken } from '@/services/auth'
import { showToast } from '@/components/Toast'

const API_BASE = process.env.NEXT_PUBLIC_SERVICE_API_BASE || 'http://localhost:8000'

// 生成唯一会话ID
const generateSessionId = () => {
  return Date.now().toString(36) + Math.random().toString(36).substr(2, 5)
}

export default function HomePage() {
  const [messages, setMessages] = useState<{ role: string; content: string }[]>([])
  const [input, setInput] = useState('')
  const [token, setToken] = useState('')
  const [loading, setLoading] = useState(false)
  const [darkMode, setDarkMode] = useState(false)
  const [sessionId, setSessionId] = useState('') // 会话ID管理
  const router = useRouter()
  const chatRef = useRef<HTMLDivElement>(null)
  const websocketRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    const t = getToken()
    if (!t) {
      router.push('/login')
    } else {
      setToken(t)
      setSessionId(generateSessionId()) // 初始化会话ID
      showToast('✅ 登录成功')
    }

    // 组件卸载时关闭WebSocket
    return () => {
      if (websocketRef.current) {
        websocketRef.current.close()
      }
    }
  }, [router])

  useEffect(() => {
    chatRef.current?.scrollTo(0, chatRef.current.scrollHeight)
  }, [messages])

  const logout = () => {
    clearToken()
    router.push('/login')
  }

  const newChat = () => {
    // 关闭当前WebSocket连接
    if (websocketRef.current) {
      websocketRef.current.close()
    }
    setMessages([])
    setSessionId(generateSessionId()) // 生成新的会话ID
    showToast('🆕 已开启新会话')
  }

  const sendQuestion = async () => {
    if (!input.trim() || loading) return

    // 添加用户消息
    setMessages(prev => [...prev, { role: 'user', content: input }])
    setInput('')
    setLoading(true)

    try {
      // 构建WebSocket连接URL（处理HTTP/HTTPS与WS/WSS的转换）
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    //   const wsUrl = `${protocol}//${window.location.host}/ws/ai-question?session_id=${sessionId}`
    const wsUrl = `ws://localhost:19069/ws/ai-question?session_id=${sessionId}`

      // 创建WebSocket连接
      const ws = new WebSocket(wsUrl)
      websocketRef.current = ws

      // 连接打开时发送问题
      ws.onopen = () => {
        console.log('WebSocket连接已建立')
        ws.send(JSON.stringify({
          question: input.trim(),
          type: 0 // 默认类型
        }))
      }

      // 先插入一个空的assistant消息占位
      let aiMsgIndex = -1
      setMessages(prev => {
        aiMsgIndex = prev.length
        return [...prev, { role: 'assistant', content: '' }]
      })

      // 接收服务器消息
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          
          // 更新AI回复内容
          if (data.status === 1 || data.status === 2) { // 继续或结束状态
            setMessages(prev => {
              const updated = [...prev]
              if (updated[aiMsgIndex]) {
                updated[aiMsgIndex] = {
                  ...updated[aiMsgIndex],
                  content: updated[aiMsgIndex].content + data.content
                }
              }
              return updated
            })
            chatRef.current?.scrollTo({ top: chatRef.current.scrollHeight, behavior: 'smooth' })
          }

          // 会话结束
          if (data.status === 2) {
            setLoading(false)
            ws.close()
          }

          // 错误处理
          if (data.status === -1) {
            setMessages(prev => [...prev, { role: 'system', content: `⚠️ ${data.content}` }])
            setLoading(false)
            ws.close()
          }
        } catch (error) {
          console.error('解析WebSocket消息失败:', error)
          setMessages(prev => [...prev, { role: 'system', content: '⚠️ 消息解析失败' }])
          setLoading(false)
          ws.close()
        }
      }

      // 连接错误处理
      ws.onerror = (error) => {
        console.error('WebSocket错误:', error)
        setMessages(prev => [...prev, { role: 'system', content: '⚠️ 连接发生错误' }])
        setLoading(false)
      }

      // 连接关闭处理
      ws.onclose = (event) => {
        console.log('WebSocket连接已关闭:', event.code, event.reason)
        if (loading) { // 如果关闭时仍在加载状态，说明异常关闭
          setMessages(prev => [...prev, { role: 'system', content: '⚠️ 连接已断开' }])
          setLoading(false)
        }
      }

    } catch (err) {
      console.error('发送问题失败:', err)
      setMessages(prev => [...prev, { role: 'system', content: '⚠️ 发送失败，请重试' }])
      setLoading(false)
    }
  }

  return (
    <div
      className={`min-h-screen flex flex-col transition-colors duration-500 ${
        darkMode
          ? 'bg-gradient-to-br from-gray-900 via-gray-800 to-gray-700 text-white'
          : 'bg-gradient-to-br from-blue-50 via-blue-100 to-blue-200 text-gray-800'
      }`}
    >
      {/* 顶部栏 */}
      <div className="flex items-center justify-between px-4 py-3 bg-white/80 dark:bg-gray-800/80 shadow">
        <span className="text-lg font-semibold">磐维数据巡检系统</span>
        <div className="flex items-center space-x-3">
          <button onClick={logout} className="text-sm text-red-500 hover:underline">
            退出
          </button>
        </div>
      </div>

      {/* 聊天内容 */}
      <div ref={chatRef} className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((m, i) => (
          <div key={i} className={`flex items-start ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            {m.role !== 'user' && (
              <img
                src="/ai-avatar.png"
                alt="AI"
                className="w-8 h-8 rounded-full mr-2 border border-gray-300 dark:border-gray-600"
              />
            )}
            <div
              className={`px-4 py-2 rounded-2xl break-words text-sm sm:text-base shadow-sm ${
                m.role === 'user'
                  ? 'bg-blue-600 text-white max-w-[80%]'
                  : m.role === 'system'
                  ? 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-200 max-w-[80%]'
                  : 'bg-gray-100 dark:bg-gray-700 dark:text-gray-100 max-w-[80%]'
              }`}
              style={{
                wordBreak: 'break-word',
                whiteSpace: 'pre-wrap',
                overflowWrap: 'anywhere',
              }}
            >
              {m.content}
            </div>
            {m.role === 'user' && (
              <img
                src="/user-avatar.png"
                alt="User"
                className="w-8 h-8 rounded-full ml-2 border border-gray-300 dark:border-gray-600"
              />
            )}
          </div>
        ))}
        {loading && <p className="text-center text-gray-400 text-sm">智能体正在思考中...</p>}
      </div>

      {/* 底部输入栏 */}
      <div className="p-3 bg-white/80 dark:bg-gray-800/80 border-t dark:border-gray-700 flex items-center space-x-2">
        <input
          type="text"
          value={input}
          placeholder="说点什么..."
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && sendQuestion()}
          className="flex-1 border rounded-full px-3 py-2 text-sm dark:bg-gray-700 dark:text-white"
        />
        <button
          onClick={sendQuestion}
          disabled={loading}
          className="bg-blue-600 text-white px-3 py-2 rounded-full hover:bg-blue-700 transition"
        >
          发送⚡
        </button>
        <button
          onClick={newChat}
          className="text-sm bg-blue-500 text-white px-3 py-1.5 rounded-full hover:bg-blue-600 transition"
        >
          新会话 +
        </button>
      </div>
    </div>
  )
}

export async function getServerSideProps() {
  return { props: {} }
}