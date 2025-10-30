import Link from 'next/link'
import { useRouter } from 'next/router'

export default function Layout({ children, title }: any) {
  const router = useRouter()

  const logout = () => {
    localStorage.removeItem('token')
    router.push('/login')
  }

  return (
    <div className="flex min-h-screen bg-gray-50">
      <aside className="w-64 bg-white border-r border-gray-100 p-5 flex flex-col justify-between">
        <div>
          <h1 className="text-lg font-bold text-indigo-600 mb-6">智能巡检平台</h1>
          <nav className="flex flex-col gap-2">
            <Link href="/dashboard" className="hover:text-indigo-600">
              📊 数据库巡检
            </Link>
            <Link href="/users" className="hover:text-indigo-600">
              👥 用户管理
            </Link>
          </nav>
        </div>
        <button
          onClick={logout}
          className="mt-6 bg-gray-100 hover:bg-gray-200 rounded-lg py-2 text-sm text-gray-600"
        >
          退出登录
        </button>
      </aside>

      <main className="flex-1 p-6">
        <h2 className="text-2xl font-semibold mb-4">{title}</h2>
        {children}
      </main>
    </div>
  )
}
