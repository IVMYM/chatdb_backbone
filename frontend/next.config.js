/** @type {import('next').NextConfig} */
const nextConfig = {
  // 关键：输出独立产物（优化Docker部署）
  output: 'standalone',
  // 确保静态资源正确打包
  distDir: '.next',
}

module.exports = nextConfig