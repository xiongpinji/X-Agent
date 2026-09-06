import React, { useState, useEffect, useCallback } from 'react';
import { Spinner } from './ui';

interface ForumPost {
  id: string;
  title: string;
  content: string;
  author_name: string;
  category: string;
  tags: string[];
  created_at: string;
  view_count: number;
  like_count: number;
  comment_count: number;
  is_pinned: boolean;
}

interface ForumComment {
  id: string;
  content: string;
  author_name: string;
  created_at: string;
  like_count: number;
}

const DIVIDER = 'var(--divider)';

/* Hairline chip — thin border, no colored fill (spec: 状态标记 = 细边框小 chip) */
const chipClass = 'inline-flex items-center px-1.5 py-0.5 text-[11px] border whitespace-nowrap';

export const ForumHome: React.FC = () => {
  const [posts, setPosts] = useState<ForumPost[]>([]);
  const [loading, setLoading] = useState(false);
  const [sortBy, setSortBy] = useState<'created_at' | 'views' | 'likes' | 'comments'>('created_at');
  const [category, setCategory] = useState<string>('');

  const fetchPosts = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (category) params.append('category', category);
      params.append('sort_by', sortBy);
      params.append('limit', '20');

      const response = await fetch(`/api/v1/forum/posts?${params}`);
      const data = await response.json();
      setPosts(data.data || []);
    } catch (error) {
      console.error('Failed to fetch posts:', error);
    } finally {
      setLoading(false);
    }
  }, [sortBy, category]);

  useEffect(() => {
    fetchPosts();
  }, [fetchPosts]);

  const selectClass = 'px-2 py-1.5 text-[13px] border bg-transparent';

  return (
    <div>
      {/* Header */}
      <div className="flex justify-between items-baseline pb-3 border-b" style={{ borderColor: DIVIDER }}>
        <h1 className="text-[22px] font-medium tracking-tight">Community Forum</h1>
        {/* New Post action lives in ForumPage wrapper (internal state nav);
            hardcoded /forum/create route does not exist. */}
      </div>

      {/* Filters */}
      <div className="flex gap-3 py-3 border-b" style={{ borderColor: DIVIDER }}>
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className={selectClass}
          style={{ borderColor: DIVIDER }}
        >
          <option value="">All Categories</option>
          <option value="general">General</option>
          <option value="bugs">Bugs</option>
          <option value="features">Features</option>
          <option value="showcase">Showcase</option>
        </select>

        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value as 'created_at' | 'views' | 'likes' | 'comments')}
          className={selectClass}
          style={{ borderColor: DIVIDER }}
        >
          <option value="created_at">Latest</option>
          <option value="views">Most Viewed</option>
          <option value="likes">Most Liked</option>
          <option value="comments">Most Discussed</option>
        </select>
      </div>

      {/* Posts List — hairline rows, no cards */}
      {loading ? (
        <Spinner />
      ) : posts.length === 0 ? (
        <p className="empty-state">No posts yet</p>
      ) : (
        <div>
          {posts.map((post) => (
            <div
              key={post.id}
              role="button"
              tabIndex={0}
              className="row-line cursor-pointer hover:bg-[var(--hover)]"
              onClick={() => window.location.href = `/forum/posts/${post.id}`}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') window.location.href = `/forum/posts/${post.id}`; }}
            >
              <div className="flex items-baseline justify-between gap-4">
                <div className="flex items-center gap-2 min-w-0">
                  {post.is_pinned && (
                    <span className={chipClass} style={{ borderColor: DIVIDER }}>Pinned</span>
                  )}
                  <h2 className="text-[15px] font-medium truncate">{post.title}</h2>
                </div>
                <span className="font-data text-xs opacity-50 whitespace-nowrap">
                  {post.view_count} views · {post.like_count} likes · {post.comment_count} comments
                </span>
              </div>
              <p className="text-[13px] opacity-60 mt-1 truncate-lines-1">{post.content}</p>
              <div className="flex items-center gap-3 mt-1.5 text-xs opacity-50 flex-wrap">
                <span>By {post.author_name}</span>
                <span className="font-data">· {new Date(post.created_at).toLocaleDateString()}</span>
                {post.tags.map((tag) => (
                  <span key={tag} className={chipClass} style={{ borderColor: DIVIDER }}>{tag}</span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export const ForumPostDetail: React.FC<{ postId: string }> = ({ postId }) => {
  const [post, setPost] = useState<ForumPost | null>(null);
  const [comments, setComments] = useState<ForumComment[]>([]);
  const [newComment, setNewComment] = useState('');
  const [loading, setLoading] = useState(true);
  const [liked, setLiked] = useState(false);
  const [bookmarked, setBookmarked] = useState(false);

  const fetchPost = useCallback(async () => {
    try {
      const response = await fetch(`/api/v1/forum/posts/${postId}`);
      const data = await response.json();
      setPost(data);
    } catch (error) {
      console.error('Failed to fetch post:', error);
    } finally {
      setLoading(false);
    }
  }, [postId]);

  const fetchComments = useCallback(async () => {
    try {
      const response = await fetch(`/api/v1/forum/posts/${postId}/comments?limit=50`);
      const data = await response.json();
      setComments(data.data || []);
    } catch (error) {
      console.error('Failed to fetch comments:', error);
    }
  }, [postId]);

  useEffect(() => {
    fetchPost();
    fetchComments();
  }, [fetchPost, fetchComments]);

  const handleAddComment = async () => {
    if (!newComment.trim()) return;

    try {
      const response = await fetch(`/api/v1/forum/posts/${postId}/comments`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: newComment }),
      });

      if (response.ok) {
        setNewComment('');
        fetchComments();
      }
    } catch (error) {
      console.error('Failed to add comment:', error);
    }
  };

  const handleLike = async () => {
    try {
      const endpoint = liked ? 'unlike' : 'like';
      await fetch(`/api/v1/forum/posts/${postId}/${endpoint}`, { method: 'POST' });
      setLiked(!liked);
      if (post) {
        setPost({
          ...post,
          like_count: post.like_count + (liked ? -1 : 1),
        });
      }
    } catch (error) {
      console.error('Failed to like post:', error);
    }
  };

  const handleBookmark = async () => {
    try {
      const endpoint = bookmarked ? 'unbookmark' : 'bookmark';
      await fetch(`/api/v1/forum/posts/${postId}/${endpoint}`, { method: 'POST' });
      setBookmarked(!bookmarked);
    } catch (error) {
      console.error('Failed to bookmark post:', error);
    }
  };

  if (loading) return <Spinner />;
  if (!post) return <div>Post not found</div>;

  return (
    <div>
      {/* Post Header — transparent container, hairline bottom */}
      <section className="py-4 border-b" style={{ borderColor: DIVIDER }}>
        <h1 className="text-[22px] font-medium tracking-tight mb-2">{post.title}</h1>
        <div className="flex justify-between items-center text-[13px] opacity-60 mb-3">
          <div>
            By <strong>{post.author_name}</strong> · <span className="font-data">{new Date(post.created_at).toLocaleDateString()}</span>
          </div>
          <div className="flex gap-4 font-data text-xs">
            <span>{post.view_count} views</span>
            <span>{post.comment_count} comments</span>
          </div>
        </div>

        {/* Tags */}
        <div className="flex gap-2 mb-4 flex-wrap">
          {post.tags.map((tag) => (
            <span key={tag} className={chipClass} style={{ borderColor: DIVIDER }}>{tag}</span>
          ))}
        </div>

        {/* Content */}
        <div className="text-[14px] leading-relaxed max-w-none mb-4">
          {post.content}
        </div>

        {/* Actions — plain hairline buttons, no filled card chrome */}
        <div className="flex gap-3">
          <button
            onClick={handleLike}
            className={liked ? 'text-[13px] px-3 py-1.5 border border-blue-600 text-blue-600' : 'text-[13px] px-3 py-1.5 border hover:bg-[var(--hover)]'}
            style={liked ? undefined : { borderColor: DIVIDER }}
          >
            ❤️ Like ({post.like_count})
          </button>
          <button
            onClick={handleBookmark}
            className={bookmarked ? 'text-[13px] px-3 py-1.5 border border-blue-600 text-blue-600' : 'text-[13px] px-3 py-1.5 border hover:bg-[var(--hover)]'}
            style={bookmarked ? undefined : { borderColor: DIVIDER }}
          >
            🔖 Bookmark
          </button>
        </div>
      </section>

      {/* Comments Section */}
      <section className="py-4">
        <h2 className="text-[11px] uppercase tracking-[0.08em] opacity-50 mb-3">Comments ({post.comment_count})</h2>

        {/* Add Comment */}
        <div className="mb-6">
          <textarea
            value={newComment}
            onChange={(e) => setNewComment(e.target.value)}
            placeholder="Add a comment..."
            rows={4}
            className="w-full mb-2 px-3 py-2 text-sm border bg-transparent"
            style={{ borderColor: DIVIDER }}
          />
          <button
            onClick={handleAddComment}
            disabled={!newComment.trim()}
            className="text-[13px] px-3 py-1.5 border bg-blue-600 text-white disabled:opacity-50"
          >
            Post Comment
          </button>
        </div>

        {/* Comments List — hairline rows */}
        <div>
          {comments.length === 0 && <p className="empty-state">No comments yet</p>}
          {comments.map((comment) => (
            <div key={comment.id} className="row-line">
              <div className="flex justify-between items-baseline mb-1">
                <strong className="text-[13px]">{comment.author_name}</strong>
                <span className="font-data text-xs opacity-50">
                  {new Date(comment.created_at).toLocaleDateString()}
                </span>
              </div>
              <p className="text-[13px] opacity-80 mb-1.5">{comment.content}</p>
              <div className="flex gap-4 text-[13px]">
                <button className="text-blue-600 hover:underline">
                  ❤️ Like ({comment.like_count})
                </button>
                <button className="text-blue-600 hover:underline">Reply</button>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
};

export const ForumCreatePost: React.FC = () => {
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [category, setCategory] = useState('general');
  const [tags, setTags] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    if (!title.trim() || !content.trim()) {
      alert('Please fill in all fields');
      return;
    }

    setLoading(true);
    try {
      const response = await fetch('/api/v1/forum/posts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title,
          content,
          category,
          tags: tags.split(',').map((t) => t.trim()).filter(Boolean),
        }),
      });

      if (response.ok) {
        const data = await response.json();
        window.location.href = `/forum/posts/${data.id}`;
      } else {
        alert('Failed to create post');
      }
    } catch (error) {
      console.error('Failed to create post:', error);
      alert('Error creating post');
    } finally {
      setLoading(false);
    }
  };

  const inputClass = 'w-full px-3 py-2 text-sm border bg-transparent';
  const labelClass = 'block text-[11px] uppercase tracking-[0.06em] opacity-50 mb-1.5';

  return (
    <div className="max-w-2xl">
      <h1 className="text-[22px] font-medium tracking-tight mb-6 pb-3 border-b">Create New Post</h1>

      <div className="space-y-4 mb-6">
        <div>
          <label htmlFor="post-title" className={labelClass}>Title</label>
          <input
            id="post-title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Post title (min 5 characters)"
            className={inputClass}
            style={{ borderColor: DIVIDER }}
          />
        </div>

        <div>
          <label htmlFor="post-category" className={labelClass}>Category</label>
          <select
            id="post-category"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className={inputClass}
            style={{ borderColor: DIVIDER }}
          >
            <option value="general">General</option>
            <option value="bugs">Bugs</option>
            <option value="features">Features</option>
            <option value="showcase">Showcase</option>
          </select>
        </div>

        <div>
          <label htmlFor="post-content" className={labelClass}>Content</label>
          <textarea
            id="post-content"
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="Post content (min 20 characters)"
            rows={10}
            className={inputClass}
            style={{ borderColor: DIVIDER }}
          />
        </div>

        <div>
          <label htmlFor="post-tags" className={labelClass}>Tags (comma-separated)</label>
          <input
            id="post-tags"
            value={tags}
            onChange={(e) => setTags(e.target.value)}
            placeholder="e.g., bug, feature, help"
            className={inputClass}
            style={{ borderColor: DIVIDER }}
          />
        </div>

        <div className="flex gap-3 pt-3 border-t" style={{ borderColor: DIVIDER }}>
          <button
            onClick={handleSubmit}
            disabled={loading}
            className="px-4 py-2 bg-blue-600 text-white text-sm font-medium disabled:opacity-50"
          >
            {loading ? 'Creating...' : 'Create Post'}
          </button>
          <button
            onClick={() => window.history.back()}
            className="px-4 py-2 border text-sm font-medium hover:bg-[var(--hover)]"
            style={{ borderColor: DIVIDER }}
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
};

interface ForumReputation {
  level: string;
  reputation_points: number;
  post_count?: number;
  comment_count?: number;
  badges?: string[];
}

export const UserProfile: React.FC<{ userId: string }> = ({ userId }) => {
  const [reputation, setReputation] = useState<ForumReputation | null>(null);
  const [followers, setFollowers] = useState(0);
  const [following, setFollowing] = useState(0);
  const [userPosts, setUserPosts] = useState<ForumPost[]>([]);
  const [loading, setLoading] = useState(true);
  const [isFollowing, setIsFollowing] = useState(false);

  const fetchUserData = useCallback(async () => {
    try {
      const [repRes, followersRes, followingRes, postsRes] = await Promise.all([
        fetch(`/api/v1/forum/users/${userId}/reputation`),
        fetch(`/api/v1/forum/users/${userId}/followers`),
        fetch(`/api/v1/forum/users/${userId}/following`),
        fetch(`/api/v1/forum/posts?author=${userId}`),
      ]);

      const repData = await repRes.json();
      const followersData = await followersRes.json();
      const followingData = await followingRes.json();
      const postsData = await postsRes.json();

      setReputation(repData);
      setFollowers(followersData.count);
      setFollowing(followingData.count);
      setUserPosts(postsData.data || []);
    } catch (error) {
      console.error('Failed to fetch user data:', error);
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    fetchUserData();
  }, [fetchUserData]);

  const handleFollow = async () => {
    try {
      const endpoint = isFollowing ? 'unfollow' : 'follow';
      await fetch(`/api/v1/forum/users/${userId}/${endpoint}`, { method: 'POST' });
      setIsFollowing(!isFollowing);
    } catch (error) {
      console.error('Failed to follow user:', error);
    }
  };

  if (loading) return <Spinner />;

  const statItems = [
    { label: 'Posts', value: reputation?.post_count || 0 },
    { label: 'Comments', value: reputation?.comment_count || 0 },
    { label: 'Followers', value: followers },
    { label: 'Following', value: following },
  ];

  return (
    <div>
      {/* User Header — editorial, hairline-separated */}
      <section className="py-4 border-b flex justify-between items-start gap-4" style={{ borderColor: DIVIDER }}>
        <div>
          <h1 className="text-[22px] font-medium tracking-tight">{userId}</h1>
          {reputation && (
            <div className="mt-2 flex items-center gap-3">
              <span className={chipClass} style={{ borderColor: DIVIDER }}>{reputation.level.toUpperCase()}</span>
              <span className="font-data text-[13px] opacity-60">
                {reputation.reputation_points} reputation points
              </span>
            </div>
          )}
        </div>
        <button
          onClick={handleFollow}
          className={isFollowing
            ? 'text-[13px] px-3 py-1.5 border hover:bg-[var(--hover)]'
            : 'text-[13px] px-3 py-1.5 border bg-blue-600 text-white'}
          style={isFollowing ? { borderColor: DIVIDER } : undefined}
        >
          {isFollowing ? 'Following' : 'Follow'}
        </button>
      </section>

      {/* Stats — single-row horizontal, 1px dividers */}
      <section className="py-4 border-b" style={{ borderColor: DIVIDER }}>
        <dl className="flex flex-wrap gap-y-4">
          {statItems.map((item, i) => (
            <div
              key={item.label}
              className={'flex flex-col gap-1.5 pr-6 mr-6' + (i < statItems.length - 1 ? ' border-r' : '')}
              style={i < statItems.length - 1 ? { borderColor: DIVIDER } : undefined}
            >
              <dd className="font-data text-[20px] leading-none order-2">{item.value}</dd>
              <dt className="text-[11px] uppercase tracking-[0.06em] opacity-50 order-1">{item.label}</dt>
            </div>
          ))}
        </dl>
      </section>

      {/* Badges */}
      {reputation?.badges && reputation.badges.length > 0 && (
        <section className="py-4 border-b" style={{ borderColor: DIVIDER }}>
          <h3 className="text-[11px] uppercase tracking-[0.08em] opacity-50 mb-2">Badges</h3>
          <div className="flex gap-2 flex-wrap">
            {reputation.badges.map((badge: string) => (
              <span key={badge} className={chipClass} style={{ borderColor: DIVIDER }}>{badge}</span>
            ))}
          </div>
        </section>
      )}

      {/* User Posts — hairline rows */}
      <section className="py-4">
        <h2 className="text-[11px] uppercase tracking-[0.08em] opacity-50 mb-2">Recent Posts</h2>
        {userPosts.length === 0 ? (
          <p className="empty-state">No posts yet</p>
        ) : (
          <div>
            {userPosts.map((post) => (
              <div
                key={post.id}
                role="button"
                tabIndex={0}
                className="row-line cursor-pointer hover:bg-[var(--hover)]"
                onClick={() => window.location.href = `/forum/posts/${post.id}`}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') window.location.href = `/forum/posts/${post.id}`; }}
              >
                <h3 className="text-[14px] font-medium">{post.title}</h3>
                <p className="font-data text-xs opacity-50 mt-1">{post.comment_count} comments</p>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
};
