import os
import re
from fastmcp.server.auth import AuthProvider, AccessToken


def validate_token_format(token: str) -> bool:
    """Validate token format requirements.

    Requirements:
    - At least 10 characters long
    - At least 2 lowercase letters
    - At least 2 uppercase letters
    - At least 2 digits

    Args:
        token: The token string to validate

    Returns:
        True if token is valid, False otherwise
    """
    if len(token) < 10:
        return False

    lowercase_count = len(re.findall(r"[a-z]", token))
    uppercase_count = len(re.findall(r"[A-Z]", token))
    digit_count = len(re.findall(r"\d", token))

    return (
        lowercase_count >= 2 and uppercase_count >= 2 and digit_count >= 2
    )


def create_bearer_auth(env_var: str = "MCP_AUTH_TOKEN") -> AuthProvider | None:
    """Create a bearer token authentication provider.

    Creates an AuthProvider that validates bearer tokens from an environment
    variable. If the environment variable is not set or empty, returns None
    (no authentication).

    Args:
        env_var: Name of the environment variable containing the bearer token

    Returns:
        AuthProvider instance if token is configured and valid, None otherwise
    """
    token = os.getenv(env_var, "").strip()

    if not token:
        return None

    if not validate_token_format(token):
        raise ValueError(
            f"Invalid token format in {env_var}. Token must be at least 10 "
            "characters with at least 2 lowercase, 2 uppercase, and 2 digits."
        )

    class BearerTokenValidator(AuthProvider):
        """Bearer token validator using environment variable."""

        async def verify_token(self, incoming_token: str) -> AccessToken | None:
            """Verify a bearer token.

            Args:
                incoming_token: The token string to validate

            Returns:
                AccessToken if valid, None if invalid
            """
            if incoming_token == token:
                return AccessToken(
                    token=incoming_token,
                    client_id="authenticated",
                    scopes=[],
                )
            return None

    return BearerTokenValidator()
