"""Cloud Chromium tab implementing the existing publisher's session interface."""

from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from http.cookiejar import MozillaCookieJar
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import getproxies

from playwright.sync_api import Error, sync_playwright


def _proxy() -> dict[str, str] | None:
    value = getproxies().get("https")
    if not value:
        return None
    parsed = urlparse(value)
    result = {"server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"}
    if parsed.username:
        result.update(username=unquote(parsed.username), password=unquote(parsed.password or ""))
    return result


def _open_browser(url: str):
    root = Path(__file__).resolve().parents[5] / "runtime" / "secrets"
    state = root / "xiaohongshu-chromium.json"
    playwright = sync_playwright().start()
    try:
        browser = playwright.chromium.launch(headless=True, proxy=_proxy())
        try:
            context = browser.new_context(storage_state=str(state) if state.exists() else None)
            if not state.exists():
                jar = MozillaCookieJar(str(root / "xiaohongshu-safari.txt"))
                jar.load(ignore_discard=True)
                cookies = []
                for cookie in jar:
                    item = dict(
                        name=cookie.name,
                        value=cookie.value,
                        domain=cookie.domain,
                        path=cookie.path,
                        secure=cookie.secure,
                        httpOnly=cookie.has_nonstandard_attr("HttpOnly"),
                    )
                    if cookie.expires:
                        item["expires"] = cookie.expires
                    cookies.append(item)
                context.add_cookies(cookies)
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            return playwright, browser, context, page, state
        except BaseException:
            browser.close()
            raise
    except BaseException:
        playwright.stop()
        raise


class ChromiumTabSession:
    """Run all Playwright calls on one dedicated thread."""

    window_id = 0

    def __init__(
        self, executor: ThreadPoolExecutor, playwright, browser, context, page, state
    ) -> None:
        self.executor = executor
        self.playwright, self.browser, self.context, self.page = playwright, browser, context, page
        self.state_path = state

    @classmethod
    def open(cls, url: str) -> ChromiumTabSession:
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="xhs-chromium")
        try:
            return cls(executor, *executor.submit(_open_browser, url).result())
        except BaseException:
            executor.shutdown(wait=True)
            raise

    def navigate(self, url: str) -> None:
        self.executor.submit(
            self.page.goto, url, wait_until="domcontentloaded", timeout=45000
        ).result()

    def run_javascript(self, source: str) -> str:
        if source.startswith("location.href="):
            target = json.loads(source.removeprefix("location.href=").partition(";")[0])
            self.navigate(target)
            return "navigating"
        return str(
            self.executor.submit(self.page.evaluate, "(source) => eval(source)", source).result()
        )

    def fill_note(self, title: str, body: str) -> dict[str, str]:
        def fill() -> dict[str, str]:
            title_field = self.page.locator('input[placeholder*="标题"]')
            editor = self.page.locator('[contenteditable=true].ProseMirror')
            title_field.fill(title)
            editor.fill(body)
            return {"title": title_field.input_value().strip(), "body": editor.inner_text().strip()}

        return self.executor.submit(fill).result()

    def _close(self) -> None:
        with suppress(Error):
            self.context.storage_state(path=str(self.state_path))
            os.chmod(self.state_path, 0o600)
        with suppress(Error):
            self.context.close()
        with suppress(Error):
            self.browser.close()
        with suppress(Error):
            self.playwright.stop()

    def close(self) -> None:
        try:
            self.executor.submit(self._close).result()
        finally:
            self.executor.shutdown(wait=True)
