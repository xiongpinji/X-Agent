"""
审批存储 - PostgreSQL实现
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models import ApprovalStoreModel
from backend.app.core.session import SessionManager

logger = logging.getLogger(__name__)


class ApprovalStorePostgres:
    """PostgreSQL审批存储实现"""

    async def create_approval(
        self,
        approval_id: str,
        tenant_id: str,
        user_id: str,
        request_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        details: dict,
        expires_at: datetime,
    ) -> ApprovalStoreModel:
        """创建审批请求"""
        async with SessionManager.get_session() as session:
            approval = ApprovalStoreModel(
                approval_id=approval_id,
                tenant_id=tenant_id,
                user_id=user_id,
                request_id=request_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                details=json.dumps(details),
                expires_at=expires_at,
            )
            session.add(approval)
            await session.flush()
            logger.info(f"审批请求创建成功: {approval_id}")
            return approval

    async def get_approval_by_id(self, approval_id: str) -> Optional[ApprovalStoreModel]:
        """根据ID获取审批"""
        async with SessionManager.get_session() as session:
            stmt = select(ApprovalStoreModel).where(ApprovalStoreModel.approval_id == approval_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_approval_by_request_id(self, request_id: str) -> Optional[ApprovalStoreModel]:
        """根据请求ID获取审批"""
        async with SessionManager.get_session() as session:
            stmt = select(ApprovalStoreModel).where(ApprovalStoreModel.request_id == request_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def list_pending_approvals(
        self,
        tenant_id: str,
        skip: int = 0,
        limit: int = 100,
    ) -> list[ApprovalStoreModel]:
        """列出待审批的请求"""
        async with SessionManager.get_session() as session:
            stmt = (
                select(ApprovalStoreModel)
                .where(
                    (ApprovalStoreModel.tenant_id == tenant_id)
                    & (ApprovalStoreModel.status == "pending")
                )
                .offset(skip)
                .limit(limit)
            )
            result = await session.execute(stmt)
            return result.scalars().all()

    async def list_approvals_by_user(
        self,
        user_id: str,
        tenant_id: str,
        skip: int = 0,
        limit: int = 100,
    ) -> list[ApprovalStoreModel]:
        """列出用户的审批请求"""
        async with SessionManager.get_session() as session:
            stmt = (
                select(ApprovalStoreModel)
                .where(
                    (ApprovalStoreModel.user_id == user_id)
                    & (ApprovalStoreModel.tenant_id == tenant_id)
                )
                .offset(skip)
                .limit(limit)
            )
            result = await session.execute(stmt)
            return result.scalars().all()

    async def approve(
        self,
        approval_id: str,
        approved_by: str,
        reason: Optional[str] = None,
    ) -> Optional[ApprovalStoreModel]:
        """批准审批请求"""
        async with SessionManager.get_session() as session:
            stmt = select(ApprovalStoreModel).where(ApprovalStoreModel.approval_id == approval_id)
            result = await session.execute(stmt)
            approval = result.scalar_one_or_none()

            if not approval:
                logger.warning(f"审批不存在: {approval_id}")
                return None

            approval.status = "approved"
            approval.approved_by = approved_by
            approval.approval_reason = reason
            approval.approved_at = datetime.now(UTC)
            await session.flush()
            logger.info(f"审批已批准: {approval_id}")
            return approval

    async def reject(
        self,
        approval_id: str,
        approved_by: str,
        reason: Optional[str] = None,
    ) -> Optional[ApprovalStoreModel]:
        """拒绝审批请求"""
        async with SessionManager.get_session() as session:
            stmt = select(ApprovalStoreModel).where(ApprovalStoreModel.approval_id == approval_id)
            result = await session.execute(stmt)
            approval = result.scalar_one_or_none()

            if not approval:
                logger.warning(f"审批不存在: {approval_id}")
                return None

            approval.status = "rejected"
            approval.approved_by = approved_by
            approval.approval_reason = reason
            approval.approved_at = datetime.now(UTC)
            await session.flush()
            logger.info(f"审批已拒绝: {approval_id}")
            return approval

    async def delete_approval(self, approval_id: str) -> bool:
        """删除审批"""
        async with SessionManager.get_session() as session:
            stmt = select(ApprovalStoreModel).where(ApprovalStoreModel.approval_id == approval_id)
            result = await session.execute(stmt)
            approval = result.scalar_one_or_none()

            if not approval:
                logger.warning(f"审批不存在: {approval_id}")
                return False

            await session.delete(approval)
            await session.flush()
            logger.info(f"审批已删除: {approval_id}")
            return True

    async def cleanup_expired_approvals(self) -> int:
        """清理过期的审批"""
        async with SessionManager.get_session() as session:
            stmt = select(ApprovalStoreModel).where(
                (ApprovalStoreModel.status == "pending")
                & (ApprovalStoreModel.expires_at < datetime.now(UTC))
            )
            result = await session.execute(stmt)
            expired_approvals = result.scalars().all()

            for approval in expired_approvals:
                approval.status = "expired"
                await session.flush()

            logger.info(f"清理了 {len(expired_approvals)} 个过期的审批")
            return len(expired_approvals)

    async def get_details(self, approval_id: str) -> Optional[dict]:
        """获取审批详情"""
        approval = await self.get_approval_by_id(approval_id)
        if not approval:
            return None
        return json.loads(approval.details)


# 全局实例
_approval_store: ApprovalStorePostgres | None = None


def get_approval_store() -> ApprovalStorePostgres:
    """获取全局审批存储实例"""
    global _approval_store
    if _approval_store is None:
        _approval_store = ApprovalStorePostgres()
    return _approval_store
