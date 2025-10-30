import '@/styles/globals.css'
import type { AppProps } from 'next/app'
import { useEffect } from 'react'
import { useRouter } from 'next/router'
import Toast from '@/components/Toast'

export default function App({ Component, pageProps }: AppProps) {
  const router = useRouter()

  useEffect(() => {
    const token = localStorage.getItem('token')
    const publicPages = ['/login']
    const path = router.pathname
    if (!token && !publicPages.includes(path)) {
      router.push('/login')
    }
  }, [router])

  return (
    <>
      <Component {...pageProps} />
      <Toast />
    </>
  )
}
