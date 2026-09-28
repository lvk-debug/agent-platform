/**
 * 页码导航器
 *
 * 文档学习的翻页控件：上一页 / 页码输入跳转 / 下一页。
 * 独立封装是为了放在页面 header 的标题右侧，不占用文档视口空间。
 * 命中区域保持 44px 以上，满足平板触屏操作。
 */
import React, { useEffect, useState } from 'react'
import { LeftOutlined, RightOutlined } from '@ant-design/icons'

interface PageNavigatorProps {
  /** 当前页码，0-based */
  pageIndex: number
  /** 总页数 */
  pageCount: number
  /** 页码变化回调，参数为 0-based 页码 */
  onChange: (pageIndex: number) => void
}

const PageNavigator: React.FC<PageNavigatorProps> = ({ pageIndex, pageCount, onChange }) => {
  // 输入框持有草稿值，允许出现清空/超范围等中间态，回车或失焦时才校正
  const [draft, setDraft] = useState(String(pageIndex + 1))

  // 外部跳转（笔记定位、导出等）改变页码时同步回输入框
  useEffect(() => {
    setDraft(String(pageIndex + 1))
  }, [pageIndex])

  const total = Math.max(pageCount, 1)

  const commit = () => {
    const parsed = Number.parseInt(draft, 10)
    if (Number.isNaN(parsed)) {
      setDraft(String(pageIndex + 1))
      return
    }
    const target = Math.min(Math.max(parsed, 1), total)
    setDraft(String(target))
    if (target - 1 !== pageIndex) onChange(target - 1)
  }

  const navButtonClass =
    'flex h-11 w-11 items-center justify-center rounded-xl text-slate-500 transition-colors hover:bg-slate-100 hover:text-indigo-600 disabled:cursor-not-allowed disabled:opacity-40'

  return (
    <div className="flex shrink-0 items-center gap-1">
      <button
        type="button"
        aria-label="上一页"
        disabled={pageIndex <= 0}
        onClick={() => onChange(Math.max(pageIndex - 1, 0))}
        className={navButtonClass}
      >
        <LeftOutlined />
      </button>

      <div className="flex items-center gap-1 rounded-xl bg-slate-100 px-1">
        <input
          type="text"
          inputMode="numeric"
          aria-label="页码"
          value={draft}
          onChange={(event) => setDraft(event.target.value.replace(/[^0-9]/g, ''))}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              commit()
              // 移动端收起软键盘，让出被遮挡的文档区域
              event.currentTarget.blur()
            }
          }}
          onBlur={commit}
          className="h-9 w-12 rounded-lg border border-transparent bg-white text-center text-sm text-slate-700 outline-none transition-colors focus:border-indigo-400"
        />
        <span className="pr-1 text-sm text-slate-500">/ {total}</span>
      </div>

      <button
        type="button"
        aria-label="下一页"
        disabled={pageIndex >= total - 1}
        onClick={() => onChange(Math.min(pageIndex + 1, total - 1))}
        className={navButtonClass}
      >
        <RightOutlined />
      </button>
    </div>
  )
}

export default PageNavigator
