import React from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ForumPostDetail } from '@/components/Forum'

const DIVIDER = 'var(--divider)'

/** Post detail route wrapper — reads :id from the URL. Backend: /api/v1/forum/*. */
const ForumPostDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  if (!id) return null
  return (
    <div className="min-h-full px-8 py-10">
      <div className="max-w-4xl">
        <button
          onClick={() => navigate('/forum')}
          className="mb-4 px-3 py-1.5 border text-sm hover:bg-[var(--hover)]"
          style={{ borderColor: DIVIDER }}
          aria-label="Back to forum"
        >
          ← 返回论坛
        </button>
        <ForumPostDetail postId={id} />
      </div>
    </div>
  )
}

export default ForumPostDetailPage
