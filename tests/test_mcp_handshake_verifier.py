"""Regression guards for the installer MCP handshake verifier."""

from scripts.verify import verify_mcp_handshake


def test_installer_handshake_verifies_the_customer_bridge() -> None:
    assert verify_mcp_handshake.MCP_MODULE == "src.mcp.stdio_bridge"


def test_installer_handshake_allows_for_cold_start() -> None:
    assert verify_mcp_handshake.HANDSHAKE_TIMEOUT_SECONDS >= 30.0
