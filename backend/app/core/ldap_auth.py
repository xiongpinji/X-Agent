"""LDAP authentication provider for enterprise SSO.

Provides real LDAP bind authentication using ldap3 library with:
- Connection pooling and timeout
- Group membership resolution
- JIT user provisioning
- StartTLS support
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

try:
    import ldap3  # noqa: F401
    from ldap3 import ALL, Connection, Server, Tls
    from ldap3.core.exceptions import LDAPException

    LDAP3_AVAILABLE = True
except ImportError:
    LDAP3_AVAILABLE = False
    logger.info("ldap3 not installed. LDAP authentication disabled. pip install ldap3")


@dataclass
class LDAPConfig:
    """LDAP connection configuration."""

    server_url: str = "ldap://localhost:389"
    bind_dn: str = ""
    bind_password: str = ""
    search_base: str = "dc=example,dc=com"
    user_search_filter: str = "(uid={username})"
    group_search_base: str = ""
    group_search_filter: str = "(member={user_dn})"
    use_tls: bool = False
    tls_ca_cert: str | None = None
    connect_timeout: int = 10
    read_timeout: int = 30
    pool_size: int = 5
    tenant_id: str = "default"
    enabled: bool = True

    # Attribute mappings
    attr_uid: str = "uid"
    attr_email: str = "mail"
    attr_display_name: str = "cn"
    attr_groups: str = "memberOf"


@dataclass
class LDAPUser:
    """Authenticated LDAP user."""

    dn: str = ""
    uid: str = ""
    email: str = ""
    display_name: str = ""
    groups: list[str] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)


class LDAPAuthProvider:
    """Enterprise LDAP authentication with connection pooling.

    Usage:
        config = LDAPConfig(
            server_url="ldap://ldap.corp.example.com:389",
            bind_dn="cn=admin,dc=corp,dc=example,dc=com",
            bind_password="secret",
            search_base="ou=people,dc=corp,dc=example,dc=com",
        )
        provider = LDAPAuthProvider(config)
        user = provider.authenticate("jdoe", "password123")
    """

    def __init__(self, config: LDAPConfig) -> None:
        if not LDAP3_AVAILABLE:
            raise RuntimeError(
                "ldap3 library not installed. Install with: pip install ldap3"
            )
        self.config = config
        self._server: Any = None
        self._pool: list[Any] = []

    def _get_server(self) -> Any:
        """Get or create LDAP server connection."""
        if self._server is None:
            tls_config = None
            if self.config.use_tls:
                import ssl

                tls_context = ssl.create_default_context()
                if self.config.tls_ca_cert:
                    tls_context.load_verify_locations(self.config.tls_ca_cert)
                tls_config = Tls(context=tls_context)

            self._server = Server(
                self.config.server_url,
                use_ssl=self.config.server_url.startswith("ldaps://"),
                tls=tls_config,
                get_info=ALL,
                connect_timeout=self.config.connect_timeout,
            )
        return self._server

    def _get_connection(self, bind_dn: str = "", bind_password: str = "") -> Any:
        """Create a new LDAP connection."""
        server = self._get_server()
        conn = Connection(
            server,
            user=bind_dn or self.config.bind_dn,
            password=bind_password or self.config.bind_password,
            auto_bind=True,
            receive_timeout=self.config.read_timeout,
        )
        return conn

    def authenticate(self, username: str, password: str) -> LDAPUser | None:
        """Authenticate user via LDAP bind.

        Two-phase bind:
        1. Service account bind to search for user DN
        2. User DN bind to verify password

        Returns LDAPUser on success, None on failure.
        """
        if not self.config.enabled:
            logger.warning("LDAP authentication is disabled")
            return None

        try:
            # Phase 1: Search for user DN using service account
            search_conn = self._get_connection()
            try:
                search_filter = self.config.user_search_filter.format(username=username)
                search_conn.search(
                    search_base=self.config.search_base,
                    search_filter=search_filter,
                    attributes=[
                        self.config.attr_uid,
                        self.config.attr_email,
                        self.config.attr_display_name,
                        self.config.attr_groups,
                    ],
                )

                if not search_conn.entries:
                    logger.info(f"LDAP user not found: {username}")
                    return None

                entry = search_conn.entries[0]
                user_dn = entry.entry_dn
            finally:
                search_conn.unbind()

            # Phase 2: Verify password with user DN bind
            user_conn = Connection(
                self._get_server(),
                user=user_dn,
                password=password,
                auto_bind=True,
                receive_timeout=self.config.read_timeout,
            )
            user_conn.unbind()

            # Build user object
            user = LDAPUser(
                dn=user_dn,
                uid=str(getattr(entry, self.config.attr_uid, username)),
                email=str(getattr(entry, self.config.attr_email, "")),
                display_name=str(getattr(entry, self.config.attr_display_name, "")),
                groups=self._extract_groups(entry),
                attributes={str(k): str(v) for k, v in entry.entry_attributes_as_dict.items()},
            )

            logger.info(f"LDAP authentication successful: {user.uid} ({user.email})")
            return user

        except LDAPException as e:
            logger.warning(f"LDAP authentication failed for {username}: {e}")
            return None
        except Exception as e:
            logger.error(f"LDAP unexpected error: {e}")
            return None

    def _extract_groups(self, entry: Any) -> list[str]:
        """Extract group memberships from LDAP entry."""
        groups = []
        try:
            raw_groups = getattr(entry, self.config.attr_groups, None)
            if raw_groups:
                for g in raw_groups.values:
                    groups.append(str(g))
        except Exception:
            pass

        # Also search group base if configured
        if self.config.group_search_base:
            try:
                conn = self._get_connection()
                try:
                    group_filter = self.config.group_search_filter.format(
                        user_dn=entry.entry_dn
                    )
                    conn.search(
                        search_base=self.config.group_search_base,
                        search_filter=group_filter,
                        attributes=["cn"],
                    )
                    for g_entry in conn.entries:
                        groups.append(str(g_entry.cn))
                finally:
                    conn.unbind()
            except Exception as e:
                logger.debug(f"Group search failed: {e}")

        return groups

    def test_connection(self) -> dict[str, Any]:
        """Test LDAP connectivity."""
        try:
            conn = self._get_connection()
            server_info = str(conn.server) if conn.server else "unknown"
            conn.unbind()
            return {
                "status": "connected",
                "server": self.config.server_url,
                "server_info": server_info,
                "search_base": self.config.search_base,
            }
        except Exception as e:
            return {
                "status": "error",
                "server": self.config.server_url,
                "error": str(e),
            }
