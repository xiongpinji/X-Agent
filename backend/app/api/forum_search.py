"""Forum search API endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from backend.app.core.security import Principal
from backend.app.dependencies import get_current_principal
from backend.app.models.forum import forum_store
from backend.app.services.forum_search import search_index

router = APIRouter(prefix="/api/v1/forum/search", tags=["forum-search"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


@router.get("/posts")
async def search_posts(
    q: str = Query(..., min_length=2, max_length=200),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    principal: PrincipalDependency = None,
) -> dict:
    """Search forum posts by full-text query.

    Args:
        q: Search query
        limit: Number of results per page
        offset: Number of results to skip
        principal: Current user principal

    Returns:
        Paginated search results
    """
    results = search_index.search(q, limit=limit + offset)

    # Filter to only posts (not comments)
    post_ids = [post_id for post_id, comment_id in results if comment_id is None]

    # Get post objects
    posts = []
    for post_id in post_ids[offset:offset + limit]:
        post = forum_store.posts.get(post_id)
        if post:
            posts.append(post.model_dump())

    return {
        "data": posts,
        "total": len(post_ids),
        "limit": limit,
        "offset": offset,
        "query": q,
    }


@router.get("/tags")
async def search_by_tag(
    tag: str = Query(..., min_length=1, max_length=50),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    principal: PrincipalDependency = None,
) -> dict:
    """Search posts by tag.

    Args:
        tag: Tag to search for
        limit: Number of results per page
        offset: Number of results to skip
        principal: Current user principal

    Returns:
        Paginated search results
    """
    post_ids = search_index.search_by_tag(tag, limit=limit + offset)

    posts = []
    for post_id in post_ids[offset:offset + limit]:
        post = forum_store.posts.get(post_id)
        if post:
            posts.append(post.model_dump())

    return {
        "data": posts,
        "total": len(post_ids),
        "limit": limit,
        "offset": offset,
        "tag": tag,
    }


@router.get("/authors/{author_id}")
async def search_by_author(
    author_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    principal: PrincipalDependency = None,
) -> dict:
    """Search posts by author.

    Args:
        author_id: Author ID to search for
        limit: Number of results per page
        offset: Number of results to skip
        principal: Current user principal

    Returns:
        Paginated search results
    """
    post_ids = search_index.search_by_author(author_id, limit=limit + offset)

    posts = []
    for post_id in post_ids[offset:offset + limit]:
        post = forum_store.posts.get(post_id)
        if post:
            posts.append(post.model_dump())

    return {
        "data": posts,
        "total": len(post_ids),
        "limit": limit,
        "offset": offset,
        "author_id": author_id,
    }


@router.get("/categories/{category}")
async def search_by_category(
    category: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    principal: PrincipalDependency = None,
) -> dict:
    """Search posts by category.

    Args:
        category: Category to search for
        limit: Number of results per page
        offset: Number of results to skip
        principal: Current user principal

    Returns:
        Paginated search results
    """
    post_ids = search_index.search_by_category(category, limit=limit + offset)

    posts = []
    for post_id in post_ids[offset:offset + limit]:
        post = forum_store.posts.get(post_id)
        if post:
            posts.append(post.model_dump())

    return {
        "data": posts,
        "total": len(post_ids),
        "limit": limit,
        "offset": offset,
        "category": category,
    }


@router.get("/trending")
async def get_trending_posts(
    days: int = Query(7, ge=1, le=30),
    limit: int = Query(10, ge=1, le=50),
    principal: PrincipalDependency = None,
) -> dict:
    """Get trending posts based on engagement.

    Args:
        days: Number of days to look back
        limit: Number of results
        principal: Current user principal

    Returns:
        List of trending posts
    """
    from datetime import datetime, timedelta

    cutoff_date = datetime.utcnow() - timedelta(days=days)

    # Get posts from the last N days
    recent_posts = [
        p for p in forum_store.posts.values()
        if p.created_at >= cutoff_date
    ]

    # Sort by engagement score (views + likes + comments)
    recent_posts.sort(
        key=lambda p: p.view_count + (p.like_count * 2) + (p.comment_count * 3),
        reverse=True
    )

    return {
        "data": [p.model_dump() for p in recent_posts[:limit]],
        "total": len(recent_posts),
        "limit": limit,
        "days": days,
    }


@router.get("/popular-tags")
async def get_popular_tags(
    limit: int = Query(20, ge=1, le=100),
    principal: PrincipalDependency = None,
) -> dict:
    """Get most popular tags.

    Args:
        limit: Number of tags to return
        principal: Current user principal

    Returns:
        List of popular tags with usage counts
    """
    tag_counts = {}
    for post in forum_store.posts.values():
        for tag in post.tags:
            tag_lower = tag.lower()
            tag_counts[tag_lower] = tag_counts.get(tag_lower, 0) + 1

    # Sort by count
    popular_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)

    return {
        "data": [{"tag": tag, "count": count} for tag, count in popular_tags[:limit]],
        "total": len(popular_tags),
        "limit": limit,
    }
