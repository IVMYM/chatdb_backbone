'use client'

import { useState, useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { getToken, clearToken } from '@/services/auth'
import { showToast } from '@/components/Toast'
const API_BASE = process.env.NEXT_PUBLIC_SERVICE_API_BASE || 'http://localhost:8000'
export default function HomePage() {
  const [messages, setMessages] = useState<{ role: string; content: string }[]>([])
  const [input, setInput] = useState('')
  const [token, setToken] = useState('')
  const [loading, setLoading] = useState(false)
  const [darkMode, setDarkMode] = useState(false)
  const router = useRouter()
  const chatRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const t = getToken()
    if (!t) router.push('/login')
    else {
      setToken(t)
      showToast('✅ 登录成功')
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
    setMessages([])
    showToast('🆕 已开启新会话')
  }
  //  const res = await fetch(`${API_BASE}/service/true_dbinspect?question=${encodeURIComponent(input)}`, {
   const sendQuestion = async () => {
  if (!input.trim()) return;
  setMessages((prev) => [...prev, { role: 'user', content: input }]);
  setInput('');
  setLoading(true);

  try {
    const res = await fetch(`http://localhost:15678/webhook/cd4bb720-88bd-4274-9a9f-c12f7032277c?chatInput=${encodeURIComponent(input)}`,
    // const res = await fetch(`${API_BASE}/service/true_dbinspect?question=${encodeURIComponent(input)}`, 
      {
        method: 'GET',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      }
    );
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const reader = res.body?.getReader();
    if (!reader) throw new Error('无响应流');

    // 先插入一个空的 assistant 消息
    let aiMsgIndex = -1;
    setMessages((prev) => {
      aiMsgIndex = prev.length;
      return [...prev, { role: 'assistant', content: '' }];
    });

    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // 将缓冲区切分为多行
      const lines = buffer.split(/\r?\n/);
      buffer = lines.pop() || ''; // 保留最后一行（可能不完整）

       for (const raw of lines) {
          if (!raw.trim()) continue;
          let s = raw.trim();
          if (s.startsWith('data:')) s = s.replace(/^data:\s*/, '');

          // 尝试解析 JSON 控制包
          let isControlPacket = false;
          try {
            const obj = JSON.parse(s);
            if (obj?.type === 'begin' || obj?.type === 'end') {
              isControlPacket = true;
            }
          } catch {
            // 不是 JSON 控制包，则是内容本体
          }

          if (isControlPacket) continue; // 忽略控制包

          // 更新 AI 消息内容，只显示纯文本
          setMessages((prev) => {
            const updated = [...prev];
            const current = updated[aiMsgIndex];
            if (!current) return prev;
            updated[aiMsgIndex] = {
              ...current,
              content: (current.content || '') + JSON.parse(s).content,
            };
            return updated;
          });

          chatRef.current?.scrollTo({ top: chatRef.current.scrollHeight, behavior: 'smooth' });
}

    }

    // 最后一次缓冲区内容
    if (buffer.trim()) {
      setMessages((prev) => {
        const updated = [...prev];
        const current = updated[aiMsgIndex];
        updated[aiMsgIndex] = { ...current, content: current.content + buffer.trim() };
        return updated;
      });
    }
  } catch (err) {
    console.error(err);
    setMessages((prev) => [...prev, { role: 'system', content: '⚠️ 连接失败，请检查 Token 或网络' }]);
  } finally {
    setLoading(false);
  }
};


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
