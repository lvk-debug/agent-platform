/**
 * Markdown 页面渲染器
 *
 * 复用项目已有的 react-markdown + remark-gfm，避免再引入 marked 与高亮库。
 */

import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import AuthImage from '../AuthImage'

interface MarkdownPageRendererProps {
  content: string
  width: number
}

const MarkdownPageRenderer: React.FC<MarkdownPageRendererProps> = ({ content, width }) => {
  return (
    <div
      className="markdown-content bg-white px-[8%] py-10 text-[15px] leading-7 text-slate-800"
      style={{ width }}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h1 className="mb-4 border-b border-slate-200 pb-2 text-2xl font-semibold text-slate-900">
              {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2 className="mb-3 mt-6 text-xl font-semibold text-slate-900">{children}</h2>
          ),
          h3: ({ children }) => (
            <h3 className="mb-2 mt-5 text-lg font-medium text-slate-900">{children}</h3>
          ),
          p: ({ children }) => <p className="mb-4 text-slate-700">{children}</p>,
          ul: ({ children }) => (
            <ul className="mb-4 list-disc space-y-1 pl-6 text-slate-700">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="mb-4 list-decimal space-y-1 pl-6 text-slate-700">{children}</ol>
          ),
          blockquote: ({ children }) => (
            <blockquote className="mb-4 border-l-4 border-indigo-300 bg-indigo-50/50 py-2 pl-4 text-slate-600">
              {children}
            </blockquote>
          ),
          code: ({ children }) => (
            <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[13px] text-indigo-600">
              {children}
            </code>
          ),
          pre: ({ children }) => (
            <pre className="mb-4 overflow-x-auto rounded-xl bg-slate-900 p-4 text-[13px] leading-6 text-slate-100">
              {children}
            </pre>
          ),
          table: ({ children }) => (
            <div className="mb-4 overflow-x-auto">
              <table className="w-full border-collapse text-sm">{children}</table>
            </div>
          ),
          th: ({ children }) => (
            <th className="border border-slate-200 bg-slate-50 px-3 py-2 text-left font-medium">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border border-slate-200 px-3 py-2">{children}</td>
          ),
          a: ({ children, href }) => (
            <a
              href={href}
              target="_blank"
              rel="noreferrer"
              className="text-indigo-600 underline decoration-indigo-300 underline-offset-2 hover:text-indigo-500"
            >
              {children}
            </a>
          ),
          img: ({ src, alt }) => (
            <AuthImage
              src={src}
              alt={alt}
              className="mb-4 max-w-full rounded-lg"
              loading="lazy"
            />
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}

export default MarkdownPageRenderer
