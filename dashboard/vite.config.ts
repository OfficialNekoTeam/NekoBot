import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { readFileSync, copyFileSync } from 'fs'
import { resolve } from 'path'
import { fileURLToPath } from 'url'
import { dirname } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const getVersion = () => {
  try {
    const versionPath = resolve(__dirname, 'version')
    const version = readFileSync(versionPath, 'utf-8').trim()
    return version
  } catch {
    console.warn('Failed to read version file, using default version')
    return '0.0.0'
  }
}

const version = getVersion()

// 自定义插件：构建后复制 version 文件到 dist 目录
const copyVersionPlugin = () => {
  return {
    name: 'copy-version',
    writeBundle() {
      try {
        const versionPath = resolve(__dirname, 'version')
        const distPath = resolve(__dirname, 'dist', 'version')
        copyFileSync(versionPath, distPath)
        console.log('✓ Version file copied to dist/')
      } catch (error) {
        console.warn('Failed to copy version file:', error)
      }
    },
  }
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), copyVersionPlugin()],
  define: {
    __APP_VERSION__: JSON.stringify(version),
  },
})
