import axios from 'axios'
const API_BASE = process.env.NEXT_PUBLIC_SERVICE_API_BASE || '/api'
console.log('API_BASE:', process.env.NEXT_PUBLIC_SERVICE_API_BASE);
export async function login(username: string, password: string) {
  const formData = new URLSearchParams()
  formData.append('username', username)
  formData.append('password', password)

  const res = await axios.post(`${API_BASE}/login`, formData, {
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
  })
  localStorage.setItem('token', res.data.access_token)
  return res.data
}

export function getToken() {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('token');
}

export function clearToken() {
  localStorage.removeItem('token');
  document.cookie = 'token=; Max-Age=0; path=/;';
}
