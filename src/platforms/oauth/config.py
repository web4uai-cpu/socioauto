"""Per-platform OAuth2 endpoint configuration.

Client IDs/secrets are never hardcoded — they are read from the environment at request time
(names below). Endpoints/scopes match each platform's public OAuth2 documentation.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class OAuthConfig:
    platform: str
    authorize_url: str
    token_url: str
    scopes: list[str]
    client_id_env: str
    client_secret_env: str
    # X (Twitter) requires PKCE for the OAuth2 authorization-code flow.
    use_pkce: bool = False
    extra_authorize_params: dict[str, str] = field(default_factory=dict)


PLATFORM_OAUTH: dict[str, OAuthConfig] = {
    "x": OAuthConfig(
        platform="x",
        authorize_url="https://twitter.com/i/oauth2/authorize",
        token_url="https://api.twitter.com/2/oauth2/token",
        scopes=["tweet.read", "tweet.write", "users.read", "offline.access"],
        client_id_env="X_CLIENT_ID",
        client_secret_env="X_CLIENT_SECRET",
        use_pkce=True,
    ),
    "linkedin": OAuthConfig(
        platform="linkedin",
        authorize_url="https://www.linkedin.com/oauth/v2/authorization",
        token_url="https://www.linkedin.com/oauth/v2/accessToken",
        scopes=["openid", "profile", "w_member_social"],
        client_id_env="LINKEDIN_CLIENT_ID",
        client_secret_env="LINKEDIN_CLIENT_SECRET",
    ),
    "facebook": OAuthConfig(
        platform="facebook",
        authorize_url="https://www.facebook.com/v19.0/dialog/oauth",
        token_url="https://graph.facebook.com/v19.0/oauth/access_token",
        scopes=["pages_manage_posts", "pages_read_engagement"],
        client_id_env="META_APP_ID",
        client_secret_env="META_APP_SECRET",
    ),
    "instagram": OAuthConfig(
        platform="instagram",
        authorize_url="https://www.facebook.com/v19.0/dialog/oauth",
        token_url="https://graph.facebook.com/v19.0/oauth/access_token",
        scopes=["instagram_basic", "instagram_content_publish", "pages_show_list"],
        client_id_env="META_APP_ID",
        client_secret_env="META_APP_SECRET",
    ),
    "tiktok": OAuthConfig(
        platform="tiktok",
        authorize_url="https://www.tiktok.com/v2/auth/authorize/",
        token_url="https://open.tiktokapis.com/v2/oauth/token/",
        scopes=["user.info.basic", "video.publish"],
        client_id_env="TIKTOK_CLIENT_KEY",
        client_secret_env="TIKTOK_CLIENT_SECRET",
    ),
    # YouTube long-form and Shorts are the same Google account and the same OAuth app; they are
    # separate platform keys only so content/scheduling specs can differ.
    "youtube": OAuthConfig(
        platform="youtube",
        authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        scopes=[
            "https://www.googleapis.com/auth/youtube.upload",
            "https://www.googleapis.com/auth/youtube.readonly",
        ],
        client_id_env="YOUTUBE_CLIENT_ID",
        client_secret_env="YOUTUBE_CLIENT_SECRET",
        use_pkce=True,
        # Google only issues a refresh token when both of these are present on the consent URL.
        extra_authorize_params={"access_type": "offline", "prompt": "consent"},
    ),
    "youtube_shorts": OAuthConfig(
        platform="youtube_shorts",
        authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        scopes=[
            "https://www.googleapis.com/auth/youtube.upload",
            "https://www.googleapis.com/auth/youtube.readonly",
        ],
        client_id_env="YOUTUBE_CLIENT_ID",
        client_secret_env="YOUTUBE_CLIENT_SECRET",
        use_pkce=True,
        extra_authorize_params={"access_type": "offline", "prompt": "consent"},
    ),
}
