"""Enterprise access for compliance-server. All calls go through mcp_servers._enterprise."""

from mcp_servers._enterprise import get_enterprise_client, guard

__all__ = ["get_enterprise_client", "guard"]
