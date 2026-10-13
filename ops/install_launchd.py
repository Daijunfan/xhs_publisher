#!/usr/bin/env python3
"""Install the validated launchd definition through the public CLI."""

from xhs_local.cli import _render_plist

if __name__ == "__main__":
    destination = _render_plist()
    print(f"wrote {destination}")
