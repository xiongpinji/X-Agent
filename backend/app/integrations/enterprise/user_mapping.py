"""User Mapping Management for Enterprise IM Platforms"""

from datetime import datetime
from typing import Any


class UserMapping:
    """Manage user mappings across platforms"""

    def __init__(self):
        # Internal user ID -> {platform: platform_user_id}
        self.user_mappings: dict[str, dict[str, str]] = {}
        # Platform user ID -> internal user ID (for reverse lookup)
        self.reverse_mappings: dict[str, dict[str, str]] = {}
        # User metadata
        self.user_metadata: dict[str, dict[str, Any]] = {}
        # Sync history
        self.sync_history: list[dict[str, Any]] = []

    async def map_user(
        self,
        internal_user_id: str,
        platform: str,
        platform_user_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Map an internal user to a platform user"""
        try:
            # Add forward mapping
            if internal_user_id not in self.user_mappings:
                self.user_mappings[internal_user_id] = {}
            self.user_mappings[internal_user_id][platform] = platform_user_id

            # Add reverse mapping
            if platform not in self.reverse_mappings:
                self.reverse_mappings[platform] = {}
            self.reverse_mappings[platform][platform_user_id] = internal_user_id

            # Store metadata
            if metadata:
                if internal_user_id not in self.user_metadata:
                    self.user_metadata[internal_user_id] = {}
                self.user_metadata[internal_user_id][platform] = metadata

            return True
        except Exception as e:
            print(f"Failed to map user: {e}")
            return False

    async def unmap_user(self, internal_user_id: str, platform: str | None = None) -> bool:
        """Unmap a user from a platform or all platforms"""
        try:
            if internal_user_id not in self.user_mappings:
                return False

            if platform:
                # Unmap from specific platform
                if platform in self.user_mappings[internal_user_id]:
                    platform_user_id = self.user_mappings[internal_user_id][platform]
                    del self.user_mappings[internal_user_id][platform]

                    # Remove reverse mapping
                    if platform in self.reverse_mappings:
                        if platform_user_id in self.reverse_mappings[platform]:
                            del self.reverse_mappings[platform][platform_user_id]

                    # Remove metadata
                    if internal_user_id in self.user_metadata:
                        if platform in self.user_metadata[internal_user_id]:
                            del self.user_metadata[internal_user_id][platform]
            else:
                # Unmap from all platforms
                for plat in list(self.user_mappings[internal_user_id].keys()):
                    await self.unmap_user(internal_user_id, plat)

            return True
        except Exception as e:
            print(f"Failed to unmap user: {e}")
            return False

    async def get_platform_user_id(self, internal_user_id: str, platform: str) -> str | None:
        """Get platform user ID for an internal user"""
        try:
            if internal_user_id in self.user_mappings:
                return self.user_mappings[internal_user_id].get(platform)
            return None
        except Exception as e:
            print(f"Failed to get platform user ID: {e}")
            return None

    async def get_internal_user_id(self, platform: str, platform_user_id: str) -> str | None:
        """Get internal user ID for a platform user"""
        try:
            if platform in self.reverse_mappings:
                return self.reverse_mappings[platform].get(platform_user_id)
            return None
        except Exception as e:
            print(f"Failed to get internal user ID: {e}")
            return None

    async def get_user_mappings(self, internal_user_id: str) -> dict[str, str]:
        """Get all platform mappings for an internal user"""
        try:
            return self.user_mappings.get(internal_user_id, {})
        except Exception as e:
            print(f"Failed to get user mappings: {e}")
            return {}

    async def get_user_metadata(self, internal_user_id: str, platform: str | None = None) -> dict[str, Any]:
        """Get user metadata"""
        try:
            if internal_user_id not in self.user_metadata:
                return {}

            if platform:
                return self.user_metadata[internal_user_id].get(platform, {})
            else:
                return self.user_metadata[internal_user_id]
        except Exception as e:
            print(f"Failed to get user metadata: {e}")
            return {}

    async def update_user_metadata(
        self,
        internal_user_id: str,
        platform: str,
        metadata: dict[str, Any],
    ) -> bool:
        """Update user metadata"""
        try:
            if internal_user_id not in self.user_metadata:
                self.user_metadata[internal_user_id] = {}

            if platform not in self.user_metadata[internal_user_id]:
                self.user_metadata[internal_user_id][platform] = {}

            self.user_metadata[internal_user_id][platform].update(metadata)
            return True
        except Exception as e:
            print(f"Failed to update user metadata: {e}")
            return False

    async def sync_user_from_platform(
        self,
        platform: str,
        platform_user_id: str,
        user_info: dict[str, Any],
    ) -> bool:
        """Sync user information from a platform"""
        try:
            # Check if user already mapped
            internal_user_id = await self.get_internal_user_id(platform, platform_user_id)

            if not internal_user_id:
                # Create new internal user ID
                internal_user_id = f"{platform}_{platform_user_id}"

            # Map the user
            await self.map_user(internal_user_id, platform, platform_user_id, user_info)

            # Log sync
            self._log_sync(platform, platform_user_id, internal_user_id, "success")

            return True
        except Exception as e:
            print(f"Failed to sync user from platform: {e}")
            self._log_sync(platform, platform_user_id, "", "failed", str(e))
            return False

    async def bulk_sync_users(
        self,
        platform: str,
        users: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Bulk sync users from a platform"""
        results = {
            "total": len(users),
            "success": 0,
            "failed": 0,
            "errors": [],
        }

        for user_info in users:
            platform_user_id = user_info.get("userid") or user_info.get("id") or user_info.get("open_id")
            if not platform_user_id:
                results["failed"] += 1
                results["errors"].append("Missing user ID")
                continue

            try:
                success = await self.sync_user_from_platform(
                    platform, platform_user_id, user_info
                )
                if success:
                    results["success"] += 1
                else:
                    results["failed"] += 1
            except Exception as e:
                results["failed"] += 1
                results["errors"].append(str(e))

        return results

    async def get_all_users(self) -> list[dict[str, Any]]:
        """Get all mapped users"""
        users = []
        for internal_user_id, mappings in self.user_mappings.items():
            user = {
                "internal_user_id": internal_user_id,
                "platforms": mappings,
                "metadata": self.user_metadata.get(internal_user_id, {}),
            }
            users.append(user)
        return users

    async def get_users_by_platform(self, platform: str) -> list[dict[str, Any]]:
        """Get all users mapped to a specific platform"""
        users = []
        if platform in self.reverse_mappings:
            for platform_user_id, internal_user_id in self.reverse_mappings[platform].items():
                user = {
                    "internal_user_id": internal_user_id,
                    "platform_user_id": platform_user_id,
                    "metadata": self.user_metadata.get(internal_user_id, {}).get(platform, {}),
                }
                users.append(user)
        return users

    async def search_user(self, query: str) -> list[dict[str, Any]]:
        """Search for users by internal ID or platform user ID"""
        results = []

        # Search in internal user IDs
        for internal_user_id, mappings in self.user_mappings.items():
            if query.lower() in internal_user_id.lower():
                results.append({
                    "internal_user_id": internal_user_id,
                    "platforms": mappings,
                })

        # Search in platform user IDs
        for _platform, reverse_map in self.reverse_mappings.items():
            for platform_user_id, internal_user_id in reverse_map.items():
                if query.lower() in platform_user_id.lower():
                    if not any(r["internal_user_id"] == internal_user_id for r in results):
                        results.append({
                            "internal_user_id": internal_user_id,
                            "platforms": self.user_mappings.get(internal_user_id, {}),
                        })

        return results

    def _log_sync(
        self,
        platform: str,
        platform_user_id: str,
        internal_user_id: str,
        status: str,
        error: str | None = None,
    ):
        """Log sync operation"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "platform": platform,
            "platform_user_id": platform_user_id,
            "internal_user_id": internal_user_id,
            "status": status,
            "error": error,
        }
        self.sync_history.append(log_entry)

        # Keep only last 1000 entries
        if len(self.sync_history) > 1000:
            self.sync_history = self.sync_history[-1000:]

    def get_sync_history(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get sync history"""
        return self.sync_history[-limit:]

    def get_sync_stats(self) -> dict[str, Any]:
        """Get sync statistics"""
        if not self.sync_history:
            return {
                "total": 0,
                "success": 0,
                "failed": 0,
                "success_rate": 0.0,
            }

        total = len(self.sync_history)
        success = sum(1 for log in self.sync_history if log["status"] == "success")
        failed = total - success

        return {
            "total": total,
            "success": success,
            "failed": failed,
            "success_rate": success / total if total > 0 else 0.0,
        }

    def get_mapping_stats(self) -> dict[str, Any]:
        """Get mapping statistics"""
        total_users = len(self.user_mappings)
        platform_counts = {}

        for platform in self.reverse_mappings:
            platform_counts[platform] = len(self.reverse_mappings[platform])

        return {
            "total_users": total_users,
            "platforms": platform_counts,
        }
