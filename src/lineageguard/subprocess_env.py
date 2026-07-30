"""Build minimal child-process environments without leaking unrelated secrets."""

from __future__ import annotations

from collections.abc import Mapping


SAFE_PROCESS_VARIABLES = (
    "HOME",
    "LANG",
    "LC_ALL",
    "NO_PROXY",
    "PATH",
    "REQUESTS_CA_BUNDLE",
    "SSL_CERT_DIR",
    "SSL_CERT_FILE",
    "TMPDIR",
)

SAFE_DATAHUB_VARIABLES = (
    "DATAHUB_GMS_TOKEN",
    "DATAHUB_MCP_DISABLE_DEFAULT_VIEW",
    "DISABLE_NEWER_GMS_FIELD_DETECTION",
    "ENTITY_SCHEMA_TOKEN_BUDGET",
    "SAVE_DOCUMENT_ORGANIZE_BY_USER",
    "SAVE_DOCUMENT_PARENT_TITLE",
    "SAVE_DOCUMENT_RESTRICT_UPDATES",
    "SAVE_DOCUMENT_TOOL_ENABLED",
    "TOOL_RESPONSE_TOKEN_LIMIT",
)


def mcp_child_environment(
    environment: Mapping[str, str],
    *,
    gms_url: str,
    mutation_enabled: bool,
) -> dict[str, str]:
    """Return only the variables the official DataHub MCP process may receive."""

    allowed_names = SAFE_PROCESS_VARIABLES + SAFE_DATAHUB_VARIABLES
    child = {
        name: environment[name]
        for name in allowed_names
        if environment.get(name) is not None
    }
    child.update(
        {
            "DATAHUB_GMS_URL": gms_url,
            "DATAHUB_TELEMETRY_ENABLED": "false",
            "TOOLS_IS_MUTATION_ENABLED": (
                "true" if mutation_enabled else "false"
            ),
        }
    )
    return child
