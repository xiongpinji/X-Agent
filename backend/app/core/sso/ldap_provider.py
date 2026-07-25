"""LDAP Provider Implementation.

P1-05: 实现真实 ldap3 连接 (bind + search + 属性映射)。
当 ldap3 库不可用时降级为明确报错 (fail-closed)。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)

try:
    from ldap3 import ALL, SUBTREE, Connection, Server

    LDAP3_AVAILABLE = True
except ImportError:
    LDAP3_AVAILABLE = False


@dataclass
class LDAPConfig:
    """LDAP configuration."""

    server_url: str  # ldap://host:port or ldaps://host:port
    bind_dn: str | None = None  # Bind DN for authentication
    bind_password: str | None = None  # Bind password
    base_dn: str = ""  # Base DN for user search
    user_search_filter: str = "(uid={username})"  # User search filter
    group_search_filter: str = "(cn={group})"  # Group search filter
    user_object_class: str = "inetOrgPerson"
    group_object_class: str = "groupOfNames"
    mail_attribute: str = "mail"
    name_attribute: str = "displayName"
    group_member_attribute: str = "member"
    timeout: int = 10
    use_ssl: bool = False  # Use LDAPS


class LDAPUser(BaseModel):
    """LDAP user."""

    username: str
    email: str | None = None
    display_name: str | None = None
    groups: list[str] = []
    attributes: dict[str, Any] = {}
    dn: str = ""


class LDAPProvider:
    """LDAP provider for enterprise directory integration.

    P1-05: 实现真实 ldap3 连接 (bind + search + 属性映射)。
    当 ldap3 库未安装时所有操作 fail-closed。
    """

    def __init__(self, config: LDAPConfig) -> None:
        self.config = config
        self._server: Any = None
        self._connection: Any = None

    def _ensure_ldap3(self) -> None:
        """Fail-closed: 如果 ldap3 未安装则拒绝操作。"""
        if not LDAP3_AVAILABLE:
            raise RuntimeError(
                "ldap3 库未安装。请执行: pip install ldap3。"
                "生产环境 LDAP 认证必须安装 ldap3。"
            )

    async def connect(self) -> bool:
        """Connect to LDAP server using ldap3."""
        self._ensure_ldap3()
        try:
            use_ssl = self.config.use_ssl or self.config.server_url.startswith("ldaps://")
            self._server = Server(
                self.config.server_url,
                get_info=ALL,
                connect_timeout=self.config.timeout,
                use_ssl=use_ssl,
            )
            # Service account bind (for search operations)
            if self.config.bind_dn and self.config.bind_password:
                self._connection = Connection(
                    self._server,
                    user=self.config.bind_dn,
                    password=self.config.bind_password,
                    auto_bind=True,
                    receive_timeout=self.config.timeout,
                )
            else:
                # Anonymous bind
                self._connection = Connection(
                    self._server,
                    auto_bind=True,
                    receive_timeout=self.config.timeout,
                )
            logger.info(f"Connected to LDAP server: {self.config.server_url}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to LDAP server: {e}")
            self._connection = None
            return False

    async def disconnect(self) -> None:
        """Disconnect from LDAP server."""
        if self._connection:
            try:
                self._connection.unbind()
                logger.info("Disconnected from LDAP server")
            except Exception as e:
                logger.error(f"Failed to disconnect from LDAP server: {e}")
            finally:
                self._connection = None

    async def authenticate(self, username: str, password: str) -> LDAPUser | None:
        """Authenticate user with LDAP (bind + search + attribute mapping).

        Flow:
        1. Search for user DN by username
        2. Bind with user's DN and password
        3. Fetch user attributes
        4. Fetch user groups
        """
        self._ensure_ldap3()
        try:
            # Ensure service connection is active
            if not self._connection:
                connected = await self.connect()
                if not connected:
                    return None

            # 1. Search for user DN
            user_dn = self._search_user_dn(username)
            if not user_dn:
                logger.warning(f"LDAP user not found: {username}")
                return None

            # 2. Bind with user's DN and password (verify credentials)
            user_conn = Connection(
                self._server,
                user=user_dn,
                password=password,
                auto_bind=True,
                receive_timeout=self.config.timeout,
            )
            user_conn.unbind()

            # 3. Fetch user attributes
            user = self._fetch_user_attributes(username, user_dn)
            if not user:
                user = LDAPUser(username=username, dn=user_dn)

            # 4. Fetch user groups
            user.groups = await self.get_user_groups(username)

            logger.info(f"LDAP authentication successful: {username}")
            return user

        except Exception as e:
            logger.error(f"LDAP authentication failed for {username}: {e}")
            return None

    def _search_user_dn(self, username: str) -> str | None:
        """Search for user DN by username."""
        if not self._connection or not self.config.base_dn:
            return None

        search_filter = self.config.user_search_filter.format(username=username)
        self._connection.search(
            search_base=self.config.base_dn,
            search_filter=search_filter,
            search_scope=SUBTREE,
            attributes=["dn"],
        )

        if self._connection.entries:
            return str(self._connection.entries[0].entry_dn)
        return None

    def _fetch_user_attributes(self, username: str, user_dn: str) -> LDAPUser | None:
        """Fetch user attributes from LDAP."""
        if not self._connection:
            return None

        attrs = [self.config.mail_attribute, self.config.name_attribute, "uid", "cn"]
        self._connection.search(
            search_base=user_dn,
            search_filter="(objectClass=*)",
            search_scope=SUBTREE,
            attributes=attrs,
        )

        if not self._connection.entries:
            return None

        entry = self._connection.entries[0]
        email = None
        display_name = None
        raw_attrs: dict[str, Any] = {}

        try:
            email = str(entry[self.config.mail_attribute].value) if hasattr(entry, self.config.mail_attribute) else None
        except (KeyError, AttributeError):
            pass
        try:
            display_name = str(entry[self.config.name_attribute].value) if hasattr(entry, self.config.name_attribute) else None
        except (KeyError, AttributeError):
            pass

        # Collect all available attributes
        for attr_name in attrs:
            try:
                val = entry[attr_name].value
                raw_attrs[attr_name] = str(val) if val else ""
            except (KeyError, AttributeError):
                pass

        return LDAPUser(
            username=username,
            email=email,
            display_name=display_name,
            attributes=raw_attrs,
            dn=user_dn,
        )

    async def search_user(self, username: str) -> LDAPUser | None:
        """Search for user in LDAP."""
        self._ensure_ldap3()
        try:
            if not self._connection:
                connected = await self.connect()
                if not connected:
                    return None

            user_dn = self._search_user_dn(username)
            if not user_dn:
                return None

            user = self._fetch_user_attributes(username, user_dn)
            if user:
                user.groups = await self.get_user_groups(username)
            return user

        except Exception as e:
            logger.error(f"LDAP user search failed: {e}")
            return None

    async def get_user_groups(self, username: str) -> list[str]:
        """Get user's groups from LDAP."""
        self._ensure_ldap3()
        try:
            if not self._connection or not self.config.base_dn:
                return []

            # Search for groups containing the user
            user_dn = self._search_user_dn(username)
            if not user_dn:
                return []

            group_filter = f"(&(objectClass={self.config.group_object_class})({self.config.group_member_attribute}={user_dn}))"
            self._connection.search(
                search_base=self.config.base_dn,
                search_filter=group_filter,
                search_scope=SUBTREE,
                attributes=["cn"],
            )

            groups = []
            for entry in self._connection.entries:
                try:
                    groups.append(str(entry.cn.value))
                except (KeyError, AttributeError):
                    pass

            logger.debug(f"LDAP groups for {username}: {groups}")
            return groups

        except Exception as e:
            logger.error(f"LDAP group search failed: {e}")
            return []

    async def validate_group_membership(self, username: str, group: str) -> bool:
        """Validate user's group membership."""
        groups = await self.get_user_groups(username)
        return group in groups
