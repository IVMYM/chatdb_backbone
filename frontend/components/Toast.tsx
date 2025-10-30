import { useState, useEffect } from 'react'

let globalShow: any

export function showToast(msg: string) {
  globalShow && globalShow(msg)
}

export default function Toast() {
  const [message, setMessage] = useState('')
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    globalShow = (msg: string) => {
      setMessage(msg)
      setVisible(true)
      setTimeout(() => setVisible(false), 2000)
    }
  }, [])

  if (!visible) return null

  return (
    <div className="fixed bottom-5 right-5 bg-black/80 text-white text-sm px-4 py-2 rounded-lg shadow-lg animate-fade-in">
      {message}
    </div>
  )
}
