import React, { useState } from 'react'
import { ForumHome, ForumPostDetail, ForumCreatePost } from '@/components/Forum'

type View = { name: 'home' } | { name: 'detail'; postId: string } | { name: 'create' }

const DIVIDER = 'var(--divider)'

/**
 * Forum page wrapper — internal navigation between the forum sub-views
 * (home / post detail / create post). Backend: /api/v1/forum/*.
 */
const ForumPage: React.FC = () => {
  const [view, setView] = useState<View>({ name: 'home' })

  return (
    <div className="min-h-full px-8 py-10">
      <div className="max-w-4xl">
        {view.name !== 'home' && (
          <button
            onClick={() => setView({ name: 'home' })}
            className="mb-4 px-3 py-1.5 border text-sm hover:bg-[var(--hover)]"
            style={{ borderColor: DIVIDER }}
            aria-label="Back to forum home"
          >
            ← 返回
          </button>
        )}
        {view.name === 'home' && (
          <div className="flex justify-end mb-4">
            <button
              onClick={() => setView({ name: 'create' })}
              className="px-4 py-2 bg-blue-600 text-white text-sm font-medium"
            >
              新建帖子
            </button>
          </div>
        )}

        {view.name === 'home' && <ForumHome />}
        {view.name === 'detail' && <ForumPostDetail postId={view.postId} />}
        {view.name === 'create' && <ForumCreatePost />}
      </div>
    </div>
  )
}

export default ForumPage
