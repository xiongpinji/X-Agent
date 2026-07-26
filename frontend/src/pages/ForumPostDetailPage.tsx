import React from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ForumPostDetail } from '@/components/Forum'

/** Post detail route wrapper — reads :id from the URL. Backend: /api/v1/forum/*. */
const ForumPostDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  if (!id) return null
  return (
    <div className="p-6 space-y-4">
      <button
        onClick={() => navigate('/forum')}
        className="px-3 py-1 rounded border border-slate-600 text-sm hover:bg-slate-700"
        aria-label="Back to forum"
      >
        ← 返回论坛
      </button>
      <ForumPostDetail postId={id} />
    </div>
  )
}

export default ForumPostDetailPage
