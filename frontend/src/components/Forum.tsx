import React, { useState, useEffect } from 'react';
import { Card, Button, Input, Textarea, Badge, Spinner } from './ui';

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

export const ForumHome: React.FC = () => {
  const [posts, setPosts] = useState<ForumPost[]>([]);
  const [loading, setLoading] = useState(false);
  const [sortBy, setSortBy] = useState<'created_at' | 'views' | 'likes' | 'comments'>('created_at');
  const [category, setCategory] = useState<string>('');

  useEffect(() => {
    fetchPosts();
  }, [sortBy, category]);

  const fetchPosts = async () => {
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
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold">Community Forum</h1>
        <Button variant="primary" onClick={() => window.location.href = '/forum/create'}>
          New Post
        </Button>
      </div>

      {/* Filters */}
      <div className="flex gap-4">
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="px-4 py-2 border rounded-lg"
        >
          <option value="">All Categories</option>
          <option value="general">General</option>
          <option value="bugs">Bugs</option>
          <option value="features">Features</option>
          <option value="showcase">Showcase</option>
        </select>

        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value as any)}
          className="px-4 py-2 border rounded-lg"
        >
          <option value="created_at">Latest</option>
          <option value="views">Most Viewed</option>
          <option value="likes">Most Liked</option>
          <option value="comments">Most Discussed</option>
        </select>
      </div>

      {/* Posts List */}
      {loading ? (
        <Spinner />
      ) : (
        <div className="space-y-4">
          {posts.map((post) => (
            <Card key={post.id} className="p-4 hover:shadow-lg transition-shadow cursor-pointer"
              onClick={() => window.location.href = `/forum/posts/${post.id}`}>
              <div className="flex justify-between items-start">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    {post.is_pinned && <Badge variant="warning">Pinned</Badge>}
                    <h2 className="text-xl font-semibold">{post.title}</h2>
                  </div>
                  <p className="text-gray-600 mt-2 line-clamp-2">{post.content}</p>
                  <div className="flex gap-2 mt-3">
                    {post.tags.map((tag) => (
                      <Badge key={tag} variant="secondary">{tag}</Badge>
                    ))}
                  </div>
                </div>
                <div className="text-right text-sm text-gray-500">
                  <div>{post.view_count} views</div>
                  <div>{post.like_count} likes</div>
                  <div>{post.comment_count} comments</div>
                </div>
              </div>
              <div className="mt-3 text-sm text-gray-500">
                By {post.author_name} • {new Date(post.created_at).toLocaleDateString()}
              </div>
            </Card>
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

  useEffect(() => {
    fetchPost();
    fetchComments();
  }, [postId]);

  const fetchPost = async () => {
    try {
      const response = await fetch(`/api/v1/forum/posts/${postId}`);
      const data = await response.json();
      setPost(data);
    } catch (error) {
      console.error('Failed to fetch post:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchComments = async () => {
    try {
      const response = await fetch(`/api/v1/forum/posts/${postId}/comments?limit=50`);
      const data = await response.json();
      setComments(data.data || []);
    } catch (error) {
      console.error('Failed to fetch comments:', error);
    }
  };

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
    <div className="space-y-6">
      {/* Post Header */}
      <Card className="p-6">
        <h1 className="text-3xl font-bold mb-4">{post.title}</h1>
        <div className="flex justify-between items-center text-sm text-gray-600 mb-4">
          <div>
            By <strong>{post.author_name}</strong> • {new Date(post.created_at).toLocaleDateString()}
          </div>
          <div className="flex gap-4">
            <span>{post.view_count} views</span>
            <span>{post.comment_count} comments</span>
          </div>
        </div>

        {/* Tags */}
        <div className="flex gap-2 mb-4">
          {post.tags.map((tag) => (
            <Badge key={tag} variant="secondary">{tag}</Badge>
          ))}
        </div>

        {/* Content */}
        <div className="prose max-w-none mb-6">
          {post.content}
        </div>

        {/* Actions */}
        <div className="flex gap-4">
          <Button
            variant={liked ? 'primary' : 'secondary'}
            onClick={handleLike}
          >
            ❤️ Like ({post.like_count})
          </Button>
          <Button
            variant={bookmarked ? 'primary' : 'secondary'}
            onClick={handleBookmark}
          >
            🔖 Bookmark
          </Button>
        </div>
      </Card>

      {/* Comments Section */}
      <Card className="p-6">
        <h2 className="text-2xl font-bold mb-4">Comments ({post.comment_count})</h2>

        {/* Add Comment */}
        <div className="mb-6 p-4 bg-gray-50 rounded-lg">
          <Textarea
            value={newComment}
            onChange={(e) => setNewComment(e.target.value)}
            placeholder="Add a comment..."
            rows={4}
            className="w-full mb-2"
          />
          <Button
            variant="primary"
            onClick={handleAddComment}
            disabled={!newComment.trim()}
          >
            Post Comment
          </Button>
        </div>

        {/* Comments List */}
        <div className="space-y-4">
          {comments.map((comment) => (
            <div key={comment.id} className="p-4 border rounded-lg">
              <div className="flex justify-between items-start mb-2">
                <strong>{comment.author_name}</strong>
                <span className="text-sm text-gray-500">
                  {new Date(comment.created_at).toLocaleDateString()}
                </span>
              </div>
              <p className="text-gray-700 mb-2">{comment.content}</p>
              <div className="flex gap-4 text-sm">
                <button className="text-blue-600 hover:underline">
                  ❤️ Like ({comment.like_count})
                </button>
                <button className="text-blue-600 hover:underline">Reply</button>
              </div>
            </div>
          ))}
        </div>
      </Card>
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

  return (
    <div className="max-w-2xl mx-auto">
      <Card className="p-6">
        <h1 className="text-3xl font-bold mb-6">Create New Post</h1>

        <div className="space-y-4">
          <div>
            <label htmlFor="post-title" className="block text-sm font-medium mb-2">Title</label>
            <Input
              id="post-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Post title (min 5 characters)"
              className="w-full"
            />
          </div>

          <div>
            <label htmlFor="post-category" className="block text-sm font-medium mb-2">Category</label>
            <select
              id="post-category"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="w-full px-4 py-2 border rounded-lg"
            >
              <option value="general">General</option>
              <option value="bugs">Bugs</option>
              <option value="features">Features</option>
              <option value="showcase">Showcase</option>
            </select>
          </div>

          <div>
            <label htmlFor="post-content" className="block text-sm font-medium mb-2">Content</label>
            <Textarea
              id="post-content"
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="Post content (min 20 characters)"
              rows={10}
              className="w-full"
            />
          </div>

          <div>
            <label htmlFor="post-tags" className="block text-sm font-medium mb-2">Tags (comma-separated)</label>
            <Input
              id="post-tags"
              value={tags}
              onChange={(e) => setTags(e.target.value)}
              placeholder="e.g., bug, feature, help"
              className="w-full"
            />
          </div>

          <div className="flex gap-4">
            <Button
              variant="primary"
              onClick={handleSubmit}
              disabled={loading}
            >
              {loading ? 'Creating...' : 'Create Post'}
            </Button>
            <Button
              variant="secondary"
              onClick={() => window.history.back()}
            >
              Cancel
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
};

export const UserProfile: React.FC<{ userId: string }> = ({ userId }) => {
  const [reputation, setReputation] = useState<any>(null);
  const [followers, setFollowers] = useState(0);
  const [following, setFollowing] = useState(0);
  const [userPosts, setUserPosts] = useState<ForumPost[]>([]);
  const [loading, setLoading] = useState(true);
  const [isFollowing, setIsFollowing] = useState(false);

  useEffect(() => {
    fetchUserData();
  }, [userId]);

  const fetchUserData = async () => {
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
  };

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

  return (
    <div className="space-y-6">
      {/* User Header */}
      <Card className="p-6">
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-3xl font-bold">{userId}</h1>
            {reputation && (
              <div className="mt-2 space-y-1">
                <div className="text-lg">
                  <Badge variant="primary">{reputation.level.toUpperCase()}</Badge>
                </div>
                <div className="text-gray-600">
                  {reputation.reputation_points} reputation points
                </div>
              </div>
            )}
          </div>
          <Button
            variant={isFollowing ? 'secondary' : 'primary'}
            onClick={handleFollow}
          >
            {isFollowing ? 'Following' : 'Follow'}
          </Button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-4 gap-4 mt-6">
          <div className="text-center">
            <div className="text-2xl font-bold">{reputation?.post_count || 0}</div>
            <div className="text-gray-600">Posts</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold">{reputation?.comment_count || 0}</div>
            <div className="text-gray-600">Comments</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold">{followers}</div>
            <div className="text-gray-600">Followers</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold">{following}</div>
            <div className="text-gray-600">Following</div>
          </div>
        </div>

        {/* Badges */}
        {reputation?.badges && reputation.badges.length > 0 && (
          <div className="mt-6">
            <h3 className="font-semibold mb-2">Badges</h3>
            <div className="flex gap-2">
              {reputation.badges.map((badge: string) => (
                <Badge key={badge} variant="warning">{badge}</Badge>
              ))}
            </div>
          </div>
        )}
      </Card>

      {/* User Posts */}
      <Card className="p-6">
        <h2 className="text-2xl font-bold mb-4">Recent Posts</h2>
        <div className="space-y-4">
          {userPosts.map((post) => (
            <div
              key={post.id}
              role="button"
              tabIndex={0}
              className="p-4 border rounded-lg hover:shadow-lg transition-shadow cursor-pointer"
              onClick={() => window.location.href = `/forum/posts/${post.id}`}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') window.location.href = `/forum/posts/${post.id}`; }}
            >
              <h3 className="font-semibold">{post.title}</h3>
              <p className="text-gray-600 text-sm mt-1">{post.comment_count} comments</p>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
};
