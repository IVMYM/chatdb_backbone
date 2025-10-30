'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { getToken, clearToken } from '@/services/auth';

export default function HomePage() {
  const [messages, setMessages] = useState<{ role: string; content: string }[]>([]);
  const [input, setInput] = useState('');
  const [token, setToken] = useState('');
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const chatRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const t = getToken();
    if (!t) router.push('/login');
    else setToken(t);
  }, [router]);

  const logout = () => {
    clearToken();
    router.push('/login');
  };

  const sendQuestion = async () => {
    if (!input.trim()) return;
    setMessages((prev) => [...prev, { role: 'user', content: input }]);
    setInput('');
    setLoading(true);

    try {
           const res = await fetch(`http://localhost:8000/service/true_dbinspect?question=${encodeURIComponent(input)}`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        }
    
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const reader = res.body?.getReader();
      if (!reader) throw new Error('无响应流');

      let aiMsg = { role: 'assistant', content: '' };
      setMessages((prev) => [...prev, aiMsg]);

      const decoder = new TextDecoder();
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value);

        // 处理 SSE 的 "data:" 前缀
        const lines = chunk.split(/\r?\n/).filter((line) => line.startsWith('data:'));
        for (const line of lines) {
          const text = line.replace(/^data:\s*/, '');
          aiMsg.content += text;
        }

        setMessages((prev) => {
          const updated = [...prev];
          updated[updated.length - 1] = { ...aiMsg };
          return updated;
        });

        // 自动滚动到底部
        chatRef.current?.scrollTo({ top: chatRef.current.scrollHeight, behavior: 'smooth' });
      }
    } catch (err) {
      console.error(err);
      setMessages((prev) => [...prev, { role: 'system', content: '⚠️ 连接失败，请检查Token或网络' }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col min-h-screen bg-gray-50">
      {/* 顶部栏 */}
      <div className="flex items-center justify-between px-4 py-3 bg-white shadow">
        <span className="text-lg font-semibold">磐维数据巡检</span>
        <button onClick={logout} className="text-sm text-red-500 hover:underline">
          退出登录
        </button>
      </div>

      {/* 聊天内容 */}
<div
  ref={chatRef}
  className="flex-1 overflow-y-auto p-4 space-y-3 bg-gray-50"
>
  {messages.map((m, i) => (
    <div
      key={i}
      className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
    >
      <div
        className={`px-4 py-2 rounded-2xl break-words text-sm sm:text-base ${
          m.role === 'user'
            ? 'bg-blue-600 text-white max-w-[80%]'
            : m.role === 'system'
            ? 'bg-red-100 text-red-700 max-w-[80%]'
            : 'bg-gray-100 text-gray-800 max-w-[80%]'
        }`}
        style={{
          wordBreak: 'break-word',
          whiteSpace: 'pre-wrap',
          overflowWrap: 'anywhere',
        }}
      >
        {m.content}
      </div>
    </div>
  ))}
  {loading && (
    <p className="text-center text-gray-400 text-sm">智能体正在思考</p>
  )}
</div>


      {/* 底部输入 */}
      <div className="p-3 bg-white border-t flex items-center space-x-2">
        <input
          type="text"
          value={input}
          placeholder="说点什么..."
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && sendQuestion()}
          className="flex-1 border rounded-full px-3 py-2 text-sm"
        />
        <button
          onClick={sendQuestion}
          disabled={loading}
          className="bg-blue-600 text-white px-3 py-2 rounded-full"
        >
          ⚡
        </button>
      </div>
    </div>
  );
}
