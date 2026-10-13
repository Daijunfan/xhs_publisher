# Xiaohongshu Mac Safari sink

This is the sole Xiaohongshu publication implementation. It packages the proven
`xhs_publish_test` Safari backend behind the project's async Sink contract.

- `browser.py` maps `PublishNote` and errors to the project contract.
- `backend.py` owns the creator-page state machine and component `publish` event.
- `macos.py` owns the isolated Safari tab and AppleScript boundary.
- `models.py` and `errors.py` define internal values only.

The backend never calls the page-private `_onPublish()` method. A result is successful
only after the creator page reports success and the note manager confirms the title or
post-count increase.

`http.py` exposes the authenticated manual publishing API used by the operating AI Agent.
It accepts approved drafts across source platforms and reuses the browser contract.
