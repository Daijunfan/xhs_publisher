"""Pure public-source URL identities shared by configuration and adapters."""

from __future__ import annotations

import re
from urllib.parse import unquote, urlsplit


def linkedin_homepage(value: str) -> str:
    parsed = urlsplit(value)
    match = re.fullmatch(
        r"/(in|company|school|showcase)/([\w.-]+)(?:/posts|/recent-activity/(?:all|posts))?",
        unquote(parsed.path).rstrip("/"),
    )
    host = parsed.hostname or ""
    if (
        parsed.scheme not in {"http", "https"}
        or (
            host not in {"linkedin.com", "www.linkedin.com"}
            and not re.fullmatch(r"[a-z]{2}\.linkedin\.com", host)
        )
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443, 80)
        or not match
    ):
        raise ValueError(
            "LinkedIn locator must be a public person, company, showcase or school homepage"
        )
    return "https://www.linkedin.com/" + match[1] + "/" + match[2].lower()


def zhihu_locator_kind(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"https", "http"}
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443, 80)
    ):
        raise ValueError("Use a Zhihu public source URL")
    if parsed.hostname == "daily.zhihu.com" and not parsed.path.strip("/"):
        return "editorial"
    if parsed.hostname in {"www.zhihu.com", "zhihu.com"} and re.fullmatch(
        r"/(people|org)/[\w.-]+(?:/(?:activities|answers|articles|posts))?/?", unquote(parsed.path)
    ):
        return "author"
    raise ValueError("Use a Zhihu author homepage or https://daily.zhihu.com/")


def reddit_homepage(value: str) -> str:
    value = value.strip()
    if re.match(r"^/?(?:r|u|user)/", value, re.I):
        value = "https://www.reddit.com/" + value.lstrip("/")
    parsed = urlsplit(value)
    match = re.fullmatch(
        r"/(r|u|user)/([a-z0-9_-]{2,30})(?:/(?:new|hot|top|submitted))?/?",
        unquote(parsed.path),
        re.I,
    )
    if (
        parsed.scheme not in {"https", "http"}
        or parsed.hostname not in {"reddit.com", "www.reddit.com", "old.reddit.com"}
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 80, 443)
        or not match
        or match[2].lower() in {"all", "popular", "friends", "mod"}
    ):
        raise ValueError("Use a Reddit community or user homepage")
    kind = "r" if match[1].lower() == "r" else "user"
    return "https://www.reddit.com/" + kind + "/" + match[2].lower() + "/"
