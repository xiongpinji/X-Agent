import React, { useState } from 'react'
import { ForumHome, ForumPostDetail, ForumCreatePost } from '@/components/Forum'

type View = { name: 'home' } | { name: 'detail'; postId: string } | { name: 'create' }

/**
 * Forum page wrapper — internal navigation between the forum sub-views
 * (home / post detail / create post). Backend: /api/v1/forum/*.
 */
const ForumPage: React.FC = () => {
  const [view, setView] = useState<View>({ name: 'home' })

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center gap-3">
        {view.name !== 'home' && (
          <button
            onClick={() => setView({ name: 'home' })}
            className="px-3 py-1 rounded border border-slate-600 text-sm hover:bg-slate-700"
            aria-label="Back to forum home"
          >
            ← 返回
          </button>
        )}
        {view.name === 'home' && (
          <button
            onClick={() => setView({ name: 'create' })}
            className="ml-auto px-4 py-2 rounded bg-blue-600 text-white text-sm hover:bg-blue-500"
          >
            新建帖子
          </button>
        )}
      </div>

      {view.name === 'home' && <ForumHome />}
      {view.name === 'detail' && <ForumPostDetail postId={view.postId} />}
      {view.name === 'create' && <ForumCreatePost />}
    </div>
  )
}

export default ForumPage
