"""Small macOS boundary used by the Safari publishing backend."""

# AppleScript source lines are kept intact for readability and behavior parity.
# ruff: noqa: E501

from __future__ import annotations

import subprocess
import tempfile
import time
from dataclasses import dataclass

from .errors import SafariAutomationError


def run_applescript(source: str, *arguments: str, timeout: float = 60.0) -> str:
    try:
        completed = subprocess.run(
            ["/usr/bin/osascript", "-e", source, *arguments],
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        stderr = getattr(error, "stderr", "") or str(error)
        raise SafariAutomationError(stderr.strip()) from error
    return completed.stdout.strip()


@dataclass(slots=True)
class SafariTabSession:
    """One dedicated minimized Safari window for the application lifetime."""

    window_id: int
    safari_was_running: bool
    _closed: bool = False

    @classmethod
    def open(cls, url: str) -> SafariTabSession:
        was_running = (
            run_applescript(
                'tell application "System Events" to return exists application process "Safari"'
            )
            == "true"
        )
        try:
            subprocess.run(
                ["/usr/bin/open", "-gja", "Safari"],
                check=True,
                capture_output=True,
                text=True,
                timeout=15,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
            raise SafariAutomationError(str(error)) from error
        time.sleep(0.75)
        source = """
on run argv
    set targetURL to item 1 of argv
    tell application "Safari"
        set beforeIds to id of every window
        make new document with properties {URL:targetURL}
        repeat 30 times
            repeat with targetWindow in windows
                set targetWindowId to id of targetWindow
                if beforeIds does not contain targetWindowId then
                    set miniaturized of targetWindow to true
                    if item 2 of argv is "false" then
                        repeat with oldWindowId in beforeIds
                            if exists (first window whose id is oldWindowId) then
                                set oldWindow to first window whose id is oldWindowId
                                set oldURL to URL of first tab of oldWindow as text
                                if oldURL starts with "favorites://" or oldURL is "about:blank" then close oldWindow
                            end if
                        end repeat
                    end if
                    return targetWindowId as text
                end if
            end repeat
            delay 0.1
        end repeat
        return "NOT_FOUND"
    end tell
end run
"""
        window_id = run_applescript(source, url, str(was_running).lower())
        if not window_id.isdecimal():
            raise SafariAutomationError(f"could not identify dedicated Safari window: {window_id}")
        return cls(
            window_id=int(window_id),
            safari_was_running=was_running,
        )

    def navigate(self, url: str) -> None:
        source = """
on run argv
    set targetWindowId to item 1 of argv as integer
    set targetURL to item 2 of argv
    tell application "Safari"
        set targetWindow to first window whose id is targetWindowId
        set URL of first tab of targetWindow to targetURL
        set miniaturized of targetWindow to true
    end tell
end run
"""
        run_applescript(source, str(self.window_id), url)

    def run_javascript(self, source: str) -> str:
        applescript = """
on run argv
    set targetWindowId to item 1 of argv as integer
    set sourceFile to POSIX file (item 2 of argv)
    set javascriptSource to read sourceFile as «class utf8»

    tell application "Safari"
        set targetWindow to first window whose id is targetWindowId
        if (count of tabs of targetWindow) is 0 then error "Safari automation window has no tab"
        return do JavaScript javascriptSource in first tab of targetWindow
    end tell
end run
"""
        with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8") as handle:
            handle.write(source)
            handle.flush()
            return run_applescript(
                applescript,
                str(self.window_id),
                handle.name,
            )

    def close(self) -> None:
        if self._closed:
            return
        source = """
on run argv
    set targetWindowId to item 1 of argv as integer
    set safariWasRunning to item 2 of argv is "true"
    tell application "System Events"
        if not (exists application process "Safari") then return
    end tell
    if safariWasRunning is false then
        tell application "Safari" to quit
        return
    end if
    tell application "Safari"
        if exists (first window whose id is targetWindowId) then close first window whose id is targetWindowId
    end tell
end run
"""
        run_applescript(
            source,
            str(self.window_id),
            str(self.safari_was_running).lower(),
        )
        self._closed = True

    def __enter__(self) -> SafariTabSession:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
