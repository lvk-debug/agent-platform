/**
 * 根据文件名扩展名返回对应的 Ant Design 文件图标
 * 仅使用项目已有的 @ant-design/icons，不引入新依赖
 */
import { ReactNode } from 'react'
import {
  FilePdfOutlined,
  FileWordOutlined,
  FileExcelOutlined,
  FileTextOutlined,
  FileOutlined,
} from '@ant-design/icons'

export function getFileIcon(filename: string): ReactNode {
  const ext = filename.split('.').pop()?.toLowerCase() || ''
  switch (ext) {
    case 'pdf':
      return <FilePdfOutlined />
    case 'doc':
    case 'docx':
      return <FileWordOutlined />
    case 'xls':
    case 'xlsx':
      return <FileExcelOutlined />
    case 'txt':
    case 'md':
    case 'html':
    case 'htm':
    case 'epub':
      return <FileTextOutlined />
    default:
      return <FileOutlined />
  }
}
