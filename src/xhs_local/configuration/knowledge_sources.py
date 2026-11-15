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
