# FRONTIER 前沿观测站 — Browser Client

Production client for the `xhs_local.frontier` backend. This directory belongs at `frontend/` beside `src/` in the server-derived repository.

## Build

Node.js 20.19+ or 22.12+ is required by Vite 7.

```sh
npm install
npm test
npm run build
```

The build emits `../src/xhs_local/frontier/static/index.html` plus hashed bundled assets. Serve this directory at `/` on the same origin as `/api/`. No CDN, external fonts, tracking, or map runtime service is needed. All maps come from the bundled Natural Earth geometry; see `public/ASSET-LICENSES.txt`.

`npm run dev` starts a loopback-only Vite development server. API requests proxy to a development tunnel at `http://127.0.0.1:18088`; this development address is not included as a production API destination.

## Product behavior

- HttpOnly cookie authentication using an owner access code. The CSRF token stays in memory; access codes and API keys are never stored in browser storage.
- `/api/events` drives all cards, counts, locations, timeline bounds and importance labels. Production contains no sample or synthetic news.
- Only valid coordinates on located events appear on the globe. The far side of the globe is occluded. Screen-space clusters open a keyboard-accessible list.
- Publication time, ingestion time, and event occurrence time are separately labeled. Unknown occurrence times never borrow the publication date and are excluded from replay.
- Date filters use Beijing calendar dates; their upper boundary is the next day's exclusive midnight, converted to UTC.
- Replay explicitly covers only loaded events with usable occurrence times. It does not claim complete historical coverage.
- Importance, event time and ingestion order; source/category/text/date filters; pagination; event details, source evidence and bookmarks; export capped at 200.
- Data refresh every 20 seconds while the page is visible. Network interruption retains the most recent displayed snapshot with a clear banner.
- Reduced motion disables auto-rotation by default. WebGL failure provides a list reading mode. Native dialogs trap focus, Escape closes them, and controls expose accessible names.
- Geography is illustrative. Country/city-level extraction is shown as approximate precision; map outlines do not assert territorial claims.

## Integration contract

- `GET /api/auth/me` → `{authenticated,csrf_token}`
- `POST /api/auth/session` `{token}` → `{authenticated,csrf_token}` + HttpOnly cookie
- `POST /api/auth/logout` + `X-CSRF-Token`
- `GET /api/events?sort=importance|event_time|discovered&q=&source=&category=&after=&before=&limit=100&offset=0&bookmarked=1`
- Result `{items,total,stats:{total,located,undated},facets:{categories:[{value,count}]}}`
- `GET /api/events/{id}` → event, with optional `{item:event}` supported
- `PUT /api/events/{id}/bookmark` `{bookmarked}` + `X-CSRF-Token`
- `GET /api/status` → collector, source and enrichment health
- `GET /api/export` → JSON result, current filters, maximum 200
- Error envelope `{error:{code,message}}`

All data-bearing source content is placed through `textContent`; only constant interface templates use HTML. Source links are parsed and restricted to HTTP/HTTPS with `noopener noreferrer`.
