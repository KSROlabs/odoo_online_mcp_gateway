# -*- coding: utf-8 -*-
"""XML-RPC client for Odoo Online with timeout handling."""
import socket
import xmlrpc.client

from .constants import ODOO_RPC_TIMEOUT_SECONDS


class _TimeoutTransport(xmlrpc.client.Transport):
    def __init__(self, timeout: int):
        super().__init__()
        self._timeout = timeout

    def make_connection(self, host):  # noqa: A003
        conn = super().make_connection(host)
        conn.timeout = self._timeout
        return conn


class _TimeoutSafeTransport(xmlrpc.client.SafeTransport):
    def __init__(self, timeout: int):
        super().__init__()
        self._timeout = timeout

    def make_connection(self, host):  # noqa: A003
        conn = super().make_connection(host)
        conn.timeout = self._timeout
        return conn


class OdooXMLRPC:
    """XML-RPC client for Odoo Online with automatic authentication and timeout handling."""

    def __init__(self, base_url: str, db: str, login: str, password: str, timeout: int = None):
        """
        Initialize Odoo XML-RPC client.

        Args:
            base_url: Odoo Online base URL (e.g., https://company.odoo.com)
            db: Database name
            login: User login (email)
            password: User password or API key
            timeout: Connection timeout in seconds (default: ODOO_RPC_TIMEOUT_SECONDS)
        """
        self.base_url = base_url.rstrip("/")
        self.db = db
        self.login = login
        self.password = password
        self.timeout = timeout or ODOO_RPC_TIMEOUT_SECONDS
        self._uid = None
        self._common = None
        self._object = None

    def _server_proxy(self, url: str) -> xmlrpc.client.ServerProxy:
        if url.startswith("https://"):
            transport = _TimeoutSafeTransport(timeout=self.timeout)
        else:
            transport = _TimeoutTransport(timeout=self.timeout)
        return xmlrpc.client.ServerProxy(url, allow_none=True, transport=transport)

    @property
    def common(self) -> xmlrpc.client.ServerProxy:
        if self._common is None:
            self._common = self._server_proxy("%s/xmlrpc/2/common" % self.base_url)
        return self._common

    @property
    def object(self) -> xmlrpc.client.ServerProxy:
        if self._object is None:
            self._object = self._server_proxy("%s/xmlrpc/2/object" % self.base_url)
        return self._object

    def authenticate(self) -> int:
        """
        Authenticate with Odoo and get user ID.

        Returns:
            User ID if authentication succeeds

        Raises:
            PermissionError: If authentication fails
        """
        uid = self.common.authenticate(self.db, self.login, self.password, {})
        if not uid:
            raise PermissionError("Odoo authentication failed")
        self._uid = uid
        return uid

    @property
    def uid(self) -> int:
        """Get current user ID, authenticating if necessary."""
        if self._uid is None:
            return self.authenticate()
        return self._uid

    def execute_kw(self, model: str, method: str, args, kwargs=None):
        """
        Execute an ORM method on a model.

        Args:
            model: Odoo model name (e.g., 'res.partner')
            method: ORM method (e.g., 'search_read', 'create')
            args: Positional arguments
            kwargs: Keyword arguments

        Returns:
            Result from Odoo

        Raises:
            Exception: If the call fails (socket timeout, fault, etc.)
        """
        if kwargs is None:
            kwargs = {}
        try:
            return self.object.execute_kw(self.db, self.uid, self.password, model, method, args, kwargs)
        except (xmlrpc.client.Fault, socket.timeout) as exc:
            # Try one re-auth on auth/session faults.
            self._uid = None
            try:
                return self.object.execute_kw(self.db, self.uid, self.password, model, method, args, kwargs)
            except Exception:
                raise exc
