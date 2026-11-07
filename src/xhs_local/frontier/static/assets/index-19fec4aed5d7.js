const __vite__mapDeps = (
  i,
  m = __vite__mapDeps,
  d = m.f || (m.f = ["assets/globe-b008dea4dfd5.js", "assets/globe-C4p2zDM5.js"]),
) => i.map((i) => d[i]);
(function () {
  const a = document.createElement("link").relList;
  if (a && a.supports && a.supports("modulepreload")) return;
  for (const c of document.querySelectorAll('link[rel="modulepreload"]')) l(c);
  new MutationObserver((c) => {
    for (const f of c)
      if (f.type === "childList")
        for (const m of f.addedNodes)
          m.tagName === "LINK" && m.rel === "modulepreload" && l(m);
  }).observe(document, { childList: !0, subtree: !0 });
  function o(c) {
    const f = {};
    return (
      c.integrity && (f.integrity = c.integrity),
      c.referrerPolicy && (f.referrerPolicy = c.referrerPolicy),
      c.crossOrigin === "use-credentials"
        ? (f.credentials = "include")
        : c.crossOrigin === "anonymous"
          ? (f.credentials = "omit")
          : (f.credentials = "same-origin"),
      f
    );
  }
  function l(c) {
    if (c.ep) return;
    c.ep = !0;
    const f = o(c);
    fetch(c.href, f);
  }
})();
const Oa = "modulepreload",
  Pa = function (t) {
    return "/" + t;
  },
  Zn = {},
  Ua = function (a, o, l) {
    let c = Promise.resolve();
    if (o && o.length > 0) {
      let g = function (h) {
        return Promise.all(
          h.map((k) =>
            Promise.resolve(k).then(
              (Y) => ({ status: "fulfilled", value: Y }),
              (Y) => ({ status: "rejected", reason: Y }),
            ),
          ),
        );
      };
      document.getElementsByTagName("link");
      const m = document.querySelector("meta[property=csp-nonce]"),
        s = m?.nonce || m?.getAttribute("nonce");
      c = g(
        o.map((h) => {
          if (((h = Pa(h)), h in Zn)) return;
          Zn[h] = !0;
          const k = h.endsWith(".css"),
            Y = k ? '[rel="stylesheet"]' : "";
          if (document.querySelector(`link[href="${h}"]${Y}`)) return;
          const G = document.createElement("link");
          if (
            ((G.rel = k ? "stylesheet" : Oa),
            k || (G.as = "script"),
            (G.crossOrigin = ""),
            (G.href = h),
            s && G.setAttribute("nonce", s),
            document.head.appendChild(G),
            k)
          )
            return new Promise((pe, L) => {
              (G.addEventListener("load", pe),
                G.addEventListener("error", () =>
                  L(new Error(`Unable to preload CSS for ${h}`)),
                ));
            });
        }),
      );
    }
    function f(m) {
      const s = new Event("vite:preloadError", { cancelable: !0 });
      if (((s.payload = m), window.dispatchEvent(s), !s.defaultPrevented))
        throw m;
    }
    return c.then((m) => {
      for (const s of m || []) s.status === "rejected" && f(s.reason);
      return a().catch(f);
    });
  },
  i = (t, a = document) => a.querySelector(t),
  Ne = (t, a = document) => [...a.querySelectorAll(t)],
  y = (t) =>
    t != null && t !== "" && Number.isFinite(Number(t))
      ? new Intl.NumberFormat("zh-CN").format(Number(t))
      : "—",
  Xn = {
    globe:
      '<circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><path d="M3.5 9h17M3.5 15h17"/>',
    radar:
      '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5.5"/><circle cx="12" cy="12" r="2"/><path d="M12 12l7-7"/>',
    search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4.5 4.5"/>',
    refresh:
      '<path d="M20 7v5h-5M4 17v-5h5"/><path d="M6 7a7 7 0 0 1 11.5-1L20 9M4 15l2.5 3A7 7 0 0 0 18 17"/>',
    bookmark: '<path d="M6 4h12v17l-6-4-6 4z"/>',
    close: '<path d="m6 6 12 12M18 6 6 18"/>',
    arrow: '<path d="M5 12h14m-5-5 5 5-5 5"/>',
    chevron: '<path d="m9 5 7 7-7 7"/>',
    external: '<path d="M13 4h7v7m0-7L10 14M9 5H4v15h15v-5"/>',
    filter:
      '<path d="M4 7h16M4 17h16"/><circle cx="8" cy="7" r="2"/><circle cx="16" cy="17" r="2"/>',
    pin: '<path d="M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 1 1 14 0Z"/><circle cx="12" cy="10" r="2"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    activity: '<path d="M2 12h5l3-8 4 16 3-8h5"/>',
    list: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.1M3 12h.1M3 18h.1"/>',
    cards:
      '<rect x="3" y="4" width="7" height="7" rx="1"/><rect x="14" y="4" width="7" height="7" rx="1"/><rect x="3" y="15" width="7" height="5" rx="1"/><rect x="14" y="15" width="7" height="5" rx="1"/>',
    timeline:
      '<path d="M6 3v18M9 6h11M9 12h8M9 18h11"/><circle cx="6" cy="6" r="1.5"/><circle cx="6" cy="12" r="1.5"/><circle cx="6" cy="18" r="1.5"/>',
    play: '<path d="m8 5 11 7-11 7z"/>',
    pause: '<path d="M8 5v14M16 5v14"/>',
    download: '<path d="M12 3v12m-4-4 4 4 4-4M4 17v4h16v-4"/>',
    check: '<path d="m5 12 4 4L19 6"/>',
    checkall: '<path d="m2 12 4 4L16 6m-5 11 4 3 7-9"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/>',
    logout: '<path d="M9 4H4v16h5M10 12h11m-4-4 4 4-4 4"/>',
    inbox:
      '<path d="M4 4h16l2 11v5H2v-5L4 4Z"/><path d="M2 15h6l2 3h4l2-3h6"/>',
    archive: '<path d="M4 8h16v13H4zM3 3h18v5H3zM9 12h6"/>',
    sources:
      '<rect x="3" y="3" width="6" height="6" rx="1"/><rect x="15" y="3" width="6" height="6" rx="1"/><rect x="9" y="15" width="6" height="6" rx="1"/><path d="M6 9v3h12V9M12 12v3"/>',
    settings:
      '<path d="M9 3h6l1 3 3 1 2 5-2 5-3 1-1 3H9l-1-3-3-1-2-5 2-5 3-1 1-3Z"/><circle cx="12" cy="12" r="3"/>',
    plus: '<path d="M12 4v16M4 12h16"/>',
    edit: '<path d="m16 3 5 5-12 12-6 1 1-6L16 3Z"/><path d="m13 6 5 5"/>',
    trash: '<path d="M3 6h18M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7M14 10v7"/>',
    undo: '<path d="M9 4 3 10l6 6M4 10h9a7 7 0 0 1 7 7v3"/>',
    image:
      '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8" cy="8" r="1.5"/><path d="m4 18 5-5 4 4 4-7 4 6"/>',
    read: '<path d="M3 5h7l2 2 2-2h7v15h-7l-2 1-2-1H3zM12 7v14"/>',
    unread: '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="2"/>',
    menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
    lock: '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V6a4 4 0 0 1 8 0v4M12 14v3"/>',
    warning: '<path d="m12 3 10 18H2L12 3Z"/><path d="M12 9v5M12 17h.01"/>',
  };
function te(t, a = "") {
  return `<svg class="icon ${a}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${Xn[t] || Xn.info}</svg>`;
}
function e(t, a, o) {
  const l = document.createElement(t);
  return (a && (l.className = a), o != null && (l.textContent = String(o)), l);
}
function ue(t, a) {
  const o = i(t);
  o && (o.textContent = String(a));
}
function q(t, a, o, l) {
  const c = e("button", a);
  return (
    (c.type = "button"),
    o && (c.innerHTML = te(o)),
    c.append(e("span", "", t)),
    l && (c.onclick = l),
    c
  );
}
function Va(t) {
  ue("#announcer", t);
}
let Sn;
function $e(t, a, o) {
  let l = i("#toast");
  l ||
    ((l = e("div", "toast")),
    (l.id = "toast"),
    l.setAttribute("role", "status"),
    l.setAttribute("aria-live", "polite"),
    (l.hidden = !0),
    document.body.append(l));
  const f = i("#radar-pane:not([hidden])") && i(".main-shell .page-header");
  (f
    ? (l.previousElementSibling !== f && f.after(l),
      l.classList?.add("toast-inflow"))
    : (l.parentElement !== document.body && document.body.append(l),
      l.classList?.remove("toast-inflow")),
    clearTimeout(Sn));
  const m = document.activeElement,
    s = () => {
      ((l.hidden = !0),
        clearTimeout(Sn),
        l.contains?.(document.activeElement) &&
          m?.isConnected &&
          m !== document.body &&
          typeof m.focus == "function" &&
          m.focus({ preventScroll: !0 }));
    };
  if ((l.replaceChildren(e("span", "", t)), a && o)) {
    const h = q(a, "toast-action", null, () => {
      (s(), o());
    });
    l.append(h);
  }
  const g = q("", "toast-close", "close", s);
  (g.setAttribute("aria-label", "关闭通知"),
    l.append(g),
    (l.hidden = !1),
    (Sn = setTimeout(s, o ? 1e4 : 6e3)));
}
function it(t, a, o = null, l = "inbox") {
  const c = e("div", "empty-state"),
    f = e("span", "empty-icon");
  return (
    (f.innerHTML = te(l)),
    c.append(f, e("h3", "", t), e("p", "", a)),
    o && c.append(q(o.label, "button secondary", null, o.run)),
    c
  );
}
const mn = new WeakMap();
let Ba = 0,
  Kn = !1;
function Et(t) {
  if (
    !(t instanceof HTMLElement) ||
    !t.isConnected ||
    t.closest("[hidden], [inert]") ||
    !t.getClientRects().length
  )
    return !1;
  const a = getComputedStyle(t);
  if (
    a.visibility === "hidden" ||
    a.visibility === "collapse" ||
    a.display === "none"
  )
    return !1;
  for (
    let o = t.closest("details:not([open])");
    o;
    o = o.parentElement?.closest("details:not([open])")
  )
    if (![...o.children].find((c) => c.tagName === "SUMMARY")?.contains(t))
      return !1;
  return !0;
}
function za(t) {
  if (
    t.key !== "Tab" ||
    t.defaultPrevented ||
    t.altKey ||
    t.ctrlKey ||
    t.metaKey
  )
    return;
  const a = Ne("dialog[open]").reduce(
    (m, s) => (!m || (mn.get(s) || 0) >= (mn.get(m) || 0) ? s : m),
    null,
  );
  if (!a) return;
  const o = Ne(
      'a[href], button, input, select, textarea, summary, [tabindex], [contenteditable="true"]',
      a,
    ).filter(
      (m) =>
        !m.matches(":disabled") &&
        (!m.hasAttribute("tabindex") || m.tabIndex >= 0) &&
        Et(m),
    ),
    l = o[0],
    c = o.at(-1),
    f = document.activeElement;
  if (!l) {
    (t.preventDefault(), (a.tabIndex = -1), a.focus());
    return;
  }
  (!a.contains(f) || f === a || (t.shiftKey ? f === l : f === c)) &&
    (t.preventDefault(), (t.shiftKey ? c : l).focus());
}
function ct(t, { onClose: a } = {}) {
  (Kn || (document.addEventListener("keydown", za), (Kn = !0)),
    t.querySelectorAll("[data-close]").forEach((o) => {
      o.onclick = () => t.close();
    }),
    t.addEventListener("click", (o) => {
      if (o.target !== t) return;
      const l = t.getBoundingClientRect();
      (o.clientX < l.left ||
        o.clientX > l.right ||
        o.clientY < l.top ||
        o.clientY > l.bottom) &&
        t.close();
    }),
    t.addEventListener("close", () => mn.delete(t)),
    a && t.addEventListener("close", a));
}
function ut(t) {
  t.open || (t.showModal(), mn.set(t, ++Ba));
}
function Pt(t, a, o = "", l = !1) {
  const c = e("div", `media-frame ${o}`),
    f = e("img");
  return (
    (f.src = t.thumbnail_url || t.url),
    (f.alt = a || "来源附图"),
    (f.loading = l ? "eager" : "lazy"),
    (f.decoding = "async"),
    (f.referrerPolicy = "no-referrer"),
    f.addEventListener(
      "error",
      () => {
        (c.classList.add("media-failed"),
          c.replaceChildren(e("span", "media-failure-label", "图片暂不可用")));
      },
      { once: !0 },
    ),
    c.append(f),
    c
  );
}
const Ha = { telegram: "Telegram", x: "X", twitter: "X", youtube: "YouTube" },
  ja = {
    ai: "人工智能",
    artificial_intelligence: "人工智能",
    technology: "科技",
    tech: "科技",
    science: "科学",
    space: "太空",
    aerospace: "航天",
    business: "商业",
    finance: "金融",
    geopolitics: "全球动态",
    politics: "政经",
    energy: "能源",
    climate: "气候",
    health: "生命科学",
    biotech: "生物科技",
    biotechnology: "生物科技",
    robotics: "机器人",
    chips: "芯片",
    semiconductors: "半导体",
    security: "安全",
    other: "其他",
    general: "综合",
  },
  nn = (t) => ja[String(t || "").toLowerCase()] || t || "待分类",
  Ke = (t) => Ha[String(t || "").toLowerCase()] || t || "来源",
  an = (t, a, o) => Math.max(a, Math.min(o, Number(t) || 0)),
  Lt = (t) => Math.round(an(t?.importance, 0, 100)),
  kt = (t) => {
    if (!t) return null;
    const a = new Date(t);
    return Number.isFinite(a.getTime()) ? a : null;
  },
  ua = new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }),
  Wa = new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: !1,
  }),
  Ga = new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    hour: "2-digit",
    minute: "2-digit",
    hour12: !1,
  }),
  Ya = new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: !1,
  }),
  Ja = new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    month: "2-digit",
    day: "2-digit",
  }),
  Ve = (t, a = !1) => {
    const o = kt(t);
    return o ? (a ? Wa : ua).format(o) : "尚未确认";
  };
function Qn(t, a) {
  if (
    typeof t != "string" ||
    !/^\d{4}-\d{2}-\d{2}$/.test(t) ||
    !(a instanceof Date) ||
    !Number.isFinite(a.getTime())
  )
    return null;
  const o = new Date(t + "T00:00:00Z"),
    l = new Date(a.toISOString().slice(0, 10) + "T00:00:00Z");
  return Number.isFinite(o.getTime()) &&
    o.toISOString().slice(0, 10) === t &&
    Math.abs(o - l) <= 864e5
    ? t
    : null;
}
function rn(t, a = !1) {
  const o = kt(t?.event_time_start);
  if (
    !o ||
    t?.event_time_precision === "unknown" ||
    t?.event_time_status === "unknown"
  )
    return "事件时间待确认";
  const l =
      t.event_time_status === "scheduled"
        ? "预计 "
        : t.event_time_status === "inferred"
          ? "推定 "
          : "",
    c = kt(t.event_time_end),
    f = c && c > o ? c : null;
  if (t.event_time_precision === "exact") {
    const h = on(o),
      k = f && on(f),
      Y = a && (!k || h.slice(0, 4) === k.slice(0, 4)) ? Ja : ua,
      G = o.getUTCSeconds() || f?.getUTCSeconds() ? Ya : Ga,
      pe = `${Y.format(o)} ${G.format(o)}`,
      L = f && `${k === h ? "" : `${Y.format(f)} `}${G.format(f)}`;
    return l + pe + (L ? ` — ${L}` : "");
  }
  if (!["month", "day", "range"].includes(t.event_time_precision))
    return "事件时间待确认";
  const m = Qn(t?.event_civil_start, o),
    s = f && Qn(t?.event_civil_end, f);
  if (
    !m ||
    (f && !s) ||
    (!f && t?.event_civil_end != null) ||
    (s && s < m) ||
    (t.event_time_precision === "range" && !s)
  )
    return "事件时间待确认";
  if (t.event_time_precision === "month") {
    const h = (G) => `${G.slice(0, 4)}年${Number(G.slice(5, 7))}月`,
      k = h(m),
      Y = s && h(s);
    return l + k + (Y && Y !== k ? ` — ${Y}` : "");
  }
  const g = (h) => h.replaceAll("-", "/");
  return l + g(m) + (s && s !== m ? ` — ${g(s)}` : "");
}
function Ft(t) {
  return t?.event_time_status !== "unknown" &&
    t?.event_time_precision !== "unknown"
    ? kt(t?.event_time_start)
    : null;
}
function Kt(t) {
  return t?.location_status === "unknown" || t?.location_status === "global"
    ? []
    : (Array.isArray(t?.locations) ? t.locations : []).filter(
        (a) =>
          typeof a.latitude == "number" &&
          typeof a.longitude == "number" &&
          Number.isFinite(a.latitude) &&
          Number.isFinite(a.longitude) &&
          Math.abs(a.latitude) <= 90 &&
          Math.abs(a.longitude) <= 180 &&
          a.status !== "unknown",
      );
}
function En(t) {
  const a = Kt(t);
  return a.length
    ? [...new Set(a.map((o) => o.name || o.country_code || "已定位"))].join(
        " · ",
      )
    : t?.location_status === "global"
      ? "全球性事件"
      : "地点待确认";
}
function Fn(t) {
  try {
    const a = new URL(String(t));
    return ["https:", "http:"].includes(a.protocol) ? a.href : null;
  } catch {
    return null;
  }
}
function Za(t) {
  return Array.isArray(t)
    ? t
        .map((a) =>
          typeof a == "string"
            ? { value: a, count: null }
            : {
                value: String(a.value ?? a.name ?? ""),
                count: Number.isFinite(a.count) ? a.count : null,
              },
        )
        .filter((a) => a.value)
    : t && typeof t == "object"
      ? Object.entries(t).map(([a, o]) => ({ value: a, count: o }))
      : [];
}
function Nn(t, a = 0) {
  const o = new URLSearchParams({
    sort: t.sort || "importance",
    limit: "100",
    offset: String(a),
  });
  for (const l of [
    "q",
    "source",
    "source_id",
    "category",
    "read",
    "scope",
    "min_importance",
  ])
    t[l] && o.set(l, t[l]);
  if (
    (t.window_days != null &&
      t.window_days !== "" &&
      o.set("window_days", String(t.window_days)),
    t.bookmarked && o.set("bookmarked", "1"),
    t.after &&
      o.set("after", new Date(`${t.after}T00:00:00+08:00`).toISOString()),
    t.before)
  ) {
    const l = new Date(`${t.before}T00:00:00+08:00`);
    (l.setUTCDate(l.getUTCDate() + 1), o.set("before", l.toISOString()));
  }
  return o;
}
const Qt = (t) =>
  ({
    healthy: "运行正常",
    running: "运行中",
    idle: "待机",
    partial: "部分可用",
    degraded: "需要关注",
    checking: "检查中",
    offline: "离线",
    disabled: "未启用",
    error: "异常",
    unavailable: "暂不可用",
    pending: "等待处理",
    ready: "已就绪",
    daily_limit: "今日整理额度已用完",
    budget_pacing: "整理额度按日内时间分配，下一批待释放",
    rate_limited: "请求较多，等待重试",
    paused: "已暂停",
  })[t] ||
  t ||
  "待检查";
function hn(t) {
  const a = kt(t);
  if (!a) return "尚无成功记录";
  const o = Math.max(0, Math.floor((Date.now() - a.getTime()) / 6e4));
  return o < 1
    ? "刚刚"
    : o < 60
      ? `${o} 分钟前`
      : o < 1440
        ? `${Math.floor(o / 60)} 小时前`
        : `${Math.floor(o / 1440)} 天前`;
}
function Xa(t, a) {
  return a == null
    ? t
    : t.filter((o) => {
        const l = Ft(o);
        return l && l.getTime() <= a;
      });
}
const wt = Object.freeze({
  hide_read: !1,
  retention_days: 7,
  retention_mode: "archive",
  retention_basis: "first_ingested",
  retain_bookmarks: !0,
  auto_mark_read: !0,
  show_images: !0,
  default_sort: "importance",
  default_view: "globe",
  default_section: "feed",
  density: "comfortable",
});
function Ka(t, a, o) {
  return Object.prototype.hasOwnProperty.call(o, t)
    ? t
    : a === "radar"
      ? "radar"
      : "feed";
}
const pa = { globe: "地理", list: "列表", cards: "卡片", timeline: "时间线" };
function ea(t) {
  if (
    typeof t != "string" ||
    !t.startsWith("/api/media/") ||
    t.startsWith("//") ||
    /[\\\u0000-\u0020]/.test(t)
  )
    return null;
  try {
    const a = new URL(t, "https://frontier.local");
    return a.origin === "https://frontier.local" &&
      a.pathname.startsWith("/api/media/")
      ? a.pathname + a.search
      : null;
  } catch {
    return null;
  }
}
function sn(t) {
  const a = [];
  for (const o of [
    ...(Array.isArray(t?.media) ? t.media : []),
    ...(Array.isArray(t?.images) ? t.images : []),
  ]) {
    const l = typeof o == "string" ? { url: o } : o || {},
      c = ea(l.url || l.src || l.path);
    !c ||
      a.some((f) => f.url === c) ||
      a.push({ ...l, url: c, thumbnail_url: ea(l.thumbnail_url) || c });
  }
  return a;
}
function bn(t, a = "first_ingested") {
  return Number(t) === 0
    ? "不限阅读窗口"
    : `${a === "published" ? "原始发布" : "首次收录"}后保留 ${Number(t) || 7} 天`;
}
function on(t) {
  const a = kt(t);
  return a
    ? new Intl.DateTimeFormat("en-CA", {
        timeZone: "Asia/Shanghai",
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
      }).format(a)
    : null;
}
function ta(t) {
  const a = new Map(),
    o = [];
  for (const l of t) {
    const c = Ft(l);
    if (!c) {
      o.push(l);
      continue;
    }
    const f = l.event_time_precision === "month" ? on(c).slice(0, 7) : on(c);
    (a.has(f) || a.set(f, []), a.get(f).push(l));
  }
  return {
    known: [...a.entries()]
      .sort(([l], [c]) => c.localeCompare(l))
      .map(([l, c]) => ({
        date: l,
        events: c.sort((f, m) => Ft(m) - Ft(f) || Lt(m) - Lt(f)),
      })),
    unknown: o,
  };
}
function Me(t) {
  return typeof t?.read == "boolean" ? t.read : !!t?.read_at;
}
function gn(t, a) {
  return t.read || (t.bookmarked ? "all" : a.hide_read ? "unread" : "all");
}
function Qa(t, a, o) {
  const l = gn(a, o);
  return !(
    (l === "read" && !Me(t)) ||
    (l === "unread" && Me(t)) ||
    (a.bookmarked && !t.bookmarked)
  );
}
function er({ api: t, onSaved: a, onLoaded: o, onArchive: l }) {
  let c = { settings: { ...wt }, version: 1 },
    f = null,
    m = !1,
    s = !1;
  function g() {
    return {
      hide_read: i("#setting-hide-read").checked,
      auto_mark_read: i("#setting-auto-mark-read").checked,
      retention_days: Number(i("#setting-retention-days").value),
      retention_basis: i("#setting-retention-basis").value,
      retain_bookmarks: i("#setting-retain-bookmarks").checked,
      show_images: i("#setting-show-images").checked,
      default_sort: i("#setting-default-sort").value,
      default_view: i("#setting-default-view").value,
      default_section: i("#setting-default-section").value,
      density: i("#setting-density").value,
    };
  }
  function h() {
    const L = c.settings;
    for (const B of [
      "hide_read",
      "auto_mark_read",
      "show_images",
      "retain_bookmarks",
    ])
      i(`#setting-${B.replaceAll("_", "-")}`).checked = !!L[B];
    for (const B of [
      "retention_days",
      "retention_basis",
      "default_sort",
      "default_view",
      "default_section",
      "density",
    ])
      i(`#setting-${B.replaceAll("_", "-")}`).value = String(L[B]);
    k();
  }
  function k() {
    if (!i("#settings-form")) return;
    const L = g();
    (ue("#settings-preview-window", bn(L.retention_days, L.retention_basis)),
      ue(
        "#settings-preview-read",
        L.hide_read
          ? "已读资讯从资讯工作区隐藏；可切换「已读」找回"
          : "已读资讯继续显示，以已读状态区分",
      ),
      ue(
        "#settings-preview-auto",
        L.auto_mark_read ? "实际打开详情后标为已读" : "由你手动标记已读",
      ),
      ue(
        "#settings-save-state",
        f
          ? "其他客户端已更新；你的草稿仍保留"
          : m
            ? "有未保存的更改"
            : "设置已与服务器同步",
      ),
      ue("#settings-preview-label", m ? "未保存规则预览" : "已保存阅读规则"),
      (i("#settings-remote-update").hidden = !f),
      (i("#settings-form").dataset.version = String(c.version)),
      (i("#settings-form").dataset.remoteVersion = f ? String(f.version) : ""),
      (i("#settings-save").disabled = !m || s));
  }
  function Y(L) {
    ((L.innerHTML = `
      <div class="settings-layout">
        <form id="settings-form" class="settings-form">
          <div id="settings-remote-update" class="settings-conflict" role="status" hidden><span>设置已在其他客户端更新。你的未保存内容保留，保存时会核对版本。</span><button id="settings-read-latest" type="button" class="text-button">放弃草稿并读取最新设置</button></div>
          <section class="settings-section"><div class="section-heading"><h2>阅读行为</h2><p>设置保存在服务器，浏览器和 Mac App 共用。</p></div>
            <label class="setting-row"><span><strong>打开详情后标为已读</strong><small>只有实际打开一条资讯才标记，浏览列表不会改变阅读状态。</small></span><input id="setting-auto-mark-read" type="checkbox" role="switch"/></label>
            <label class="setting-row"><span><strong>自动隐藏已读资讯</strong><small>从资讯和地理视图中隐藏已读内容，正在阅读的详情保持打开。</small></span><input id="setting-hide-read" type="checkbox" role="switch"/></label>
          </section>
          <section class="settings-section"><div class="section-heading"><h2>资讯保留与归档</h2><p>按你选择的时间基准，自动管理服务器上的活动阅读窗口。</p></div>
            <label class="setting-field" for="setting-retention-basis"><span><strong>保留时间基准</strong><small>来源发布时间缺失时，按首次收录时间计算。</small></span><select id="setting-retention-basis"><option value="first_ingested">首次收录后保留</option><option value="published">原始发布后保留</option></select></label>
            <label class="setting-field" for="setting-retention-days"><span><strong>资讯工作区保留天数</strong><small>例如 2 天：按所选基准保留最近 48 小时的内容。</small></span><div class="number-field"><input id="setting-retention-days" type="number" min="0" max="3650" step="1" required/><span>天</span></div></label>
            <p class="field-help">可设置 1–3650 天；输入 0 保留全部。时间窗口在服务器持续生效，不依赖当前浏览器。</p>
            <div class="setting-explanation">${te("archive")}<div><strong>到期自动归档，可以找回</strong><p>超期资讯移入「归档」，原文、图片与阅读状态保留。延长窗口后，相应资讯会重新进入工作区。此设置不会永久删除内容。</p><button type="button" id="settings-open-archive" class="text-button">打开归档 ${te("arrow")}</button></div></div>
            <label class="setting-row"><span><strong>收藏不受保留窗口限制</strong><small>开启后收藏始终留在活动窗口；关闭后也可从全部时间或归档中找回收藏。</small></span><input id="setting-retain-bookmarks" type="checkbox" role="switch"/></label>
          </section>
          <section class="settings-section"><div class="section-heading"><h2>显示与默认入口</h2><p>选择下次进入的页面，以及资讯工作台内的布局。</p></div>
            <label class="setting-field" for="setting-default-section"><span><strong>下次默认直接进入</strong><small>保存后下次打开首页（网址不含 ?section）时生效；指定页面的链接和手动导航不受影响。浏览器与 Mac App 共用。</small></span><select id="setting-default-section"><option value="feed">资讯工作台（保持原默认）</option><option value="radar">情报雷达</option></select></label>
            <label class="setting-row"><span><strong>显示资讯图片</strong><small>显示来源原始附图和视频封面；关闭后采用紧凑文字布局。</small></span><input id="setting-show-images" type="checkbox" role="switch"/></label>
            <label class="setting-field" for="setting-default-view"><span><strong>资讯工作台默认视图</strong></span><select id="setting-default-view"><option value="globe">地理 · 地球与资讯联动</option><option value="list">列表 · 快速阅读</option><option value="cards">卡片 · 图片优先</option><option value="timeline">时间线 · 事件发生顺序</option></select></label>
            <label class="setting-field" for="setting-default-sort"><span><strong>默认排序</strong></span><select id="setting-default-sort"><option value="importance">重要度优先</option><option value="event_time">事件发生时间</option><option value="discovered">最近收录</option></select></label>
            <label class="setting-field" for="setting-density"><span><strong>资讯密度</strong></span><select id="setting-density"><option value="comfortable">标准</option><option value="compact">紧凑</option></select></label><p class="field-help">标准密度在列表、卡片和时间线显示摘要；地理视图优先展示标题与来源，完整摘要可打开详情阅读。紧凑密度收起摘要并缩小行间距。</p>
          </section>
          <div class="settings-save-bar"><span id="settings-save-state" role="status"></span><button id="settings-reset" type="button" class="button secondary">撤销更改</button><button id="settings-save" class="button primary" type="submit">保存设置</button></div>
          <div id="settings-error" class="form-error" role="alert" hidden></div>
        </form>
        <aside class="settings-summary"><span id="settings-preview-label" class="section-kicker">已保存阅读规则</span><h3 id="settings-preview-window"></h3><p id="settings-preview-auto"></p><p id="settings-preview-read"></p><hr/><h4>两种时间，各司其职</h4><p>保留窗口按你选择的首次收录或原始发布时间计算。时间线与日期筛选使用事件发生时间，未确认的事件不会用发布时间替代。</p><h4>阅读状态可以恢复</h4><p>在资讯顶部切换「已读」，或在详情中标为未读。取消自动隐藏后，已读内容会重新显示。</p><h4>收藏独立保留</h4><p>收藏标记始终保留。是否豁免活动阅读窗口，使用左侧开关设置；超期内容可在全部时间或归档中找回。</p></aside>
      </div>`),
      h(),
      i("#settings-form").addEventListener("input", () => {
        ((m = !0), k());
      }),
      (i("#settings-reset").onclick = () => {
        ((m = !1),
          f && (c = f),
          (f = null),
          h(),
          (i("#settings-error").hidden = !0));
      }),
      (i("#settings-read-latest").onclick = () => {
        ((m = !1), (f = null), G(L));
      }),
      (i("#settings-open-archive").onclick = l),
      (i("#settings-form").onsubmit = async (B) => {
        if ((B.preventDefault(), s || !m)) return;
        const O = g(),
          de = i("#settings-error");
        if (
          ((de.hidden = !0),
          !Number.isInteger(O.retention_days) ||
            O.retention_days < 0 ||
            O.retention_days > 3650)
        ) {
          ((de.textContent = "保留天数须为 0–3650 的整数。"),
            (de.hidden = !1),
            i("#setting-retention-days").focus());
          return;
        }
        ((s = !0), k(), ue("#settings-save", "正在保存…"));
        try {
          ((c = await t("/api/settings", {
            method: "PUT",
            body: JSON.stringify({ settings: O, version: c.version }),
          })),
            (c.settings = { ...wt, ...c.settings }),
            (m = !1),
            (f = null),
            h(),
            a(c),
            $e("阅读与显示设置已保存"));
        } catch (ce) {
          (de.replaceChildren(
            e(
              "span",
              "",
              ce.status === 409
                ? "设置已在其他窗口更新。你输入的内容仍保留，请先重新读取最新设置。"
                : ce.message,
            ),
          ),
            ce.status === 409 &&
              de.append(
                q(
                  "放弃草稿并读取最新设置",
                  "text-button",
                  "refresh",
                  async () => {
                    ((m = !1), (f = null), await G(L));
                  },
                ),
              ),
            (de.hidden = !1));
        } finally {
          ((s = !1),
            i("#settings-save") && (ue("#settings-save", "保存设置"), k()));
        }
      }));
  }
  async function G(L) {
    if (!(m && i("#settings-form"))) {
      L.replaceChildren(e("p", "panel-loading", "正在读取阅读与显示设置…"));
      try {
        ((c = await t("/api/settings")),
          (c.settings = { ...wt, ...c.settings }),
          (m = !1),
          (f = null),
          Y(L),
          o?.(c));
      } catch (B) {
        B.status !== 401 &&
          L.replaceChildren(
            it(
              "设置暂不可用",
              B.message,
              { label: "重试", run: () => G(L) },
              "settings",
            ),
          );
      }
    }
  }
  function pe(L) {
    if (!L?.settings || !Number.isInteger(L.version)) return;
    const B = { settings: { ...wt, ...L.settings }, version: L.version };
    if (i("#settings-form") && (m || s)) {
      (B.version !== c.version && (f = B), k());
      return;
    }
    ((c = B), (m = !1), (f = null), i("#settings-form") && h());
  }
  return { load: G, setCurrent: pe, observe: pe, isDirty: () => m };
}
const na = {
  healthy: "正常",
  error: "异常 / 部分失败",
  rate_limited: "限流",
  auth_required: "人工介入",
  checking: "未覆盖 · 待检查",
  offline: "未覆盖 · 状态过期",
  pending: "未覆盖 · 待应用",
};
function Ln(t, a = null) {
  if (!t?.enabled || t.deleted_at) return "other";
  const o = t.status || {},
    l = o.state;
  if (!l || ["checking", "offline", "pending"].includes(l)) return "unknown";
  const c = Number.isInteger(o.consecutive_failures)
    ? o.consecutive_failures
    : o.failures;
  if (
    ["error", "rate_limited", "auth_required"].includes(l) &&
    ((Number.isInteger(c) && c >= 3) || o.pause_suggestion)
  )
    return "attention";
  if (
    l === "healthy" &&
    t.counts?.raw_7d === 0 &&
    o.last_success_at &&
    !o.last_success_partial
  ) {
    const f = Date.parse(a || ""),
      m = Date.parse(o.last_success_at);
    if (Number.isNaN(f) || (Number.isFinite(m) && m >= f)) return "quiet";
  }
  return "other";
}
function tr(t, a, o = null) {
  return a === "deleted"
    ? !!t.deleted_at
    : t.deleted_at
      ? !1
      : a === "disabled"
        ? !t.enabled
        : a === "current"
          ? !0
          : t.enabled
            ? ["attention", "quiet", "unknown"].includes(a)
              ? Ln(t, o) === a
              : a === "uncovered"
                ? Ln(t, o) === "unknown"
                : a === "zero_output"
                  ? t.counts?.raw_7d === 0
                  : a === "unobserved"
                    ? t.counts != null &&
                      "last_raw_at" in t.counts &&
                      !t.counts.last_raw_at
                    : a === "suggested"
                      ? !!t.status?.pause_suggestion
                      : t.status?.state === a
            : !1;
}
function nr(t) {
  return !t.last_success_at || t.last_new_items == null
    ? "最近成功检查的新增内容：未知"
    : t.last_success_partial || t.error_class === "partial"
      ? `最近部分完成检查：入库新增 ${y(t.last_new_items)} 条，存在采集缺口`
      : t.last_new_items === 0
        ? "最近成功检查：无新资讯"
        : `最近成功检查：新增 ${y(t.last_new_items)} 条`;
}
function ar({ api: t, onView: a }) {
  let o = null,
    l = 0,
    c = [],
    f = null,
    m = null,
    s = "",
    g = "",
    h = "current",
    k = 50,
    Y = null,
    G = !1,
    pe = "",
    L = null;
  const B = (A) =>
      (!s || A.platform === s) &&
      (!g ||
        `${A.name || ""} ${A.locator || ""} ${A.platform}`
          .toLowerCase()
          .includes(g.toLowerCase())),
    O = (A) => Ln(A, f?.output?.window_start_utc);
  function de() {
    const A = c.filter((_) => B(_) && tr(_, h, f?.output?.window_start_utc));
    if (h === "current" || h === "attention") {
      const _ = { attention: 0, quiet: 1, unknown: 2, other: 3 };
      A.sort(
        (P, C) =>
          _[O(P)] - _[O(C)] ||
          (O(P) === "attention"
            ? (C.status?.consecutive_failures || 0) -
              (P.status?.consecutive_failures || 0)
            : 0),
      );
    }
    return A;
  }
  function ce(A) {
    pe = A;
    const _ = i("#source-action-feedback");
    _ && ((_.textContent = A), (_.hidden = !A));
  }
  function _e() {
    const A = L ?? (typeof window > "u" || window.innerWidth > 760);
    ((m.innerHTML = `
      <div class="sources-intro"><div><h2>你的资讯来源</h2><p>管理 Telegram、X 和 YouTube 订阅。修改后由服务器持续采集。</p></div><button id="source-add" class="button primary">${te("plus")}<span>添加来源</span></button></div>
      <div class="source-summary" id="source-summary"></div>
      <section class="source-priority" id="source-priority" aria-label="来源行动优先级"></section>
      <details class="source-platform-details" id="source-platform-details" ${A ? "open" : ""}><summary>按平台查看采集状态与近7日原始入库（可展开）</summary><div class="source-health-summary" id="source-health-summary"></div></details>
      <div class="source-sync" id="source-sync" role="status"></div>
      <div class="source-action-feedback" id="source-action-feedback" role="status" hidden></div>
      <div class="source-toolbar"><label class="search-field source-search">${te("search")}<input id="source-search" type="search" placeholder="搜索账号、频道或名称" aria-label="搜索订阅来源" maxlength="200"/></label><label class="select-field"><span class="sr-only">来源平台</span><select id="sources-platform-filter"><option value="">全部平台</option><option value="telegram">Telegram</option><option value="x">X</option><option value="youtube">YouTube</option></select></label><label class="select-field"><span class="sr-only">来源状态</span><select id="sources-state-filter"><option value="current">当前来源（行动优先）</option><option value="attention">人工核查 · 持续失败/明确提示</option><option value="quiet">成功检查 · 7日零入库</option><option value="unknown">尚未检查 / 轮询状态未知</option><option value="healthy">正常</option><option value="error">异常 / 部分失败</option><option value="rate_limited">限流</option><option value="auth_required">人工介入</option><option value="uncovered">轮询状态未知</option><option value="zero_output">零入库（启用）</option><option value="unobserved">原文未观测（启用）</option><option value="checking">未覆盖 · 待检查</option><option value="offline">未覆盖 · 状态过期</option><option value="pending">未覆盖 · 待应用</option><option value="suggested">建议暂停</option><option value="disabled">已停用</option><option value="deleted">已移除 · 可恢复</option></select></label><button id="source-refresh" class="button secondary">${te("refresh")}<span>刷新状态</span></button></div>
      <div class="sources-table" role="table" aria-label="资讯订阅来源"><div class="sources-table-head" role="row"><span role="columnheader">来源</span><span role="columnheader">采集状态</span><span role="columnheader">原始入库 / 来源贡献</span><span role="columnheader">操作</span></div><div id="source-list" role="rowgroup"></div></div>
      <div class="source-list-footer"><span id="source-list-count"></span><button id="sources-more" class="text-button" hidden>显示更多</button></div>
      <p class="source-footnote">停用会保留订阅配置；移除后可从「已移除」恢复。已有资讯、图片、收藏与阅读记录继续保留。</p>`),
      (i("#source-platform-details").ontoggle = (_) => {
        L = _.target.open;
      }),
      (i("#source-add").onclick = () => fe()),
      (i("#source-refresh").onclick = () => re(m, !0)),
      (i("#source-search").value = g),
      (i("#sources-platform-filter").value = s),
      (i("#sources-state-filter").value = h),
      (i("#source-search").oninput = (_) => {
        ((g = _.target.value.trim()), (k = 50), ae());
      }),
      (i("#sources-platform-filter").onchange = (_) => {
        ((s = _.target.value), (k = 50), ae());
      }),
      (i("#sources-state-filter").onchange = (_) => {
        ((h = _.target.value), (k = 50), ae());
      }),
      (i("#sources-more").onclick = () => {
        ((k += 50), ae());
      }));
  }
  function R() {
    const A = i("#source-priority");
    if (!A) return;
    const _ = c.filter((Q) => !Q.deleted_at && B(Q)),
      P = _.filter((Q) => Q.enabled),
      C = { attention: 0, quiet: 0, unknown: 0 };
    for (const Q of P) O(Q) in C && C[O(Q)]++;
    const F = P.length - C.attention - C.quiet - C.unknown;
    A.replaceChildren();
    const I = e("div", "source-priority-heading");
    I.append(
      e("h3", "", "先处理需要判断的来源"),
      e(
        "p",
        "",
        `当前平台/搜索范围：启用 ${y(P.length)} / 未移除 ${y(_.length)}。各行动类别互斥；不以零入库推断失败。`,
      ),
    );
    const W = e("div", "source-priority-nav");
    (W.setAttribute("role", "group"),
      W.setAttribute("aria-label", "来源行动筛选"));
    for (const [Q, he, X] of [
      ["attention", "人工核查 · 持续失败/明确提示", C.attention],
      ["quiet", "检查正常 · 7日零入库", C.quiet],
      ["unknown", "轮询尚未覆盖 / 状态未知", C.unknown],
      ["current", "全部当前（含停用）", _.length],
    ]) {
      const H = e(
        "button",
        `source-priority-button priority-${Q}${h === Q ? " is-active" : ""}`,
      );
      ((H.type = "button"),
        (H.dataset.mode = Q),
        H.setAttribute("aria-pressed", String(h === Q)),
        H.setAttribute(
          "aria-label",
          `${he}：${y(X)}${Q === "current" ? " 个当前来源" : ` / ${y(P.length)} 个启用来源`}`,
        ),
        H.append(
          e("span", "source-priority-name", he),
          e(
            "strong",
            "source-priority-count",
            Q === "current" ? y(X) : `${y(X)} / ${y(P.length)}`,
          ),
        ),
        (H.onclick = () => {
          ((h = Q),
            (k = 50),
            (i("#sources-state-filter").value = h),
            ae(),
            Ne(".source-priority-button")
              .find((ie) => ie.dataset.mode === Q)
              ?.focus?.());
        }),
        W.append(H));
    }
    A.append(
      I,
      W,
      e(
        "p",
        "source-priority-note",
        `其余启用 ${y(F)} 个（含有入库或暂未达到人工核查阈值）仍可在「全部当前」查看；已停用 ${y(_.length - P.length)} 个可从状态筛选找回。人工核查仅依据连续失败至少 3 次或采集器明确提示；成功检查和近7日零入库必须同时成立才进入正常零入库组。未覆盖可能仍有真实入库。`,
      ),
    );
  }
  function ne() {
    const A = i("#source-summary");
    A.replaceChildren();
    const _ = i("#source-health-summary");
    _.replaceChildren();
    for (const X of ["telegram", "x", "youtube"]) {
      const H = f?.health?.platforms?.[X],
        ie = e("div", "source-health-card");
      if (
        (ie.append(
          e(
            "strong",
            "",
            `${Ke(X)} · 启用 ${y(H?.enabled)} / 配置 ${y(H?.total)}`,
          ),
        ),
        H)
      )
        for (const [le, Se] of Object.entries(na)) {
          const Ue = q(`${Se} ${y(H.states[le])}`, "text-button", null, () => {
            ((s = X),
              (h = le),
              (k = 50),
              (i("#sources-platform-filter").value = s),
              (i("#sources-state-filter").value = le),
              ae());
          });
          ie.append(Ue);
        }
      else ie.append(e("span", "", "健康分母未知，请刷新服务器版本"));
      const J = c
          .filter((le) => le.platform === X && le.enabled && !le.deleted_at)
          .filter((le) => Number.isInteger(le.counts?.raw_7d)),
        se = J.filter((le) => le.counts.raw_7d > 0),
        Te = se.filter((le) =>
          ["checking", "offline", "pending"].includes(le.status?.state),
        ),
        we = e("div", "source-platform-output");
      (we.append(
        e(
          "strong",
          "",
          `近7天原始记录入库 ${y(J.length ? J.reduce((le, Se) => le + Se.counts.raw_7d, 0) : null)} 条`,
        ),
        e(
          "span",
          "",
          `有入库来源 ${y(se.length)} / ${y(J.length)} · 轮询未知但有入库 ${y(Te.length)}`,
        ),
      ),
        ie.append(we),
        _.append(ie));
    }
    _.append(
      e(
        "p",
        "source-footnote",
        `轮询健康来自 collector-status，原始入库与事件贡献来自 SQLite，互不推断。近7天按 UTC 首次入库时间计算（${f?.output?.window_start_utc || "起点未知"} 起）；视频待转写条目只有元数据，不等于已获得正文。事件按形成时间去重，非独立核验；watch/research 为当前明确分诊关联的不同事件（跨主题同类去重，两类可能重叠），不是模型完成率。零入库与未观测筛选仅针对启用且未移除来源。轮询快照：${f?.health?.observed_at ? Ve(f.health.observed_at, !0) : "未知"}${f?.health?.fresh ? "" : "（过期或不可用）"}。`,
      ),
    );
    const P = c.filter((X) => !X.deleted_at),
      C = P.filter((X) => X.enabled),
      F = C.filter((X) => O(X) === "attention");
    for (const [X, H] of [
      ["当前订阅", P.length],
      ["已启用", C.length],
      ["已停用", P.length - C.length],
      ["人工核查", F.length],
    ]) {
      const ie = e("div");
      (ie.append(e("strong", "", y(H)), e("span", "", X)), A.append(ie));
    }
    const I = f?.sync || {},
      W = i("#source-sync"),
      Q =
        f?.revision != null &&
        f?.applied_revision != null &&
        f.revision > f.applied_revision;
    ((W.className = `source-sync${I.error ? " warning" : ""}`),
      W.replaceChildren());
    const he = e("span");
    ((he.innerHTML = te(I.error ? "warning" : Q ? "clock" : "check")),
      W.append(he),
      W.append(
        e(
          "span",
          "",
          I.error
            ? `配置已保存，采集器同步需要关注：${I.error}`
            : I.state === "offline"
              ? "采集器状态已过期或不可用；单源当前结果未知，历史检查记录仍保留。"
              : Q || I.state === "pending"
                ? "配置已保存，正在等待采集器应用。已保存不等于已开始采集。"
                : I.state === "applied" ||
                    I.state === "healthy" ||
                    f?.revision === f?.applied_revision
                  ? "订阅配置已同步到采集器。下次成功采集时间会在对应来源更新。"
                  : "服务器已保存来源配置，采集状态由实际采集结果更新。",
        ),
      ));
  }
  function ae() {
    const A = i("#source-list");
    if (!A) return;
    R();
    const _ = i("#source-action-feedback");
    _ && ((_.textContent = pe), (_.hidden = !pe));
    const P = de();
    (A.replaceChildren(),
      P.length ||
        A.append(
          it(
            h === "deleted"
              ? "没有已移除的来源"
              : h !== "current" || g || s
                ? "本组暂无匹配来源"
                : "还没有订阅来源",
            h === "deleted"
              ? "移除的订阅会出现在这里，之后可恢复。"
              : h !== "current" || g || s
                ? "可尝试其他行动类别、状态、平台或关键词；零入库本身不代表采集失败。"
                : "添加你关注的频道或账号，服务器会持续收录更新。",
            h === "current" && !g && !s
              ? { label: "添加来源", run: () => fe() }
              : null,
            "sources",
          ),
        ));
    for (const C of P.slice(0, k)) {
      const F = e("article", "source-row");
      ((F.dataset.id = C.id),
        (F.dataset.priority = O(C)),
        F.setAttribute("role", "row"));
      const I = e("div", "source-identity");
      I.setAttribute("role", "cell");
      const W = e(
          "span",
          `platform-mark ${C.platform}`,
          C.platform === "telegram"
            ? "T"
            : C.platform === "youtube"
              ? "Y"
              : "X",
        ),
        Q = e("div", "source-identity-copy");
      Q.append(e("strong", "", C.name || C.locator));
      const he = e("span", "", C.locator || C.url || "");
      Q.append(he);
      const X = e("small", "", Ke(C.platform));
      (Q.append(X), I.append(W, Q));
      const H = e("div", "source-status");
      H.setAttribute("role", "cell");
      const ie = C.status || {},
        qe = C.deleted_at
          ? "deleted"
          : C.enabled
            ? ie.state || "checking"
            : "disabled",
        J = C.deleted_at
          ? "已移除"
          : C.enabled
            ? ie.state
              ? na[ie.state] || Qt(ie.state)
              : "轮询状态未知"
            : "已停用",
        se = C.counts || {},
        Te = Number.isInteger(se.raw_7d) ? se.raw_7d : null;
      H.append(e("span", `state-badge ${qe}`, J));
      const we = O(C);
      if (
        (we === "attention"
          ? H.append(
              e(
                "p",
                "source-governance-note needs-attention",
                `人工核查：${ie.pause_suggestion ? "采集器已有明确提示" : `连续失败 ${y(ie.consecutive_failures ?? ie.failures)} 次`}；请先检查登录、地址或采集错误。`,
              ),
            )
          : we === "quiet"
            ? H.append(
                e(
                  "p",
                  "source-governance-note quiet",
                  "已有成功检查 · 近7日零入库，并非故障结论。",
                ),
              )
            : we === "unknown" &&
              H.append(
                e(
                  "p",
                  "source-governance-note unknown",
                  "尚无可靠轮询结论；待应用、未检查或状态过期均不视作采集失败。",
                ),
              ),
        Te > 0 &&
          we === "unknown" &&
          H.append(
            e(
              "p",
              "source-observation-note",
              `近7天入库 ${y(Te)} 条，轮询状态暂缺`,
            ),
          ),
        ie.last_error && C.enabled && !C.deleted_at)
      ) {
        const ze = e("p", "source-row-error", ie.last_error);
        ((ze.title = ie.last_error), H.append(ze));
      }
      (H.append(
        e(
          "small",
          "",
          `错误类别 ${ie.error_class || "—"} · 连续失败 ${y(ie.consecutive_failures)}`,
        ),
      ),
        H.append(e("small", "", nr(ie))));
      for (const [ze, Ee] of [
        ["成功检查", ie.last_success_at],
        ["失败检查", ie.last_failure_at],
        ["下次计划", ie.next_run_at],
      ])
        H.append(e("small", "", `${ze}：${Ee ? Ve(Ee, !0) : "未知"}`));
      (H.append(
        e("small", "muted", `轮询间隔 ${y(C.poll_seconds)} 秒（并非入库频率）`),
      ),
        ie.pause_suggestion &&
          C.enabled &&
          !C.deleted_at &&
          H.append(e("p", "source-pause-suggestion", ie.pause_suggestion)));
      const le = e(
        "div",
        `source-timing source-production${Te > 0 ? " has-output" : " no-output"}`,
      );
      le.setAttribute("role", "cell");
      const Se = e("div", "source-production-head");
      (Se.append(e("strong", "", y(Te)), e("span", "", "近7天首收录原始记录")),
        le.append(Se),
        se.video_pending_7d > 0 &&
          le.append(
            e(
              "small",
              "source-video-pending",
              `其中视频待转写 ${y(se.video_pending_7d)} 条`,
            ),
          ));
      const Ue = e("div", "source-production-facts");
      (Ue.append(
        e("span", "", `近7天形成事件 ${y(se.events_7d)}`),
        e(
          "span",
          "",
          `明确 watch ${y(se.watch_events)} · research ${y(se.research_events)}`,
        ),
      ),
        le.append(
          Ue,
          e(
            "small",
            "source-last-raw",
            `最近原始入库：${se.last_raw_at ? Ve(se.last_raw_at, !0) : "历史未观测"}`,
          ),
        ));
      const Be = e("div", "source-row-actions");
      Be.setAttribute("role", "cell");
      const We = (ze, Ee, pt, nt, At = "icon-button") => {
        const ft = q(At.includes("icon-button") ? "" : ze, At, Ee, nt);
        if (
          ((ft.dataset.action = pt),
          ft.setAttribute("aria-label", `${ze}：${C.name || C.locator}`),
          (ft.title = ze),
          ["view", "edit", "toggle"].includes(pt))
        ) {
          const ot = ft.querySelector("span");
          ot &&
            ((ot.className = "source-action-label"),
            (ot.textContent =
              pt === "view"
                ? "查看"
                : pt === "edit"
                  ? "编辑"
                  : C.enabled
                    ? "停用"
                    : "启用"));
        }
        Be.append(ft);
      };
      if (C.deleted_at)
        We(
          "恢复来源",
          "undo",
          "restore",
          () => j(C, "restore"),
          "button secondary small",
        );
      else {
        We("查看资讯", "list", "view", () => a(C));
        const ze = Fn(C.url);
        if (ze) {
          const Ee = e("a", "icon-button");
          ((Ee.href = ze),
            (Ee.target = "_blank"),
            (Ee.rel = "noopener noreferrer"),
            (Ee.innerHTML = te("external")),
            (Ee.title = "打开原始频道"),
            Ee.setAttribute(
              "aria-label",
              `打开原始频道：${C.name || C.locator}`,
            ),
            Be.append(Ee));
        }
        (We("编辑来源", "edit", "edit", () => fe(C)),
          We(
            C.enabled ? "停用来源" : "启用来源",
            C.enabled ? "pause" : "play",
            "toggle",
            () => j(C, "toggle"),
          ),
          We("移除来源", "trash", "delete", () => E(C)));
      }
      (F.append(I, H, le, Be), A.append(F));
    }
    (ue(
      "#source-list-count",
      `显示 ${y(Math.min(k, P.length))} / ${y(P.length)} 个来源`,
    ),
      (i("#sources-more").hidden = P.length <= k));
  }
  function ye() {
    if (i("#source-dialog")) return;
    const A = e("dialog", "form-dialog");
    ((A.id = "source-dialog"),
      A.setAttribute("aria-labelledby", "source-dialog-title"),
      (A.innerHTML = `<div class="dialog-header"><h2 id="source-dialog-title">添加来源</h2><button class="icon-button" data-close aria-label="关闭来源编辑">${te("close")}</button></div><form id="source-form"><div class="form-body">
      <label for="source-platform">平台<select id="source-platform" required><option value="telegram">Telegram</option><option value="x">X</option><option value="youtube">YouTube</option></select></label>
      <label for="source-locator">账号或频道地址<input id="source-locator" type="text" maxlength="500" required autocomplete="off" placeholder="@channel 或 https://t.me/channel"/></label><p id="source-locator-help" class="field-help"></p>
      <label for="source-name">显示名称 <span class="muted">可选</span><input id="source-name" type="text" maxlength="100" autocomplete="off" placeholder="给这个来源一个容易辨认的名称"/></label>
      <label for="source-poll">采集间隔（秒）<input id="source-poll" type="number" min="60" max="86400" step="1" required/></label><p class="field-help">此间隔是期望检查频率；平台冷却、限流和任务排队可能延后执行。</p>
      <label class="checkbox-label"><input id="source-enabled" type="checkbox"/>启用此来源</label>
      <div id="source-form-error" class="form-error" role="alert" hidden></div><p class="form-note">保存后等待服务器应用订阅。实际成功检查可能没有新资讯；失败、未检查与成功无新增分别记录。</p></div>
      <div class="dialog-footer"><button class="button secondary" type="button" data-close>取消</button><button id="source-submit" class="button primary" type="submit">添加来源</button></div></form>`),
      document.body.append(A),
      ct(A),
      (i("#source-platform").onchange = () => {
        ge(!0);
      }),
      (i("#source-form").onsubmit = me));
    const _ = e("dialog", "confirm-dialog");
    ((_.id = "source-remove-dialog"),
      _.setAttribute("aria-labelledby", "source-remove-title"),
      (_.innerHTML = `<div class="dialog-header"><h2 id="source-remove-title">移除来源</h2><button class="icon-button" data-close aria-label="关闭移除确认">${te("close")}</button></div><div class="form-body"><p id="source-remove-message"></p><p class="muted">此来源将停止采集。已有资讯、图片、收藏与阅读记录保留，你可在「已移除」中恢复此订阅。</p><div id="source-remove-error" class="form-error" role="alert" hidden></div></div><div class="dialog-footer"><button class="button secondary" data-close>取消</button><button id="source-remove-confirm" class="button danger">移除来源</button></div>`),
      document.body.append(_),
      ct(_));
  }
  function ge(A = !1) {
    const _ = i("#source-platform").value,
      P = f?.limits?.minimum_poll_seconds || {
        telegram: 60,
        x: 300,
        youtube: 1800,
      },
      C = { telegram: 300, x: 3600, youtube: 7200 };
    ((i("#source-poll").min = String(P[_])),
      (i("#source-poll").max = String(
        f?.limits?.maximum_poll_seconds || 86400,
      )),
      A && (i("#source-poll").value = String(C[_])));
    const F = {
      telegram: [
        "@channel 或 https://t.me/channel",
        "填写频道用户名、公开频道链接，或当前已登录账号可访问的频道标识。",
      ],
      x: [
        "@username 或 https://x.com/username",
        "填写账号用户名或主页链接。服务器使用现有 X 采集连接。",
      ],
      youtube: [
        "https://www.youtube.com/@channel",
        "填写 YouTube 频道主页、@handle 或频道 ID。视频整理与转写可能需要更长时间。",
      ],
    };
    ((i("#source-locator").placeholder = F[_][0]),
      ue("#source-locator-help", F[_][1]));
  }
  function fe(A = null) {
    (ye(),
      (Y = A),
      ue("#source-dialog-title", A ? "编辑来源" : "添加来源"),
      ue("#source-submit", A ? "保存更改" : "添加来源"),
      (i("#source-platform").value = A?.platform || "telegram"),
      (i("#source-platform").disabled = !!A),
      (i("#source-locator").value = A?.locator || ""),
      (i("#source-name").value = A?.name || ""),
      (i("#source-enabled").checked = A ? !!A.enabled : !0),
      (i("#source-poll").value = String(A?.poll_seconds || 300)),
      (i("#source-form-error").hidden = !0),
      (i("#source-submit").disabled = !1),
      ge(),
      ut(i("#source-dialog")),
      i("#source-locator").focus());
  }
  async function me(A) {
    A.preventDefault();
    const _ = i("#source-submit"),
      P = i("#source-form-error");
    ((P.hidden = !0), (_.disabled = !0));
    const C = {
      platform: i("#source-platform").value,
      locator: i("#source-locator").value.trim(),
      name: i("#source-name").value.trim(),
      enabled: i("#source-enabled").checked,
      poll_seconds: Number(i("#source-poll").value),
    };
    (C.name || delete C.name,
      Y && (delete C.platform, (C.version = Y.version)));
    try {
      (await t(
        Y ? `/api/sources/${encodeURIComponent(Y.id)}` : "/api/sources",
        { method: Y ? "PATCH" : "POST", body: JSON.stringify(C) },
      ),
        i("#source-dialog").close(),
        ce(
          Y
            ? "来源修改已保存，等待采集器应用；既有原始记录与历史资讯保留。"
            : "来源已添加，等待采集器应用；已保存不代表已开始采集。",
        ),
        $e(Y ? "来源配置已保存，等待采集器应用" : "来源已添加，等待采集器应用"),
        await re(m, !0));
    } catch (F) {
      ((P.textContent =
        F.status === 409
          ? "此来源已在其他窗口修改，或相同账号已存在。请刷新来源列表后确认；当前输入已保留。"
          : F.message),
        (P.hidden = !1));
    } finally {
      _.disabled = !1;
    }
  }
  function E(A) {
    (ye(),
      ue("#source-remove-message", `确定移除「${A.name || A.locator}」？`),
      (i("#source-remove-error").hidden = !0),
      (i("#source-remove-confirm").onclick = async () => {
        const _ = i("#source-remove-confirm");
        _.disabled = !0;
        try {
          (await t(`/api/sources/${encodeURIComponent(A.id)}`, {
            method: "DELETE",
            body: JSON.stringify({ version: A.version }),
          }),
            i("#source-remove-dialog").close(),
            ce(
              "已移除订阅并停止后续采集配置；可到「已移除 · 可恢复」筛选恢复，历史原始记录和资讯仍保留。",
            ),
            $e("来源已移除，可从「已移除」恢复"),
            await re(m, !0));
        } catch (P) {
          (ue(
            "#source-remove-error",
            P.status === 409 ? "此来源已被修改，请刷新后重试。" : P.message,
          ),
            (i("#source-remove-error").hidden = !1));
        } finally {
          _.disabled = !1;
        }
      }),
      ut(i("#source-remove-dialog")));
  }
  async function j(A, _) {
    const P = Ne(".source-row").find((C) => C.dataset.id === A.id);
    P?.querySelectorAll("button").forEach((C) => {
      C.disabled = !0;
    });
    try {
      const C =
        _ === "toggle"
          ? { enabled: !A.enabled, version: A.version }
          : { version: A.version };
      (await t(
        `/api/sources/${encodeURIComponent(A.id)}${_ === "restore" ? "/restore" : ""}`,
        { method: _ === "restore" ? "POST" : "PATCH", body: JSON.stringify(C) },
      ),
        ce(
          _ === "restore"
            ? "来源已恢复，等待采集器应用；可在「当前来源」查看，历史资料未删除。"
            : A.enabled
              ? "停用已保存，等待采集器应用；此来源会移出当前行动组，在「已停用」可重新启用，历史资料保留。"
              : "启用已保存，等待采集器应用；在「当前来源」可查看，但不表示采集已成功。",
        ),
        $e(
          _ === "restore"
            ? "来源已恢复，等待采集器应用"
            : A.enabled
              ? "停用设置已保存，等待采集器应用"
              : "启用设置已保存，等待采集器应用",
        ),
        await re(m, !0));
    } catch (C) {
      ($e(
        C.status === 409 ? "来源已在其他窗口修改，请刷新后重试。" : C.message,
      ),
        P?.querySelectorAll("button").forEach((F) => {
          F.disabled = !1;
        }));
    }
  }
  async function re(A, _ = !1) {
    if (!G) {
      if (_ && l > Date.now()) {
        (clearTimeout(o), (o = setTimeout(() => re(A, !0), l - Date.now())));
        return;
      }
      ((G = !0),
        (m = A),
        (!_ || !i("#source-list")) &&
          m.replaceChildren(
            e("p", "panel-loading", "正在读取订阅来源与采集状态…"),
          ),
        i("#source-refresh") && (i("#source-refresh").disabled = !0));
      try {
        ((f = await t("/api/sources?include_deleted=1")),
          (l = 0),
          (c = Array.isArray(f.items) ? f.items : []),
          _e(),
          ne(),
          ae());
      } catch (P) {
        (P.status === 429 &&
          (l = Date.now() + Math.max(1, Number(P.retryAfter) || 5) * 1e3),
          P.status !== 401 &&
            (_ && i("#source-list")
              ? $e(P.message)
              : m.replaceChildren(
                  it(
                    "来源管理暂不可用",
                    P.message,
                    { label: "重新连接", run: () => re(A) },
                    "sources",
                  ),
                )));
      } finally {
        ((G = !1),
          i("#source-refresh") && (i("#source-refresh").disabled = !1),
          clearTimeout(o),
          f?.revision > f?.applied_revision &&
            m?.isConnected &&
            !m.hidden &&
            (o = setTimeout(() => re(m, !0), Math.max(5e3, l - Date.now()))));
      }
    }
  }
  return {
    load: re,
    refresh() {
      if (
        m?.isConnected &&
        !m.hidden &&
        !G &&
        !i("#source-dialog")?.open &&
        !i("#source-remove-dialog")?.open
      )
        return re(m, !0);
    },
    getRecords: () => c,
  };
}
let Nt = [],
  _t = 0,
  fa = "",
  Dt = !1;
function rr() {
  if (i("#image-dialog")) return;
  const t = e("dialog", "image-dialog");
  ((t.id = "image-dialog"),
    t.setAttribute("aria-labelledby", "image-title"),
    (t.innerHTML = `<div class="dialog-header"><h2 id="image-title">来源附图</h2><div class="image-top-actions"><button id="image-original" class="button secondary small" aria-pressed="false">实际大小</button><button class="icon-button" data-close aria-label="关闭图片查看器">${te("close")}</button></div></div><div class="image-stage"><button id="image-prev" class="image-nav previous" aria-label="上一张图片">${te("chevron")}</button><div id="image-main"></div><button id="image-next" class="image-nav next" aria-label="下一张图片">${te("chevron")}</button></div><div id="image-caption" class="image-caption"></div>`),
    document.body.append(t),
    ct(t),
    (i("#image-prev").onclick = () => Xt(_t - 1)),
    (i("#image-next").onclick = () => Xt(_t + 1)),
    (i("#image-original").onclick = () => {
      ((Dt = !Dt),
        i("#image-main").classList.toggle("actual-size", Dt),
        i("#image-original").setAttribute("aria-pressed", String(Dt)),
        ue("#image-original", Dt ? "适应窗口" : "实际大小"));
    }),
    t.addEventListener("keydown", (a) => {
      a.key === "ArrowLeft"
        ? (a.preventDefault(), Xt(_t - 1))
        : a.key === "ArrowRight" && (a.preventDefault(), Xt(_t + 1));
    }));
}
function Xt(t) {
  _t = (t + Nt.length) % Nt.length;
  const a = Nt[_t];
  ((Dt = !1),
    ue(
      "#image-title",
      `${a.kind === "thumbnail" ? "视频封面" : "来源附图"} · ${_t + 1} / ${Nt.length}`,
    ),
    i("#image-main").replaceChildren(
      Pt(
        { ...a, thumbnail_url: a.url },
        `第 ${_t + 1} 张来源图片`,
        "lightbox-image",
        !0,
      ),
    ),
    i("#image-main").classList.remove("actual-size"),
    i("#image-original").setAttribute("aria-pressed", "false"),
    ue("#image-original", "实际大小"),
    (i("#image-prev").hidden = Nt.length <= 1),
    (i("#image-next").hidden = Nt.length <= 1),
    ue("#image-caption", fa));
}
function ma(t, a = 0, o = "") {
  t?.length && (rr(), (Nt = t), (fa = o), Xt(a), ut(i("#image-dialog")));
}
const ln = Object.freeze([
    { id: "telegram", label: "Telegram" },
    { id: "x", label: "X" },
    { id: "youtube", label: "YouTube" },
  ]),
  ir = Object.freeze([
    {
      name: "AI 芯片",
      query: "AI芯片",
      platforms: ["telegram", "x", "youtube"],
      min_importance: 0,
      description: "示例方向：算力、模型训练与半导体，按你的真实问题改写",
    },
    {
      name: "量子计算",
      query: "量子计算",
      platforms: ["telegram", "x", "youtube"],
      min_importance: 0,
      description: "示例方向：芯片路线、量子纠错，按你的真实问题改写",
    },
    {
      name: "商业航天 · SpaceX",
      query: "SpaceX",
      platforms: ["telegram", "x", "youtube"],
      min_importance: 0,
      description: "示例仅检索 SpaceX 相关发射与技术验证，不代表全部商业航天；请按你的真实问题改写",
    },
  ]);
function oe(t, a = 500) {
  return typeof t == "string"
    ? t
        .replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/g, "")
        .slice(0, a)
    : "";
}
function ve(t) {
  const a = Number(t);
  return Number.isFinite(a) && a >= 0 ? Math.min(1e9, Math.floor(a)) : 0;
}
function An(t) {
  const a = oe(t, 500).trim().split(/\s+/).filter(Boolean).length;
  return a
    ? a === 1
      ? "当前 1 个检索条件 · 先用单个准确关键词观察召回，再按需要收紧。"
      : "当前 " +
        a +
        " 个 AND 条件 · 所有词须同时命中，可能漏掉只提及其中一个词的消息。建议首次先用 1 个关键词。"
    : "先写一个你想持续追踪的真实关键词或短语；留空不会创建主题。";
}
function aa(t) {
  const a = oe(t?.name, 100).trim().replace(/\s+/g, " "),
    o = oe(t?.query, 500).trim().replace(/\s+/g, " "),
    l = [...new Set(Array.isArray(t?.platforms) ? t.platforms : [])].filter(
      (m) => ln.some((s) => s.id === m),
    ),
    c = Number(t?.min_importance),
    f = {};
  return (
    (!a || [...a].length > 48) && (f.name = "主题名需为 1–48 个字符。"),
    (!o || [...o].length > 160) &&
      (f.query = "关键词需为 1–160 个字符，中文和空格均可使用。"),
    o &&
      o.split(" ").length > 8 &&
      (f.query = "最多使用 8 个空格分隔的词，多个词会同时匹配（AND）。"),
    l.length || (f.platforms = "至少选择一个平台。"),
    (!Number.isInteger(c) || c < 0 || c > 100) &&
      (f.min_importance = "最低重要度应为 0–100 的整数。"),
    {
      ok: !Object.keys(f).length,
      errors: f,
      data: { name: a, query: o, platforms: l, min_importance: c },
    }
  );
}
function sr(t) {
  if (typeof t != "string" || !/^\d{4}-\d{2}-\d{2}$/.test(t)) return !1;
  const a = Date.parse(t + "T00:00:00Z");
  return Number.isFinite(a) && new Date(a).toISOString().slice(0, 10) === t;
}
function or(t, a = 31) {
  if (!Array.isArray(t)) return [];
  const o = new Map();
  for (const s of t) {
    const g = Array.isArray(s) ? s[0] : (s?.date ?? s?.day);
    if (!sr(g)) continue;
    const h = Array.isArray(s) ? s[1] : (s?.count ?? s?.total ?? s?.value);
    h == null ||
      h === "" ||
      !Number.isFinite(Number(h)) ||
      Number(h) < 0 ||
      o.set(g, ve(h));
  }
  if (!o.size) return [];
  const l = [...o.keys()].sort().slice(-Math.max(1, Math.min(31, ve(a) || 31))),
    c = Date.parse(l[0] + "T00:00:00Z"),
    f = Date.parse(l.at(-1) + "T00:00:00Z"),
    m = [];
  for (
    let s = Math.max(c, f - (Math.min(31, ve(a) || 31) - 1) * 864e5);
    s <= f;
    s += 864e5
  ) {
    const g = new Date(s).toISOString().slice(0, 10);
    m.push({ day: g, count: o.get(g) ?? 0 });
  }
  return m;
}
function lr(t) {
  if (!t.length) return "暂无按天趋势数据";
  const a = t[0].day.slice(5).replace("-", "月") + "日",
    o = t.at(-1).day.slice(5).replace("-", "月") + "日",
    l = t.reduce((c, f) => c + ve(f.count), 0);
  return (
    "按 UTC 日期，" +
    a +
    "至" +
    o +
    "，每天首次收录数量依次为 " +
    t.map((c) => ve(c.count) + " 条").join("、") +
    "；合计 " +
    l +
    " 条。"
  );
}
function dr(t) {
  const a = oe(t, 200).trim().split(/\s+/).filter(Boolean);
  return { q: a[0] || "", terms: a, approximate: a.length > 1 };
}
function cr(t) {
  const a = kt(t?.event_time_start),
    o = rn(t),
    l = t?.event_time_precision,
    c = t?.event_time_status;
  if (
    a &&
    ["exact", "day", "month", "range"].includes(l) &&
    ["explicit", "inferred", "scheduled"].includes(c) &&
    o !== "事件时间待确认"
  )
    return {
      kind: "event",
      label: "事件时间候选",
      value: a,
      evidence_label: o,
      calendar_kind: l === "exact" ? "北京时间" : "原文日历候选",
    };
  const f = kt(t?.first_ingested_at);
  return f
    ? { kind: "ingested", label: "首次收录 · 非事件时间", value: f }
    : { kind: "unknown", label: "事件时间待确认", value: null };
}
function ht(t) {
  const a = typeof t == "string" && t.length <= 2048 ? Fn(t) : null;
  if (!a) return null;
  try {
    const o = new URL(a);
    if (/^https?:\/\/[^/?#]*@/i.test(t)) return null;
    const l = o.hostname
      .replace(/^\[|\]$/g, "")
      .replace(/\.+$/, "")
      .toLowerCase();
    return o.username ||
      o.password ||
      !l.includes(".") ||
      /(?:^|\.)(?:localhost|local|internal|home|lan)$/.test(l) ||
      /(?:^|\.)home\.arpa$/.test(l) ||
      /(?:^|\.)(?:nip\.io|sslip\.io|localtest\.me|lvh\.me)$/.test(l) ||
      l.includes(":") ||
      /^(?:\d+\.){3}\d+$/.test(l)
      ? null
      : a;
  } catch {
    return null;
  }
}
function ur(t) {
  return (Array.isArray(t) ? t : [])
    .map((a) => ({ source: a, href: ht(a?.url) }))
    .filter(({ href: a }) => a !== null)
    .slice(0, 3);
}
function pr(t) {
  const a = Math.max(0, Math.min(100, Math.round(Number(t) || 0)));
  return {
    score: a,
    level: a >= 85 ? "critical" : a >= 70 ? "high" : "normal",
    label: a >= 85 ? "高优先级" : a >= 70 ? "重点关注" : "关注线索",
  };
}
function fr(t, a, o = "") {
  const l = oe(a).trim().normalize("NFKC").toLocaleLowerCase();
  return !!(
    l &&
    (Array.isArray(t) ? t : []).some(
      (c) =>
        String(c?.id) !== String(o) &&
        oe(c?.name).trim().normalize("NFKC").toLocaleLowerCase() === l,
    )
  );
}
const mr = [
  {
    id: "free",
    label: "免费",
    headline: "开始建立第一条观察线",
    features: ["基础主题追踪", "查看重点事件与原始证据"],
    assumedPrice: 0,
  },
  {
    id: "pro",
    label: "Pro",
    headline: "同时关注更多方向",
    features: ["多主题并行追踪", "较长的历史观察范围"],
    assumedPrice: null,
  },
  {
    id: "analyst",
    label: "Analyst",
    headline: "持续复盘复杂信号",
    features: ["更充裕的主题容量", "更长的历史观察范围"],
    assumedPrice: null,
  },
];
function hr(t, a = null) {
  const o = Array.isArray(t?.plans)
      ? t.plans
      : Array.isArray(t?.tiers)
        ? t.tiers
        : [],
    l = t?.current_plan ?? t?.current_plan_id ?? t?.current ?? a,
    c =
      typeof l == "string"
        ? l.toLowerCase()
        : String(l?.id || "").toLowerCase();
  return {
    plans: mr.map((m) => {
      const s =
          o.find((O) => String(O?.id || "").toLowerCase() === m.id) ||
          (String(a?.id || "").toLowerCase() === m.id ? a : {}),
        g = s.limits && typeof s.limits == "object" ? s.limits : {},
        h = g.max_topics ?? g.topics ?? s.max_topics,
        k =
          h != null && h !== "" && Number.isInteger(Number(h)) && Number(h) >= 0
            ? Number(h)
            : null,
        Y =
          Number.isInteger(Number(g.history_days)) && Number(g.history_days) > 0
            ? Number(g.history_days)
            : null,
        G =
          Number.isInteger(Number(g.trend_days)) && Number(g.trend_days) > 0
            ? Number(g.trend_days)
            : null,
        L = o.find((O) => String(O?.id || "").toLowerCase() === m.id)?.pricing
          ?.suggested_monthly_usd,
        B =
          L != null && Number.isFinite(Number(L)) && Number(L) >= 0
            ? Number(L)
            : m.assumedPrice;
      return {
        ...m,
        label: oe(s.label || s.name || m.label, 60),
        maxTopics: k,
        historyDays: Y,
        trendDays: G,
        assumedPrice: B,
        limits: g,
        capabilities: s.capabilities ?? null,
        current:
          c === m.id || (!c && String(a?.id || "").toLowerCase() === m.id),
      };
    }),
    current: c || null,
    verified: o.length > 0,
  };
}
const fn = [
  ["judgment", "我的判断"],
  ["support", "支持或疑问"],
  ["falsification", "反证条件"],
  ["next_step", "下一步"],
  ["review_on", "复查日"],
];
function Rn(t) {
  return typeof t != "string" || /[\s\\]/.test(t) ? null : ht(t);
}
function br({ api: t, now: a = () => new Date() }) {
  const o = new Map();
  function l(c) {
    if (o.has(c)) return o.get(c).root;
    const f = e("section", "detail-section dossier");
    ((f.dataset.eventId = c),
      (f.tabIndex = -1),
      f.setAttribute("aria-label", "证据核查与个人研判卡"));
    const m = e("div", "dossier-head");
    (m.append(
      e("span", "dossier-kicker", "个人研究 · 可追溯"),
      e("h3", "", "证据核查与研判"),
    ),
      f.append(
        m,
        e(
          "p",
          "dossier-intro",
          "先比对自动摘要与采集原文，再留下可以被推翻的判断。引用不是独立证实，保存时固定当时证据；旧修订不会被覆盖。",
        ),
      ));
    const s = {
      root: f,
      version: null,
      dirty: !1,
      busy: !1,
      exportMode: null,
      exportVersion: null,
      exportPinned: !1,
      savedFields: null,
      savedEvidence: null,
      revisionEvidence: new Map(),
      revisionFields: new Map(),
    };
    o.set(c, s);
    const g = e("p", "dossier-status", "正在加载研判…");
    g.setAttribute("role", "status");
    const h = e("div", "dossier-reminder");
    h.hidden = !0;
    const k = e("details", "dossier-evidence");
    k.open = !0;
    const Y = e("summary", "", "01 · 核查自动摘要与原始记录"),
      G = e("div", "dossier-evidence-body");
    k.append(Y, G);
    const pe = e("form", "dossier-form"),
      L = {};
    for (const [N, z] of fn) {
      const K = e("label", "dossier-field");
      K.append(e("span", "", z));
      const ee = e(N === "review_on" ? "input" : "textarea");
      ((ee.name = N),
        (ee.disabled = !0),
        N === "review_on"
          ? (ee.type = "date")
          : ((ee.rows = N === "judgment" ? 4 : 3), (ee.maxLength = 2e4)),
        N === "support" &&
          (ee.placeholder =
            "核对原文后写下理由，使用 [1] 等编号指向具体记录。"),
        N === "falsification" &&
          (ee.placeholder = "出现什么事实时，必须修改或撤回判断？"),
        N === "next_step" && (ee.placeholder = "下次具体要核对什么？"),
        (ee.oninput = () => {
          ((s.dirty = !0),
            (g.textContent = "有未保存的草稿 · 导出仍使用已保存版本"),
            N === "review_on" && Ee(ee.value, !0),
            We());
        }),
        K.append(ee),
        N === "review_on" &&
          K.append(
            e(
              "small",
              "dossier-field-help",
              "到期时在事件卡内提示，不会发送系统通知。",
            ),
          ),
        pe.append(K),
        (L[N] = ee));
    }
    const B = q("保存新修订", "button primary");
    ((B.type = "submit"), (B.disabled = !0));
    const O = q("放弃草稿改动", "button secondary", null, async () => {
        if (!s.dirty || s.busy) return;
        ((s.dirty = !1),
          (g.textContent = "正在还原最新保存的修订…"),
          (await ot()) ||
            ((s.dirty = !0),
            (g.textContent =
              "无法取得保存版本，输入框里的草稿仍保留；请检查连接后再试。"),
            We()));
      }),
      de = q("撤回已保存判断", "button secondary", null, () => {
        s.busy ||
          s.dirty ||
          !s.version ||
          ((X.hidden = !1),
          (g.textContent = "撤回会追加一条新修订，旧判断与当时的引文保留。"),
          ie.focus());
      }),
      ce = e("div", "dossier-actions dossier-write-actions");
    (ce.append(B, O, de), pe.append(ce));
    const _e = e("section", "dossier-export-chooser");
    _e.setAttribute("aria-label", "选择研判导出用途");
    const R = e(
        "p",
        "dossier-export-intro",
        "先选择用途，再核对风险提示，最后主动复制或下载。所有导出仅为本机操作，不会自动发信、发布、计费或发送给客户。",
      ),
      ne = q(
        "选择对外核对摘要（仅本人原创判断＋出处链接）",
        "button secondary dossier-export-select",
        null,
        () => Be("share"),
      ),
      ae = q(
        "选择含原文个人完整归档（仅本人）",
        "button secondary dossier-export-select",
        null,
        () => Be("full"),
      );
    (ne.setAttribute("aria-pressed", "false"),
      ae.setAttribute("aria-pressed", "false"));
    const ye = e("div", "dossier-export-choices");
    ye.append(ne, ae);
    const ge = e("section", "dossier-export-panel dossier-share-panel");
    ((ge.hidden = !0), (ge.tabIndex = -1));
    const fe = e("h5", "", "对外核对摘要 · 不含自动摘要和采集原文"),
      me = e("div", "dossier-export-warning");
    (me.setAttribute("role", "note"),
      me.append(
        e(
          "p",
          "",
          "亲核原文：请本人逐条打开原始出处，核对事实主张、时间、独立性与链接可达性。系统的自动整理、出处编号与哈希不代表已核实；错误判断也可能进入草稿。",
        ),
        e(
          "p",
          "",
          "核授权与法律：须逐源检查采集/处理、版权、商业衍生、引用/外发许可及隐私、保密与适用法律；仅有公开链接不等于获准转发。请确保判断确为本人原创、无未授权引用或敏感信息。",
        ),
        e(
          "p",
          "",
          "非已核实/不可无许可转发：此摘要只是待人工核对的文本候选，不是经过事实或法律审查的客户成品。未经本人亲核和合法授权，不得对任何人转发或商用。",
        ),
      ));
    const E = e("p", "dossier-export-version", "尚未选择保存版本"),
      j = q("复制对外核对摘要", "button secondary", null, () =>
        qt(!1, "share"),
      ),
      re = q("下载对外核对摘要 .txt", "button secondary", null, () =>
        qt(!0, "share"),
      ),
      A = e("div", "dossier-actions dossier-export-actions");
    (A.append(j, re), ge.append(fe, me, E, A));
    const _ = e("section", "dossier-export-panel dossier-full-panel");
    ((_.hidden = !0), (_.tabIndex = -1));
    const P = e(
        "p",
        "dossier-export-warning",
        "含冻结的自动摘要、采集原文全文、出处及可能受版权/隐私限制的材料。仅供本人完整归档与内部核查；未经逐源核实、清权和法律审查，禁止直接转发给外部或作为客户报告。",
      ),
      C = e("p", "dossier-export-version", "尚未选择保存版本"),
      F = q("复制含引用研究卡（含原文·仅本人）", "button secondary", null, () =>
        qt(!1, "full"),
      ),
      I = q("导出文本（含原文·仅本人）", "button secondary", null, () =>
        qt(!0, "full"),
      ),
      W = e("div", "dossier-actions dossier-export-actions");
    (W.append(F, I),
      _.append(
        e("h5", "", "含原文个人完整归档 · 严禁未经许可对外分发"),
        P,
        C,
        W,
      ),
      _e.append(
        e("h4", "dossier-export-title", "选择复制／导出用途"),
        R,
        ye,
        ge,
        _,
      ));
    const Q = q("刷新研判", "button secondary", null, () => ot()),
      he = e("div", "dossier-actions dossier-refresh-actions");
    (he.append(Q), pe.append(_e, he));
    const X = e("div", "dossier-withdraw");
    ((X.hidden = !0),
      X.append(
        e("h4", "", "追加撤回修订"),
        e(
          "p",
          "muted",
          "撤回不是删除历史，而是明确声明最新判断不再成立；历史证据仍可复查。",
        ),
      ));
    const H = e("label", "dossier-field");
    H.append(e("span", "", "撤回原因（必填）"));
    const ie = e("textarea");
    ((ie.rows = 2),
      (ie.maxLength = 300),
      (ie.placeholder = "例如：原始出处与摘要冲突，暂时不能确认。"),
      H.append(ie),
      X.append(H));
    const qe = q("确认并保存撤回修订", "button primary", null, async () => {
        if (s.busy || s.dirty || !s.version) return;
        const N = ie.value.trim();
        if (!N) {
          ((g.textContent = "请写下撤回原因，避免产生不可解释的版本。"),
            ie.focus());
          return;
        }
        const z = s.version,
          K = Se();
        ((K.judgment = `已撤回 v${z} 判断：${N}`),
          (K.support = `此前支持材料不再作为当前判断依据，请查看历史 v${z} 核对。`),
          Ue(K),
          (s.dirty = !0),
          (X.hidden = !0),
          We(),
          await pe.onsubmit({ preventDefault() {} }));
      }),
      J = e("div", "dossier-actions");
    (J.append(
      qe,
      q("取消撤回", "button secondary", null, () => {
        ((X.hidden = !0), (ie.value = ""));
      }),
    ),
      X.append(J));
    const se = e("div", "dossier-conflict");
    se.hidden = !0;
    const Te = e("details", "dossier-history"),
      we = e("div", "dossier-history-list");
    Te.append(e("summary", "", "03 · 历史修订与版本回看"), we);
    const le = e("div", "dossier-preview");
    f.append(
      g,
      h,
      k,
      e("h4", "dossier-step", "02 · 人工研判与下次检查"),
      pe,
      X,
      se,
      Te,
      le,
    );
    function Se() {
      return Object.fromEntries(fn.map(([N]) => [N, L[N].value]));
    }
    function Ue(N) {
      for (const [z] of fn) L[z].value = N[z] || "";
    }
    function Be(N, z = s.version, K = !1) {
      s.busy ||
        ((s.exportMode = N),
        (s.exportPinned = K),
        (s.exportVersion = Number.isInteger(z) && z > 0 ? z : null),
        (ge.hidden = N !== "share"),
        (_.hidden = N !== "full"),
        ne.setAttribute("aria-pressed", String(N === "share")),
        ae.setAttribute("aria-pressed", String(N === "full")),
        K && (N === "share" ? ge : _).focus(),
        s.exportVersion ||
          (g.textContent =
            "请先保存一份人工研判修订，才能复制或下载；当前尚无可导出版本。"),
        We());
    }
    function We() {
      ((Q.disabled = s.busy),
        (B.disabled = s.busy || s.version == null),
        (O.disabled = s.busy || !s.dirty),
        (de.disabled = s.busy || s.dirty || !s.version),
        (qe.disabled = s.busy),
        (ne.disabled = ae.disabled = s.busy));
      const N = s.exportVersion
        ? `已保存 v${s.exportVersion} · ${s.dirty ? "当前输入是未保存草稿，不会被导出" : "非事实/授权审核证明"}`
        : "尚无保存版本 · 请先保存";
      ((E.textContent = `摘要目标：${N}`),
        (C.textContent = `归档目标：${N}`),
        (j.disabled = re.disabled =
          s.busy || !s.exportVersion || s.exportMode !== "share"),
        (F.disabled = I.disabled =
          s.busy || !s.exportVersion || s.exportMode !== "full"));
    }
    function ze(N) {
      ((s.busy = N), We());
    }
    function Ee(N, z = !1) {
      if (!/^\d{4}-\d{2}-\d{2}$/.test(N)) {
        h.hidden = !0;
        return;
      }
      const K = a(),
        ee = [
          K.getFullYear(),
          String(K.getMonth() + 1).padStart(2, "0"),
          String(K.getDate()).padStart(2, "0"),
        ].join("-"),
        De = N <= ee;
      ((h.className = `dossier-reminder ${De ? "is-due" : "is-upcoming"}`),
        h.replaceChildren(
          e(
            "strong",
            "",
            De ? (N === ee ? "今日应复看" : "复看日期已过") : "下次复看",
          ),
          e(
            "span",
            "",
            `${N} · ${z ? "草稿（未保存）" : "已保存版本"} · 仅在此卡提示，不发送通知`,
          ),
        ),
        (h.hidden = !1));
    }
    function pt(N) {
      const z = L.support,
        K = `[${N}]`,
        ee = Number.isInteger(z.selectionStart)
          ? z.selectionStart
          : z.value.length,
        De = Number.isInteger(z.selectionEnd) ? z.selectionEnd : ee,
        Ie = ee > 0 && !/\s/.test(z.value[ee - 1]) ? " " : "";
      ((z.value = z.value.slice(0, ee) + Ie + K + z.value.slice(De)),
        z.oninput(),
        z.focus(),
        (g.textContent = `已插入引用 ${K} · 请先比对原文，再说明支持或疑问`));
    }
    function nt(N) {
      const z = N?.records || [],
        K = N?.event || {};
      ((Y.textContent = `01 · 核查自动摘要与原始记录（${z.length}）`),
        G.replaceChildren(),
        G.append(
          e(
            "p",
            "dossier-evidence-limit",
            `原始记录 ${N?.raw_record_count ?? z.length} 条 · 出处标识 ${N?.publisher_count ?? "未知"} 个 · 独立性未核实。${N?.notice || "链接可达性未检查。"}`,
          ),
        ));
      const ee = e("div", "dossier-compare"),
        De = e("div", "dossier-claim"),
        Ie = e("div", "dossier-originals");
      (De.append(
        e("span", "dossier-kicker", "自动摘要 · 未经人工事实核验"),
        e(
          "p",
          "dossier-claim-text",
          K.summary || "没有自动摘要；请直接核对采集原文。",
        ),
      ),
        K.event_time_evidence &&
          De.append(
            e("span", "dossier-kicker", "时间依据 · 待核"),
            e("blockquote", "evidence-quote", K.event_time_evidence),
          ),
        K.event_time_note &&
          De.append(e("p", "dossier-text", K.event_time_note)));
      for (const Ge of K.locations || [])
        Ge.evidence &&
          De.append(
            e("p", "dossier-text", `${Ge.name || "地点"}：${Ge.evidence}`),
          );
      (Ie.append(e("span", "dossier-kicker", "采集原文 · 与左侧逐项对照")),
        z.length ||
          Ie.append(
            e("p", "dossier-missing", "尚无完成的采集正文，不能据此确认主张。"),
          ));
      for (const [Ge, Oe] of z.entries()) {
        const Je = e("article", "dossier-source"),
          Ct = e("div", "dossier-source-head");
        Ct.append(
          e("strong", "", `[${Ge + 1}] ${Oe.name || "出处未标记"}`),
          e("span", "dossier-source-platform", Ke(Oe.platform)),
        );
        const Ht = Rn(Oe.url);
        if (Ht) {
          const Tt = e("a", "source-link", "打开原始出处 ↗");
          ((Tt.href = Ht),
            (Tt.target = "_blank"),
            (Tt.rel = "noopener noreferrer"),
            Ct.append(Tt));
        } else
          Ct.append(e("span", "dossier-unavailable", "安全原文链接不可用"));
        Je.append(
          Ct,
          e(
            "p",
            "dossier-source-meta",
            `${Oe.title || "原始内容"} · 发布：${Ve(Oe.published_at, !0)} · 首次收录：${Ve(Oe.first_ingested_at, !0)}`,
          ),
        );
        const It = e("details", "dossier-original");
        ((It.open = Ge === 0),
          It.append(
            e("summary", "", Oe.text ? "展开／收起采集原文" : "采集正文缺失"),
          ));
        const jt = e(
          "p",
          "dossier-original-text",
          Oe.text || "采集正文缺失，不能据此核实。",
        );
        ((jt.tabIndex = 0),
          It.append(jt),
          Je.append(It),
          Je.append(
            e(
              "p",
              "dossier-fingerprint",
              `记录 ${Oe.record_id} · SHA-256 ${Oe.sha256 || "未知"} · 链接可达性未检查`,
            ),
          ),
          Je.append(
            q(
              `插入引用 [${Ge + 1}]`,
              "button secondary small dossier-cite",
              null,
              () => pt(Ge + 1),
            ),
          ),
          Ie.append(Je));
      }
      (ee.append(De, Ie), G.append(ee));
    }
    async function At(N) {
      const z = (s.revisionRequest = (s.revisionRequest || 0) + 1);
      try {
        const K = await t(
          `/api/events/${encodeURIComponent(c)}/dossier/revisions/${N}`,
        );
        if (z !== s.revisionRequest) return;
        (s.revisionEvidence.set(N, K.evidence),
          s.revisionFields.set(N, K.fields),
          le.replaceChildren(
            e("h4", "", `回看 v${N} · ${Ve(K.created_at, !0)}`),
          ));
        for (const [De, Ie] of fn)
          le.append(
            e("h4", "", Ie),
            e("p", "dossier-text", K.fields[De] || "未填写"),
          );
        const ee = K.evidence;
        (le.append(
          e(
            "p",
            "detail-note",
            `当时保存了 ${ee.raw_record_count} 条原始记录，${ee.publisher_count} 个出处标识；独立性未知。${ee.notice}`,
          ),
        ),
          le.append(
            e("h4", "", "当时的自动摘要（未经人工事实核验）"),
            e("p", "dossier-text", ee.event.summary),
          ),
          le.append(
            e(
              "p",
              "dossier-text",
              `发生时间：${ee.event.event_time_start || "未知"}${ee.event.event_time_end ? ` → ${ee.event.event_time_end}` : ""}；地点状态：${ee.event.location_status}`,
            ),
          ),
          ee.event.event_time_evidence &&
            le.append(
              e("blockquote", "evidence-quote", ee.event.event_time_evidence),
            ),
          ee.event.event_time_note &&
            le.append(e("p", "dossier-text", ee.event.event_time_note)));
        for (const De of ee.event.locations || [])
          le.append(
            e(
              "p",
              "dossier-text",
              `${De.name || "地点"}：${De.evidence || "依据待确认"}`,
            ),
          );
        for (const [De, Ie] of ee.records.entries()) {
          const Ge = e("details", "dossier-reference");
          Ge.append(
            e(
              "summary",
              "",
              `[${De + 1}] ${Ie.name} · ${Ke(Ie.platform)} · ${Ie.record_id}`,
            ),
          );
          const Oe = Rn(Ie.url);
          if (Oe) {
            const Je = e("a", "source-link", "打开原始出处（可达性未检查）");
            ((Je.href = Oe),
              (Je.target = "_blank"),
              (Je.rel = "noopener noreferrer"),
              Ge.append(Je));
          } else Ge.append(e("p", "muted", "安全原文链接不可用"));
          (Ge.append(
            e("h4", "", Ie.title || "原始内容"),
            e(
              "p",
              "muted",
              `发布：${Ve(Ie.published_at, !0)} · 首次收录：${Ve(Ie.first_ingested_at, !0)}`,
            ),
            e("p", "dossier-fingerprint", `SHA-256：${Ie.sha256}`),
            e("p", "dossier-text", Ie.text || "原文正文缺失"),
          ),
            le.append(Ge));
        }
        le.append(
          q(`以 v${N} 为新草稿`, "button secondary", null, () => {
            if (s.dirty) {
              g.textContent =
                "本地已有未保存草稿，请先保存或放弃，以免覆盖输入。";
              return;
            }
            (Ue(K.fields),
              (s.dirty = !0),
              We(),
              Ee(L.review_on.value, !0),
              (g.textContent = `已载入 v${N} 为草稿；旧版未修改，保存后才会追加新修订。`));
          }),
          q(`选择 v${N} 对外核对摘要`, "button secondary", null, () =>
            Be("share", N, !0),
          ),
          q(
            `导出此版本 v${N}（含原文，先选择用途）`,
            "button secondary",
            null,
            () => Be("full", N, !0),
          ),
          q("关闭回看", "button secondary", null, () => le.replaceChildren()),
        );
      } catch (K) {
        z === s.revisionRequest &&
          (g.textContent = `回看未能加载：${K.message}`);
      }
    }
    function ft(N) {
      (we.replaceChildren(),
        N.history.length || we.append(e("p", "muted", "尚无保存的修订。")));
      for (const z of N.history)
        we.append(
          q(
            `v${z.version} · ${Ve(z.created_at, !0)}`,
            "button secondary small",
            null,
            () => At(z.version),
          ),
        );
    }
    async function ot() {
      const N = (s.loadRequest = (s.loadRequest || 0) + 1);
      try {
        const z = await t(`/api/events/${encodeURIComponent(c)}/dossier`);
        if (N !== s.loadRequest) return null;
        (s.dirty ||
          (Ue(z.fields),
          (s.version = z.version),
          (g.textContent = z.version
            ? `已保存 v${z.version} · 可回看、撤回或选择导出用途`
            : "尚未保存研判，可先写“我尚不知道”。")),
          (s.savedFields = z.fields),
          (s.savedEvidence = z.evidence),
          s.exportPinned || (s.exportVersion = s.version),
          nt(z.evidence),
          Ee(L.review_on.value, s.dirty));
        for (const K of Object.values(L)) K.disabled = !1;
        return (ft(z), ze(!1), z);
      } catch (z) {
        return (
          N === s.loadRequest &&
            ((g.textContent = `研判未能加载：${z.message}`), ze(!1)),
          null
        );
      }
    }
    function xn(N, z) {
      return N?.code === "dossier_plan_required" || N?.status === 403
        ? "当前权限不足（可能为 Free）：保存版本导出仅供 Pro/Analyst 内测使用；没有支付或自动升级入口。"
        : N?.code === "revision_missing" || N?.status === 404
          ? "找不到这份已保存修订；请刷新研判并重新选择版本，不会改用其他版本。"
          : N?.status === 401
            ? "会话已过期，请重新登录后主动重试；没有导出任何文本。"
            : z === "share" &&
                (N?.status === 400 ||
                  N?.status === 409 ||
                  N?.status === 422 ||
                  /(?:judgment|share|dossier_fields)/i.test(N?.code || ""))
              ? `对外核对摘要被拒绝：请确认已保存原创判断有效、非误判/撤回，且来源可公开核对；${N.message || "请核对判断和版本后重试。"}`
              : `导出未完成：${N?.message || "请检查连接和已保存版本后重试。"}`;
    }
    function kn(N, z) {
      if (
        (N?.format ?? N?.export_format) !== "share" ||
        N?.event_id !== c ||
        N?.version !== z ||
        typeof N?.text != "string" ||
        !N.text.trim()
      )
        throw new Error(
          "服务器未明确返回此事件/版本的 share 安全版；已阻止复制/下载，不会回退到含原文个人归档。",
        );
      const K = z === s.version ? s.savedEvidence : s.revisionEvidence.get(z);
      if (
        /FRONTIER 个人研究卡|保存时的引用与原文|站内详情：\/\?event=/.test(
          N.text,
        ) ||
        (K?.records || []).some(
          (ee) =>
            typeof ee.text == "string" &&
            ee.text.length >= 12 &&
            N.text.includes(ee.text),
        )
      )
        throw new Error(
          "摘要疑似包含私人归档或完整采集原文；已阻止复制/下载，请先核对服务端输出。",
        );
      return N.text;
    }
    async function qt(N, z) {
      if (s.busy || s.exportMode !== z) return;
      const K = s.exportVersion;
      if (!K) {
        g.textContent =
          "尚无已保存版本。请先填写人工判断并保存修订，之后再主动选择复制或下载。";
        return;
      }
      if (z === "share") {
        const ee = K === s.version ? s.savedFields : s.revisionFields.get(K),
          De = ee?.judgment?.trim();
        if (ee && !De) {
          g.textContent =
            "已保存的判断为空，无法生成对外核对摘要。请先填写本人原创判断并保存新修订，不能用自动摘要冒充人工核证。";
          return;
        }
        if (De && /^已撤回\s*v\d+\s*判断/.test(De)) {
          g.textContent =
            "本修订明确撤回了此前判断，不能将它作为对外有效结论。请先亲核证据、写下新的原创判断并保存修订。";
          return;
        }
      }
      ze(!0);
      try {
        const ee = `/api/events/${encodeURIComponent(c)}/dossier/revisions/${K}/export${z === "share" ? "?format=share" : ""}`,
          De = await t(ee),
          Ie = z === "share" ? kn(De, K) : De?.text;
        if (typeof Ie != "string" || !Ie.trim())
          throw new Error("服务器没有返回可用的导出文本。");
        const Ge = z === "share" ? "对外核对摘要" : "含原文个人完整归档";
        if (N) {
          const Oe = URL.createObjectURL(
              new Blob([Ie], { type: "text/plain;charset=utf-8" }),
            ),
            Je = e("a");
          ((Je.href = Oe),
            (Je.download =
              z === "share"
                ? `frontier-share-check-v${K}.txt`
                : `frontier-research-v${K}.txt`),
            f.append(Je),
            Je.click(),
            Je.remove(),
            setTimeout(() => URL.revokeObjectURL(Oe), 1e3),
            (g.textContent = `已下载${Ge} v${K}${s.dirty ? "；当前草稿未保存" : ""}。尚未完成事实核证/清权，不代表允许对外发送。`));
        } else
          try {
            (await navigator.clipboard.writeText(Ie),
              (g.textContent = `已复制${Ge} v${K}${s.dirty ? "；当前草稿未保存" : ""}。尚未完成事实核证/清权，不代表允许对外发送。`));
          } catch {
            const Oe = e("textarea", "dossier-copy");
            ((Oe.readOnly = !0),
              (Oe.value = Ie),
              Oe.setAttribute("aria-label", `${Ge}纯文本，可手动复制`),
              le.replaceChildren(Oe),
              Oe.focus(),
              Oe.select(),
              (g.textContent = `${Ge}自动复制不可用，请手动复制下方纯文本；核查事实、版权和许可前不要对外发送。`));
          }
      } catch (ee) {
        g.textContent = xn(ee, z);
      } finally {
        ze(!1);
      }
    }
    return (
      (pe.onsubmit = async (N) => {
        if ((N.preventDefault(), s.busy || s.version == null)) return;
        const z = Se();
        ((s.loadRequest = (s.loadRequest || 0) + 1),
          ze(!0),
          (g.textContent = "正在保存新修订…"));
        try {
          const K = await t(`/api/events/${encodeURIComponent(c)}/dossier`, {
            method: "PUT",
            body: JSON.stringify({ version: s.version, fields: z }),
          });
          ((s.version = K.version),
            (s.dirty = JSON.stringify(z) !== JSON.stringify(Se())),
            (s.exportVersion = K.version),
            (s.exportPinned = !1),
            (s.savedFields = z),
            (s.savedEvidence = K.evidence),
            (se.hidden = !0),
            (X.hidden = !0),
            (ie.value = ""),
            (g.textContent = `已保存 v${K.version}${s.dirty ? "；之后的输入仍是草稿" : ""}`),
            await ot());
        } catch (K) {
          if (
            ((g.textContent = `保存未完成，草稿仍保留：${K.message}`),
            K.status === 409)
          ) {
            ((s.dirty = !0),
              (se.hidden = !1),
              se.replaceChildren(
                e(
                  "p",
                  "",
                  "其他会话已有新修订。先回看最新内容，再在草稿中合并。",
                ),
              ));
            const ee = await ot();
            ee &&
              se.append(
                q(`查看远端 v${ee.version}`, "button secondary", null, () =>
                  At(ee.version),
                ),
                q(
                  "已核对，以最新版本继续编辑",
                  "button secondary",
                  null,
                  () => {
                    ((s.version = ee.version),
                      (se.hidden = !0),
                      (g.textContent = `草稿已保留，以 v${ee.version} 为基线；合并后再次保存。`));
                  },
                ),
              );
          }
        } finally {
          ze(!1);
        }
      }),
      (s.load = ot),
      We(),
      ot(),
      f
    );
  }
  return {
    mount: l,
    refresh(c) {
      const f = o.get(c);
      f && !f.busy && f.load();
    },
  };
}
function gr({
  api: t,
  getSettings: a,
  onRead: o,
  onBookmark: l,
  onLocate: c,
  onClosed: f,
}) {
  const m = br({ api: t });
  let s = null,
    g = 0,
    h = null,
    k = null,
    Y = null;
  function G(R) {
    const ne = R.querySelector("h3") || R;
    function ae() {
      const fe = window.visualViewport;
      let me = fe?.offsetTop || 0,
        E = fe?.offsetLeft || 0,
        j = me + (fe?.height || window.innerHeight),
        re = E + (fe?.width || window.innerWidth);
      for (let F = ne.parentElement; F; F = F.parentElement) {
        const I = getComputedStyle(F),
          W = F.getBoundingClientRect();
        (/auto|scroll|hidden|clip/.test(I.overflowY) &&
          ((me = Math.max(me, W.top + F.clientTop)),
          (j = Math.min(j, W.top + F.clientTop + F.clientHeight))),
          /auto|scroll|hidden|clip/.test(I.overflowX) &&
            ((E = Math.max(E, W.left + F.clientLeft)),
            (re = Math.min(re, W.left + F.clientLeft + F.clientWidth))));
      }
      const A = i(".sidebar");
      A &&
        getComputedStyle(A).position === "fixed" &&
        (j = Math.min(j, A.getBoundingClientRect().top));
      const _ = R.getBoundingClientRect(),
        P = _.height <= j - me && _.width <= re - E ? R : ne,
        C = P.getBoundingClientRect();
      return {
        element: P,
        x: C.left < E ? C.left - E : Math.max(0, C.right - re),
        y: C.top < me ? C.top - me : Math.max(0, C.bottom - j),
      };
    }
    const ye = ae(),
      ge = ye.x === 0 && ye.y === 0;
    if ((R.focus({ preventScroll: ge }), !ge)) {
      ye.element.scrollIntoView({ block: "nearest", inline: "nearest" });
      for (let fe = ne.parentElement; fe; fe = fe.parentElement) {
        const me = ae();
        if (me.x === 0 && me.y === 0) break;
        const E = getComputedStyle(fe),
          j = fe === document.scrollingElement;
        (me.y &&
          fe.scrollHeight > fe.clientHeight &&
          (j || /auto|scroll/.test(E.overflowY)) &&
          (fe.scrollTop += me.y),
          me.x &&
            fe.scrollWidth > fe.clientWidth &&
            (j || /auto|scroll/.test(E.overflowX)) &&
            (fe.scrollLeft += me.x));
      }
    }
  }
  function pe() {
    if (h !== document.body && Et(h)) {
      G(h);
      return;
    }
    const R = Y ? document.getElementById(Y) : null,
      ne = [
        "timeline-list",
        "event-list",
        "inbox-list",
        "cluster-content",
        "radar-pane",
      ]
        .map((ge) => document.getElementById(ge))
        .filter(Et),
      ae = Et(R) ? [R] : ne;
    for (const ge of ae) {
      const fe = Ne(".event-card, .radar-highlight-card", ge)
        .find((me) => me.dataset.id === k && Et(me))
        ?.querySelector(".event-open, .radar-event-open");
      if (Et(fe)) {
        G(fe);
        return;
      }
    }
    const ye =
      ae[0] ||
      ["radar-new", "nav-radar", "view-timeline", "view-globe", "nav-feed"]
        .map((ge) => document.getElementById(ge))
        .find(Et);
    ye &&
      (!ye.hasAttribute("tabindex") &&
        !ye.matches("button, a[href]") &&
        (ye.tabIndex = -1),
      G(ye));
  }
  function L() {
    if (i("#detail-dialog")) return;
    const R = e("dialog", "detail-dialog");
    ((R.id = "detail-dialog"),
      R.setAttribute("aria-labelledby", "detail-title"),
      (R.innerHTML = `<div class="detail-topbar"><span class="detail-top-label">资讯详情</span><div class="detail-top-actions"><button id="detail-copy" class="icon-button" aria-label="复制此资讯链接" title="复制资讯链接">${te("external")}</button><button class="icon-button" data-close aria-label="关闭资讯详情">${te("close")}</button></div></div><div id="detail-content" class="detail-content"></div>`),
      document.body.append(R),
      ct(R, {
        onClose: () => {
          (g++, (s = null), f?.(), pe());
        },
      }),
      (i("#detail-copy").onclick = async () => {
        if (!s) return;
        const ne = new URL(location.href);
        ne.searchParams.set("event", s.id);
        try {
          (await navigator.clipboard.writeText(ne.href), $e("资讯链接已复制"));
        } catch {
          $e("浏览器未允许复制链接，请使用地址栏分享。");
        }
      }));
  }
  function B(R) {
    ma(sn(s), R, s?.title || "来源图片");
  }
  function O(R, ne) {
    const ae = e("section", "detail-section");
    return (ae.append(e("h3", "", R), ne), ae);
  }
  function de(R) {
    const ne = i("#detail-content"),
      ae = ne.dataset.id === R.id,
      ye = ne.scrollTop,
      ge = ae ? Ne(".source-text", ne).map((J) => J.open) : [];
    (ne.replaceChildren(), (ne.dataset.id = R.id));
    const fe = e("div", "detail-category-line");
    (fe.append(e("span", "category-label", nn(R.category))),
      R.archived && fe.append(e("span", "state-badge archived", "已归档")));
    const me = e("h1", "detail-title", R.title || "未命名资讯");
    me.id = "detail-title";
    const E = [...new Set((R.sources || []).map((J) => Ke(J.platform)))],
      j = e(
        "div",
        "detail-byline",
        `${E.join(" · ") || "来源待整理"} · 关联 ${R.sources?.length || 0} 条原始记录 · 独立性未核实`,
      );
    ne.append(fe, me, j);
    const re = e("div", "detail-actions"),
      A = q("", "button secondary small", "read");
    ((A.id = "detail-read"),
      (A.onclick = () => o(s, !Me(s), { automatic: !1 })));
    const _ = q("", "button secondary small", "bookmark");
    ((_.id = "detail-bookmark"), (_.onclick = () => l(s)));
    const P = q("在地球上定位", "button secondary small", "pin", () => {
      const J = s;
      (i("#detail-dialog").close(), c(J));
    });
    P.disabled = !Kt(R).length;
    const C = q("核对原文并研判", "button primary small", null, () => {
      const J = ne.querySelector(".dossier");
      J &&
        (J.scrollIntoView({ block: "start", behavior: "smooth" }),
        J.focus({ preventScroll: !0 }));
    });
    (re.append(A, _, P, C), ne.append(re));
    const F = a().show_images ? sn(R) : [];
    if (F.length) {
      const J = e("section", "detail-gallery");
      J.setAttribute("aria-label", `来源图片，共 ${F.length} 张`);
      const se = e("button", "detail-media-lead media-thumb");
      ((se.type = "button"),
        (se.dataset.index = "0"),
        se.setAttribute(
          "aria-label",
          `放大${F[0].kind === "thumbnail" ? "视频封面" : "来源图片"}，共 ${F.length} 张`,
        ),
        se.append(Pt(F[0], R.title, "", !0)),
        (se.onclick = () => B(0)));
      const Te = e(
        "span",
        "media-count",
        `${F[0].kind === "thumbnail" ? "视频封面" : "来源附图"}${F.length > 1 ? ` · ${F.length} 张` : ""}`,
      );
      if ((se.append(Te), J.append(se), F.length > 1)) {
        const we = e("div", "media-strip");
        (F.forEach((le, Se) => {
          const Ue = e("button", "media-thumb gallery-thumb");
          ((Ue.type = "button"),
            (Ue.dataset.index = String(Se)),
            Ue.setAttribute("aria-label", `查看第 ${Se + 1} 张图片`),
            Ue.append(Pt(le, `第 ${Se + 1} 张来源图片`)),
            (Ue.onclick = () => B(Se)),
            we.append(Ue));
        }),
          J.append(we));
      }
      ne.append(J);
    } else
      a().show_images &&
        R.media?.some((J) => J.status === "pending") &&
        ne.append(
          e("p", "media-pending", "来源图片正在准备，原文链接仍可打开。"),
        );
    R.summary && ne.append(e("p", "detail-summary", R.summary));
    const I = e("dl", "detail-facts");
    for (const [J, se, Te] of [
      [
        "事件发生时间",
        rn(R),
        {
          explicit: "原文明确",
          inferred: "依据上下文推定",
          scheduled: "计划发生，尚未确认完成",
          unknown: "没有足够的时间依据",
        }[R.event_time_status] || "时间依据待确认",
      ],
      [
        "发生或影响地区",
        En(R),
        Kt(R)
          .map(
            (we) =>
              ({
                city: "城市级",
                country: "国家级",
                region: "地区级",
                exact: "具体地点",
                approximate: "近似位置",
              })[we.precision] || "原文提及",
          )
          .join(" · ") || "没有足够的地点依据",
      ],
      ["原始发布时间", Ve(R.source_published_at, !0), "消息或视频的发布时刻"],
      [
        "首次收录",
        Ve(R.first_ingested_at || R.ingested_at, !0),
        "首次进入本站的时刻",
      ],
    ]) {
      const we = e("div");
      (we.append(e("dt", "", J), e("dd", "", se), e("small", "muted", Te)),
        I.append(we));
    }
    ne.append(I);
    const W = e("details", "evidence-details");
    if (
      (W.append(e("summary", "", "查看时间与地理依据")),
      R.event_time_evidence || R.event_time_note)
    ) {
      const J = e("div");
      (R.event_time_evidence &&
        J.append(e("blockquote", "evidence-quote", R.event_time_evidence)),
        R.event_time_note &&
          J.append(e("p", "event-time-note muted", R.event_time_note)),
        W.append(O("时间依据", J)));
    }
    const Q = Kt(R).filter((J) => J.evidence);
    if (Q.length) {
      const J = e("div");
      for (const se of Q) {
        const Te = e("p");
        (Te.append(
          e("strong", "", `${se.name || "地点"}：`),
          document.createTextNode(se.evidence),
        ),
          J.append(Te));
      }
      W.append(O("地理依据", J));
    }
    (!R.event_time_evidence &&
      !R.event_time_note &&
      !Q.length &&
      W.append(
        e(
          "p",
          "muted",
          "原文尚不足以确定事件时间或地理位置，未使用来源发布时间或作者所在地代替。",
        ),
      ),
      ne.append(W));
    const he = e("section", "detail-scoring"),
      X = e("div", "score-heading"),
      H = e("div");
    (H.append(e("strong", "", String(Lt(R))), e("span", "", "/ 100")),
      X.append(e("h3", "", "重要度"), H),
      he.append(
        X,
        e("p", "", R.score_reason || "用于阅读优先级，不代表事实真实性。"),
      ));
    const ie = e("details");
    ie.append(e("summary", "", "查看评分分项"));
    for (const [J, se] of [
      ["impact", "影响程度"],
      ["scope", "影响范围"],
      ["novelty", "新颖程度"],
      ["urgency", "时效程度"],
    ]) {
      if (R.score_components?.[J] == null) continue;
      const Te = e("div", "score-row"),
        we = e("progress");
      ((we.max = 100),
        (we.value = an(R.score_components[J], 0, 100)),
        we.setAttribute("aria-label", se),
        Te.append(
          e("span", "", se),
          we,
          e("span", "", String(Math.round(we.value))),
        ),
        ie.append(Te));
    }
    if ((he.append(ie), ne.append(he), R.tags?.length)) {
      const J = e("div", "detail-tags");
      (R.tags.forEach((se) => J.append(e("span", "", se))), ne.append(J));
    }
    const qe = e("div", "detail-sources");
    for (const J of R.sources || []) {
      const se = e("article", "detail-source"),
        Te = e("div", "detail-source-heading"),
        we = e("div");
      (we.append(
        e("span", "source-platform", Ke(J.platform)),
        e("strong", "", J.name || Ke(J.platform)),
      ),
        Te.append(we));
      const le = Rn(J.url);
      if (le) {
        const Se = e("a", "source-link");
        ((Se.href = le),
          (Se.target = "_blank"),
          (Se.rel = "noopener noreferrer"),
          Se.append(document.createTextNode("打开原文 ")));
        const Ue = e("span");
        ((Ue.innerHTML = te("external")), Se.append(Ue), Te.append(Se));
      } else Te.append(e("span", "muted", "安全原文链接不可用"));
      if (
        (se.append(
          Te,
          e("p", "source-published", `发布于 ${Ve(J.published_at, !0)}`),
        ),
        se.append(
          e(
            "p",
            "dossier-fingerprint",
            `原始记录：${J.id} · 研判引用编号以证据卡冻结快照为准 · 链接可达性未检查`,
          ),
        ),
        J.text)
      ) {
        se.append(e("blockquote", "evidence-quote", J.text.slice(0, 280)));
        const Se = e("details", "source-text");
        (Se.append(
          e("summary", "", "阅读完整原始内容"),
          e("p", "source-raw-text", J.text),
        ),
          se.append(Se));
      } else se.append(e("p", "muted", "原文正文缺失，不能据此声称已核实。"));
      qe.append(se);
    }
    (ne.append(O(`原始来源 · ${y(R.sources?.length || 0)}`, qe)),
      ne.append(
        e(
          "p",
          "detail-note",
          `已关联 ${R.sources?.length || 0} 条原始记录，独立性尚未核验，多条记录不代表多个独立证实。摘要、时间、地点与重要度来自自动辅助整理，不是经过人工事实核实；阅读时请展开原文、交叉核对依据。`,
        ),
      ),
      ne.append(m.mount(R.id)),
      ce(),
      ae
        ? (Ne(".source-text", ne).forEach((J, se) => {
            J.open = !!ge[se];
          }),
          (ne.scrollTop = ye))
        : (ne.scrollTop = 0));
  }
  function ce() {
    if (!s || !i("#detail-read")) return;
    const R = Me(s),
      ne = i("#detail-read");
    ((ne.innerHTML = te(R ? "unread" : "check")),
      ne.append(e("span", "", R ? "标为未读" : "标为已读")),
      ne.setAttribute("aria-pressed", String(R)));
    const ae = !!s.bookmarked,
      ye = i("#detail-bookmark");
    ((ye.innerHTML = te(ae ? "check" : "bookmark")),
      ye.append(e("span", "", ae ? "已收藏" : "收藏")),
      ye.setAttribute("aria-pressed", String(ae)),
      ye.classList.toggle("selected", ae),
      ue(".detail-top-label", R ? "资讯详情 · 已读" : "资讯详情 · 未读"));
  }
  async function _e(R, ne) {
    L();
    const ae = ++g;
    (i("#detail-dialog").open ||
      ((h = document.activeElement),
      (Y =
        h?.closest(
          "#event-list, #timeline-list, #inbox-list, #cluster-content, #radar-pane",
        )?.id || null)),
      (k = String(R)),
      m.refresh(R),
      i("#cluster-dialog")?.close(),
      // A provisional list item may omit `id`; bind only the verified route ID
      // before dossier.mount() can issue its first native GET.
      (s =
        ne && (ne.id == null || String(ne.id) === String(R))
          ? { ...ne, id: String(R) }
          : null),
      s
        ? de(s)
        : i("#detail-content").replaceChildren(
            e("p", "panel-loading", "正在载入资讯详情…"),
          ),
      ut(i("#detail-dialog")),
      (i("#detail-content").scrollTop = 0));
    try {
      const ye = await t(`/api/events/${encodeURIComponent(R)}`);
      if (ae !== g || !i("#detail-dialog").open) return;
      const event = ye.item || ye;
      // The source DB can return a valid event detail with no `id` in its
      // JSON `data`. Never pass undefined to dossier.mount(): use the actual
      // requested deep-link ID, but reject an explicitly conflicting ID.
      if (
        !event ||
        typeof event !== "object" ||
        (event.id != null && String(event.id) !== String(R))
      )
        throw new Error("事件详情 ID 与请求不一致，已停止载入个人研判。");
      ((s = { ...event, id: String(R) }),
        de(s),
        // A Top3 -> personal dossier deep link is for verification/review only.
        // Its explicit same-origin from=daily route never silently marks read;
        // all other native event opens retain the user's auto-read preference.
        a().auto_mark_read &&
          new URLSearchParams(window.location.search).get("from") !== "daily" &&
          !Me(s) &&
          (await o(s, !0, { automatic: !0 })));
    } catch (ye) {
      if (ae !== g || ye.status === 401) return;
      if (s) $e(`详情未能刷新，保留已载入内容。${ye.message}`);
      else {
        const ge = e("div", "empty-state");
        (ge.append(
          e("h3", "", "资讯详情暂不可用"),
          e("p", "", ye.message),
          q("重新加载", "button secondary", "refresh", () => _e(R)),
        ),
          i("#detail-content").replaceChildren(ge));
      }
    }
  }
  return {
    open: _e,
    current: () => s,
    update(R) {
      s?.id === R.id && (Object.assign(s, R), ce());
    },
    close() {
      i("#detail-dialog")?.close();
    },
    rerender() {
      s && i("#detail-dialog")?.open && de(s);
    },
  };
}
const ra = {
  pending: "等待整理",
  processing: "正在整理",
  completed: "已整理为事件",
  filtered: "原文保留",
  failed: "整理需重试",
  video_processing: "视频处理中",
};
function vr({
  api: t,
  getSettings: a,
  beforeFetch: o,
  syncPolicy: l,
  onEvent: c,
  onReadingChanged: f,
}) {
  let m,
    s = [],
    g = 0,
    h = new Set(),
    k = null,
    Y = !1,
    G = 0,
    pe,
    L = 0,
    B = null;
  const O = new Set(),
    de = {
      q: "",
      source: "",
      read: "",
      scope: "active",
      sort: "discovered",
      state: "all",
    };
  function ce(E = 0) {
    const j = new URLSearchParams({ limit: "100", offset: String(E) });
    for (const [re, A] of Object.entries(de)) A && j.set(re, A);
    return j;
  }
  function _e() {
    ((m.innerHTML = `<div class="inbox-intro"><div><h2>原始收件箱</h2><p>实时阅读刚采集的原文与图片，不需要等待事件整理。这里按原始发布或本站收录时间排列。</p></div><button id="inbox-refresh" class="button secondary">${te("refresh")}<span>刷新</span></button></div>
      <div class="inbox-toolbar"><label class="search-field">${te("search")}<input id="inbox-search" type="search" placeholder="搜索原始消息" aria-label="搜索原始消息" maxlength="200"/></label><select id="inbox-platform" aria-label="收件箱来源平台"><option value="">全部平台</option><option value="telegram">Telegram</option><option value="x">X</option><option value="youtube">YouTube</option></select><select id="inbox-state" aria-label="原文整理状态"><option value="all">全部整理状态</option><option value="pending">等待整理</option><option value="processing">正在整理</option><option value="completed">已整理为事件</option><option value="video_processing">视频处理中</option><option value="filtered">原文保留</option><option value="failed">整理需重试</option></select><select id="inbox-read" aria-label="原文阅读状态"><option value="">按阅读设置</option><option value="all">全部</option><option value="unread">未读</option><option value="read">已读</option></select><select id="inbox-scope" aria-label="原文阅读窗口"><option value="active">当前阅读窗口</option><option value="all">全部时间</option><option value="archive">已归档</option></select><select id="inbox-sort" aria-label="原文排序"><option value="discovered">最近收录</option><option value="published">原始发布时间</option></select></div>
      <div class="inbox-list-tools"><label class="checkbox-label"><input id="inbox-select-all" type="checkbox"/>选择已加载消息</label><span id="inbox-selection" class="muted"></span><button id="inbox-bulk-read" class="text-button">标为已读</button><button id="inbox-bulk-unread" class="text-button">标为未读</button><span id="inbox-policy" class="policy-note"></span></div>
      <div id="inbox-list" class="inbox-list" tabindex="-1" aria-label="原始消息列表"></div><div class="inbox-footer"><span id="inbox-count"></span><button id="inbox-more" class="button secondary" hidden>加载更多</button></div>`),
      (i("#inbox-search").value = de.q));
    for (const [E, j] of [
      ["platform", "source"],
      ["read", "read"],
      ["scope", "scope"],
      ["sort", "sort"],
      ["state", "state"],
    ])
      ((i(`#inbox-${E}`).value = de[j]),
        (i(`#inbox-${E}`).onchange = (re) => {
          ((de[j] = re.target.value), h.clear(), ae());
        }));
    ((i("#inbox-search").oninput = (E) => {
      (clearTimeout(pe),
        (pe = setTimeout(() => {
          ((de.q = E.target.value.trim()), h.clear(), ae());
        }, 300)));
    }),
      (i("#inbox-refresh").onclick = () => ae()),
      (i("#inbox-more").onclick = () => ae(!0)),
      (i("#inbox-select-all").onchange = (E) => {
        ((h = E.target.checked ? new Set(s.map((j) => j.id)) : new Set()),
          ne());
      }),
      (i("#inbox-bulk-read").onclick = () => me([...h], !0)),
      (i("#inbox-bulk-unread").onclick = () => me([...h], !1)),
      ne());
  }
  function R() {
    (ue("#inbox-selection", h.size ? `已选 ${y(h.size)} 条` : ""),
      (i("#inbox-bulk-read").disabled = !h.size),
      (i("#inbox-bulk-unread").disabled = !h.size));
    const E = i("#inbox-select-all");
    ((E.checked = s.length > 0 && h.size === s.length),
      (E.indeterminate = h.size > 0 && h.size < s.length));
  }
  function ne() {
    const E = i("#inbox-list");
    if (!E) return;
    const j = E.scrollTop;
    (E.replaceChildren(),
      !s.length &&
        !Y &&
        E.append(
          it(
            "这个范围内没有原始消息",
            de.read === "unread" || (!de.read && a().hide_read)
              ? "可以切换全部阅读状态，或查看全部时间。新的采集内容会出现在这里。"
              : "调整关键词、平台或阅读窗口。新消息会在采集完成后进入收件箱。",
            {
              label: "查看全部时间",
              run: () => {
                ((de.scope = "all"),
                  (de.read = "all"),
                  (i("#inbox-scope").value = "all"),
                  (i("#inbox-read").value = "all"),
                  ae());
              },
            },
          ),
        ));
    for (const _ of s) {
      const P = e("article", `inbox-item${Me(_) ? " is-read" : ""}`);
      P.dataset.id = _.id;
      const C = e("input", "inbox-checkbox");
      ((C.type = "checkbox"),
        (C.checked = h.has(_.id)),
        C.setAttribute(
          "aria-label",
          `选择原文：${_.title || _.text?.slice(0, 40) || Ke(_.platform)}`,
        ),
        (C.onchange = () => {
          (C.checked ? h.add(_.id) : h.delete(_.id), R());
        }));
      const F = e("div", "inbox-item-content"),
        I = e("button", "inbox-open");
      ((I.type = "button"),
        I.setAttribute(
          "aria-label",
          `阅读原文：${_.title || _.text?.slice(0, 40) || Ke(_.platform)}`,
        ));
      const W = e("div", "inbox-item-copy"),
        Q = e("div", "inbox-item-top");
      Q.append(
        e("span", "source-platform", Ke(_.platform)),
        e("span", "inbox-source-name", _.name || Ke(_.platform)),
        e("span", `state-badge ${_.state}`, ra[_.state] || "等待整理"),
      );
      const he =
        _.title ||
        _.text
          ?.split(
            `
`,
          )
          .find((qe) => qe.trim()) ||
        "原始消息";
      (W.append(Q, e("h3", "", he)),
        _.text && _.text !== he && W.append(e("p", "inbox-excerpt", _.text)),
        I.append(W));
      const X = a().show_images ? sn(_) : [];
      if (X.length) {
        const qe = Pt(X[0], "", "inbox-image");
        (X.length > 1 && qe.append(e("span", "media-count", `${X.length} 张`)),
          I.append(qe));
      }
      ((I.onclick = () => fe(_.id)), F.append(I));
      const H = e("div", "inbox-item-bottom");
      H.append(
        e("span", "", `发布 ${Ve(_.source_published_at, !0)}`),
        e("span", "", `收录 ${hn(_.first_ingested_at || _.ingested_at)}`),
      );
      const ie = q(
        Me(_) ? "标为未读" : "标为已读",
        "text-button inbox-read-button",
        Me(_) ? "unread" : "check",
        () => me([_.id], !Me(_)),
      );
      (H.append(ie), F.append(H), P.append(C, F), E.append(P));
    }
    ((E.scrollTop = j),
      ue("#inbox-count", `已加载 ${y(s.length)} / ${y(g)} 条原始消息`),
      (i("#inbox-more").hidden = s.length >= g));
    const re = a(),
      A = B?.effective_read || de.read || (re.hide_read ? "unread" : "all");
    ((i("#inbox-read").options[0].text =
      (B?.hide_read ?? re.hide_read) ? "未读" : "全部"),
      ue(
        "#inbox-policy",
        `${de.scope === "all" ? "全部时间" : de.scope === "archive" ? "超出保留窗口，可恢复" : bn(B?.retention_days ?? re.retention_days, B?.retention_basis || re.retention_basis)} · ${A === "unread" ? "仅未读" : A === "read" ? "仅已读" : "全部阅读状态"}`,
      ),
      R());
  }
  async function ae(E = !1) {
    const j = ++G;
    ((Y = !0),
      i("#inbox-list")?.setAttribute("aria-busy", "true"),
      i("#inbox-more") && (i("#inbox-more").disabled = !0),
      s.length ||
        i("#inbox-list")?.replaceChildren(
          e("p", "panel-loading", "正在读取原始消息…"),
        ));
    try {
      if ((await o?.(), j !== G)) return;
      const re = `/api/inbox?${ce(E ? s.length : 0)}`;
      let A = await t(re);
      if (
        ((await l?.(A.policy)) && (A = await t(re)),
        E &&
          B &&
          A.policy &&
          [
            "retention_days",
            "retention_basis",
            "hide_read",
            "retain_bookmarks",
            "effective_read",
            "scope",
          ].some((P) => B[P] !== A.policy[P]) &&
          ((E = !1), (A = await t(`/api/inbox?${ce()}`))),
        j !== G)
      )
        return;
      B = A.policy || null;
      const _ = Array.isArray(A.items) ? A.items : [];
      ((s = E ? [...s, ..._.filter((P) => !s.some((C) => C.id === P.id))] : _),
        (g = Number(A.total) || 0),
        (h = new Set([...h].filter((P) => s.some((C) => C.id === P)))),
        (Y = !1),
        ne());
    } catch (re) {
      if (j !== G || re.status === 401) return;
      s.length
        ? $e(re.message)
        : i("#inbox-list")?.replaceChildren(
            it("收件箱暂不可用", re.message, {
              label: "重试",
              run: () => ae(),
            }),
          );
    } finally {
      j === G &&
        ((Y = !1),
        i("#inbox-list")?.setAttribute("aria-busy", "false"),
        i("#inbox-more") && (i("#inbox-more").disabled = !1));
    }
  }
  function ye() {
    if (i("#inbox-dialog")) return;
    const E = e("dialog", "detail-dialog inbox-dialog");
    ((E.id = "inbox-dialog"),
      E.setAttribute("aria-labelledby", "inbox-detail-title"),
      (E.innerHTML = `<div class="detail-topbar"><span>原始消息</span><button class="icon-button" data-close aria-label="关闭原文详情">${te("close")}</button></div><div id="inbox-detail-content" class="detail-content"></div>`),
      document.body.append(E),
      ct(E, {
        onClose: () => {
          ((k = null),
            L++,
            document.activeElement === document.body &&
              i("#inbox-list")?.focus({ preventScroll: !0 }));
        },
      }));
  }
  function ge() {
    if (!k) return;
    const E = k,
      j = i("#inbox-detail-content"),
      re = j.scrollTop;
    j.replaceChildren();
    const A = e(
      "h1",
      "detail-title",
      E.title ||
        E.text
          ?.split(
            `
`,
          )
          .find((W) => W.trim()) ||
        "原始消息",
    );
    ((A.id = "inbox-detail-title"),
      j.append(
        e("div", "detail-byline", `${Ke(E.platform)} · ${E.name || ""}`),
        A,
        e("span", `state-badge ${E.state}`, ra[E.state] || "等待整理"),
      ));
    const _ = e("div", "detail-actions"),
      P = q(
        Me(E) ? "标为未读" : "标为已读",
        "button secondary small",
        Me(E) ? "unread" : "check",
        () => me([E.id], !Me(E)),
      );
    ((P.id = "inbox-detail-read"), (P.disabled = O.has(E.id)), _.append(P));
    const C = Fn(E.url);
    if (C) {
      const W = e("a", "button secondary small", "打开原文");
      ((W.href = C),
        (W.target = "_blank"),
        (W.rel = "noopener noreferrer"),
        _.append(W));
    }
    (E.event_id &&
      _.append(
        q("查看整理后的事件", "button primary small", "arrow", () => {
          const W = E.event_id;
          (i("#inbox-dialog").close(), c(W));
        }),
      ),
      j.append(_));
    const F = e("div", "raw-time-facts");
    (F.append(
      e("span", "", `原始发布 ${Ve(E.source_published_at, !0)}`),
      e("span", "", `首次收录 ${Ve(E.first_ingested_at || E.ingested_at, !0)}`),
    ),
      j.append(F));
    const I = a().show_images ? sn(E) : [];
    if (I.length) {
      const W = e("div", "inbox-media-grid");
      for (const [Q, he] of I.entries()) {
        const X = e("button", "inbox-media-original");
        ((X.type = "button"),
          (X.onclick = () => ma(I, Q, E.title || "原始消息附图")),
          X.setAttribute("aria-label", `打开第 ${Q + 1} 张原图`),
          X.append(
            Pt(
              he,
              he.kind === "thumbnail" ? "视频封面" : `原文第 ${Q + 1} 张附图`,
              "",
              Q === 0,
            ),
          ),
          W.append(X));
      }
      j.append(W);
    }
    (j.append(
      e(
        "p",
        "raw-message-text",
        E.text || "原文暂无文本内容，请通过来源链接查看。",
      ),
    ),
      j.append(
        e(
          "p",
          "detail-note",
          "这里展示采集到的原始消息。整理状态不影响阅读；消息发布时间不等于事件发生时间。",
        ),
      ),
      (j.scrollTop = re));
  }
  async function fe(E) {
    ye();
    const j = ++L;
    ((k = s.find((re) => re.id === E) || null),
      k
        ? ge()
        : i("#inbox-detail-content").replaceChildren(
            e("p", "panel-loading", "正在读取原文…"),
          ),
      ut(i("#inbox-dialog")),
      (i("#inbox-detail-content").scrollTop = 0));
    try {
      const re = await t(`/api/inbox/${encodeURIComponent(E)}`);
      if (j !== L || !i("#inbox-dialog")?.open) return;
      ((k = re.item || re),
        ge(),
        a().auto_mark_read && !Me(k) && (await me([E], !0, !0)));
    } catch (re) {
      re.status !== 401 && $e(re.message);
    }
  }
  async function me(E, j, re = !1) {
    if (((E = [...new Set(E)].filter((F) => !O.has(F))), !E.length)) return;
    E.forEach((F) => O.add(F));
    const A = E.map((F) => ({
        id: F,
        read: Me(s.find((I) => I.id === F) || (k?.id === F ? k : null)),
      })),
      _ = [];
    let P = null;
    for (let F = 0; F < E.length; F += 200) {
      const I = E.slice(F, F + 200);
      try {
        await t(
          I.length === 1
            ? `/api/inbox/${encodeURIComponent(I[0])}/read`
            : "/api/inbox/read",
          {
            method: I.length === 1 ? "PUT" : "POST",
            body: JSON.stringify(
              I.length === 1 ? { read: j } : { ids: I, read: j },
            ),
          },
        );
      } catch (W) {
        P = W;
        break;
      }
      _.push(...I);
      for (const W of s)
        I.includes(W.id) &&
          ((W.read = j), (W.read_at = j ? new Date().toISOString() : null));
      k &&
        I.includes(k.id) &&
        ((k.read = j), (k.read_at = j ? new Date().toISOString() : null), ge());
      for (const W of I) h.delete(W);
    }
    const C = async () => {
      for (const F of [!0, !1]) {
        const I = A.filter((W) => W.read === F && _.includes(W.id)).map(
          (W) => W.id,
        );
        I.length && (await me(I, F, !0));
      }
    };
    if ((E.forEach((F) => O.delete(F)), k && E.includes(k.id) && ge(), P)) {
      for (const F of E.filter((I) => !_.includes(I))) h.add(F);
      (ne(),
        $e(
          `已处理 ${y(_.length)} / ${y(E.length)} 条，剩余保留选择。${P.message}`,
          _.length ? "撤销已完成部分" : void 0,
          _.length ? C : void 0,
        ));
    } else
      (f?.(),
        await ae(),
        (!re || a().hide_read) &&
          $e(
            j
              ? `${_.length === 1 ? "消息" : `${y(_.length)} 条消息`}已标为已读`
              : "已恢复为未读",
            "撤销",
            C,
          ));
  }
  return {
    async load(E) {
      ((m = E), _e(), await ae());
    },
    refresh() {
      if (m && !m.hidden && !Y) return ae();
    },
    settingsChanged() {
      (i("#inbox-list") && ne(), k && i("#inbox-dialog")?.open && ge());
    },
  };
}
const ia = (t) => String(t ?? "").replace(/[A-Z]/g, (a) => a.toLowerCase());
function yr(t, a) {
  const o =
    typeof a?.query == "string"
      ? a.query.trim().split(/\s+/).filter(Boolean)
      : [];
  if (
    !o.length ||
    !Array.isArray(a?.platforms) ||
    !a.platforms.includes(t?.platform) ||
    typeof t?.text != "string" ||
    typeof t?.title != "string"
  )
    return !1;
  const l = ia(t.title + " " + t.text);
  return o.every((c) => l.includes(ia(c)));
}
function wr({
  api: t,
  onOpenEvent: a,
  occurrenceLabel: o,
  utcLabel: l,
  platformLabel: c,
}) {
  const f = new Map(),
    m = new Map();
  let s = 0;
  const g = (L, B = 6e3) => (typeof L == "string" ? L.slice(0, B) : ""),
    h = (L) => String(L?.id ?? "");
  function k() {
    (s++, f.clear(), m.clear());
  }
  function Y(L, B = !1) {
    const O = f.get(L);
    if (!B && O && Date.now() - O.at < 6e4) return Promise.resolve(O.data);
    if (m.has(L)) return m.get(L);
    const de = s,
      ce = Promise.resolve()
        .then(() => t("/api/events/" + encodeURIComponent(L) + "/dossier"))
        .then((_e) => {
          if (s !== de) throw Error("页面已切换，请重新打开。");
          if (
            String(_e?.event_id ?? "") !== L ||
            !Array.isArray(_e?.evidence?.records)
          )
            throw Error("原文接口返回不完整，不能把摘要当作原文。");
          return (f.set(L, { data: _e, at: Date.now() }), _e);
        })
        .finally(() => {
          m.get(L) === ce && m.delete(L);
        });
    return (m.set(L, ce), ce);
  }
  function G(L, B, O) {
    const de = e("div", "radar-evidence-clock");
    return (de.append(e("dt", "", L), e("dd", "", B), e("small", "", O)), de);
  }
  function pe(L, B, O = !1) {
    const de = h(L),
      ce = e("section", "radar-evidence-workbench");
    ((ce.dataset.evidenceFeatured = String(O)),
      ce.setAttribute("aria-label", "原文、三钟、反证同屏核查"));
    const _e = e("div", "radar-evidence-lane-head");
    _e.append(e("strong", "", "一屏核对 · 原文 / 三钟 / 反证"));
    const R = e("div", "radar-evidence-header-actions"),
      ne = (Array.isArray(L?.sources) ? L.sources : [])
        .map((I) => ({ source: I, url: ht(I?.url) }))
        .find((I) => I.url);
    if (ne) {
      const I = e("a", "radar-evidence-header-link", "开同题原文 ↗");
      ((I.href = ne.url),
        (I.target = "_blank"),
        (I.rel = "noopener noreferrer"),
        (I.title = "服务端词项命中出处；未核实独立性、立场、可达性与授权"),
        R.append(I));
    }
    const ae = q(
      "同屏核对原文与反证",
      "button secondary radar-evidence-toggle",
      null,
    );
    ae.setAttribute("aria-expanded", "false");
    function ye() {
      const I = ce
        .closest(".radar-personal-card")
        ?.querySelector(".radar-decision-controls [data-radar-decision]");
      (I?.focus({ preventScroll: !1 }),
        I?.scrollIntoView({ block: "center", behavior: "instant" }));
    }
    const ge = q(
      "人工分诊 ↓",
      "button secondary radar-evidence-quick-decision",
      null,
      ye,
    );
    (R.append(ae, ge), _e.append(R), ce.append(_e));
    const fe = e("div", "radar-evidence-lane-body");
    fe.hidden = !0;
    const me = e("dl", "radar-evidence-clocks"),
      E = e("p", "radar-evidence-status");
    E.setAttribute("role", "status");
    const j = e("div", "radar-evidence-compare"),
      re = o(L);
    (me.append(
      G("事件发生候选", re, "发生事实与发生时刻均需亲核；未知保持未知。"),
      G(
        "原文最早标记发表",
        l(L?.source_published_at),
        "所有关联已完成原文的最早标记时间，不一定是眼前同题原文。",
      ),
      G(
        "本站首次收录",
        l(L?.first_ingested_at),
        "仅说明首次进入本站，不是发布或发生时刻。",
      ),
    ),
      fe.append(j, me, E));
    const A = e(
      "p",
      "radar-evidence-scope",
      "词项命中仅用于查找候选出处，不代表支持自动主张；出处独立性未核实，链接可达性与商业授权未检查。",
    );
    (fe.append(A), ce.append(fe));
    let _ = 0,
      P = !1;
    function C(I) {
      const W = I.evidence.records,
        Q = W.filter((we) => yr(we, B)),
        he = Q[0],
        X = e("div", "radar-evidence-original");
      if (
        (X.append(
          e(
            "div",
            "radar-evidence-panel-label",
            "A · 已采集同题一手原文（词项命中，不是事实确认）",
          ),
        ),
        !he)
      )
        X.append(
          e(
            "p",
            "radar-evidence-missing",
            "该事件的原文快照已变化，或现在没有符合本主题全部词项的已完成原文。请重新检查主题条件，不要用自动摘要代替原文。",
          ),
        );
      else {
        const we = e("div", "radar-evidence-source");
        (we.append(
          e("strong", "", g(he.name, 95) || "来源未标记"),
          e("span", "", c(he.platform)),
        ),
          X.append(we));
        const le = typeof he.text == "string" ? he.text : "",
          Se = e(
            "p",
            "radar-primary-original-text",
            le ? le.slice(0, 1100) : "原始正文缺失；必须到出处核对。",
          );
        if (((Se.tabIndex = 0), X.append(Se), le.length > 1100)) {
          const Be = q(
            "展开完整已采集正文",
            "button secondary radar-evidence-fulltext",
            null,
            () => {
              const We = Be.getAttribute("aria-expanded") === "true";
              ((Se.textContent = We ? le.slice(0, 1100) : le),
                (Be.querySelector("span").textContent = We
                  ? "展开完整已采集正文"
                  : "收起完整正文"),
                Be.setAttribute("aria-expanded", String(!We)));
            },
          );
          (Be.setAttribute("aria-expanded", "false"), X.append(Be));
        }
        const Ue = ht(he.url);
        if (Ue) {
          const Be = e(
            "a",
            "radar-evidence-primary-link",
            "新窗口打开此条原始出处 ↗",
          );
          ((Be.href = Ue),
            (Be.target = "_blank"),
            (Be.rel = "noopener noreferrer"),
            X.append(Be));
        } else
          X.append(
            e(
              "p",
              "radar-evidence-missing",
              "此条同题原文无可安全打开的出处链接，只能先读已采集正文；请勿借用其他关联来源。",
            ),
          );
      }
      const H = e("details", "radar-evidence-provenance");
      (H.append(e("summary", "", "查看原文发表时间及关联范围")),
        he &&
          H.append(
            e(
              "p",
              "radar-evidence-original-date",
              "眼前原文标记发表：" +
                l(he.published_at) +
                " · 本条原文本站收录：" +
                l(he.first_ingested_at),
            ),
          ),
        H.append(
          e(
            "p",
            "radar-evidence-match-count",
            "本次快照：同一条原文 AND 命中 " +
              Q.length +
              " / " +
              W.length +
              " 条已完成关联原文。关联不等于多个独立确认，可能包含同题否定或同名歧义。",
          ),
        ),
        X.append(H));
      const ie = e("div", "radar-evidence-counter");
      (ie.append(
        e("div", "radar-evidence-panel-label", "B · 反证与下一步（本人决定）"),
      ),
        ie.append(
          e(
            "p",
            "radar-evidence-automated",
            "待查主张 · " +
              (g(I?.evidence?.event?.summary, 900) ||
                "自动摘要缺失；直接阅读左侧原文。"),
          ),
        ));
      const qe = e("div", "radar-evidence-challenge"),
        J =
          typeof I?.fields?.falsification == "string"
            ? I.fields.falsification.trim()
            : "";
      (J && Number.isInteger(I?.version) && I.version > 0
        ? qe.append(
            e(
              "strong",
              "",
              "本人已保存 v" + I.version + " 反证条件（未自动核实）",
            ),
            e("p", "", g(J)),
          )
        : qe.append(
            e("strong", "", "本人尚未填写反证条件"),
            e(
              "p",
              "",
              "可以先核对：原文是否其实在否认这个主张？有无不同出处的反例或失败测试？",
            ),
          ),
        ie.append(qe));
      const se = e("div", "radar-evidence-next"),
        Te = q(
          "去事件详情核对／记录反证",
          "button primary radar-evidence-next-detail",
          "arrow",
          () => a(de),
        );
      (se.append(Te),
        ie.append(se),
        j.replaceChildren(X, ie),
        (E.textContent =
          "读取了本站采集快照；相关性、观点与来源独立性仍需本人亲核。"),
        (ce.dataset.evidenceState = "ready"));
    }
    async function F(I = !1) {
      const W = ++_;
      ((P = !0),
        (fe.hidden = !1),
        ae.setAttribute("aria-expanded", "true"),
        (ae.querySelector("span").textContent = "收起原文与反证"),
        (ce.dataset.evidenceState = "loading"),
        (E.textContent = "正在只读读取已采集原文与现有人工反证，不会提交判断…"),
        I && j.replaceChildren());
      try {
        const Q = await Y(de, I);
        if (W !== _ || !P) return;
        C(Q);
      } catch (Q) {
        if (W !== _ || !P) return;
        ((ce.dataset.evidenceState = "error"),
          j.replaceChildren(),
          (E.textContent =
            "暂时读不到原文，已停止使用摘要替代；请点下方重试。" +
            (Q?.message ? "（" + g(Q.message, 100) + "）" : "")),
          j.append(
            q(
              "重新读取原文（只读）",
              "button secondary radar-evidence-retry",
              "refresh",
              () => F(!0),
            ),
          ));
      }
    }
    return (
      (ae.onclick = () => {
        if (P) {
          ((P = !1),
            ++_,
            (fe.hidden = !0),
            ae.setAttribute("aria-expanded", "false"),
            (ae.querySelector("span").textContent = "同屏核对原文与反证"));
          return;
        }
        F();
      }),
      ce
    );
  }
  return { render: pe, reset: k };
}
const _r = Object.freeze({
  pending: "等待整理",
  retry: "等待重试",
  processing: "正在整理",
  awaiting_video: "等待视频处理",
  video_processing: "视频处理中",
  failed: "整理失败",
  completed: "已整理为事件",
  filtered: "已过滤 · 原文保留",
});
function Cn(t, a = "") {
  return (
    _r[a === "video_pending" && t === "pending" ? "video_processing" : t] ||
    "整理状态待确认"
  );
}
function Ot(t) {
  const a =
    typeof t == "string"
      ? /^(\d{4}-\d{2}-\d{2})T\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?(?:Z|[+-]\d{2}:\d{2})?$/i.exec(
          t,
        )
      : null;
  if (!a) return null;
  const o = new Date(a[1] + "T00:00:00Z");
  if (!Number.isFinite(o.getTime()) || o.toISOString().slice(0, 10) !== a[1])
    return null;
  const l = /(?:Z|[+-]\d\d:\d\d)$/i.test(t) ? t : t + "Z",
    c = new Date(l);
  return Number.isFinite(c.getTime())
    ? c.toISOString().replace("T", " ").slice(0, 19) + " UTC"
    : null;
}
function sa(t) {
  const a = t?.event_time_precision,
    o = t?.event_time_status;
  if (
    !["exact", "day", "month", "range"].includes(a) ||
    !["explicit", "inferred", "scheduled"].includes(o) ||
    !Ot(t?.event_time_start)
  )
    return "未知（需核对）";
  const l = t?.event_time_end;
  if (l != null && !Ot(l)) return "未知（需核对）";
  const c = Date.parse(t.event_time_start),
    f = l == null ? null : Date.parse(l);
  if ((a === "range" && (f == null || f <= c)) || (f != null && f < c))
    return "未知（需核对）";
  const m = rn(t);
  return m === "事件时间待确认"
    ? "未知（需核对）"
    : m + (a === "exact" ? "（北京时间）" : "（原文日历候选）");
}
function Tn(t) {
  return Ot(t) || "UTC 首次收录时间待确认";
}
const oa = {
  name: "",
  query: "",
  platforms: ln.map((t) => t.id),
  min_importance: 0,
};
function Jt(t, a, o, l = "icon-button") {
  const c = q("", l, a, o);
  return (c.setAttribute("aria-label", t), (c.title = t), c);
}
function xr(t, a, o) {
  const l = e("div", o);
  return (l.append(e("span", "", t), e("strong", "", a)), l);
}
function et(t, a = "") {
  return e("span", "radar-badge" + (a ? " " + a : ""), t);
}
function Zt(t) {
  const a = e("p", "radar-inline-error", t);
  return (a.setAttribute("role", "alert"), a);
}
function la(t, a) {
  const o = a?.plans?.find((c) => c.current),
    l = t?.limits?.max_topics ?? t?.limits?.topics ?? o?.maxTopics;
  return l != null && l !== "" && Number.isInteger(Number(l)) && Number(l) >= 0
    ? Number(l)
    : null;
}
function mt(t) {
  return ln.find((a) => a.id === t)?.label || Ke(t);
}
function kr(t) {
  return (
    ([402, 403].includes(t?.status) && t?.code !== "csrf_rejected") ||
    /limit|quota|plan|permission/.test(String(t?.code || ""))
  );
}
function $r({
  api: t,
  onOpenEvent: a,
  onOpenWorkspace: o,
  onOpenInbox: l,
  isActive: c,
}) {
  const f = wr({
    api: t,
    onOpenEvent: a,
    occurrenceLabel: sa,
    utcLabel: (n) => Ot(n) || "未知（未提供可靠 UTC 时刻）",
    platformLabel: mt,
  });
  let m = null,
    s = null,
    g = null,
    h = null,
    k = null,
    Y = 0,
    G = 0,
    pe = null,
    L = "",
    B = 0,
    O = !1,
    de = null;
  const ce = new Map(),
    _e = (n) => Number.isSafeInteger(n) && n >= 0,
    R = (n, d, u) => JSON.stringify([String(n), String(d), u]);
  function ne(n) {
    if (n) {
      n.value_feedback = null;
      for (const d of Array.isArray(n.topics) ? n.topics : [])
        d.suspended || ((d._statsUnconfirmed = !0), (d.metrics = null));
    }
  }
  function ae(n, d) {
    let u = 0;
    for (const [p, b] of ce) {
      if (_e(d) && _e(b.ownerRevision) && d >= b.ownerRevision) {
        ce.delete(p);
        continue;
      }
      u++;
      const x = n?.topics
        ?.find((w) => String(w.id) === b.topicId)
        ?.highlights?.find((w) => String(w.id) === b.eventId);
      x && (x[b.axis] = b.value);
    }
    return (u && ne(n), u);
  }
  function ye(n, d, u, p, b) {
    const v = _e(b?.owner_revision) ? b.owner_revision : null;
    (ce.set(R(n.id, d.id, u), {
      topicId: String(n.id),
      eventId: String(d.id),
      axis: u,
      value: p,
      ownerRevision: v,
    }),
      ae(s, null),
      (L =
        v === null
          ? "写入已确认，但服务端未提供可校验的版本回执；暂按本轴回执显示，最新状态与统计待核实。"
          : "写入已确认，正在核验最新服务端快照；统计暂不当作已同步。"));
  }
  let ge = null,
    fe = null,
    me = null,
    E = 0,
    j = null,
    re = null,
    A = null,
    _ = null,
    P = null,
    C = null,
    F = 0,
    I = 0,
    W = !1,
    Q = !1,
    he = null;
  const X = new Set(),
    H = () => (Array.isArray(s?.topics) ? s.topics : []),
    ie = (n) => (Number.isSafeInteger(n) && n >= 0 ? n : null),
    qe = () => he && !H().some((n) => String(n?.id) === he.id),
    J = () => hr(g, s?.plan || null),
    se = () => {
      const n = la(s?.plan, J());
      return n != null && H().length >= n;
    },
    Te = () => !O && !se() && !qe();
  function we() {
    (B++,
      f.reset(),
      (m = null),
      (s = null),
      (g = null),
      (k = null),
      Y++,
      (pe = null),
      (L = ""),
      ce.clear(),
      (de = null),
      (h = null),
      (G = 0),
      (O = !1),
      (j = null),
      (re = null),
      (A = null),
      (_ = null),
      F++,
      I++,
      (W = !1),
      (Q = !1),
      X.clear(),
      (he = null),
      ge?.isConnected && ge.remove(),
      fe?.isConnected && fe.remove(),
      me?.isConnected && me.remove(),
      E++,
      (ge = null),
      (fe = null),
      (me = null));
  }
  function le(n) {
    ((m = n), !s && !h && Se());
    const d = !h && (!s || Date.now() - G > 15e3) ? Ee() : h;
    if (!s) return d || Promise.resolve();
    if (k?.enabled === !0) {
      const u = ze();
      return d ? Promise.allSettled([d, u]) : u;
    }
    return (nt(), d || Promise.resolve());
  }
  function Se() {
    if (!m?.isConnected) return;
    const n = e("div", "radar-initial-loading");
    (n.setAttribute("role", "status"),
      n.append(
        e("span", "radar-loading-pulse"),
        e("h2", "", "正在汇集你的关注主题"),
        e("p", "", "读取服务器上的主题、真实事件与日趋势…"),
      ),
      m.replaceChildren(n));
  }
  const Ue = "未能同步最新研判，请刷新";
  function Be() {
    const n = ++Y;
    return (
      k?.enabled === !0 && (k = { enabled: !0, items: [], syncing: !0 }),
      n
    );
  }
  function We(n, d, u) {
    d !== B ||
      n !== Y ||
      !m?.isConnected ||
      (u.status === "fulfilled" && u.value && typeof u.value == "object"
        ? (k = u.value)
        : (k = {
            enabled:
              k?.enabled === !0 || s?.plan?.limits?.review_due_enabled === !0,
            items: [],
            error: Ue,
          }));
  }
  function ze() {
    const n = B,
      d = Be();
    return (
      c() && nt(),
      t("/api/radar/reviews")
        .then(
          (u) => We(d, n, { status: "fulfilled", value: u }),
          () => We(d, n, { status: "rejected" }),
        )
        .then(() => {
          n === B && d === Y && c() && nt();
        })
    );
  }
  async function Ee({ silent: n = !1, afterWrite: d = !1 } = {}) {
    if (h && !d) return h;
    (h && d && (await h), !n && !s && Se());
    const u = B,
      p = Be();
    return (
      s && c() && nt(),
      (h = (async () => {
        const [b, v, x] = await Promise.allSettled([
          t("/api/radar"),
          t("/api/plans"),
          t("/api/radar/reviews"),
        ]);
        if (!(u !== B || !m?.isConnected)) {
          if (
            (v.status === "fulfilled" && (g = v.value),
            b.status === "fulfilled")
          ) {
            const w = b.value,
              $ = w && typeof w == "object" && Array.isArray(w.topics),
              T = _e(w?.owner_revision) ? w.owner_revision : null;
            let S = "";
            ($
              ? de !== null && (T === null || T < de)
                ? ((pe = null),
                  (S =
                    "忽略较早或缺版本的读取结果；保留此前已核验快照，请重新同步。"))
                : ((s = w),
                  (pe = null),
                  (G = Date.now()),
                  T !== null && (de = T),
                  (S = ae(s, T)
                    ? "本次读取版本早于提交回执（或缺少版本）；仅本轴暂按回执显示，主题进度与14日统计待核实。"
                    : ""))
              : ((pe = new Error("服务端雷达结构不完整")),
                (S = "读取结果无有效主题列表，不能当作零主题；保留上次快照。")),
              ce.size && ae(s, null),
              (L = [
                S,
                v.status === "rejected"
                  ? "档位说明暂时无法同步，以下仅供规划参考。"
                  : "",
              ]
                .filter(Boolean)
                .join(" ")));
          } else {
            const w = b.reason;
            if (w?.status === 401) return;
            ((pe = w),
              ce.size && ae(s, null),
              (L = s
                ? ce.size
                  ? "本次读取失败；已确认的选择暂按本轴回执显示，主题进度与14日统计待核实。"
                  : "本次刷新未成功，下面保留上次读取的雷达快照。"
                : ""));
          }
          (he &&
            (qe()
              ? b.status === "fulfilled" &&
                he.ownerRevision !== null &&
                ie(s?.owner_revision) !== null &&
                ie(s.owner_revision) > he.ownerRevision
                ? ((he = null),
                  (L =
                    "服务端较新状态已不含刚保存的主题，可能在另一客户端被删除；请自行核对，不会自动再创建。"))
                : (L =
                    "主题已确认保存，但个人雷达尚未收到可信的新列表；请重新同步，勿重复创建。")
              : (he = null)),
            We(p, u, x),
            (!n || c()) && nt());
        }
      })().finally(() => {
        u === B && (h = null);
      })),
      h
    );
  }
  function pt(n) {
    if (!m?.isConnected) return;
    const d = document.activeElement,
      u = m.contains(d) ? d?.dataset?.radarFocus : null,
      p = m.scrollTop;
    (m.replaceChildren(n),
      (m.scrollTop = p),
      u &&
        c() &&
        !document.querySelector("dialog[open]") &&
        Ne("[data-radar-focus]", m)
          .find((v) => v.dataset.radarFocus === u)
          ?.focus({ preventScroll: !0 }));
  }
  function nt() {
    if (!m?.isConnected) return;
    const n = e("div", "radar-layout");
    if ((n.append(At()), !s)) {
      const u = e("div", "radar-service-state");
      (u.append(
        it(
          "雷达暂时无法载入",
          pe?.message || "服务暂时不可用，请稍后重试。",
          { label: "重新读取雷达", run: () => Ee() },
          "activity",
        ),
      ),
        n.append(u, Tt()),
        pt(n));
      return;
    }
    if (L) {
      const u = e("div", "radar-status-message");
      (u.setAttribute("role", "status"),
        u.append(
          e("span", "", L),
          q("重新同步", "text-button", "refresh", () => Ee()),
        ),
        n.append(u));
    }
    (n.append(K()), H().length && n.append(ot()));
    const d = ft();
    (d && n.append(d), n.append(xn(), kn(), qt(), Tt()), pt(n));
  }
  function At() {
    const n = e("section", "radar-hero");
    n.setAttribute("aria-labelledby", "radar-hero-title");
    const d = e("div", "radar-hero-content");
    d.append(e("div", "radar-kicker", "FRONTIER  /  INTELLIGENCE RADAR"));
    const u = !!qe(),
      p = !!(s && !H().length && !u);
    p && n.classList.add("radar-hero-first-preview");
    const b = e(
      "h2",
      "",
      u
        ? "主题已保存，等待同步真实匹配。"
        : p
          ? "还没有主题？先只读试查，不必保存。"
          : "每天 10 分钟，先核对证据再做判断。",
    );
    if (
      ((b.id = "radar-hero-title"),
      d.append(
        b,
        e(
          "p",
          "",
          u
            ? "保存回执已确认，但列表尚未同步；现在不重复创建，也不虚构分诊事件。"
            : p
              ? "用自己的关键词试查已收录记录；打开表单不会发查询。只有你再次点击「试查」才向当前云端发请求，不建主题、不代做分诊。"
              : "这是建议的每日人工核验顺序，不是倒计时或已完成记录。已整理事件可能来自历史窗口，请按每条时间与原文判断。",
        ),
      ),
      !p && !u)
    ) {
      const D = e("ol", "radar-daily-method");
      D.setAttribute(
        "aria-label",
        "建议每天用 10 分钟完成的四步人工流程，均不自动记为完成",
      );
      for (const [Z, U] of [
        ["01", "查原文"],
        ["02", "人工分诊"],
        ["03", "评价有用性"],
        ["04", "结束本轮复盘"],
      ]) {
        const be = e("li", "radar-daily-method-step");
        (be.append(e("span", "", Z), e("strong", "", U)), D.append(be));
      }
      d.append(D);
    }
    const v = e("div", "radar-hero-actions"),
      x = q(
        u
          ? "已保存 · 暂停重复创建"
          : se()
            ? "已达到主题上限"
            : p
              ? "先只读试查 · 不保存主题"
              : "新建雷达主题",
        "button primary radar-primary-button",
        p ? "search" : "plus",
        () => Mt(),
      );
    ((x.id = "radar-new"),
      (x.dataset.radarFocus = "new"),
      (x.disabled = !s || !Te()));
    const w = H().some((D) => (D.highlights || []).length > 0),
      $ = H().some((D) => (D.raw_leads?.items || []).length > 0);
    (v.append(
      x,
      q(
        u
          ? "重新读取已保存主题"
          : p
            ? "先看如何开始"
            : w
              ? "开始分诊"
              : $
                ? "查看未整理原文"
                : "内测权益说明",
        "button secondary radar-plain-button",
        u ? "refresh" : "arrow",
        u ? () => Ee({ afterWrite: !0 }) : p ? Ca : w || $ ? Ea : Wt,
      ),
    ),
      v.append(
        q("看待整理原文", "button secondary radar-plain-button", "inbox", () =>
          l?.(),
        ),
      ),
      d.append(v),
      d.append(
        e(
          "p",
          "radar-trust-note",
          u
            ? "服务器已接受本次保存；现在的旧快照不证明主题为零。同步前不显示任何未经返回的个人事件或进度。"
            : p
              ? "下方 3 个方向仅为可编辑的草稿示例，不是你的关注主题，不会自动提交或制造信号。信号只来自真实收录记录。"
              : "仅显示已完成整理的事件；采集与处理可能有盲区，零匹配不等于零进展。请查看下方覆盖报告与来源状态。",
        ),
      ));
    const T = s?.plan,
      S = e("div", "radar-hero-caption");
    (S.append(
      et(
        T ? (oe(T.label, 50) || "当前档位") + " · 内测使用" : "私人雷达工作区",
        "current",
      ),
    ),
      s?.generated_at &&
        S.append(
          e("span", "", "快照更新：" + Ve(s.generated_at, !0) + "（北京时间）"),
        ),
      d.append(S),
      n.append(d));
    const M = e("div", "radar-visual");
    M.setAttribute("aria-hidden", "true");
    const V = e("div", "radar-scope");
    if (
      (V.append(
        e("i", "radar-ring ring-one"),
        e("i", "radar-ring ring-two"),
        e("i", "radar-ring ring-three"),
        e("i", "radar-sweep"),
        e("i", "radar-center"),
        e("i", "radar-dot dot-one"),
        e("i", "radar-dot dot-two"),
        e("i", "radar-dot dot-three"),
      ),
      M.append(
        V,
        e("div", "radar-visual-annotation", "TRACK · TRIAGE · REVIEW"),
      ),
      n.append(M),
      H().length && !u)
    ) {
      (n.classList.add("radar-hero-returning"),
        n.classList.toggle("radar-hero-guide-expanded", Q),
        n.removeAttribute("aria-labelledby"),
        n.setAttribute("aria-label", "今日情报雷达操作与可展开使用说明"),
        (d.id = "radar-returning-full-guide"));
      const D = e("div", "radar-returning-brief");
      D.append(
        e("span", "radar-returning-kicker", "TODAY  /  REVIEW ONE SIGNAL"),
      );
      const Z = e("h2", "", "今天先核对一条线索");
      ((Z.id = "radar-quick-title"),
        D.append(
          Z,
          e(
            "p",
            "",
            "先核出处再人工分诊；匹配可能是历史记录，链接不等于独立证实。",
          ),
        ));
      const U = e("div", "radar-returning-actions"),
        be = q(
          "到首条来源 / 分诊",
          "button primary radar-returning-jump",
          "arrow",
          Ta,
        );
      be.dataset.radarFocus = "returning-jump";
      const Le = q(
        Q ? "收起说明" : "展开使用说明",
        "button secondary radar-returning-guide-toggle",
        null,
        () => {
          ((Q = !Q),
            n.classList.toggle("radar-hero-guide-expanded", Q),
            Le.setAttribute("aria-expanded", String(Q)),
            (Le.querySelector("span").textContent = Q
              ? "收起说明"
              : "展开使用说明"));
        },
      );
      ((Le.dataset.radarFocus = "returning-guide"),
        Le.setAttribute("aria-controls", d.id),
        Le.setAttribute("aria-expanded", String(Q)),
        U.append(be, Le),
        D.append(U),
        n.prepend(D));
    }
    return n;
  }
  function ft() {
    const n = k;
    if (n?.enabled !== !0) return null;
    const d = Array.isArray(n.items) ? n.items : [],
      u = d.filter((T) => T?.status === "overdue").length,
      p = d.filter((T) => T?.status === "today").length,
      b = e("section", "radar-review-due");
    ((b.id = "radar-review-due"),
      b.setAttribute("aria-labelledby", "radar-review-title"));
    const v = e("div", "radar-review-heading"),
      x = e("div");
    x.append(e("span", "radar-overline", "RESEARCH / REVIEW QUEUE"));
    const w = e("h2", "", "待复核研判");
    if (
      ((w.id = "radar-review-title"),
      x.append(
        w,
        e(
          "p",
          "",
          "仅按每个事件最新的个人研判版本安排复查。先读原文，再手动更新判断与复查日。",
        ),
      ),
      v.append(
        x,
        et(
          n.syncing
            ? "同步中"
            : n.error
              ? "同步失败"
              : "已到期 " + y(u + p) + " · 未来 7 天 " + y(d.length - u - p),
          "personal",
        ),
      ),
      b.append(v),
      b.append(
        e(
          "p",
          "radar-review-scope",
          "复查日按北京时间（UTC+08:00）日界计算，今日 " +
            (oe(n.today, 10) || "未知") +
            "；不同于原文首次收录的 UTC 日。最多展示 " +
            y(n.limit || 50) +
            " 条；无消息推送或自动 AI 研判。支持与反证是个人笔记，原文独立性未知。",
        ),
      ),
      n.syncing)
    ) {
      const T = e("div", "radar-review-empty", "正在同步最新研判…");
      return (T.setAttribute("role", "status"), b.append(T), b);
    }
    if (n.error) {
      const T = e("div", "radar-review-empty", Ue);
      return (
        T.setAttribute("role", "alert"),
        b.append(
          T,
          q(
            "重新读取复核安排",
            "button secondary radar-review-retry",
            "refresh",
            () => ze(),
          ),
        ),
        b
      );
    }
    if (!d.length)
      return (
        b.append(
          e(
            "div",
            "radar-review-empty",
            n.has_revisions
              ? "未来 7 天内没有应复核的最新研判；已保存的历史版本仍可从事件详情查阅。"
              : "尚无个人研判。打开上方事件详情，写下判断与复查日后便会在这里看到复核安排。",
          ),
        ),
        b
      );
    const $ = e("div", "radar-review-list");
    for (const T of d) {
      if (!T || typeof T.event_id != "string" || !T.event_id) continue;
      const S = e(
        "article",
        "radar-review-item " +
          (["today", "overdue"].includes(T.status) ? "is-due" : "is-upcoming"),
      );
      S.dataset.eventId = T.event_id;
      const M = e("div", "radar-review-item-top"),
        V = Number(T.days_until),
        D = Number.isInteger(V) ? V : null,
        Z =
          D == null
            ? "日期待核对"
            : D < 0
              ? "逾期 " + y(-D) + " 天"
              : D === 0
                ? "今天到期"
                : "还有 " + y(D) + " 天";
      (M.append(
        et(Z, D != null && D <= 0 ? "review-due" : "review-next"),
        e(
          "span",
          "radar-review-date",
          (oe(T.review_on, 10) || "日期待核对") + " · 最新 v" + y(T.version),
        ),
      ),
        S.append(M));
      const U = q(
        oe(T.title, 240) || "无标题事件",
        "radar-review-open",
        "arrow",
        () => a(T.event_id),
      );
      ((U.dataset.radarFocus = "review-due:" + T.event_id),
        U.setAttribute(
          "aria-label",
          "打开事件详情并复核：" + (oe(T.title, 120) || "无标题事件"),
        ),
        S.append(U),
        S.append(
          e(
            "p",
            "radar-review-judgment",
            "最近判断：" +
              (oe(T.judgment, 180) || "尚未写下判断，请到详情补充。"),
          ),
        ));
      const be = e("div", "radar-review-conditions");
      (be.append(
        e("p", "", "支持/疑问：" + (oe(T.support, 120) || "尚未填写")),
        e("p", "", "反证条件：" + (oe(T.falsification, 120) || "尚未填写")),
      ),
        S.append(be),
        $.append(S));
    }
    return (b.append($), b);
  }
  function ot() {
    const n = s?.value_feedback,
      d = (x) => Number.isSafeInteger(x) && x >= 0,
      u =
        n?.window_days === 14 &&
        n?.day_timezone === "Asia/Shanghai" &&
        d(n?.rated_count) &&
        d(n?.useful_count) &&
        d(n?.noise_count) &&
        d(n?.feedback_days) &&
        n.useful_count + n.noise_count === n.rated_count &&
        n.feedback_days <= 14 &&
        (n.rated_count === 0 || n.feedback_days > 0) &&
        typeof n.scope == "string" &&
        !!n.scope.trim(),
      p = e("details", "radar-value-feedback");
    ((p.id = "radar-value-feedback"),
      (p.open = W),
      p.addEventListener("toggle", () => {
        p.isConnected && (W = p.open);
      }));
    const b = e("summary", "radar-value-summary");
    b.dataset.radarFocus = "value-feedback-summary";
    const v = e("div", "radar-value-body");
    if (!u)
      (b.append(
        e("strong", "", "近14日 · 人工价值反馈"),
        e("span", "", "统计暂不可用"),
      ),
        v.append(
          e(
            "p",
            "radar-value-no-data",
            "尚未收到完整、可信的本人反馈聚合，无法估算有用率与操作日数；不会补造样本。可稍后重新读取。",
          ),
        ));
    else {
      const x = n.rated_count,
        w = n.useful_count,
        $ = n.noise_count,
        T = n.feedback_days,
        S = x
          ? "近14日 · 现存人工标注 " +
            y(x) +
            " 条（值得看 " +
            y(w) +
            " / 没帮助 " +
            y($) +
            "） · 反馈操作日数 " +
            y(T) +
            "/14"
          : "近14日 · 尚无本人有效反馈，无法估算有用率 · 反馈操作日数 " +
            y(T) +
            "/14";
      if (
        (b.append(e("strong", "", "我的显式价值反馈"), e("span", "", S)), x)
      ) {
        const M = Math.round((w / x) * 1e3) / 10;
        (v.append(
          e(
            "p",
            "radar-value-ratio",
            "仅在已评价样本中的「值得看」比例：" +
              M +
              "%（" +
              y(w) +
              "/" +
              y(x) +
              "）；不是全部信息的准确率、付费价值或目标达成证明。",
          ),
        ),
          x < 10 &&
            v.append(
              e(
                "p",
                "radar-value-small-sample",
                "人工标注样本不足10条，只是你标注的少量样本，不具代表性，不能推断整体质量。",
              ),
            ));
      } else
        v.append(
          e(
            "p",
            "radar-value-no-data",
            "尚无本人反馈，无法估算有用率；即使曾点击后撤销，操作日数仍会如实保留。",
          ),
        );
      (v.append(
        e(
          "p",
          "radar-value-operation-days",
          "「反馈操作日数」= 近14个北京时间（Asia/Shanghai）自然日内，实际点击标注、改判或撤销的不同日期；不是登录天数、阅读天数或留存率。",
        ),
      ),
        typeof n.scope == "string" &&
          n.scope.trim() &&
          v.append(
            e("p", "radar-value-scope", "服务端统计范围：" + oe(n.scope, 220)),
          ));
    }
    return (
      v.append(
        e(
          "p",
          "radar-value-method",
          "仅基于本人明确选择「值得看 / 没帮助」的记录；行动状态不等于有用。14天持续使用和真实商业价值仍待验证。",
        ),
      ),
      p.append(b, v),
      p
    );
  }
  function xn() {
    const n = H(),
      d = !!qe() || n.some((w) => w._statsUnconfirmed),
      u = n.reduce((w, $) => w + ve($.metrics?.total), 0),
      p = n.reduce((w, $) => w + ve($.metrics?.unread), 0),
      b = n.reduce((w, $) => w + ve($.metrics?.new_since_review), 0),
      v = e("section", "radar-overview");
    v.setAttribute("aria-label", "雷达概览（各主题数据可能重复）");
    const x = [
      [
        "已配置主题",
        qe() ? "已保存 · 待同步" : y(n.length),
        qe() ? "已确认保存，暂不据旧列表计算总量" : "暂停的主题不参与统计",
        "topics",
      ],
      ["匹配事件", d ? "待同步" : y(u), "各主题累计，可能重叠", "total"],
      ["待阅读", d ? "待同步" : y(p), "各主题未读事件数", "unread"],
      [
        "本轮新增",
        d ? "待同步" : y(b),
        "首轮复盘前包含历史匹配；各主题可重叠",
        "new",
      ],
    ];
    for (const [w, $, T, S] of x) {
      const M = e("div", "radar-overview-tile radar-overview-" + S);
      (M.append(e("span", "", w), e("strong", "", $), e("small", "", T)),
        v.append(M));
    }
    return v;
  }
  function kn() {
    const n = s?.coverage_today || {},
      d = ve(n.raw_new),
      u = ve(n.completed),
      p = ve(n.filtered),
      b = ve(n.pending) + ve(n.awaiting_video),
      v = ve(n.failed),
      x = (D) => y(ve(n[D])),
      w = e("section", "radar-daily-pulse");
    ((w.id = "radar-today"),
      w.setAttribute("aria-labelledby", "radar-pulse-title"));
    const $ = e("div", "radar-pulse-heading"),
      T = e("h2", "", "今日处理覆盖");
    ((T.id = "radar-pulse-title"),
      $.append(
        T,
        e("span", "", (oe(n.utc_day, 12) || "今日") + " / UTC 首次收录"),
      ),
      w.append($));
    const S = e("div", "radar-pulse-legend");
    for (const [D, Z, U] of [
      ["已完成整理", u, "done"],
      ["内容过滤", p, "filtered"],
      ["待分析 / 视频准备", b, "pending"],
      ["分析失败", v, "failed"],
    ]) {
      const be = e("span", "radar-pulse-legend-item " + U);
      (be.append(e("i", ""), e("strong", "", y(Z)), e("span", "", D)),
        S.append(be));
    }
    w.append(
      e(
        "p",
        "radar-pulse-intro",
        "今日派生原文 " +
          y(d) +
          " 条；以下是处理状态，不是独立事实核实率，也不包括尚未采到的内容。",
      ),
    );
    const M = e("div", "radar-pipeline-bar");
    if (
      (M.setAttribute("role", "img"),
      M.setAttribute(
        "aria-label",
        "今日首次收录 " +
          y(d) +
          " 条原文，整理 " +
          x("completed") +
          " 条，过滤 " +
          x("filtered") +
          " 条，待分析 " +
          y(b) +
          " 条，失败 " +
          y(v) +
          " 条。",
      ),
      d)
    )
      for (const [D, Z] of [
        [u, "done"],
        [p, "filtered"],
        [b, "pending"],
        [v, "failed"],
        [ve(n.other), "other"],
      ]) {
        if (!D) continue;
        const U = e("span", "radar-pipeline-" + Z);
        ((U.style.width = Math.max(0, Math.min(100, (D / d) * 100)) + "%"),
          U.setAttribute("aria-hidden", "true"),
          M.append(U));
      }
    else M.append(e("span", "radar-pipeline-empty"));
    w.append(M, S);
    const V = e("p", "radar-coverage-warning");
    return (
      V.append(
        e("strong", "", b + v > 0 ? "存在处理覆盖缺口：" : "覆盖解释："),
      ),
      V.append(
        e(
          "span",
          "",
          "待处理 " +
            y(b) +
            "、失败 " +
            y(v) +
            " 条可能尚无雷达事件；采集源失联/限流不包含在这些数值里，请以来源页真实状态为准。",
        ),
      ),
      w.append(V),
      w
    );
  }
  function qt() {
    const n = e("section", "radar-global-signals");
    n.setAttribute("aria-labelledby", "radar-global-title");
    const d = e("div", "radar-section-heading"),
      u = e("div");
    u.append(e("span", "radar-overline", "EDITORIAL / SEPARATE FROM PERSONAL"));
    const p = e("h2", "", "今日全站高重要度 · 独立排序");
    ((p.id = "radar-global-title"),
      u.append(
        p,
        e(
          "p",
          "",
          "仅展示 UTC 今日首次入库、已关联完成原文且编辑重要度 ≥ 85 的最多 5 条事件；不因符合个人主题而加分。重要度并非事实真实性概率。",
        ),
      ),
      d.append(u),
      n.append(d));
    const b = Array.isArray(s?.global_signals) ? s.global_signals : [];
    if (!b.length)
      n.append(
        e(
          "p",
          "radar-global-empty",
          "今天暂没有满足此高分门槛的已整理事件。待处理原文和采集失败可能导致缺口，不能理解为全球没有变化。",
        ),
      );
    else {
      const v = e("div", "radar-global-grid");
      for (const x of b) v.append(Ct(x, null));
      n.append(v);
    }
    return n;
  }
  function N(n) {
    const d = n.latest_brief;
    if (!d || typeof d != "object") return null;
    const u = e("details", "radar-saved-brief"),
      p = String(n.id);
    ((u.open = X.has(p)),
      u.addEventListener("toggle", () => {
        u.isConnected && (u.open ? X.add(p) : X.delete(p));
      }));
    const b = Array.isArray(d.items) ? d.items : [],
      v = e(
        "summary",
        "",
        "复看上轮不可变简报 · " +
          Ve(d.generated_at, !0) +
          " · " +
          y(b.length) +
          " 条",
      );
    ((v.dataset.radarFocus = "saved-brief:" + p),
      v.addEventListener("click", () => {
        u.open ? X.delete(p) : X.add(p);
      }),
      u.append(v));
    const x = e("div", "radar-brief-body");
    x.append(
      e(
        "p",
        "",
        "此为当时冻结的主题、指标和前 " +
          y(b.length) +
          " 条线索；刷新和后续分诊不会改变。事件详情会展示其最新信息。",
      ),
    );
    const w = d.metrics || {};
    if (
      (x.append(
        e(
          "p",
          "radar-brief-stats",
          "保存时：匹配 " +
            y(ve(w.total)) +
            " · 已分诊 " +
            y(ve(w.triaged)) +
            " · 当日新增 " +
            y(ve(w.today_added)) +
            " · 未读 " +
            y(ve(w.unread)),
        ),
      ),
      b.length)
    ) {
      const $ = e("ol", "radar-brief-list"),
        T = { dismiss: "忽略", watch: "持续关注", research: "深入研判" };
      for (const S of b) {
        const M = e("li", "radar-brief-item"),
          V = q(oe(S?.title, 220) || "事件详情", "radar-brief-open", null, () =>
            a(String(S?.id)),
          );
        ((V.disabled = !S?.id),
          M.append(
            V,
            e(
              "span",
              "radar-brief-result",
              "个人匹配 " +
                y(ve(S?.personal_relevance)) +
                " / 编辑重要度 " +
                y(ve(S?.importance)) +
                " · " +
                (T[S?.decision] || "保存时未分诊"),
            ),
          ));
        const D = (Array.isArray(S?.sources) ? S.sources : [])
          .map((Z) => ({ ...Z, safe: ht(Z?.url) }))
          .filter((Z) => Z.safe);
        if (D.length) {
          const Z = e("span", "radar-brief-evidence");
          for (const U of D.slice(0, 2)) {
            const be = e("a", "", oe(U.name, 45) || mt(U.platform));
            ((be.href = U.safe),
              (be.target = "_blank"),
              (be.rel = "noopener noreferrer"),
              Z.append(be));
          }
          M.append(Z);
        } else
          M.append(
            e("span", "radar-brief-evidence", "原始外链不可用，查看事件详情"),
          );
        $.append(M);
      }
      x.append($);
    }
    return (
      x.append(
        e(
          "p",
          "radar-brief-disclaimer",
          oe(d.scope, 260) || "原始出处数量不意味着多方独立核实。",
        ),
      ),
      u.append(x),
      u
    );
  }
  function z() {
    const n = he,
      d = e("section", "radar-status-message radar-confirmed-topic-pending");
    ((d.id = "radar-pending-topic"),
      (d.tabIndex = -1),
      d.setAttribute("role", "status"),
      d.setAttribute("aria-live", "polite"),
      d.append(
        e("strong", "", "已确认保存：" + oe(n?.name, 150)),
        e(
          "span",
          "",
          "已收到本次主题创建回执，但最新雷达列表尚不可核对。不能据旧列表认定没有主题，也不会自动重试写入、填充事件或统计。",
        ),
      ));
    const u = q("重新读取已保存主题", "button secondary", "refresh", () =>
      Ee({ afterWrite: !0 }),
    );
    return ((u.dataset.radarFocus = "confirmed-topic-refresh"), d.append(u), d);
  }
  function K() {
    const n = e("section", "radar-topic-area");
    H().length && !qe() && n.classList.add("radar-topic-returning");
    const d = e("div", "radar-section-heading"),
      u = e("div");
    u.append(e("span", "radar-overline", "YOUR SIGNALS"));
    const p = !!qe();
    if (
      (u.append(
        e(
          "h2",
          "",
          H().length
            ? "正在追踪的主题"
            : p
              ? "主题已保存，匹配列表待同步"
              : "从一个关注点开始",
        ),
      ),
      u.append(
        e(
          "p",
          "",
          p
            ? "先使用下方单独的重新读取入口；没有服务器新列表时不能做原文核对或两轴人工分诊。"
            : H().length
              ? "每天建议用 10 分钟：点原文核对 → 人工选分诊 → 独立选有用/无用 → 最后才提交本轮已阅；这四步不自动代做。"
              : "你来决定追踪的问题。创建后才会看到自己的匹配状态；零匹配和原文尚未整理是两回事。",
        ),
      ),
      d.append(u),
      H().length)
    ) {
      const b = q("添加主题", "button secondary", "plus", () => Mt());
      ((b.disabled = !Te()), (b.dataset.radarFocus = "add"), d.append(b));
    }
    if ((n.append(d), se())) {
      const b = la(s?.plan, J()),
        v = e("div", "radar-limit-note");
      (v.setAttribute("role", "status"),
        v.append(
          e("strong", "", "当前主题额度已用完"),
          e(
            "span",
            "",
            "当前档位最多允许 " +
              y(b) +
              " 个主题。可编辑、删除已有主题，或查看下方的权益差异。",
          ),
        ),
        v.append(q("查看档位", "text-button", "arrow", Wt)),
        n.append(v));
    }
    if ((p && n.append(z()), !H().length && !p)) n.append(ee());
    else if (H().length) {
      const b = e("div", "radar-topic-grid");
      for (const v of H()) b.append(De(v));
      n.append(b);
    }
    return n;
  }
  function ee() {
    const n = e("div", "radar-empty");
    n.id = "radar-first-run";
    const d = e("div", "radar-empty-intro");
    (d.append(e("span", "radar-overline", "FIRST RUN · 0 SAVED TOPICS")),
      d.append(e("h3", "", "没有主题 ≠ 今天没有新闻。先由你选一个真实问题。")),
      d.append(
        e(
          "p",
          "",
          "当前还没有你的关注条件，不能显示个人匹配或分诊进度。建立主题后会分别报告已整理事件、近 48 小时未整理原文；没有匹配时也会明确告知，不会填充假信号。",
        ),
      ));
    const u = q(
      "我已想好关注的问题 · 填主题",
      "button primary radar-first-cta",
      "plus",
      () => Mt(),
    );
    ((u.disabled = !Te()), d.append(u), n.append(d));
    const p = e("ol", "radar-first-steps");
    for (const [x, w] of [
      [
        "选择真实问题",
        "用一句话想清楚自己在关注什么，不要照搬示例当作已观察到的事实。",
      ],
      [
        "先放宽，稍后收紧",
        "主题关键词按空格拆分且必须全部出现（AND）；首次建议 1 个关键词、重要度 0（不限）。",
      ],
      [
        "亲手提交并核对状态",
        "有已整理匹配事件才能做「忽略 / 持续关注 / 深入研判」；未整理原文只能先核对，匹配为 0 也不等于全网无消息。",
      ],
    ].entries()) {
      const $ = e("li", "radar-first-step");
      ($.append(e("strong", "", "0" + (x + 1) + " · " + w[0])),
        $.append(e("span", "", w[1])),
        p.append($));
    }
    n.append(p);
    const b = e(
      "p",
      "radar-examples-caption",
      "不知道怎么填？以下 3 张是可修改的输入草稿，不是已有主题；点选只打开编辑表单，不会发送创建请求。",
    );
    n.append(b);
    const v = e("div", "radar-example-grid");
    for (const [x, w] of ir.entries()) {
      const $ = e("article", "radar-example");
      ($.append(
        e("span", "radar-example-index", "示例 0" + (x + 1) + "  /  仅供改写"),
      ),
        $.append(e("h4", "", w.name), e("p", "", w.description)));
      const T = e("div", "radar-example-foot");
      T.append(e("span", "", "默认不限制重要度"));
      const S = q("填入可编辑草稿", "button secondary", "edit", () =>
        Mt(null, w),
      );
      ((S.disabled = !Te()),
        (S.dataset.radarFocus = "example:" + x),
        T.append(S),
        $.append(T),
        v.append($));
    }
    return (n.append(v), n);
  }
  function De(n) {
    const d = String(n?.id ?? ""),
      u = e("article", "radar-topic-card");
    u.dataset.topicId = d;
    const p = e("div", "radar-topic-upper"),
      b = e("div", "radar-topic-identity");
    (b.append(e("span", "radar-overline", "TRACKED TOPIC")),
      b.append(e("h3", "", oe(n.name, 150) || "未命名主题")),
      b.append(
        e(
          "p",
          "radar-topic-query",
          "关键词 / " + (oe(n.query, 300) || "未设置"),
        ),
      ));
    const v = e("div", "radar-topic-tags");
    for (const xe of Array.isArray(n.platforms) ? n.platforms : []) {
      const Re = ln.find((Xe) => Xe.id === xe);
      Re && v.append(et(Re.label, "platform"));
    }
    (v.append(et("事件重要度 ≥ " + ve(n.min_importance), "importance")),
      b.append(v),
      p.append(b));
    const x = e("div", "radar-topic-actions"),
      w = Jt("编辑主题：" + oe(n.name), "edit", () => Mt(n));
    ((w.dataset.radarFocus = "edit:" + d), (w.disabled = O));
    const $ = Jt("删除主题：" + oe(n.name), "trash", () => Ma(n));
    if (
      (($.dataset.radarFocus = "delete:" + d),
      ($.disabled = O),
      x.append(w, $),
      p.append(x),
      u.append(p),
      n.suspended)
    ) {
      const xe = e("div", "radar-suspended");
      return (
        xe.setAttribute("role", "status"),
        xe.append(
          e("strong", "", "此主题的分析已暂停"),
          e(
            "p",
            "",
            "原来的关键词、历史判断与来源不删除，但已超出当前档位可同时分析的主题数。可以编辑或删除此主题；尚未接入真实支付升级。",
          ),
        ),
        xe.append(
          q("查看档位限制", "button secondary radar-plain-button", "arrow", Wt),
        ),
        u.append(xe),
        u
      );
    }
    const T = e("div", "radar-topic-body"),
      S = e("div", "radar-topic-metrics");
    if (n._statsUnconfirmed)
      S.append(
        e(
          "p",
          "radar-topic-stat-warning",
          "本主题计数、今日进度与趋势尚未通过服务端版本核验；未知不等于 0。",
        ),
      );
    else {
      for (const [Ye, dt, Fa] of [
        ["匹配事件", n.metrics?.total, "total"],
        ["待阅读", n.metrics?.unread, "unread"],
        [
          n.last_reviewed_at ? "复盘后首次收录" : "尚未复盘 · 已收录匹配",
          n.metrics?.new_since_review,
          "new",
        ],
        ["今日首次收录", n.metrics?.today_added, "today"],
      ])
        S.append(xr(Ye, y(ve(dt)), "radar-metric " + Fa));
      const xe = ve(n.metrics?.today_added),
        Re = ve(n.metrics?.today_triaged),
        Xe =
          Number.isSafeInteger(n.metrics?.pending_triage) &&
          n.metrics.pending_triage >= 0
            ? ve(n.metrics.pending_triage)
            : null,
        at = e("div", "radar-progress-line");
      at.append(
        e(
          "strong",
          "",
          xe
            ? "今日首次收录的匹配事件中已分诊 " + y(Re) + " / " + y(xe)
            : "今日首次收录的匹配事件 0 条",
        ),
        e(
          "span",
          "",
          Xe === null
            ? "当前待分诊数量待确认"
            : "当前待分诊 " + y(Xe) + " 条（含历史收录）",
        ),
      );
      const ke = e("progress", "radar-progress-bar");
      ((ke.max = Math.max(1, xe)),
        (ke.value = Math.min(xe, Re)),
        ke.setAttribute(
          "aria-label",
          "今日首次收录的匹配事件中已分诊：" + y(Re) + " / " + y(xe),
        ),
        S.append(at, ke));
      const Fe = e(
        "p",
        "radar-last-review",
        n.last_reviewed_at
          ? (s?.plan?.limits?.saved_brief_enabled
              ? "上轮简报已保存："
              : "上轮复盘水位已更新：") +
              Ve(n.last_reviewed_at, !0) +
              " · 北京时间"
          : s?.plan?.limits?.saved_brief_enabled
            ? "尚未保存首轮简报"
            : "尚未完成首轮复盘",
      );
      (S.append(Fe),
        S.append(
          e(
            "p",
            "radar-topic-coverage",
            "其中 " +
              y(ve(n.metrics?.with_event_time)) +
              " 条有事件时间字段，" +
              y(ve(n.metrics?.with_location)) +
              " 条有地理位置依据。",
          ),
        ));
      const rt = n.metrics?.decided || {};
      S.append(
        e(
          "p",
          "radar-topic-decisions",
          "显式分诊：忽略 " +
            y(ve(rt.dismiss)) +
            " · 持续关注 " +
            y(ve(rt.watch)) +
            " · 深入研判 " +
            y(ve(rt.research)) +
            "（不更改阅读或收藏）",
        ),
      );
    }
    (T.append(S), n._statsUnconfirmed || T.append(Je(n.metrics?.trend)));
    const M = Array.isArray(n.highlights) ? n.highlights : [],
      V = Array.isArray(n.raw_leads?.items) ? n.raw_leads.items : [];
    !M.length && V.length && u.append(Ie(n));
    const D = e("div", "radar-highlights"),
      Z = e("div", "radar-highlights-title");
    if (
      (Z.append(
        e("h4", "", "个人主题 · 优先核对的匹配事件"),
        e(
          "span",
          "",
          "未分诊优先 · 可能包含历史事件，非全部今日新增 · 按时间与出处核实",
        ),
      ),
      D.append(Z),
      M.length)
    ) {
      const xe = e("div", "radar-highlights-grid");
      for (const [Re, Xe] of M.entries()) {
        const at = Ct(Xe, n, Re === 0);
        (Re >= 4 && (at.hidden = !0), xe.append(at));
      }
      if ((D.append(xe), M.length > 4)) {
        const Re = q(
          "展开其余 " + y(M.length - 4) + " 条真实事件",
          "button secondary radar-expand-button",
          "arrow",
        );
        (Re.setAttribute("aria-expanded", "false"),
          (Re.onclick = () => {
            const Xe = Re.getAttribute("aria-expanded") === "true";
            for (const [at, ke] of [...xe.children].entries())
              at >= 4 && (ke.hidden = Xe);
            (Re.setAttribute("aria-expanded", String(!Xe)),
              (Re.querySelector("span").textContent = Xe
                ? "展开其余 " + y(M.length - 4) + " 条真实事件"
                : "收起额外线索"));
          }),
          D.append(Re));
      }
    } else {
      const xe = e("div", "radar-highlights-empty radar-topic-zero-state");
      if (
        (xe.setAttribute("role", "status"),
        xe.append(
          e(
            "strong",
            "",
            n._statsUnconfirmed
              ? "此主题线索列表暂未核验"
              : ve(n.metrics?.total)
                ? "主题已生效 · 当前窗口没有待分诊事件"
                : "主题已生效 · 暂无匹配的已整理事件",
          ),
        ),
        xe.append(
          e(
            "p",
            "",
            n._statsUnconfirmed
              ? "读取版本尚未追上已确认的写入；不能把当前空列表解释为零匹配。"
              : V.length
                ? "另有 " +
                  y(V.length) +
                  " 条未整理原文（见上方），尚未核实、没有重要度，也不能三态分诊。"
                : "近 48 小时抽样窗口也暂无匹配的未整理原文；可能尚未采集、未整理、超出窗口或筛选过严，不代表全网没有进展。",
          ),
        ),
        n._statsUnconfirmed)
      )
        xe.append(
          q(
            "重新核验服务端",
            "button secondary radar-zero-edit",
            "refresh",
            () => Ee(),
          ),
        );
      else {
        (xe.append(
          e(
            "p",
            "radar-zero-cause",
            An(n.query) +
              " 当前事件最低重要度 " +
              ve(n.min_importance) +
              "；提高门槛只会减少候选。",
          ),
        ),
          xe.append(
            e(
              "p",
              "",
              "等有已整理匹配事件，才会出现「忽略 / 持续关注 / 深入研判」三个选择；此处没有假任务或假完成。",
            ),
          ));
        const Re = q(
          "编辑条件 · 再查匹配",
          "button secondary radar-zero-edit",
          "edit",
          () => Mt(n),
        );
        ((Re.disabled = O), xe.append(Re));
      }
      D.append(xe);
    }
    (u.append(D), (M.length || !V.length) && u.append(Ie(n)), u.append(T));
    const U = N(n);
    U && u.append(U);
    const be = e("div", "radar-topic-footer"),
      Le = !!s?.plan?.limits?.saved_brief_enabled,
      He = s?.plan?.limits?.dossier_write_enabled === !0,
      Ae = k?.enabled === !0,
      je = e("div", "radar-review-explainer");
    (je.append(
      e(
        "strong",
        "",
        "04 · 结束本轮 · " + (Le ? "留存不可变简报" : "仅更新复盘水位"),
      ),
    ),
      je.append(
        e(
          "p",
          "",
          (Le
            ? "当前服务端允许冻结最多 8 条的上轮简报，并推进复盘基线。"
            : "当前服务端只允许推进复盘水位，不生成永久简报。") +
            (He ? " 可在事件详情人工保存研判版本。" : "") +
            (Ae ? " 到期复核见下方服务端队列。" : "") +
            " 本轮已阅不等于逐条读完原文，也不改变已读与收藏。",
        ),
      ),
      je.append(
        e(
          "small",
          "",
          "键盘：聚焦事件卡后按 1 / 2 / 3 分诊，按 0 撤销；再次点击已选项也可撤销。",
        ),
      ),
      be.append(je));
    const Ce = e("div", "radar-topic-cta"),
      Pe = q(
        Le ? "本轮已阅 · 保存简报" : "本轮已阅 · 更新水位",
        "button secondary radar-review-button",
        "check",
        () => Ia(n, Pe),
      );
    ((Pe.disabled = O), (Pe.dataset.radarFocus = "review:" + d));
    const Ze = q(
      "去工作台进一步搜索",
      "button primary radar-workspace-button",
      "arrow",
      () => o(n),
    );
    return (
      (Ze.dataset.radarFocus = "workspace:" + d),
      Ce.append(Pe, Ze),
      be.append(Ce),
      u.append(be),
      u
    );
  }
  function Ie(n) {
    const d = n?.raw_leads || {},
      u = Array.isArray(d.items) ? d.items : [],
      p = e("section", "radar-raw-leads");
    p.setAttribute("aria-label", "尚未整理原文线索");
    const b = e("div", "radar-raw-heading");
    if (
      (b.append(
        e("h4", "", "近 48 小时 · 仅原文线索"),
        et("尚未整理 / 未核实", "raw-only"),
      ),
      p.append(b),
      p.append(
        e(
          "p",
          "radar-raw-scope",
          "按 UTC 首次收录时间，最近最多 " +
            y(ve(d.scan_cap || 2400)) +
            " 条未整理原文中筛选标题/正文 AND 关键词及所选平台；最多显示 " +
            y(ve(d.display_cap || 4)) +
            " 条。排除已整理和已过滤原文，非全量搜索；不参与上方事件分诊、简报或重要度评分。",
        ),
      ),
      !u.length)
    )
      p.append(
        e(
          "p",
          "radar-raw-empty",
          "此抽样窗口内暂无匹配原文；可能尚未采集或超出扫描上限，不代表没有新消息。",
        ),
      );
    else {
      const v = e("div", "radar-raw-grid");
      for (const x of u) {
        const w = typeof x?.id == "string" ? x.id : "",
          $ = e("article", "radar-raw-card");
        $.dataset.rawId = w;
        const T = e("div", "radar-raw-card-heading");
        (T.append(
          et("仅原文 · 未核实", "raw-only"),
          et(Cn(x?.state, x?.content_type), "raw-state"),
        ),
          $.append(T),
          $.append(
            e("h5", "radar-raw-title", oe(x?.title, 300) || "无标题原始记录"),
          ),
          x?.preview &&
            $.append(e("p", "radar-raw-preview", oe(x.preview, 520))),
          $.append(
            e(
              "p",
              "radar-raw-meta",
              mt(x?.platform) +
                " · " +
                (oe(x?.source_name, 100) || "来源名称未提供") +
                " · 首次收录 " +
                Tn(x?.first_ingested_at),
            ),
          ));
        const S = e("div", "radar-raw-actions");
        if (w) {
          const V = q(
            "核对原始收件箱记录",
            "button secondary radar-raw-inspect",
            "inbox",
            () => Oe(x),
          );
          ((V.dataset.radarFocus = "raw:" + String(n.id) + ":" + w),
            S.append(V));
        }
        const M = ht(x?.url);
        if (M) {
          const V = e("a", "radar-raw-external", "打开原始来源 ↗");
          ((V.href = M),
            (V.target = "_blank"),
            (V.rel = "noopener noreferrer"),
            V.setAttribute(
              "aria-label",
              "新窗口核对原始来源：" + (oe(x?.title, 90) || "无标题原文"),
            ),
            S.append(V));
        }
        ($.append(S), v.append($));
      }
      p.append(v);
    }
    return (
      p.append(
        q("浏览完整原始收件箱", "text-button radar-raw-inbox", "arrow", () =>
          l?.(),
        ),
      ),
      p
    );
  }
  function Ge() {
    if (me?.isConnected) return me;
    const n = e("dialog", "radar-raw-dialog");
    ((n.id = "radar-raw-dialog"),
      n.setAttribute("aria-labelledby", "radar-raw-detail-title"));
    const d = e("div", "dialog-header"),
      u = e("h2", "", "核对原始收件箱记录");
    ((u.id = "radar-raw-detail-title"),
      d.append(
        u,
        Jt("关闭原始记录", "close", () => n.close()),
      ));
    const p = e("div", "radar-raw-detail");
    return (
      (p.id = "radar-raw-detail-body"),
      n.append(d, p),
      document.body.append(n),
      ct(n, {
        onClose: () => {
          E++;
        },
      }),
      (me = n),
      n
    );
  }
  async function Oe(n) {
    const d = typeof n?.id == "string" ? n.id : "";
    if (!d) return;
    const u = Ge(),
      p = i("#radar-raw-detail-body", u),
      b = ++E;
    (p.replaceChildren(e("p", "radar-raw-loading", "正在读取原始收件箱记录…")),
      u.open || ut(u));
    try {
      const v = await t("/api/inbox/" + encodeURIComponent(d));
      if (b !== E || !u.open) return;
      const x = v?.item || v;
      if (String(x?.id ?? "") !== d)
        throw new Error("返回的原文编号不符，请刷新后重试。");
      (p.replaceChildren(),
        p.append(et("仅原文 · 未核实，不等于已整理事件", "raw-only")),
        p.append(e("h3", "", oe(x.title, 450) || "无标题原始记录")),
        p.append(
          e(
            "p",
            "radar-raw-meta",
            mt(x.platform) +
              " · " +
              Cn(x.state, x.content_type) +
              " · 首次收录 " +
              Tn(x.first_ingested_at),
          ),
        ),
        p.append(
          e(
            "p",
            "radar-raw-detail-source",
            "原始来源：" + (oe(x.name, 120) || "未提供来源名称"),
          ),
        ));
      const w = oe(x.text, 12e3);
      (p.append(
        e("div", "radar-raw-fulltext", w || "原始正文为空，请核对来源链接。"),
      ),
        typeof x.text == "string" &&
          x.text.length > 12e3 &&
          p.append(
            e("p", "radar-raw-scope", "原文较长，当前仅展示前 12,000 字符。"),
          ));
      const $ = e("div", "radar-raw-detail-actions"),
        T = ht(x.url);
      if (T) {
        const S = e(
          "a",
          "button secondary radar-raw-external",
          "打开原始来源 ↗",
        );
        ((S.href = T),
          (S.target = "_blank"),
          (S.rel = "noopener noreferrer"),
          $.append(S));
      }
      ($.append(
        q("浏览原始收件箱", "button secondary", "inbox", () => {
          (u.close(), l?.());
        }),
      ),
        p.append($));
    } catch (v) {
      if (b !== E || !u.open) return;
      (p.replaceChildren(
        e("p", "radar-inline-error", "读取原始记录失败：" + oe(v.message, 300)),
      ),
        p.append(
          q("前往原始收件箱", "button secondary", "inbox", () => {
            (u.close(), l?.());
          }),
        ));
    }
  }
  function Je(n) {
    const d = or(n),
      u = e("div", "radar-trend"),
      p = e("div", "radar-trend-heading");
    if (
      (p.append(e("span", "", "按天趋势"), e("small", "", "首次收录 / UTC 日")),
      u.append(p),
      !d.length)
    )
      return (u.append(e("div", "radar-trend-no-data", "暂无按天趋势")), u);
    const b = e("div", "radar-trend-bars");
    (b.setAttribute("role", "img"), b.setAttribute("aria-label", lr(d)));
    const v = Math.max(1, ...d.map((w) => w.count));
    for (const w of d) {
      const $ = e(
        "span",
        "radar-trend-column" + (w.count === v && w.count ? " is-peak" : ""),
      );
      (($.style.height =
        (w.count ? Math.round(12 + (w.count / v) * 88) : 3) + "%"),
        ($.title = w.day + " 首次收录 " + y(w.count) + " 条"),
        $.setAttribute("aria-hidden", "true"),
        b.append($));
    }
    u.append(b);
    const x = e("div", "radar-trend-axis");
    return (
      x.append(
        e("span", "", d[0].day.slice(5)),
        e("span", "", "最高 " + y(v) + " / 天"),
        e("span", "", d.at(-1).day.slice(5)),
      ),
      u.append(x),
      u
    );
  }
  function Ct(n, d, u = !1) {
    const p = e("article", "radar-highlight-card"),
      b = String(n?.id ?? "");
    p.dataset.id = b;
    const v = !d?.id;
    (p.classList.add(v ? "radar-global-card" : "radar-personal-card"),
      v || (p.dataset.evidenceFeatured = String(u)),
      v ||
        ((p.tabIndex = 0),
        (p.dataset.radarFocus = "highlight:" + String(d.id) + ":" + b),
        p.setAttribute(
          "aria-label",
          "个人线索卡，按 1 忽略、2 持续关注、3 深入研判、0 撤销分诊",
        )));
    const x = pr(n?.importance);
    p.classList.add("priority-" + x.level);
    const w = e("div", "radar-highlight-head");
    (v ||
      w.append(
        et("个人匹配 " + y(ve(n?.personal_relevance)) + " / 100", "personal"),
      ),
      w.append(et("编辑重要度 " + x.score + " / 100", x.level)),
      w.append(e("span", "radar-highlight-category", nn(n?.category))),
      w.append(et(Me(n) ? "已读" : "未读", Me(n) ? "read" : "unread")),
      n?.bookmarked && w.append(et("已收藏", "bookmarked")),
      n?.archived && w.append(et("已归档 · 超出当前阅读窗口", "archived")));
    const $ = { dismiss: "忽略", watch: "持续关注", research: "深入研判" };
    (Object.hasOwn($, n?.decision) &&
      w.append(et("已分诊 · " + $[n.decision], "decision")),
      p.append(w));
    const T = q("", "radar-event-open", null, () => a(b));
    (T.append(e("strong", "", oe(n?.title, 350) || "未命名资讯")),
      T.setAttribute(
        "aria-label",
        "打开事件详情：" + (oe(n?.title, 350) || "未命名资讯"),
      ),
      (T.disabled = !b),
      (T.dataset.radarFocus = (v ? "global-event:" : "event:") + b),
      p.append(T),
      n?.summary &&
        p.append(e("p", "radar-highlight-summary", oe(n.summary, 900))));
    const S = cr(n),
      M = e("div", "radar-highlight-meta"),
      V =
        S.kind === "event"
          ? " · " + S.evidence_label + "（" + S.calendar_kind + "）"
          : S.value
            ? " · " + Ve(S.value, S.kind === "ingested")
            : "";
    (M.append(e("span", "radar-time-" + S.kind, S.label + V)),
      n?.location_status &&
        M.append(
          e(
            "span",
            "",
            n.location_status === "located"
              ? "存在位置依据"
              : n.location_status === "global"
                ? "全球性事件"
                : "地点待确认",
          ),
        ),
      p.append(M),
      v || p.append(f.render(n, d, u)));
    const D = e("div", "radar-highlight-sources"),
      Z = Array.isArray(n?.sources) ? n.sources : [];
    if (!v) {
      const Ae = e("div", "radar-card-step radar-evidence-step");
      (Ae.append(
        e("strong", "", "01 · 查原始出处"),
        e("small", "", "点击安全外链自愿核对，链接存在不代表主张已证实"),
      ),
        D.append(Ae));
    }
    const U = ur(Z),
      be = y(n?.source_count ?? Z.length),
      Le = v
        ? "关联原文 · " + be + " 条记录（独立性未核实）"
        : "事件关联 " +
          be +
          " 条已完成原文（未必命中主题） · 本主题词项命中且可安全打开 " +
          y(U.length) +
          " 条（最多3条，未经事实核实）";
    D.append(e("span", "radar-sources-label", Le));
    let He = 0;
    for (const { source: Ae, href: je } of U) {
      const Ce = e(
        "a",
        "radar-source-link",
        oe(Ae?.name, 60) || mt(Ae?.platform),
      );
      ((Ce.href = je),
        (Ce.rel = "noopener noreferrer"),
        (Ce.target = "_blank"),
        Ce.setAttribute(
          "aria-label",
          "新窗口打开原始证据：" + (oe(Ae?.name, 60) || mt(Ae?.platform)),
        ),
        D.append(Ce),
        He++);
    }
    if (
      (He ||
        D.append(
          e(
            "span",
            "radar-no-links",
            "原始链接暂不可安全打开；请到事件详情核对，不要仅凭摘要判断事实",
          ),
        ),
      p.append(D),
      typeof n?.why == "string" && n.why.trim())
    ) {
      const Ae = e("details", "radar-why-details");
      (Ae.append(
        e("summary", "", "为何进入重点列表"),
        e("p", "", oe(n.why, 1200)),
      ),
        p.append(Ae));
    }
    if (!v) {
      const Ae = e("div", "radar-card-step radar-decision-heading");
      (Ae.append(
        e("strong", "", "02 · 我接下来怎么处理？"),
        e("small", "", "人工行动选择 · 与内容是否有用无关"),
      ),
        p.append(Ae));
      const je = e("div", "radar-decision-controls");
      (je.setAttribute("role", "group"),
        je.setAttribute("aria-label", "人工分诊：" + oe(n?.title, 120)));
      const Ce = Zt("");
      Ce.hidden = !0;
      const Pe = new Map();
      for (const [ke, Fe, rt] of [
        ["dismiss", "忽略", "1"],
        ["watch", "持续关注", "2"],
        ["research", "深入研判", "3"],
      ]) {
        const Ye = ke === n?.decision,
          dt = q(
            Fe,
            "button radar-decision-button" + (Ye ? " selected" : ""),
            null,
            () => jt(d, n, Ye ? null : ke, dt, Ce),
          );
        ((dt.dataset.radarDecision = ke),
          (dt.dataset.radarFocus =
            "decision:" + String(d.id) + ":" + b + ":" + ke),
          dt.setAttribute("aria-pressed", String(Ye)),
          (dt.title = Ye
            ? "当前为“" + Fe + "”，再点一次可撤销"
            : "把这条情报分诊为“" + Fe + "”"),
          (dt.disabled = O),
          Pe.set(rt, dt),
          je.append(dt));
      }
      if (
        (p.addEventListener("keydown", (ke) => {
          ke.target !== p ||
            ke.altKey ||
            ke.ctrlKey ||
            ke.metaKey ||
            ke.isComposing ||
            O ||
            (["0", "1", "2", "3"].includes(ke.key) &&
              (ke.preventDefault(),
              ke.stopPropagation(),
              ke.key === "0"
                ? n?.decision != null && jt(d, n, null, p, Ce)
                : Pe.get(ke.key)?.click()));
        }),
        p.append(je, Ce),
        u)
      ) {
        const ke = p.querySelector(".radar-evidence-workbench");
        ke && p.append(ke);
      }
      const Ze = e("div", "radar-usefulness");
      Ze.setAttribute("aria-label", "与分诊行动独立的个人价值评价");
      const xe = e("div", "radar-usefulness-hint");
      xe.append(
        e("strong", "", "03 · 内容对我有用吗？"),
        e("small", "", "与三态行动独立 · 再点已选项可撤销"),
      );
      const Re = e("div", "radar-usefulness-controls");
      (Re.setAttribute("role", "group"),
        Re.setAttribute("aria-label", "本人价值反馈：" + oe(n?.title, 120)));
      const Xe = Zt("");
      Xe.hidden = !0;
      const at = ["useful", "noise"].includes(n?.usefulness)
        ? n.usefulness
        : null;
      for (const [ke, Fe] of [
        ["useful", "值得看"],
        ["noise", "没帮助"],
      ]) {
        const rt = at === ke,
          Ye = q(
            Fe,
            "button radar-usefulness-button" + (rt ? " selected" : ""),
            null,
            () => It(d, n, rt ? null : ke, Ye, Xe),
          );
        ((Ye.dataset.radarUsefulness = ke),
          (Ye.dataset.radarFocus =
            "usefulness:" + String(d.id) + ":" + b + ":" + ke),
          Ye.setAttribute("aria-pressed", String(rt)),
          (Ye.title = rt
            ? "已选择「" + Fe + "」，再点一次撤销评价"
            : "将此线索评价为「" + Fe + "」"),
          (Ye.disabled = O || !b),
          Re.append(Ye));
      }
      (Ze.append(xe, Re, Xe), p.append(Ze));
    }
    return p;
  }
  function Ht(n, d, u) {
    const p = Ne(".radar-topic-card", m).find(
      ($) => $.dataset.topicId === String(n.id),
    );
    if (!p) return;
    const b = Ne("[data-radar-focus]", p).find(
      ($) => $.dataset.radarFocus === u,
    );
    if (
      b &&
      !b.closest("[hidden]") &&
      !b.disabled &&
      (b.focus({ preventScroll: !0 }), document.activeElement === b)
    )
      return;
    const v = Ne(".radar-personal-card:not([hidden])", p),
      x = v.find(($) => $.dataset.id !== String(d.id)) || v[0];
    if (x) {
      x.focus({ preventScroll: !0 });
      return;
    }
    Ne("[data-radar-focus]", p)
      .find(
        ($) => $.dataset.radarFocus === "review:" + String(n.id) && !$.disabled,
      )
      ?.focus({ preventScroll: !0 });
  }
  async function It(n, d, u, p, b) {
    if (O || !d?.id || !n?.id) return;
    const v = B,
      x = document.activeElement,
      w =
        m?.contains(x) &&
        (x === p ||
          x?.closest?.(".radar-personal-card") ===
            p.closest(".radar-personal-card")),
      $ = p.dataset.radarFocus,
      T = p.closest(".radar-usefulness-controls"),
      S = Ne("button", T);
    let M = !1;
    ((O = !0), T.setAttribute("aria-busy", "true"));
    for (const V of S) V.disabled = !0;
    b.hidden = !0;
    try {
      const V = await t(
        "/api/radar/topics/" + encodeURIComponent(n.id) + "/usefulness",
        {
          method: "POST",
          body: JSON.stringify({ event_id: String(d.id), value: u }),
        },
      );
      if (
        v !== B ||
        ((M = !0),
        ye(n, d, "usefulness", u, V),
        await Ee({ afterWrite: !0 }),
        v !== B)
      )
        return;
      const Z = H()
          .find((Le) => String(Le.id) === String(n.id))
          ?.highlights?.find((Le) => String(Le.id) === String(d.id)),
        U = ce.has(R(n.id, d.id, "usefulness")),
        be = !U && !!Z && Z.usefulness !== u;
      $e(
        U
          ? "反馈已提交，但最新服务端版本尚未核实；14日统计暂不可用。"
          : be
            ? "反馈已提交；较新一致的服务端读取显示其他选择，已按最新服务端呈现。"
            : u == null
              ? "已撤销这条线索的价值评价"
              : u === "useful"
                ? "已标注「值得看」"
                : "已标注「没帮助」",
      );
    } catch (V) {
      v === B &&
        V?.status !== 401 &&
        ((b.textContent = [404, 409].includes(V?.status)
          ? "该事件的主题匹配或评价窗口可能已失效，请刷新雷达核对后重试。"
          : oe(V?.message, 240) || "保存评价失败，请重试；之前的选择未更改。"),
        (b.hidden = !1));
    } finally {
      if (v !== B) return;
      if (((O = !1), M && c() && s && m?.isConnected)) (nt(), w && Ht(n, d, $));
      else if (p.isConnected) {
        T.removeAttribute("aria-busy");
        for (const V of S) V.disabled = !1;
        w && p.focus({ preventScroll: !0 });
      }
    }
  }
  async function jt(n, d, u, p, b) {
    if (O || !d?.id || !n?.id) return;
    const v = B,
      x = document.activeElement,
      w =
        x === p ||
        x?.closest?.(".radar-personal-card")?.dataset?.id === String(d.id),
      $ = p?.dataset?.radarFocus;
    let T = !1;
    ((O = !0), (p.disabled = !0), (b.hidden = !0));
    try {
      const S = await t(
        "/api/radar/topics/" + encodeURIComponent(n.id) + "/decisions",
        {
          method: "POST",
          body: JSON.stringify({ event_id: String(d.id), decision: u }),
        },
      );
      if (
        v !== B ||
        ((T = !0),
        ye(n, d, "decision", u, S),
        await Ee({ afterWrite: !0 }),
        v !== B)
      )
        return;
      const V = H()
          .find((U) => String(U.id) === String(n.id))
          ?.highlights?.find((U) => String(U.id) === String(d.id)),
        D = ce.has(R(n.id, d.id, "decision")),
        Z = !D && !!V && V.decision !== u;
      $e(
        D
          ? "分诊已提交，但最新服务端版本尚未核实；主题进度暂不可用。"
          : Z
            ? "分诊已提交；较新一致的服务端读取显示其他选择，已按最新服务端呈现。"
            : u == null
              ? "已撤销这条事件的分诊"
              : u === "dismiss"
                ? "已标记忽略"
                : u === "watch"
                  ? "已加入持续关注"
                  : "已标记深入研判",
      );
    } catch (S) {
      v === B &&
        S?.status !== 401 &&
        ((b.textContent =
          S?.status === 409
            ? "匹配条件可能已变化，请刷新主题重试。"
            : S?.message),
        (b.hidden = !1));
    } finally {
      if (v !== B) return;
      ((O = !1),
        T && c() && s && m?.isConnected
          ? (nt(), w && Ht(n, d, $))
          : p.isConnected &&
            ((p.disabled = !1), w && p.focus({ preventScroll: !0 })));
    }
  }
  function Tt() {
    const n = e("section", "radar-plans");
    ((n.id = "radar-plans"),
      n.setAttribute("aria-labelledby", "radar-plans-title"));
    const d = e("div", "radar-section-heading radar-plan-heading"),
      u = e("div");
    u.append(e("span", "radar-overline", "PLANS / TRANSPARENT BY DESIGN"));
    const p = e("h2", "", "不同观察深度，清楚的能力边界");
    ((p.id = "radar-plans-title"),
      u.append(
        p,
        e(
          "p",
          "",
          "以下是产品阶段的档位比较。Pro / Analyst 金额仅为价格假设，不是销售报价；未接入支付。",
        ),
      ),
      d.append(u, et("无支付入口 · 内测阶段", "hypothesis")),
      n.append(d));
    const b = J(),
      v = e("div", "radar-pricing-grid");
    for (const w of b.plans) {
      const $ = e("article", "radar-plan-card" + (w.current ? " active" : "")),
        T = e("div", "radar-plan-top");
      (T.append(e("span", "radar-plan-label", w.label)),
        w.current && T.append(et("当前权益", "current")),
        $.append(T));
      const S = e("div", "radar-plan-price");
      (S.append(
        e(
          "strong",
          "",
          w.assumedPrice == null ? "未提供价格" : "$" + w.assumedPrice,
        ),
      ),
        S.append(
          e(
            "span",
            "",
            w.assumedPrice == null
              ? " · 服务端价目暂不可用"
              : w.assumedPrice === 0
                ? " / 免费使用"
                : " USD / 月 · 未验证假设",
          ),
        ),
        $.append(S, e("p", "radar-plan-headline", w.headline)));
      const M = e("ul", "radar-plan-features");
      if (
        (w.maxTopics != null
          ? M.append(
              e("li", "", "最多 " + y(w.maxTopics) + " 个主题（实际限额）"),
            )
          : M.append(e("li", "", "主题额度以服务端档位限制为准")),
        w.historyDays != null &&
          M.append(
            e("li", "", "事件追踪范围：最近 " + y(w.historyDays) + " 天"),
          ),
        w.trendDays != null &&
          M.append(
            e("li", "", "每日趋势：最近 " + y(w.trendDays) + " 天（UTC）"),
          ),
        w.historyDays == null)
      )
        for (const U of w.features) M.append(e("li", "", U + " · 规划方向"));
      $.append(M);
      const V = w.limits || {},
        D = e("p", "radar-plan-review-rights");
      (D.append(e("strong", "", "本轮复盘 / ")),
        V.saved_brief_enabled === !0
          ? D.append(document.createTextNode("可保存不可变上轮简报"))
          : V.saved_brief_enabled === !1
            ? D.append(document.createTextNode("仅更新水位，不保存简报"))
            : D.append(document.createTextNode("权益待服务端确认")),
        V.dossier_write_enabled === !0 &&
          D.append(document.createTextNode(" · 可人工保存研判")),
        V.review_due_enabled === !0 &&
          D.append(document.createTextNode(" · 到期复核队列（无推送）")),
        $.append(D));
      const Z = q(
        w.current ? "当前内测权益，无需付费" : "未开通购买与切换",
        "button " +
          (w.current ? "secondary selected" : "secondary") +
          " radar-plan-action",
      );
      ((Z.disabled = !0), $.append(Z), v.append($));
    }
    n.append(v);
    const x = e(
      "p",
      "radar-pricing-note",
      b.verified
        ? "主题数等服务端返回的限制具有实际约束力；其他描述为产品方向说明。单用户当前权益不代表已付款、订阅生效或正式对外销售。"
        : "档位接口未提供完整的权益信息，上方仅作产品规划展示。实际操作权限以雷达接口为准；没有扣款、结算或模拟支付按钮。",
    );
    return (n.append(x), n);
  }
  function Ca() {
    const n = i("#radar-first-run", m);
    (n?.scrollIntoView({ behavior: "smooth", block: "start" }),
      n?.querySelector(".radar-first-cta")?.focus({ preventScroll: !0 }));
  }
  function Ta() {
    const n = i(".radar-personal-card:not([hidden])", m),
      d =
        n?.querySelector(".radar-source-link") ||
        n?.querySelector(".radar-decision-button") ||
        i(".radar-raw-inspect", m) ||
        i(".radar-topic-area", m);
    d &&
      (d.scrollIntoView({ behavior: "smooth", block: "center" }),
      ["BUTTON", "A"].includes(d.tagName) || (d.tabIndex = -1),
      d.focus({ preventScroll: !0 }));
  }
  function Ea() {
    const n = i(".radar-personal-card", m) || i(".radar-raw-leads", m);
    if (!n) return Wt();
    ((n.tabIndex = -1),
      n.scrollIntoView({ behavior: "smooth", block: "center" }),
      n.focus({ preventScroll: !0 }));
  }
  function Wt() {
    i("#radar-plans", m)?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
    const n = i("#radar-plans-title", m);
    n && ((n.tabIndex = -1), n.focus({ preventScroll: !0 }));
  }
  function jn(n) {
    return {
      query: i("#radar-topic-query", n).value,
      platforms: Ne('input[name="platforms"]:checked', n).map((d) => d.value),
      min_importance: Number(i("#radar-score-input", n).value),
    };
  }
  function Wn(n) {
    return JSON.stringify(jn(n));
  }
  function Gt(n, d = !1) {
    F++;
    const u = d && !["idle", void 0].includes(n.dataset.previewState);
    n.dataset.previewState = u ? "expired" : "idle";
    const p = i("#radar-preview-result", n);
    p &&
      (p.replaceChildren(),
      (p.hidden = !0),
      p.setAttribute("aria-busy", "false"));
    const b = i("#radar-preview-next", n);
    (b && (b.replaceChildren(), (b.hidden = !0)),
      i("#radar-save-step", n)?.removeAttribute("data-preview-guided"));
    const v = i("#radar-preview-trigger", n);
    v &&
      (v.setAttribute("aria-expanded", "false"),
      (v.querySelector("span").textContent = "先试查真实匹配（不创建主题）"));
    const x = i("#radar-preview-status", n);
    x &&
      (x.textContent = u
        ? "输入条件已改变，上一轮试查已过期且已隐藏；请手动重新试查。"
        : "尚未试查。填写关键词和筛选条件，再点击按钮；不会创建或修改主题。");
  }
  function cn(n, d, u, p) {
    return (
      d === F && u === I && n === ge && n.isConnected && n.open && Wn(n) === p
    );
  }
  function yt(n) {
    return Number.isSafeInteger(n) && n >= 0 ? y(n) : "待确认";
  }
  function Gn(n, d, u) {
    const p = e("li", "radar-preview-item " + u);
    return (
      p.append(
        e("strong", "radar-preview-item-title", n),
        e("p", "radar-preview-item-meta", d),
      ),
      p
    );
  }
  function Na(n, d, u, p, b) {
    const v = i("#radar-preview-next", n),
      x =
        Number.isSafeInteger(d.matched_events) && d.matched_events >= 0
          ? d.matched_events
          : null,
      w =
        Number.isSafeInteger(d.raw_display_cap) && d.raw_display_cap >= 0
          ? Math.min(4, d.raw_display_cap)
          : 4,
      $ = Array.isArray(d.raw_samples)
        ? Math.min(w, d.raw_samples.filter(Boolean).length)
        : 0,
      T = x !== null && x > 0,
      S = x === 0 && $ > 0,
      M = x === 0 && $ === 0,
      V = j !== null,
      D = T
        ? i(
            "#radar-preview-result .radar-preview-event .radar-preview-source-link",
            n,
          )
        : S
          ? i(
              "#radar-preview-result .radar-preview-raw .radar-preview-source-link",
              n,
            )
          : null,
      Z = e(
        "div",
        "radar-preview-next-card " +
          (T ? "has-history" : S ? "raw-only" : "zero"),
      );
    (Z.append(
      e(
        "strong",
        "",
        T
          ? "下一步 · 有 " + y(x) + " 条已整理历史匹配，先核出处再决定是否创建"
          : S
            ? "下一步 · 只有 " + y($) + " 条有限原文样本，尚不能三态分诊"
            : M
              ? "下一步 · 两类记录都没有可展示的匹配，先调整条件"
              : "下一步 · 历史数量无法确认，建议先检查条件",
      ),
    ),
      Z.append(
        e(
          "p",
          "",
          T
            ? D
              ? "可直接在新窗口打开首条已完成关联原文（不保存），不必在样本滚动区里寻找链接；如需先检查三钟，再使用下方定位按钮。单条原文不等于独立核实。"
              : "本次已整理样本没有可安全打开的原始出处，不能仅凭标题核实。无需保存；可以改条件重新试查。"
            : S
              ? D
                ? "这是有限扫描的未经核实原文样本，不是原文总量。可直接在新窗口打开首条原文（不保存）；尚不能三态分诊。"
                : "这是最近有限扫描的未经核实样本，并非原文总量；当前没有可安全打开的原始出处，不能仅凭标题核实。待整理成事件才能三态分诊。"
              : M
                ? "这不代表全网无消息。试查只按已收录可搜索文字中的词项作字面匹配，不会跨语言自动翻译或扩词。若你核对过公开原文中的英文专名/简称，可自愿改用原文词项再手动试查（不保证有匹配）；也可减少 AND 词、降低门槛或放宽平台。"
                : "暂不依据未知的历史数量指导创建；可以改条件再手动试查。",
        ),
      ));
    const U = e("div", "radar-preview-next-actions"),
      be = () => !O && n.dataset.previewState === "ready" && cn(n, u, p, b),
      Le = (He) => {
        !be() ||
          !He?.isConnected ||
          (He.scrollIntoView({ behavior: "auto", block: "center" }),
          He.focus({ preventScroll: !0 }));
      };
    if (T || S) {
      if (D) {
        const Ce = ht(D.getAttribute("href"));
        if (Ce) {
          // V137: direct-open previously hid the destination behind a generic CTA.
          // Show the exact URL origin BEFORE the user's voluntary outbound click.
          // This is provenance transparency, never an authenticity endorsement.
          const destination = new URL(Ce);
          const destinationInfo = e("div", "radar-preview-destination");
          destinationInfo.append(
            e("strong", "", "即将打开的外部地址："),
            e("code", "radar-preview-destination-origin", destination.origin),
            e(
              "p",
              "",
              (destination.protocol === "http:" ? "HTTP 连接未加密。" : "") +
                "域名取自已收录链接，页面可能跳转或失效；不是一手来源、事实或来源独立性已核实的证明。请本人去原站核对发布者、日期及反证。",
            ),
          );
          U.append(destinationInfo);
          const Ze = e(
            "a",
            "button secondary radar-preview-next-secondary radar-preview-source-direct",
            T
              ? "直接打开首条已完成关联原文 ↗（新窗口 · 不保存）"
              : "直接打开首条未整理原文 ↗（新窗口 · 不保存）",
          );
          ((Ze.href = Ce),
            (Ze.target = "_blank"),
            (Ze.rel = "noopener noreferrer"),
            Ze.setAttribute(
              "aria-label",
              (T
                ? "新窗口打开首条已完成关联原文"
                : "新窗口打开首条未整理原文") +
                "；目的站 " + destination.origin +
                "；将访问第三方网站，可能跳转，不保存主题、不代表核实",
            ),
            Ze.addEventListener("click", (xe) => {
              (!be() ||
                !D.isConnected ||
                !i("#radar-preview-result", n)?.contains(D)) &&
                xe.preventDefault();
            }),
            U.append(Ze));
        }
        const Pe = q(
          "先查看原始出处（不保存）",
          "button secondary radar-preview-next-secondary radar-preview-source-jump",
          "arrow",
          () => {
            !be() ||
              !D.isConnected ||
              !i("#radar-preview-result", n)?.contains(D) ||
              (D.scrollIntoView({ behavior: "auto", block: "center" }),
              D.focus({ preventScroll: !0 }));
          },
        );
        ((Pe.id = "radar-preview-source-jump"), U.append(Pe));
      }
      const He = q(
        V ? "本人核对条件并保存修改" : D
          ? "本人确认关注条件 · 保存主题（不自动判断）"
          : "本人保存主题 · 原文仍待核对",
        "button primary radar-preview-next-primary",
        "arrow",
        () => {
          if (!be()) return;
          const Ce = i("#radar-save-step", n),
            Pe = i("#radar-topic-name", n);
          Ce.dataset.previewGuided = "true";
          if (!Pe.value.trim()) {
            Ce.scrollIntoView({ behavior: "auto", block: "nearest" });
            Le(Pe);
            return;
          }
          // One intentional owner action via native validation, CSRF, receipt.
          i("#radar-form-submit", n)?.click();
        },
      );
      ((He.id = "radar-preview-next-primary"), U.append(He));
      const Ae = e("div", "radar-preview-finish-choices");
      Ae.append(
        q(
          "改关键词再试查",
          "button secondary radar-preview-next-secondary",
          "edit",
          () => Le(i("#radar-topic-query", n)),
        ),
      );
      const je = q(
        V ? "结束试查 · 不保存修改" : "结束试查 · 不创建主题",
        "button secondary radar-preview-next-secondary radar-preview-finish",
        null,
        () => {
          if (!be()) return;
          ((C =
            P?.isConnected && !P.matches(":disabled") ? P : i("#radar-new", m)),
            n.close());
        },
      );
      ((je.id = "radar-preview-finish"), Ae.append(je), U.append(Ae));
    } else {
      if (M) {
        // V141: zero-result recovery happens where the person is reading it.
        // This is a NEW explicit owner read-only action, never an automatic
        // translation/expansion, save, triage or verification claim.
        const retry = e("div", "radar-preview-retry"),
          label = e("label", "", "自己改一个原文检索词，再主动只读试查"),
          field = e("input"),
          note = e("p", "radar-preview-retry-note",
            "可用原文里的专名、简称或较少的词试试；空格是 AND。不自动翻译或找同义词，也不保存主题。"),
          status = e("p", "radar-preview-retry-status",
            "当前显示的是上一轮零匹配结果；修改输入不会发送请求。");
        field.id = "radar-preview-retry-query";
        field.type = "text";
        field.maxLength = 160;
        field.value = i("#radar-topic-query", n)?.value || "";
        field.autocomplete = "off";
        field.setAttribute("aria-describedby", "radar-preview-retry-note radar-preview-retry-status");
        note.id = "radar-preview-retry-note";
        status.id = "radar-preview-retry-status";
        status.setAttribute("role", "status");
        label.htmlFor = field.id;
        const repeat = q(
          "按此新词重新只读试查 →（不保存）",
          "button primary radar-preview-next-primary radar-preview-retry-button",
          "search",
          () => {
            if (!be() || !field.isConnected || !n.contains(field)) return;
            const ownerQuery = field.value.trim(),
              nativeQuery = i("#radar-topic-query", n);
            if (!ownerQuery || !nativeQuery) {
              status.textContent = "请先写下真实检索词；没有发出新请求。";
              field.focus();
              return;
            }
            // Native input event expires the OLD server result and preserves
            // its original validation, auto-name rules and CSRF protection.
            nativeQuery.value = ownerQuery;
            nativeQuery.dispatchEvent(new Event("input", { bubbles: true }));
            void Ra(); // The person's explicit button/Enter is the POST consent.
          },
        );
        repeat.id = "radar-preview-next-primary";
        field.addEventListener("input", () => {
          status.textContent = "新词尚未试查；当前零匹配仍来自旧条件。";
        });
        // An input inside the native topic form must NEVER submit that form
        // when Enter is pressed: route Enter to explicit read-only retry.
        field.addEventListener("keydown", (event) => {
          if (event.key === "Enter" && !event.isComposing) {
            event.preventDefault();
            event.stopPropagation();
            repeat.click();
          }
        });
        retry.append(label, field, note, status, repeat);
        U.append(retry);
      } else {
        const He = q(
          "修改关键词后重新试查",
          "button primary radar-preview-next-primary",
          "edit",
          () => Le(i("#radar-topic-query", n)),
        );
        ((He.id = "radar-preview-next-primary"), U.append(He));
      }
      const Ae = i("#radar-score-input", n),
        je = Ne('input[name="platforms"]:not(:checked)', n)[0],
        Ce = Number(Ae.value) > 0 ? Ae : je;
      Ce &&
        U.append(
          q(
            Number(Ae.value) > 0 ? "检查最低重要度" : "检查搜索平台",
            "button secondary radar-preview-next-secondary",
            "arrow",
            () => Le(Ce),
          ),
        );
    }
    (Z.append(U), v.replaceChildren(Z), (v.hidden = !1));
  }
  function Yn(n, d, u) {
    const p = e("p", "radar-preview-source"),
      b = ht(n);
    if (!b)
      return (
        p.append(
          e(
            "span",
            "radar-preview-source-missing",
            "这条样本暂没有可安全打开的原始链接，不能仅据标题核实。",
          ),
        ),
        p
      );
    const v = e("a", "radar-preview-source-link", u);
    return (
      (v.href = b),
      (v.target = "_blank"),
      (v.rel = "noopener noreferrer"),
      v.setAttribute("aria-label", u + " · " + oe(d, 120)),
      p.append(v, e("span", "", " · " + oe(d, 120) + "（请自行核对原文）")),
      p
    );
  }
  function La(n) {
    const d = e("div", "radar-preview-content"),
      u = e("div", "radar-preview-result-head");
    (u.append(
      e("span", "radar-overline", "已收录数据 · 只读试查"),
      e("h4", "", "这组条件在当前数据里的匹配"),
      e(
        "p",
        "",
        "本次不保存主题。统计只说明已收录的过去，不预测未来，也不核实内容真假。",
      ),
    ),
      d.append(u));
    const p = e("div", "radar-preview-stats"),
      b = e("article", "radar-preview-stat radar-preview-history");
    b.append(
      e("span", "", "已整理事件 · 历史确数"),
      e("strong", "", yt(n.matched_events)),
      e(
        "p",
        "",
        "最近 " +
          yt(n.window_days) +
          " 天的历史窗口匹配；今日首次收录且已整理 " +
          yt(n.today_events) +
          " 条（按 UTC 首次收录日，不代表今日才完成整理）。不能据此预测今后消息量。",
      ),
    );
    const v = e("article", "radar-preview-stat radar-preview-originals"),
      x = Array.isArray(n.raw_samples)
        ? n.raw_samples.filter(Boolean).slice(0, 4)
        : [],
      w =
        Number.isSafeInteger(n.raw_display_cap) && n.raw_display_cap >= 0
          ? Math.min(4, n.raw_display_cap)
          : 4,
      $ = x.slice(0, w);
    (v.append(
      e("span", "", "待处理原文 · 有限扫描样本"),
      e("strong", "", y($.length) + " 条样本"),
      e(
        "p",
        "",
        "近 " +
          yt(n.raw_lookback_hours) +
          " 小时、最近最多 " +
          yt(n.raw_scan_cap) +
          " 条待处理原文的有限扫描；服务端返回 " +
          yt(n.raw_sample_count) +
          " 条展示样本（最多展示 " +
          yt(n.raw_display_cap) +
          " 条），既不是扫描命中总量，也不是原文总量。",
      ),
    ),
      p.append(b, v),
      d.append(p));
    const T = e("div", "radar-preview-lanes"),
      S = e("section", "radar-preview-lane"),
      M = e("h5", "", "已整理 · 有来源记录的事件标题"),
      V = Array.isArray(n.event_samples)
        ? n.event_samples.filter(Boolean).slice(0, 3)
        : [];
    if ((S.append(M), V.length)) {
      const Z = e("ul", "radar-preview-list");
      for (const U of V) {
        const be =
            Number.isFinite(U.importance) &&
            U.importance >= 0 &&
            U.importance <= 100
              ? y(U.importance) + " / 100"
              : "待确认",
          Le = Gn(
            oe(U.title, 240) || "事件标题待确认",
            "编辑重要度 " +
              be +
              "（不代表真实性） · 关联已完成原文记录 " +
              yt(U.source_count) +
              " 条（独立核实程度未知）",
            "radar-preview-event",
          ),
          He = e("dl", "radar-preview-clocks");
        for (const [je, Ce] of [
          ["事件发生候选", sa(U)],
          ["已完成原文最早标记发表", Ot(U.source_published_at)],
          ["本站首次收录", Ot(U.first_ingested_at)],
        ]) {
          const Pe = e("div", "radar-preview-clock");
          (Pe.append(e("dt", "", je), e("dd", "", Ce || "未知（需核对）")),
            He.append(Pe));
        }
        Le.append(He);
        const Ae = U?.source;
        (Le.append(
          Yn(
            Ae?.url,
            mt(Ae?.platform) + " · " + (oe(Ae?.name, 100) || "原始出处"),
            "打开已完成关联原文",
          ),
        ),
          Z.append(Le));
      }
      S.append(
        Z,
        e(
          "p",
          "radar-preview-clock-note",
          "发生时间按已知精度与状态呈现：确切时刻才按北京时间换算，只有日/月/区间的条目保留原文日历候选（原文时区需自行核实）；旧数据缺原文日历与精度一律标未知，不把内部 UTC 午夜当作事实发生时刻。最早标记发表取自所选平台的已完成关联原文，可能不是下方可点击的那一篇。三者不可互相冒充；请打开一手原文核对事实、时区和反证。",
        ),
      );
    } else
      S.append(
        e(
          "p",
          "radar-preview-empty",
          "历史窗口未返回已整理事件样本；不会用示例补齐。",
        ),
      );
    const D = e("section", "radar-preview-lane radar-preview-raw-lane");
    if (
      (D.append(e("h5", "", "待处理 · 原始标题样本（未经核实）")), $.length)
    ) {
      const Z = e("ul", "radar-preview-list");
      for (const U of $) {
        const be = Gn(
          oe(U.title, 240) || "原文标题待确认",
          mt(U.platform) +
            " · " +
            Cn(U.state) +
            " · 首次收录 " +
            Tn(U.first_ingested_at),
          "radar-preview-raw",
        );
        (be.append(
          Yn(
            U?.url,
            mt(U?.platform) + " · 未整理、未经事实核实",
            "打开待处理原始出处",
          ),
        ),
          Z.append(be));
      }
      D.append(Z);
    } else
      D.append(
        e(
          "p",
          "radar-preview-empty",
          "本次有限扫描未返回原文样本；这不是全部原文为零的证据。",
        ),
      );
    if (
      (T.append(S, D),
      d.append(T),
      d.append(
        e(
          "p",
          "radar-preview-evidence-note",
          "以上链接仅用于本人核对原始记录；源记录数不代表独立核实、链接存在不代表 AI 标题和摘要已证实。试查不标记已读、不建立主题。",
        ),
      ),
      n.matched_events === 0)
    ) {
      const Z = e("div", "radar-preview-diagnosis");
      (Z.append(
        e("strong", "", "已整理事件零匹配，下一步可以这样调整"),
        e(
          "p",
          "",
          "① 减少关键词之间的 AND 条件（空格表示必须同时命中）；② 降低最低重要度（可先调到 0）；③ 换选或增加平台，然后再手动试查。④ 试查只按已收录可搜索文字中的词项作字面匹配，不会跨语言自动翻译或扩词；若你核对过公开原文中的英文专名/简称，可自愿改用原文词项再手动试查（不保证有匹配）。尚未整理的原文可能还未形成事件。",
        ),
      ),
        d.append(Z));
    } else if (
      Number.isSafeInteger(n.matched_events) &&
      n.matched_events > 100
    ) {
      const Z = e(
        "p",
        "radar-preview-wide",
        "当前条件较宽，每日人工分诊可能耗时，可适当收窄。这里是历史窗口匹配确数，并非每日新增量。",
      );
      d.append(Z);
    }
    if (
      (d.append(
        e(
          "p",
          "radar-preview-result-note",
          "试查不保存 · 不核实事件真实性/来源独立性 · 没匹配不代表没有新消息。若需持续跟踪，请在下方亲自确认并提交主题。",
        ),
      ),
      typeof n.scope == "string" && n.scope.trim())
    ) {
      const Z = e("details", "radar-preview-scope");
      (Z.append(
        e("summary", "", "查看服务端实际统计口径"),
        e("p", "", oe(n.scope, 1200)),
      ),
        d.append(Z));
    }
    return d;
  }
  async function Ra() {
    const n = $n();
    if (!n.open || O) return;
    const d = aa({ name: "临时试查", ...jn(n) });
    if ((un(n), !d.ok)) {
      (Gt(n),
        pn(n, d.errors),
        (i("#radar-preview-status", n).textContent =
          "请修正上方条件后再试查；尚未发出请求，也没有创建主题。"));
      return;
    }
    const u = ++F,
      p = I,
      b = Wn(n),
      v = i("#radar-preview-result", n),
      x = i("#radar-preview-trigger", n),
      w = i("#radar-preview-next", n);
    (w.replaceChildren(),
      (w.hidden = !0),
      i("#radar-save-step", n)?.removeAttribute("data-preview-guided"),
      (n.dataset.previewState = "loading"),
      v.replaceChildren(
        e(
          "p",
          "radar-preview-loading",
          "正在读取真实收录记录…不会保存或创建主题。",
        ),
      ),
      (v.hidden = !1),
      v.setAttribute("aria-busy", "true"),
      x.setAttribute("aria-expanded", "true"),
      (x.querySelector("span").textContent = "正在试查…（可重新试查）"),
      (i("#radar-preview-status", n).textContent =
        "只读试查进行中；没有提交创建请求。"));
    const { query: $, platforms: T, min_importance: S } = d.data;
    try {
      const M = await t("/api/radar/preview", {
        method: "POST",
        body: JSON.stringify({ query: $, platforms: T, min_importance: S }),
      });
      if (!cn(n, u, p, b)) return;
      if (!M || M.preview !== !0 || M.saved !== !1)
        throw new Error("试查响应缺少「未保存」确认，已拒绝展示结果。");
      const V =
        Array.isArray(M.platforms) &&
        M.platforms.length === T.length &&
        T.every((D) => M.platforms.includes(D));
      if (M.query !== $ || M.min_importance !== S || !V)
        throw new Error(
          "服务端返回的试查条件与本次输入不同，已拒绝显示可能过期的结果。",
        );
      (v.replaceChildren(La(M)),
        (n.dataset.previewState = "ready"),
        Na(n, M, u, p, b),
        i("#radar-preview-next", n).scrollIntoView({
          behavior: "auto",
          block: "nearest",
        }),
        (i("#radar-preview-status", n).textContent =
          "试查完成：结果仅基于当前已收录数据，未创建主题。请查看下方对应的下一步。"));
    } catch (M) {
      if (!cn(n, u, p, b)) return;
      const V =
          M?.status === 404
            ? "试查接口暂未可用。可稍后重试；不会影响下方手动创建或保存。"
            : "试查失败：" +
              (oe(M?.message, 160) || "服务暂时不可用") +
              "。输入仍保留；可重试，也可直接手动提交主题。",
        D = Zt(V);
      (v.replaceChildren(D),
        (n.dataset.previewState = "error"),
        (i("#radar-preview-status", n).textContent =
          "试查未成功；无可信匹配结果可展示，也没有创建主题。"));
    } finally {
      cn(n, u, p, b) &&
        (v.setAttribute("aria-busy", "false"),
        (x.querySelector("span").textContent =
          "重新试查真实匹配（不创建主题）"));
    }
  }
  function $n() {
    if (ge?.isConnected) return ge;
    const n = e("dialog", "radar-form-dialog");
    ((n.id = "radar-form-dialog"),
      n.setAttribute("aria-labelledby", "radar-form-title"));
    const d = e("div", "dialog-header"),
      u = e("h2", "", "创建雷达主题");
    ((u.id = "radar-form-title"),
      d.append(
        u,
        Jt("关闭主题编辑", "close", () => {
          O || n.close();
        }),
      ));
    const p = e("form", "radar-form");
    ((p.id = "radar-topic-form"), (p.noValidate = !0));
    const b = e("p", "radar-form-first-context");
    ((b.id = "radar-form-context"), p.append(b));
    const activationSteps = e("ol", "radar-activation-steps");
    for (const label of ["本人填词", "只读试查", "原文核对", "明确保存", "手动分诊"])
      activationSteps.append(e("li", "", label));
    activationSteps.setAttribute("aria-label", "首次激活的五个由本人选择的步骤，无自动完成");
    p.append(activationSteps);
    const v = e("label", "radar-form-label", "③ 给真实关注起个主题名"),
      x = e("input");
    ((x.name = "name"),
      (x.id = "radar-topic-name"),
      (x.required = !0),
      (x.maxLength = 48),
      (x.placeholder = "例如：我的量子纠错路线观察"),
      (v.htmlFor = x.id),
      v.append(x));
    const w = e("label", "radar-form-label", "① 输入你真正在意的关键词 / 短语"),
      $ = e("textarea");
    (($.name = "query"),
      ($.id = "radar-topic-query"),
      ($.rows = 3),
      ($.required = !0),
      ($.maxLength = 160),
      ($.placeholder = "例如：量子计算（首次先用一个关键词）"),
      (w.htmlFor = $.id),
      w.append($));
    const T = e("p", "radar-query-feedback");
    const nameNote = e("p", "radar-auto-name-note");
    nameNote.id = "radar-auto-name-note";
    ((T.id = "radar-query-feedback"),
      T.setAttribute("role", "status"),
      T.setAttribute("aria-live", "polite"),
      $.setAttribute("aria-describedby", "radar-query-feedback radar-auto-name-note"),
      $.addEventListener("input", () => {
        T.textContent = An($.value);
        if (x.dataset.radarAutoName === "true") {
          x.value = $.value.trim().replace(/\s+/g, " ").slice(0, 48);
          nameNote.textContent = x.value
            ? "主题名＝你刚输入的词（保存前可修改）；尚未自动创建。"
            : "你输入关键词后会用同一文字作为可编辑主题名，不会自动创建。";
        }
      }),
      x.addEventListener("input", () => {
        x.dataset.radarAutoName = "false";
        nameNote.textContent = "主题名已由你单独编辑；后续修改关键词不会覆盖名称。";
      }),
      p.append(
        w,
        T,
        nameNote,
        e(
          "p",
          "radar-form-hint",
          "空格是 AND（全都要匹配），不是自然语言搜索；最多 8 个条件。一个中文短语无需加空格。",
        ),
        Yt("query"),
      ));
    const S = e("fieldset", "radar-platforms");
    S.append(e("legend", "", "搜索平台（可多选）"));
    const M = e("div", "radar-platform-options");
    for (const Fe of ln) {
      const rt = e("label", "radar-platform-choice"),
        Ye = e("input");
      ((Ye.type = "checkbox"),
        (Ye.name = "platforms"),
        (Ye.value = Fe.id),
        rt.append(Ye, e("span", "", Fe.label)),
        M.append(rt));
    }
    S.append(M);
    const V = e("div", "radar-score-field"),
      D = e("div");
    D.append(e("label", "", "最低重要度"));
    const Z = e("output", "", "0 / 100 · 不设门槛");
    ((Z.id = "radar-score-value"), D.append(Z), V.append(D));
    const U = e("input");
    ((U.type = "range"),
      (U.name = "min_importance"),
      (U.id = "radar-score-input"),
      (U.min = "0"),
      (U.max = "100"),
      (U.step = "5"),
      U.setAttribute("aria-label", "最低重要度，0 到 100"),
      (U.oninput = () => {
        Z.textContent =
          U.value + " / 100" + (U.value === "0" ? " · 不设门槛" : "");
      }),
      V.append(
        U,
        e(
          "p",
          "radar-form-hint",
          "首次默认 0（不筛掉低分的已整理事件），有结果后可再提高；未整理原文没有分数。",
        ),
      ));
    const filters = e("details", "radar-first-filters");
    filters.id = "radar-first-filters";
    filters.append(
      e("summary", "", "可选筛选 · 默认全平台 / 重要度 0（不限）"),
      S, Yt("platforms"), V, Yt("min_importance"),
    );
    p.append(filters);
    const be = e("section", "radar-preview-check");
    ((be.id = "radar-preview-check"),
      be.setAttribute("aria-label", "只读试查真实匹配"));
    const Le = e("div", "radar-preview-top");
    Le.append(
      e("span", "radar-preview-eyebrow", "② 本人手动试查 · 不保存"),
      e("h3", "", "先看看真实收录里有没有线索"),
      e(
        "p",
        "",
        "无需先起名；按上方条件主动试查历史事件与待处理原文。",
      ),
      e(
        "p",
        "radar-preview-privacy",
        "知情提示：点击试查才会将关键词、所选平台和最低重要度发送到当前连接的云端服务；“不创建主题”只表示本次不保存主题，服务端仍可能留下请求日志。打开原文链接会访问第三方网站。若不愿发送，请直接取消。",
      ),
    );
    const He = q(
      "先试查真实匹配（不创建主题）",
      "button secondary radar-preview-trigger",
      "search",
      Ra,
    );
    ((He.id = "radar-preview-trigger"),
      He.setAttribute("aria-controls", "radar-preview-result"),
      He.setAttribute("aria-expanded", "false"));
    const Ae = e(
      "p",
      "radar-preview-status",
      "尚未试查。点击按钮才会查询，不会自动请求。",
    );
    ((Ae.id = "radar-preview-status"),
      Ae.setAttribute("role", "status"),
      Ae.setAttribute("aria-live", "polite"));
    const je = e("div", "radar-preview-next");
    ((je.id = "radar-preview-next"), (je.hidden = !0));
    const Ce = e("div", "radar-preview-result");
    ((Ce.id = "radar-preview-result"),
      (Ce.hidden = !0),
      Ce.setAttribute("role", "region"),
      Ce.setAttribute("aria-label", "本次真实匹配试查结果"),
      (Ce.tabIndex = 0),
      be.append(
        Le,
        He,
        Ae,
        je,
        Ce,
        e(
          "p",
          "radar-preview-policy",
          "试查不保存 / 不核实真实性 / 没匹配不代表没有新消息。",
        ),
      ),
      p.append(be));
    const Pe = e("section", "radar-save-step");
    ((Pe.id = "radar-save-step"),
      Pe.setAttribute("aria-labelledby", "radar-save-step-title"));
    const Ze = e("h3", "", "③ 最后核对 · 本人明确确认并创建");
    ((Ze.id = "radar-save-step-title"),
      Pe.append(
        Ze,
        e(
          "p",
          "radar-save-step-hint",
          "这里才是真正保存。起名、核对关键词和平台；首次由你点击带「我确认」的保存按钮；试查不会代替你的保存或判断。",
        ),
      ),
      Pe.append(v, Yt("name")));
    // The explicit submit activation is the owner's acknowledgement; no
    // second checkbox is silently toggled or automatically submitted.
    const xe = e("p", "radar-first-confirm");
    xe.id = "radar-first-confirm";
    xe.textContent = "只有你亲自点击保存才建立主题；试查和原文访问不保存、不自动分诊。";
    Pe.append(xe);
    const Xe = Zt("");
    ((Xe.id = "radar-form-general-error"), (Xe.hidden = !0), Pe.append(Xe));
    const at = e("div", "radar-dialog-actions");
    at.append(
      q("取消", "button secondary", null, () => {
        O || n.close();
      }),
    );
    const ke = e("button", "button primary", "创建主题");
    return (
      (ke.type = "submit"),
      (ke.id = "radar-form-submit"),
      at.append(ke),
      Pe.append(at),
      p.append(Pe),
      n.append(d, p),
      document.body.append(n),
      n.addEventListener(
        "click",
        (Fe) => {
          O && Fe.target === n && Fe.stopImmediatePropagation();
        },
        { capture: !0 },
      ),
      ct(n, {
        onClose: () => {
          (I++, Gt(n), (j = null), (re = null), un(n));
          const Fe = C;
          ((C = null),
            Fe?.isConnected &&
              !Fe.matches(":disabled") &&
              requestAnimationFrame(() => {
                !n.open && Fe.isConnected && Fe.focus({ preventScroll: !0 });
              }));
        },
      }),
      n.addEventListener("cancel", (Fe) => {
        O && Fe.preventDefault();
      }),
      p.addEventListener("input", (Fe) => {
        Fe.target.matches(
          '#radar-topic-query, #radar-score-input, input[name="platforms"]',
        ) && Gt(n, !0);
      }),
      p.addEventListener("change", (Fe) => {
        Fe.target.matches('input[name="platforms"], #radar-score-input') &&
          Gt(n, !0);
      }),
      (p.onsubmit = qa),
      (ge = n),
      n
    );
  }
  function Yt(n) {
    const d = e("p", "radar-field-error");
    return (
      (d.id = "radar-error-" + n),
      (d.hidden = !0),
      d.setAttribute("role", "alert"),
      d
    );
  }
  function un(n) {
    (Ne(".radar-field-error", n).forEach((u) => {
      ((u.textContent = ""), (u.hidden = !0));
    }),
      Ne("input,textarea", n).forEach((u) => {
        (u.removeAttribute("aria-invalid"),
          u.removeAttribute("aria-describedby"));
      }),
      i("#radar-topic-query", n)?.setAttribute(
        "aria-describedby",
        "radar-query-feedback radar-auto-name-note",
      ));
    const d = i("#radar-form-general-error", n);
    d && ((d.textContent = ""), (d.hidden = !0));
  }
  function Mt(n = null, d = null) {
    if (O) return;
    if (!n && se()) {
      ($e("当前主题数已达档位上限，可编辑或删除已有主题。"), Wt());
      return;
    }
    const u = $n(),
      p = n || d || oa,
      b = !n && !!s && H().length === 0 && !qe(),
      v = i("#radar-preview-check", u),
      x = i(".radar-platforms", u);
    (b ? i("#radar-first-filters", u).after(v) : i("#radar-save-step", u).before(v),
      (i("#radar-first-filters", u).open = !b),
      u.classList.toggle("radar-form-first-preview", b),
      (i(".radar-activation-steps", u).hidden = !b),
      (i(".radar-preview-top>p:not(.radar-preview-privacy)", u).textContent = b
        ? "默认全平台、重要度 0（不限）；需要时展开上方筛选，再主动试查。"
        : "无需先起名；按上方条件主动试查历史事件与待处理原文。"),
      (i(".radar-preview-privacy", u).textContent = b
        ? "点击试查才把关键词及筛选发到当前云端（可能留日志），不保存主题；原文打开第三方。不同意请取消。"
        : "知情提示：点击试查才会将关键词、所选平台和最低重要度发送到当前连接的云端服务；“不创建主题”只表示本次不保存主题，服务端仍可能留下请求日志。打开原文链接会访问第三方网站。若不愿发送，请直接取消。"),
      (j = n ? String(n.id) : null),
      (re = n ? n.version : null),
      (i("#radar-form-title", u).textContent = n
        ? "编辑雷达主题"
        : "新建雷达主题"),
      (i("#radar-save-step-title", u).textContent = n
        ? "③ 核对并保存本次修改"
        : "③ 最后核对 · 本人明确确认并创建"),
      (i(".radar-save-step-hint", u).textContent = n
        ? "预览不会修改已保存主题；请核对名称与筛选条件，只有亲自提交「保存修改」后才会更新。"
        : "这里才是真正保存。起名、核对关键词和平台；首次由你点击带「我确认」的保存按钮；试查不会代替你的保存或判断。"),
      (i("#radar-form-context", u).textContent = n
        ? "正在编辑已保存的真实主题，修改后会重新计算匹配。"
        : d
          ? "以下是【可编辑的示例草稿】，并非你的真实主题。请把关键词改成你实际关心的内容，先手动试查，再亲自确认保存。"
          : "由你输入关键词，主题名默认沿用且可改；先只读试查，最后亲自决定是否保存。"),
      (i("#radar-topic-name", u).value = oe(p.name, 100)),
      (i("#radar-topic-name", u).dataset.radarAutoName = String(b && !d)),
      (i("#radar-auto-name-note", u).hidden = !b || !!d),
      (i("#radar-auto-name-note", u).textContent =
        "你输入关键词后会用同一文字作为可编辑主题名，不会自动创建。"),
      (i("#radar-topic-query", u).value = oe(p.query, 500)),
      (i("#radar-query-feedback", u).textContent = An(p.query)),
      Ne('input[name="platforms"]', u).forEach(($) => {
        $.checked = (p.platforms || oa.platforms).includes($.value);
      }),
      (i("#radar-score-input", u).value = String(p.min_importance ?? 0)),
      i("#radar-score-input", u).oninput(),
      (i("#radar-first-confirm", u).hidden = !b),
      (i("#radar-form-submit", u).textContent = n
        ? "保存修改"
        : b ? "我确认这是本人真实关注 · 保存主题" : "创建主题并查看匹配"),
      I++,
      Gt(u));
    const w = document.activeElement;
    ((P =
      w instanceof HTMLElement &&
      !u.contains(w) &&
      w.matches(
        'button, a[href], input, textarea, select, [tabindex]:not([tabindex="-1"])',
      )
        ? w
        : i("#radar-new", m)),
      un(u),
      ut(u),
      i(n ? "#radar-topic-name" : "#radar-topic-query", u).focus());
  }
  function pn(n, d) {
    let u = null;
    for (const [p, b] of Object.entries(d)) {
      const v = i("#radar-error-" + p, n);
      v && ((v.textContent = b), (v.hidden = !1));
      const x = i(
        p === "platforms"
          ? 'input[name="platforms"]'
          : p === "min_importance"
            ? "#radar-score-input"
            : p === "confirm"
              ? "#radar-topic-confirm"
              : "#radar-topic-" + p,
        n,
      );
      x &&
        (x.setAttribute("aria-invalid", "true"),
        x.setAttribute(
          "aria-describedby",
          (v?.id || "") + (p === "query" ? " radar-query-feedback" : ""),
        ),
        (u ||= x));
    }
    u?.focus();
  }
  async function qa(n) {
    if ((n.preventDefault(), O)) return;
    const d = $n(),
      u = j,
      p = {
        name: i("#radar-topic-name", d).value,
        query: i("#radar-topic-query", d).value,
        platforms: Ne('input[name="platforms"]:checked', d).map((S) => S.value),
        min_importance: Number(i("#radar-score-input", d).value),
      };
    un(d);
    const b = aa(p);
    if (!b.ok) {
      pn(d, b.errors);
      return;
    }
    if (fr(H(), b.data.name, u || "")) {
      pn(d, { name: "已有同名雷达主题，可直接编辑已有主题。" });
      return;
    }
    // Explicit owner click on the labelled submit confirms this topic.
    // Preview/source browsing never triggers a topic save or any decision.
    const v = i("#radar-form-submit", d),
      x = v.textContent;
    let w = null,
      $ = !1;
    ((O = !0), (v.disabled = !0), (v.textContent = "正在保存…"));
    const T = Ne("input,textarea", d);
    for (const S of T) S.disabled = !0;
    try {
      const S = u
          ? "/api/radar/topics/" + encodeURIComponent(u)
          : "/api/radar/topics",
        M = await t(S, {
          method: u ? "PATCH" : "POST",
          body: JSON.stringify(u ? { ...b.data, version: re } : b.data),
        }),
        V = M?.topic?.id ?? M?.id;
      if (
        ((w =
          (typeof V == "string" || typeof V == "number") && String(V).trim()
            ? String(V)
            : null),
        !u && !w)
      )
        throw new Error(
          "保存响应缺少已创建的主题 ID，无法确认保存；请重新读取主题，不要直接重复提交。",
        );
      (u ||
        (he = {
          id: w,
          name: oe(M?.topic?.name, 150) || b.data.name,
          ownerRevision: ie(M?.owner_revision),
        }),
        ($ = !0),
        d.close(),
        await Ee({ afterWrite: !0 }),
        $e(
          u
            ? "雷达主题已更新"
            : "雷达主题已保存；已整理匹配才可三态分诊，未整理原文先核对，零匹配也不代表没有新闻。",
        ));
    } catch (S) {
      if (S.status !== 401) {
        const M = kr(S)
            ? S.message + "。请查看页面底部的档位说明；支付未开放。"
            : S.status === 409
              ? "主题存在冲突或已在其他窗口变更：" +
                S.message +
                "。输入已保留，可核对后重试。"
              : S.message,
          V = i("#radar-form-general-error", d);
        ((V.textContent = M), (V.hidden = !1), (V.tabIndex = -1), V.focus());
      }
    } finally {
      ((O = !1), (v.disabled = !1), (v.textContent = x));
      for (const S of T) S.disabled = !1;
      if ($ && !d.open && c() && s) {
        nt();
        const S = u || w || H().find((U) => U.name === b.data.name)?.id,
          M = Ne(".radar-topic-card", m).find(
            (U) => U.dataset.topicId === String(S),
          ),
          V =
            !u &&
            (M?.querySelector(".radar-personal-card:not([hidden])") ||
              M?.querySelector(".radar-raw-card")),
          D = i(
            '#radar-pending-topic [data-radar-focus="confirmed-topic-refresh"]',
            m,
          ),
          Z =
            V ||
            M?.querySelector("h3") ||
            D ||
            i("#radar-pending-topic", m) ||
            i("#radar-new", m);
        Z &&
          ((Z === V || Z.tagName === "H3") && (Z.tabIndex = -1),
          Z.scrollIntoView({ behavior: "auto", block: "center" }),
          Z.focus({ preventScroll: !0 }));
      }
    }
  }
  async function Ia(n, d) {
    if (O) return;
    ((O = !0), (d.disabled = !0));
    const u = d.querySelector("span");
    u && (u.textContent = "记录中…");
    try {
      (await t("/api/radar/topics/" + encodeURIComponent(n.id) + "/review", {
        method: "POST",
        body: JSON.stringify({ version: n.version }),
      }),
        await Ee({ afterWrite: !0 }),
        $e(
          s?.plan?.limits?.saved_brief_enabled
            ? "本轮简报已持久保存；阅读与收藏状态未改变。"
            : "本轮复盘水位已更新；免费档不生成永久简报，阅读与收藏状态未改变。",
        ));
    } catch (p) {
      (p.status !== 401 &&
        $e(p.status === 409 ? "主题有更新，请刷新后重试。" : p.message),
        (p.status === 404 || p.status === 409) &&
          (await Ee({ silent: !0, afterWrite: !0 })));
    } finally {
      ((O = !1),
        c() &&
          s &&
          (nt(),
          Ne("[data-radar-focus]", m)
            .find((p) => p.dataset.radarFocus === "review:" + String(n.id))
            ?.focus({ preventScroll: !0 })),
        d.isConnected &&
          ((d.disabled = !1),
          u &&
            (u.textContent = s?.plan?.limits?.saved_brief_enabled
              ? "本轮已阅 · 保存简报"
              : "本轮已阅 · 更新水位")));
    }
  }
  function Jn() {
    if (fe?.isConnected) return fe;
    const n = e("dialog", "radar-delete-dialog");
    ((n.id = "radar-delete-dialog"),
      n.setAttribute("aria-labelledby", "radar-delete-title"));
    const d = e("div", "dialog-header"),
      u = e("h2", "", "删除这个雷达主题？");
    ((u.id = "radar-delete-title"),
      d.append(
        u,
        Jt("关闭删除确认", "close", () => {
          O || n.close();
        }),
      ));
    const p = e("div", "radar-delete-body"),
      b = e("p");
    ((b.id = "radar-delete-copy"),
      p.append(
        b,
        e(
          "p",
          "radar-form-hint",
          "只会删除该主题及其阅后基线；不会删除原始事件、收藏或阅读记录。",
        ),
      ));
    const v = Zt("");
    ((v.id = "radar-delete-error"), (v.hidden = !0), p.append(v));
    const x = e("div", "radar-dialog-actions");
    x.append(
      q("保留主题", "button secondary", null, () => {
        O || n.close();
      }),
    );
    const w = q("确认删除", "button danger");
    return (
      (w.id = "radar-delete-confirm"),
      (w.onclick = Da),
      x.append(w),
      p.append(x),
      n.append(d, p),
      document.body.append(n),
      n.addEventListener(
        "click",
        ($) => {
          O && $.target === n && $.stopImmediatePropagation();
        },
        { capture: !0 },
      ),
      ct(n, {
        onClose: () => {
          ((A = null), (_ = null));
        },
      }),
      n.addEventListener("cancel", ($) => {
        O && $.preventDefault();
      }),
      (fe = n),
      n
    );
  }
  function Ma(n) {
    if (O) return;
    const d = Jn();
    ((A = String(n.id)),
      (_ = n.version),
      (i("#radar-delete-copy", d).textContent =
        "将删除「" + oe(n.name, 100) + "」的雷达配置。此操作不可撤销。"));
    const u = i("#radar-delete-error", d);
    ((u.hidden = !0),
      (u.textContent = ""),
      ut(d),
      i("#radar-delete-confirm", d).focus());
  }
  async function Da() {
    if (O || A == null) return;
    const n = Jn(),
      d = A,
      u = i("#radar-delete-confirm", n);
    ((O = !0),
      (u.disabled = !0),
      (u.querySelector("span").textContent = "正在删除…"));
    try {
      (await t("/api/radar/topics/" + encodeURIComponent(d), {
        method: "DELETE",
        body: JSON.stringify({ version: _ }),
      }),
        n.close(),
        await Ee({ afterWrite: !0 }),
        $e("主题已删除，事件与阅读记录保留。"),
        i("#radar-new", m)?.focus({ preventScroll: !0 }));
    } catch (p) {
      if (p.status !== 401) {
        const b = i("#radar-delete-error", n);
        ((b.textContent =
          p.status === 409
            ? "主题状态已改变：" + p.message + "。请重新查看后操作。"
            : p.message),
          (b.hidden = !1));
      }
    } finally {
      ((O = !1),
        !n.open &&
          c() &&
          s &&
          (nt(), i("#radar-new", m)?.focus({ preventScroll: !0 })),
        u.isConnected &&
          ((u.disabled = !1),
          (u.querySelector("span").textContent = "确认删除")));
    }
  }
  return {
    load: le,
    refresh: Ee,
    reset: we,
    onEventClosed() {
      if (!c()) return;
      const n = !!h;
      (Ee({ silent: !0 }), n && ze());
    },
  };
}
const On = i("#app"),
  r = {
    session: !1,
    csrf: "",
    settings: { ...wt },
    settingsVersion: 1,
    section: "feed",
    view: "globe",
    items: [],
    total: 0,
    stats: {},
    facets: {},
    status: null,
    statusError: "",
    filters: {
      q: "",
      source: "",
      source_id: "",
      category: "",
      after: "",
      before: "",
      sort: "importance",
      read: "",
      scope: "active",
      window_days: "",
      min_importance: "",
      bookmarked: !1,
    },
    selected: new Set(),
    selectedEvent: null,
    loading: !1,
    requestId: 0,
    failCount: 0,
    fetchedAt: null,
    globe: null,
    globeLoading: !1,
    refreshTimer: null,
    pagination: !1,
    cutoff: null,
    replayTimer: null,
    pendingUpdate: null,
    newIds: new Set(),
    overrides: new Map(),
    busyReads: new Set(),
    busyBookmarks: new Set(),
    sourceName: "",
    cluster: null,
    policy: null,
    settingsFetchedAt: 0,
    settingsRequest: null,
    readBackoff: 0,
    writeBackoff: 0,
    refreshingWorkspace: !1,
  },
  qn = {
    feed: "资讯工作台",
    radar: "情报雷达",
    inbox: "原始收件箱",
    bookmarks: "收藏",
    archive: "归档",
    sources: "来源管理",
    settings: "阅读与显示设置",
  };
async function Qe(t, a = {}) {
  const o = (a.method || "GET").toUpperCase(),
    l = t === "/api/status" && o === "GET" ? xt : null,
    c = ["GET", "HEAD"].includes(o) ? "readBackoff" : "writeBackoff";
  if (!t.startsWith("/api/auth/") && r[c] > Date.now()) {
    const s = Math.ceil((r[c] - Date.now()) / 1e3),
      g = new Error(
        `请求较多，请在 ${s} 秒后重试。你的筛选、选择和输入仍保留。`,
      );
    throw ((g.status = 429), (g.retryAfter = s), g);
  }
  const f = new AbortController(),
    m = setTimeout(() => f.abort(), 22e3);
  try {
    const s = await fetch(t, {
        credentials: "same-origin",
        cache: "no-store",
        ...a,
        signal: f.signal,
        headers: {
          Accept: "application/json",
          ...(["GET", "HEAD"].includes(o) ? {} : { "X-CSRF-Token": r.csrf }),
          ...(a.body ? { "Content-Type": "application/json" } : {}),
          ...(a.headers || {}),
        },
      }),
      g = await s.json().catch(() => ({}));
    if (s.status === 401) {
      if (l === null || l === xt) {
        const k = r.session;
        ((r.session = !1),
          (r.csrf = ""),
          !t.endsWith("/auth/session") &&
            !i("#login-form") &&
            en(k ? "登录已过期，请重新输入访问码。" : ""));
      }
      const h = new Error("访问码无效或会话已过期。");
      throw ((h.status = 401), h);
    }
    if (!s.ok) {
      const h = new Error(
        typeof g.error == "string"
          ? g.error
          : g.error?.message ||
              g.message ||
              `请求未完成（${s.status}），请重试。`,
      );
      if (((h.status = s.status), (h.code = g.error?.code), s.status === 429)) {
        const k = s.headers.get("Retry-After"),
          Y = Number(k),
          G =
            k && Number.isFinite(Y)
              ? Y
              : k
                ? (Date.parse(k) - Date.now()) / 1e3
                : 5;
        ((h.retryAfter = Math.max(
          1,
          Math.min(3600, Number.isFinite(G) ? Math.ceil(G) : 5),
        )),
          (h.message = `请求较多，请在 ${h.retryAfter} 秒后重试。你的筛选、选择和输入仍保留。`),
          !t.startsWith("/api/auth/") &&
            (l === null || l === xt) &&
            (r[c] = Date.now() + h.retryAfter * 1e3));
      }
      throw h;
    }
    return g;
  } catch (s) {
    throw s.name === "AbortError"
      ? new Error("连接超时，请检查服务器连接后重试。")
      : s;
  } finally {
    clearTimeout(m);
  }
}
const wn = er({
    api: Qe,
    onSaved: (t) => {
      (In(t), (r.policy = null), Bt(), bt());
    },
    onLoaded: (t) => In(t),
    onArchive: () => st("archive"),
  }),
  ha = ar({
    api: Qe,
    onView: (t) => {
      ((r.filters.source_id = t.id),
        (r.filters.source = t.platform),
        (r.sourceName = t.name || t.locator),
        st("feed"));
    },
  }),
  $t = gr({
    api: Qe,
    getSettings: () => r.settings,
    onRead: $a,
    onBookmark: Sa,
    onLocate: Ar,
    onClosed: () => {
      (Rt.onEventClosed(),
        (r.selectedEvent = null),
        r.globe?.setSelected(null),
        Ne(".event-card.selected").forEach((a) =>
          a.classList.remove("selected"),
        ));
      const t = new URL(location.href);
      (t.searchParams.delete("event"),
        history.replaceState(null, "", t.pathname + t.search));
    },
  }),
  Pn = vr({
    api: Qe,
    getSettings: () => r.settings,
    beforeFetch: Ut,
    syncPolicy: ba,
    onEvent: (t) => _n(t),
    onReadingChanged: () => {
      r.pagination = !1;
    },
  }),
  Rt = $r({
    api: Qe,
    onOpenEvent: (t) => {
      ((r.selectedEvent = t), $t.open(t, null));
    },
    onOpenWorkspace: Cr,
    onOpenInbox: () => st("inbox"),
    isActive: () => r.section === "radar",
  });
function In(t) {
  if (
    !t?.settings ||
    !Number.isInteger(t.version) ||
    t.version < r.settingsVersion
  )
    return !1;
  const a =
      t.version !== r.settingsVersion ||
      Object.keys(wt).some((l) => t.settings[l] !== r.settings[l]),
    o = r.settings;
  return (
    (r.settings = { ...wt, ...t.settings }),
    (r.settingsVersion = t.version),
    (r.settingsFetchedAt = Date.now()),
    wn.observe(t),
    a
      ? ((document.documentElement.dataset.density = r.settings.density),
        (document.documentElement.dataset.settingsVersion = String(t.version)),
        r.globe?.setShowImages(r.settings.show_images),
        (r.pendingUpdate = null),
        i("#updates-button") && (i("#updates-button").hidden = !0),
        [
          "hide_read",
          "retention_days",
          "retention_basis",
          "retain_bookmarks",
        ].some((l) => o[l] !== r.settings[l]) && (r.pagination = !1),
        i("#event-list") && (Bt(), lt(), gt()),
        o.show_images !== r.settings.show_images &&
          ($t.rerender(), Pn.settingsChanged()),
        !0)
      : !1
  );
}
async function Ut({ force: t = !1 } = {}) {
  return r.session
    ? r.settingsRequest
      ? r.settingsRequest
      : !t && Date.now() - r.settingsFetchedAt < 5e3
        ? !1
        : ((r.settingsRequest = Qe("/api/settings")
            .then((a) => (r.session ? In(a) : !1))
            .finally(() => {
              r.settingsRequest = null;
            })),
          r.settingsRequest)
    : !1;
}
async function ba(t) {
  return Number.isInteger(t?.settings_version)
    ? (t.settings_version > r.settingsVersion && (await Ut({ force: !0 })),
      t.settings_version > r.settingsVersion && (await Ut({ force: !0 })),
      t.settings_version < r.settingsVersion)
    : !1;
}
async function Un() {
  if (!(
    !r.session ||
    document.hidden ||
    !navigator.onLine ||
    r.refreshingWorkspace ||
    r.readBackoff > Date.now()
  )) {
    r.refreshingWorkspace = !0;
    try {
      const t = await Ut({ force: !0 });
      (["feed", "archive", "bookmarks"].includes(r.section)
        ? await bt({ silent: !t })
        : r.section === "inbox"
          ? await Pn.refresh()
          : r.section === "sources"
            ? await ha.refresh()
            : r.section === "radar" && (await Rt.refresh({ silent: !0 })),
        await dn());
    } catch (t) {
      t.status !== 401 && St(t.message);
    } finally {
      r.refreshingWorkspace = !1;
    }
  }
}
function en(t = "") {
  (xt++,
    Rt.reset(),
    clearInterval(r.refreshTimer),
    vt(),
    r.globe?.destroy(),
    (r.globe = null),
    (r.globeLoading = !1),
    (r.items = []),
    (r.session = !1),
    r.selected.clear(),
    r.overrides.clear(),
    (r.pendingUpdate = null),
    (r.policy = null),
    (r.settingsFetchedAt = 0),
    (r.status = null),
    (r.statusError = ""),
    Ne("dialog").forEach((a) => a.remove()),
    (On.innerHTML = `<main class="login-shell"><a class="login-brand" href="/">${te("globe")}<span>FRONTIER<small>全球前沿讯息站</small></span></a><section class="login-card" aria-labelledby="login-title"><div class="login-symbol">${te("lock")}</div><h1 id="login-title">连接你的资讯工作台</h1><p class="login-intro">持续汇集 Telegram、X 和 YouTube 资讯，按地理位置、事件时间与重要度阅读。</p><form id="login-form"><label for="access-code">访问码</label><input id="access-code" type="password" name="token" autocomplete="current-password" required maxlength="512" placeholder="输入访问码"/><p id="login-error" class="form-error" role="alert"></p><button id="login-submit" class="button primary" type="submit">进入工作台 ${te("arrow")}</button></form><p class="login-help">Mac App 支持自动登录，也可在 App 的连接面板复制访问码。</p></section><footer class="login-footer"><span>私人资讯工作区</span><span>Telegram · X · YouTube</span></footer></main>`),
    ue("#login-error", t),
    (i("#login-form").onsubmit = async (a) => {
      a.preventDefault();
      const o = i("#login-submit"),
        l = i("#access-code");
      ((o.disabled = !0), ue("#login-error", ""));
      try {
        const c = await Qe("/api/auth/session", {
          method: "POST",
          body: JSON.stringify({ token: l.value.trim() }),
        });
        ((l.value = ""),
          (r.csrf = c.csrf_token || (await Qe("/api/auth/me")).csrf_token),
          (r.session = !0),
          await ga());
      } catch (c) {
        i("#login-error") &&
          (ue("#login-error", c.message), (o.disabled = !1), l.focus());
      }
    }));
}
async function ga() {
  try {
    const o = await Qe("/api/settings");
    ((r.settings = { ...wt, ...o.settings }),
      (r.settingsVersion = o.version),
      (r.settingsFetchedAt = Date.now()),
      wn.setCurrent(o));
  } catch (o) {
    if (o.status === 401) return;
    $e("未能读取阅读设置，暂用默认值；保存设置前请重试。");
  }
  const t = new URLSearchParams(location.search);
  ((r.view = pa[t.get("view")] ? t.get("view") : r.settings.default_view),
    (r.section = Ka(t.get("section"), r.settings.default_section, qn)),
    (r.filters.sort = ["importance", "event_time", "discovered"].includes(
      t.get("sort"),
    )
      ? t.get("sort")
      : r.settings.default_sort));
  for (const o of [
    "q",
    "source",
    "source_id",
    "category",
    "after",
    "before",
    "read",
    "min_importance",
  ])
    t.has(o) && (r.filters[o] = t.get(o).slice(0, 200));
  (r.filters.min_importance &&
    (!/^\d+$/.test(r.filters.min_importance) ||
      Number(r.filters.min_importance) > 100) &&
    (r.filters.min_importance = ""),
    (r.filters.bookmarked = r.section === "bookmarks"),
    (r.filters.scope =
      r.section === "archive"
        ? "archive"
        : t.get("scope") === "all" && r.section === "feed"
          ? "all"
          : "active"),
    (document.documentElement.dataset.density = r.settings.density),
    (document.documentElement.dataset.settingsVersion = String(
      r.settingsVersion,
    )),
    (On.innerHTML = `<div class="app-shell">
    <aside class="sidebar"><a class="brand" href="/" aria-label="FRONTIER 全球前沿讯息站">${te("globe")}<span>FRONTIER<small>全球前沿讯息站</small></span></a><div class="workspace-label">个人工作区</div>
      <nav class="side-nav" aria-label="工作区导航"><button id="nav-feed" data-section="feed">${te("globe")}<span>资讯工作台</span></button><button id="nav-radar" data-section="radar">${te("radar")}<span>情报雷达</span></button><button id="nav-inbox" data-section="inbox">${te("inbox")}<span>原始收件箱</span></button><button id="nav-bookmarks" data-section="bookmarks">${te("bookmark")}<span>收藏</span></button><button id="nav-archive" data-section="archive">${te("archive")}<span>归档</span></button><span class="nav-separator"></span><button id="nav-sources" data-section="sources">${te("sources")}<span>来源管理</span></button><button id="nav-settings" data-section="settings">${te("settings")}<span>设置</span></button></nav>
      <div class="sidebar-bottom"><button id="health-button" class="sidebar-status">${te("activity")}<span id="connection-label">正在连接</span><span id="connection-dot" class="status-dot checking"></span></button><div class="sidebar-platforms" id="sidebar-platforms"><span>Telegram</span><span>X</span><span>YouTube</span></div><button id="logout" class="sidebar-logout">${te("logout")}<span>退出工作区</span></button></div>
    </aside>
    <main class="main-shell"><header class="page-header"><div class="page-title-group"><span class="mobile-brand">FRONTIER</span><h1 id="page-title">资讯工作台</h1><span id="page-count" class="page-count"></span></div><div class="header-actions"><span id="sync-time" class="sync-time">正在同步</span><button id="refresh" class="icon-button" title="刷新数据" aria-label="刷新资讯">${te("refresh")}</button><button id="mobile-health" class="icon-button mobile-only" aria-label="查看运行状态">${te("activity")}</button><button id="mobile-logout" type="button" class="icon-button mobile-only" aria-label="退出工作区" title="退出工作区">${te("logout")}</button></div></header>
      <div id="connection-banner" class="connection-banner" role="status" hidden></div><div id="quota-banner" class="quota-banner" role="status" hidden></div>
      <section id="feed-workspace" class="feed-workspace">
        <div class="filter-bar"><label class="search-field">${te("search")}<input id="search" type="search" placeholder="搜索资讯、关键词或事件" aria-label="搜索资讯" maxlength="200"/><kbd>/</kbd></label><select id="source-filter" aria-label="来源平台"><option value="">全部平台</option><option value="telegram">Telegram</option><option value="x">X</option><option value="youtube">YouTube</option></select><select id="category-filter" aria-label="资讯领域"><option value="">全部领域</option></select><select id="read-filter" aria-label="阅读状态"><option value="">全部</option><option value="all">全部</option><option value="unread">未读</option><option value="read">已读</option></select><button id="date-toggle" class="button secondary" aria-expanded="false" aria-controls="date-panel">${te("filter")}<span>更多筛选</span><span id="filter-count" class="filter-count" hidden></span></button></div>
        <div id="date-panel" class="advanced-filters" hidden><div class="advanced-date"><strong>事件发生日期</strong><span class="field-help">北京时间。时间未确认的资讯不进入日期范围。</span><form id="date-form"><label for="date-after">开始<input id="date-after" type="date"/></label><label for="date-before">结束<input id="date-before" type="date"/></label><button class="button secondary small" type="submit">应用日期</button><button id="date-clear" type="button" class="text-button">不限日期</button></form><p id="date-error" class="form-error" role="alert" hidden></p></div><div class="advanced-window"><label for="window-filter"><strong>本次阅读窗口</strong></label><select id="window-filter"><option value="">使用已保存规则</option><option value="2">保留近 2 天</option><option value="7">保留近 7 天</option><option value="30">保留近 30 天</option><option value="0">全部时间</option></select><span class="field-help">按已保存的时间基准计算；长期规则可在设置修改。</span><label for="importance-filter"><strong>最低重要度</strong></label><input id="importance-filter" type="number" min="0" max="100" step="1" placeholder="不限（0–100）" aria-describedby="importance-note"/><span id="importance-note" class="field-help">只查看评分不低于该数值的资讯。</span><p id="importance-error" class="form-error" role="alert" hidden></p></div></div>
        <div class="context-bar"><div class="filter-chips" id="filter-chips"></div><button id="clear-filters" class="text-button" hidden>清除筛选</button><button id="retention-link" class="policy-link"></button></div>
        <div class="view-toolbar"><div class="view-tabs" role="group" aria-label="资讯显示视图"><button id="view-globe" data-view="globe">${te("globe")}<span>地理</span></button><button id="view-list" data-view="list">${te("list")}<span>列表</span></button><button id="view-cards" data-view="cards">${te("cards")}<span>卡片</span></button><button id="view-timeline" data-view="timeline">${te("timeline")}<span>时间线</span></button></div><div class="view-actions"><button id="updates-button" class="new-updates" hidden></button><select id="sort" aria-label="事件排序"><option value="importance">重要度优先</option><option value="event_time">事件发生时间</option><option value="discovered">最近收录</option></select><button id="export" class="icon-button" aria-label="导出当前筛选前 200 条资讯" title="导出当前筛选前 200 条资讯">${te("download")}</button></div></div>
        <div class="selection-bar"><label class="checkbox-label"><input id="select-visible" type="checkbox"/>选择已加载资讯</label><span id="selection-count" class="muted"></span><div id="selection-actions" class="selection-actions" hidden><button id="bulk-read" class="text-button">${te("checkall")}标为已读</button><button id="bulk-unread" class="text-button">${te("unread")}标为未读</button><button id="selection-clear" class="text-button">取消选择</button></div><button id="mark-visible-read" class="text-button">标记已加载为已读</button><span id="view-coverage" class="view-coverage"></span></div>
        <div class="workspace-body"><div id="workspace-grid" class="workspace-grid">
          <section class="map-panel" aria-labelledby="globe-title"><div class="map-header"><div><h2 id="globe-title">全球事件分布</h2><span id="map-count">正在载入位置</span></div><button id="map-info" class="icon-button" aria-label="地图数据说明">${te("info")}</button></div><div id="globe-stage" class="globe-stage" role="region" aria-label="3D 地球，可拖动旋转与滚轮缩放，或使用下方控制。新闻点位也可通过键盘访问。"><div id="globe-loading" class="globe-loading">${te("globe")}<span>正在载入地球</span></div></div><div id="map-empty" class="map-empty" hidden></div><div class="map-legend"><span><i class="legend-dot high"></i>重要度 ≥ 80</span><span><i class="legend-dot"></i>已定位事件</span></div><div class="map-controls"><button id="zoom-in" class="icon-button zoom-symbol" aria-label="放大地球">+</button><button id="zoom-out" class="icon-button zoom-symbol" aria-label="缩小地球">−</button><button id="reset-globe" class="icon-button" aria-label="重置地球视角">${te("globe")}</button><button id="rotate" class="icon-button" aria-label="开启地球缓慢旋转" aria-pressed="false">${te("play")}</button></div><div class="map-attribution">Natural Earth · 点位基于原文证据</div></section>
          <section class="feed-panel"><div class="feed-panel-heading"><h2 id="feed-heading">当前资讯</h2><span id="feed-description"></span></div><div id="event-list" class="event-list" tabindex="-1" aria-label="资讯列表" aria-busy="true"></div><div class="feed-footer"><span id="feed-loaded"></span><button id="load-more" class="text-button" hidden>加载更多 ${te("arrow")}</button></div></section>
        </div><section id="timeline-view" class="timeline-view" aria-label="事件发生时间线" hidden><div class="timeline-info"><div><h2>按事件发生时间回看</h2><p id="timeline-coverage"></p></div><button id="timeline-return-all" class="text-button" hidden>退出回放</button></div><div class="replay-controls"><button id="replay" class="button secondary small" aria-label="播放事件时间回放">${te("play")}播放</button><div class="replay-track"><div id="timeline-bars" class="timeline-bars" aria-hidden="true"></div><input id="timeline-slider" type="range" min="0" max="1000" value="1000" step="1" aria-label="事件时间回放进度"/><div class="timeline-labels"><span id="timeline-start"></span><strong id="timeline-current"></strong><span id="timeline-end"></span></div></div></div><div id="timeline-list" class="timeline-list"></div><div class="timeline-more"><button id="timeline-load-more" class="button secondary" hidden>加载更多事件</button></div></section></div>
      </section>
      <section id="radar-pane" class="aux-pane radar-pane" hidden></section><section id="sources-pane" class="aux-pane" hidden></section><section id="settings-pane" class="aux-pane" hidden></section><section id="inbox-pane" class="aux-pane inbox-pane" hidden></section>
    </main></div>
    <dialog id="health-dialog" class="health-dialog" aria-labelledby="health-title"><div class="dialog-header"><h2 id="health-title">采集与整理状态</h2><button class="icon-button" data-close aria-label="关闭运行状态">${te("close")}</button></div><div id="health-content" class="health-content"></div></dialog>
    <dialog id="cluster-dialog" class="cluster-dialog" aria-labelledby="cluster-title"><div class="dialog-header"><h2 id="cluster-title">此区域的资讯</h2><button class="icon-button" data-close aria-label="关闭区域资讯">${te("close")}</button></div><div id="cluster-content" class="cluster-content"></div></dialog>`),
    Sr(),
    Bt(),
    ya(),
    zn());
  const a = r.section;
  (a === "radar" && st(a, !1, !t.has("section")),
    await Promise.allSettled([a === "radar" ? Promise.resolve() : bt(), dn()]),
    a !== "radar" && st(a, !1, !t.has("section")),
    t.get("event") && _n(t.get("event")),
    (r.refreshTimer = setInterval(Un, 3e4)));
}
function Sr() {
  (Ne("[data-section]").forEach((a) => {
    a.onclick = () => st(a.dataset.section);
  }),
    Ne("[data-view]").forEach((a) => {
      a.onclick = () => Bn(a.dataset.view);
    }),
    (i("#refresh").onclick = yn),
    (i("#health-button").onclick = ca),
    (i("#mobile-health").onclick = ca),
    (i("#logout").onclick = async () => {
      xt++;
      try {
        (await Qe("/api/auth/logout", { method: "POST", body: "{}" }),
          en("你已退出工作区。"));
      } catch (a) {
        $e(a.message);
      }
    }));
  // Mobile bottom navigation hides the desktop sidebar logout button.
  // Expose the SAME explicit logout flow in the mobile header, never auto-logout.
  i("#mobile-logout").onclick = () => i("#logout").click();
  let t;
  ((i("#search").oninput = (a) => {
    (clearTimeout(t),
      (t = setTimeout(() => {
        ((r.filters.q = a.target.value.trim()), tt());
      }, 300)));
  }),
    (i("#source-filter").onchange = (a) => {
      ((r.filters.source = a.target.value),
        (r.filters.source_id = ""),
        (r.sourceName = ""),
        tt());
    }),
    (i("#category-filter").onchange = (a) => {
      ((r.filters.category = a.target.value), tt());
    }),
    (i("#read-filter").onchange = (a) => {
      ((r.filters.read = a.target.value), tt());
    }),
    (i("#sort").onchange = (a) => {
      ((r.filters.sort = a.target.value), tt());
    }),
    (i("#window-filter").onchange = (a) => {
      ((r.filters.window_days = a.target.value), tt());
    }),
    (i("#importance-filter").onchange = (a) => {
      const o = a.target.value.trim();
      if (o && (!/^\d+$/.test(o) || Number(o) > 100)) {
        (ue("#importance-error", "重要度应为 0–100 的整数。"),
          (i("#importance-error").hidden = !1),
          (a.target.value = r.filters.min_importance));
        return;
      }
      ((i("#importance-error").hidden = !0),
        (r.filters.min_importance =
          o === "" || Number(o) === 0 ? "" : String(Number(o))),
        tt());
    }),
    (i("#date-toggle").onclick = () => {
      const a = i("#date-panel").hidden;
      ((i("#date-panel").hidden = !a),
        i("#date-toggle").setAttribute("aria-expanded", String(a)));
    }),
    (i("#date-form").onsubmit = (a) => {
      a.preventDefault();
      const o = i("#date-after").value,
        l = i("#date-before").value;
      if (o && l && o > l) {
        (ue("#date-error", "开始日期应早于或等于结束日期。"),
          (i("#date-error").hidden = !1));
        return;
      }
      ((r.filters.after = o),
        (r.filters.before = l),
        (i("#date-error").hidden = !0),
        tt());
    }),
    (i("#date-clear").onclick = () => {
      ((r.filters.after = ""), (r.filters.before = ""), tt());
    }),
    (i("#clear-filters").onclick = () => {
      for (const a of [
        "q",
        "source",
        "source_id",
        "category",
        "after",
        "before",
        "read",
        "window_days",
        "min_importance",
      ])
        r.filters[a] = "";
      ((r.sourceName = ""), (r.filters.scope = "active"), tt());
    }),
    (i("#retention-link").onclick = () => st("settings")),
    (i("#load-more").onclick = () => bt({ append: !0 })),
    (i("#timeline-load-more").onclick = () => bt({ append: !0 })),
    (i("#export").onclick = Rr),
    (i("#select-visible").onchange = (a) => {
      ((r.selected = a.target.checked
        ? new Set(Vt().map((o) => o.id))
        : new Set()),
        lt(),
        gt());
    }),
    (i("#selection-clear").onclick = () => {
      (r.selected.clear(), lt(), gt());
    }),
    (i("#bulk-read").onclick = () => tn([...r.selected], !0)),
    (i("#bulk-unread").onclick = () => tn([...r.selected], !1)),
    (i("#mark-visible-read").onclick = () =>
      tn(
        Vt()
          .filter((a) => !Me(a))
          .map((a) => a.id),
        !0,
      )),
    (i("#updates-button").onclick = () => {
      r.pendingUpdate
        ? (_a(r.pendingUpdate, !1, !1),
          (r.pendingUpdate = null),
          (i("#updates-button").hidden = !0))
        : yn();
    }),
    (i("#zoom-in").onclick = () => r.globe?.zoom(1)),
    (i("#zoom-out").onclick = () => r.globe?.zoom(-1)),
    (i("#reset-globe").onclick = () => r.globe?.reset()),
    (i("#rotate").onclick = () =>
      r.globe?.setAutoRotate(!r.globe.controls.autoRotate, !0)),
    (i("#map-info").onclick = () =>
      $e(
        "地图使用 Natural Earth 数据。只有原文支持的位置会落点，国家或城市级点位不代表精确地址；未知地点仍可在列表阅读。",
      )),
    (i("#replay").onclick = Nr),
    (i("#timeline-slider").oninput = (a) => {
      (vt(), Mn(Number(a.target.value)));
    }),
    (i("#timeline-return-all").onclick = Lr),
    ct(i("#health-dialog")),
    ct(i("#cluster-dialog")));
}
function st(t, a = !0, o = !1) {
  if (!qn[t] || !i("#feed-workspace")) return;
  ((r.section = t),
    Ne("[data-section]").forEach((c) => {
      (c.classList.toggle("active", c.dataset.section === t),
        c.setAttribute(
          "aria-current",
          c.dataset.section === t ? "page" : "false",
        ));
    }),
    ue("#page-title", qn[t]));
  const l = ["feed", "bookmarks", "archive"].includes(t);
  ((i("#feed-workspace").hidden = !l),
    (i("#radar-pane").hidden = t !== "radar"),
    (i("#sources-pane").hidden = t !== "sources"),
    (i("#settings-pane").hidden = t !== "settings"),
    (i("#inbox-pane").hidden = t !== "inbox"),
    (i("#page-count").hidden = !l),
    (i("#refresh").hidden = !l && t !== "radar"),
    i("#refresh").setAttribute(
      "aria-label",
      t === "radar" ? "刷新雷达" : "刷新资讯",
    ),
    r.globe?.setActive(l && r.view === "globe"),
    l
      ? ((r.policy = null),
        (r.filters.bookmarked = t === "bookmarks"),
        (r.filters.scope =
          t === "archive"
            ? "archive"
            : t === "feed" && r.filters.scope === "all"
              ? "all"
              : "active"),
        t === "archive" && (r.filters.window_days = ""),
        Bt(),
        zn(),
        a && tt())
      : t === "radar"
        ? Rt.load(i("#radar-pane"))
        : t === "sources"
          ? ha.load(i("#sources-pane"))
          : t === "settings"
            ? wn.load(i("#settings-pane"))
            : t === "inbox" && Pn.load(i("#inbox-pane")),
    Vn(o));
}
async function Ar(t) {
  if (!t) return;
  const a = r.section === "radar";
  (a &&
    ((r.filters = {
      ...r.filters,
      q: String(t.title || "").slice(0, 200),
      source: "",
      source_id: "",
      category: "",
      after: "",
      before: "",
      read: "all",
      scope: "all",
      window_days: "0",
      min_importance: "",
      bookmarked: !1,
    }),
    (r.sourceName = "")),
    st("feed", !1),
    Bn("globe"),
    a && tt(),
    await va(),
    !(!r.session || r.section !== "feed" || r.view !== "globe") &&
      (r.globe?.focus(t)
        ? ((r.selectedEvent = t.id),
          a &&
            $e(
              "已从雷达切换到地理视图，并按事件标题筛选，定位该条事件；可清除筛选返回全部。",
            ),
          i("#globe-stage")?.scrollIntoView({ block: "nearest" }))
        : $e("地球视图暂不可用，可在资讯列表阅读该事件。")));
}
function Cr(t) {
  const { q: a, terms: o } = dr(t?.query),
    l = Array.isArray(t?.platforms)
      ? t.platforms.filter((m) => ["telegram", "x", "youtube"].includes(m))
      : [],
    c = Math.min(100, Math.max(0, Math.round(Number(t?.min_importance) || 0)));
  ((r.filters = {
    ...r.filters,
    q: a,
    source: l.length === 1 ? l[0] : "",
    source_id: "",
    category: "",
    after: "",
    before: "",
    read: "all",
    sort: "importance",
    scope: "all",
    min_importance: c ? String(c) : "",
    window_days: "0",
    bookmarked: !1,
  }),
    (r.sourceName = ""),
    (r.view = "list"),
    st("feed", !1),
    c &&
      ((i("#date-panel").hidden = !1),
      i("#date-toggle").setAttribute("aria-expanded", "true")),
    tt());
  let f = "已带入关键词、最低重要度和全部历史；事件已读状态不受影响。";
  (l.length === 2 && (f += " 工作台暂无双平台联合筛选，请用平台选单分别核对。"),
    o.length > 1 &&
      (f +=
        " 雷达的 " +
        o.length +
        " 个关键词按 AND 同时匹配；工作台暂不支持完全复现，已使用首词「" +
        a +
        "」进行宽检索，请再核对其他关键词。"),
    $e(f),
    i("#search")?.focus({ preventScroll: !0 }));
}
function Vn(t = !1) {
  const a = new URL(location.href);
  for (const o of [
    "q",
    "source",
    "source_id",
    "category",
    "after",
    "before",
    "read",
    "sort",
    "min_importance",
  ])
    r.filters[o]
      ? a.searchParams.set(o, r.filters[o])
      : a.searchParams.delete(o);
  (r.filters.scope === "all" && r.section === "feed"
    ? a.searchParams.set("scope", "all")
    : a.searchParams.delete("scope"),
    a.searchParams.set("view", r.view),
    t ||
    (r.section === "feed" &&
      r.settings.default_section !== "radar" &&
      !a.searchParams.has("section"))
      ? a.searchParams.delete("section")
      : a.searchParams.set("section", r.section),
    history.replaceState(null, "", `${a.pathname}${a.search}`));
}
function Bt() {
  if (!i("#search")) return;
  document.activeElement !== i("#search") && (i("#search").value = r.filters.q);
  for (const [s, g] of [
    ["#source-filter", "source"],
    ["#category-filter", "category"],
    ["#read-filter", "read"],
    ["#sort", "sort"],
    ["#window-filter", "window_days"],
    ["#date-after", "after"],
    ["#date-before", "before"],
    ["#importance-filter", "min_importance"],
  ])
    i(s).value = r.filters[g];
  const t = r.policy
      ? { ...r.settings, hide_read: r.policy.hide_read }
      : r.settings,
    a = r.policy?.effective_read || gn(r.filters, t);
  ((i("#read-filter").options[0].text =
    gn({ ...r.filters, read: "" }, t) === "unread" ? "未读" : "全部"),
    (i("#read-filter").title =
      `阅读状态：${{ all: "全部", unread: "未读", read: "已读" }[a]}${r.filters.read ? "，本次筛选覆盖阅读设置" : "，按已保存的阅读设置"}`),
    (i("#window-filter").disabled = r.section === "archive"),
    (i("#window-filter").options[0].text = bn(
      r.settings.retention_days,
      r.settings.retention_basis,
    )));
  const o = i("#filter-chips");
  o.replaceChildren();
  const l = (s, g) => {
    const h = q(s, "filter-chip", "close", () => {
      ((r.filters[g] = ""), g === "source_id" && (r.sourceName = ""), tt());
    });
    (h.setAttribute("aria-label", `移除筛选：${s}`), o.append(h));
  };
  if (
    (r.filters.source_id && l(r.sourceName || "指定订阅来源", "source_id"),
    r.filters.after || r.filters.before)
  ) {
    const s = q(
      `${r.filters.after || "最早"} 至 ${r.filters.before || "至今"} · 事件发生`,
      "filter-chip",
      "close",
      () => {
        ((r.filters.after = ""), (r.filters.before = ""), tt());
      },
    );
    o.append(s);
  }
  if (
    (r.filters.min_importance !== "" &&
      l("重要度 ≥ " + r.filters.min_importance, "min_importance"),
    r.filters.scope === "all" && r.section === "feed")
  ) {
    const s = q("包含归档 · 全部历史", "filter-chip", "close", () => {
      ((r.filters.scope = "active"), tt());
    });
    (s.setAttribute("aria-label", "移除全部历史筛选"), o.append(s));
  }
  r.filters.window_days !== "" &&
    l(
      r.filters.window_days === "0"
        ? "全部时间"
        : `本次保留 ${r.filters.window_days} 天`,
      "window_days",
    );
  const c =
    +!!(r.filters.after || r.filters.before) +
    +(r.filters.window_days !== "") +
    +(r.filters.min_importance !== "");
  (ue("#filter-count", c),
    (i("#filter-count").hidden = c === 0),
    (i("#clear-filters").hidden = !(
      [
        "q",
        "source",
        "source_id",
        "category",
        "after",
        "before",
        "read",
        "window_days",
        "min_importance",
      ].some((s) => r.filters[s] !== "") || r.filters.scope === "all"
    )));
  const f =
      r.policy?.retention_days ??
      (r.filters.window_days === ""
        ? r.settings.retention_days
        : Number(r.filters.window_days)),
    m = r.policy?.retention_basis || r.settings.retention_basis;
  ue(
    "#retention-link",
    r.filters.scope === "all"
      ? "全部历史 · 包含归档"
      : r.section === "archive"
        ? `已归档 · 超出 ${f} 天窗口`
        : `${bn(f, m)}${!r.filters.read && t.hide_read && !r.filters.bookmarked ? " · 自动隐藏已读" : a === "read" ? " · 仅已读" : a === "unread" ? " · 仅未读" : " · 显示已读"}`,
  );
}
function tt() {
  (vt(),
    (r.cutoff = null),
    r.selected.clear(),
    (r.items = []),
    (r.policy = null),
    (r.pagination = !1),
    (r.pendingUpdate = null),
    Bt(),
    Vn(),
    bt());
}
function Bn(t) {
  pa[t] && ((r.view = t), zn(), Vn());
}
function zn() {
  i("#workspace-grid") &&
    (Ne("[data-view]").forEach((t) => {
      const a = t.dataset.view === r.view;
      (t.classList.toggle("active", a),
        t.setAttribute("aria-pressed", String(a)));
    }),
    (i("#workspace-grid").className = `workspace-grid view-${r.view}`),
    (i("#workspace-grid").hidden = r.view === "timeline"),
    (i("#timeline-view").hidden = r.view !== "timeline"),
    r.globe?.setActive(
      r.view === "globe" &&
        ["feed", "archive", "bookmarks"].includes(r.section),
    ),
    r.view === "globe" &&
      ["feed", "archive", "bookmarks"].includes(r.section) &&
      (va(), requestAnimationFrame(() => r.globe?.resize())),
    lt(),
    gt());
}
async function va() {
  if (r.globe || !i("#globe-stage")) return;
  if (r.globeLoading) return r.globeLoading;
  const t = (async () => {
    try {
      const { FrontierGlobe: a } = await Ua(
        async () => {
          const { FrontierGlobe: o } = await import("./globe-b008dea4dfd5.js");
          return { FrontierGlobe: o };
        },
        __vite__mapDeps([0, 1]),
      );
      if (!r.session || !i("#globe-stage")) return;
      ((r.globe = new a(i("#globe-stage"), {
        onSelect: _n,
        onCluster: Er,
        onRotate: (o) => {
          const l = i("#rotate");
          l &&
            ((l.innerHTML = te(o ? "pause" : "play")),
            l.setAttribute("aria-pressed", String(o)),
            l.setAttribute(
              "aria-label",
              o ? "停止地球旋转" : "开启地球缓慢旋转",
            ));
        },
        onFallback: da,
      })),
        r.globe.setShowImages(r.settings.show_images),
        r.globe.setActive(
          r.view === "globe" &&
            ["feed", "archive", "bookmarks"].includes(r.section),
        ),
        i("#globe-loading")?.remove(),
        zt());
    } catch {
      da("当前设备未能启用 3D 渲染。资讯、图片和时间线仍可正常阅读。");
    }
  })();
  r.globeLoading = t;
  try {
    await t;
  } finally {
    r.globeLoading === t && (r.globeLoading = !1);
  }
}
function da(t) {
  (i("#globe-loading")?.remove(),
    i(".globe-fallback") ||
      i("#globe-stage")?.append(
        it(
          "地理视图暂不可用",
          t,
          { label: "切换列表", run: () => Bn("list") },
          "globe",
        ),
      ),
    i("#globe-stage")?.lastElementChild?.classList.add("globe-fallback"),
    (i(".map-controls").hidden = !0));
}
function ya() {
  const t = i("#event-list");
  if (t) {
    t.replaceChildren();
    for (let a = 0; a < 7; a++) {
      const o = e("div", "skeleton-row");
      (o.setAttribute("aria-hidden", "true"),
        (o.innerHTML = "<span></span><strong></strong><p></p>"),
        t.append(o));
    }
  }
}
function Vt() {
  const t = r.policy?.effective_read
    ? { ...r.filters, read: r.policy.effective_read }
    : r.filters;
  return Xa(
    r.items.filter((a) => Qa(a, t, r.settings)),
    r.cutoff,
  );
}
function wa(t) {
  for (const a of t) {
    const o = r.overrides.get(a.id);
    o &&
      (Date.now() > o.expires
        ? r.overrides.delete(a.id)
        : Object.assign(a, o.values));
  }
  return t;
}
async function bt({ append: t = !1, silent: a = !1 } = {}) {
  if (
    !r.session ||
    (a && (r.loading || r.pagination || r.cutoff != null || r.selected.size))
  )
    return;
  const o = ++r.requestId;
  ((r.loading = !0),
    i("#event-list")?.setAttribute("aria-busy", "true"),
    i("#refresh")?.classList.add("refreshing"),
    !a && !t && !r.items.length && ya(),
    i("#load-more") && (i("#load-more").disabled = !0));
  try {
    if ((await Ut(), o !== r.requestId || !r.session)) return;
    const l = `/api/events?${Nn(r.filters, t ? r.items.length : 0)}`;
    let c = await Qe(l);
    if (
      o !== r.requestId ||
      !r.session ||
      ((await ba(c.policy)) && (c = await Qe(l)),
      t &&
        r.policy &&
        c.policy &&
        [
          "retention_days",
          "retention_basis",
          "hide_read",
          "retain_bookmarks",
          "effective_read",
          "scope",
        ].some((h) => r.policy[h] !== c.policy[h]) &&
        ((t = !1), (c = await Qe(`/api/events?${Nn(r.filters)}`))),
      o !== r.requestId || !r.session)
    )
      return;
    const f = wa(Array.isArray(c.items) ? c.items : []);
    c.items = f;
    const m = a
        ? f.filter((h) => !r.items.some((k) => k.id === h.id)).length
        : 0,
      s =
        i("#event-list")?.scrollTop > 40 ||
        $t.current() ||
        i("#timeline-view")?.scrollTop > 40,
      g =
        r.policy &&
        c.policy &&
        [
          "settings_version",
          "retention_days",
          "retention_basis",
          "hide_read",
          "retain_bookmarks",
        ].some((h) => r.policy[h] !== c.policy[h]);
    if (a && s && m && !g) {
      r.pendingUpdate = c;
      const h = i("#updates-button");
      ((h.textContent = `${y(m)} 条新资讯`),
        (h.hidden = !1),
        (r.failCount = 0),
        St());
      return;
    }
    _a(c, t, a);
  } catch (l) {
    if (o !== r.requestId || l.status === 401) return;
    (r.failCount++,
      St(l.message),
      r.items.length
        ? a || $e(l.message)
        : (i("#event-list")?.replaceChildren(
            it(
              "暂时无法连接资讯服务",
              l.message,
              { label: "重新连接", run: yn },
              "activity",
            ),
          ),
          i("#timeline-list")?.replaceChildren(
            it(
              "时间线暂不可用",
              l.message,
              { label: "重试", run: yn },
              "timeline",
            ),
          )));
  } finally {
    o === r.requestId &&
      ((r.loading = !1),
      i("#event-list")?.setAttribute("aria-busy", "false"),
      i("#refresh")?.classList.remove("refreshing"),
      i("#load-more") && (i("#load-more").disabled = !1));
  }
}
function _a(t, a = !1, o = !1) {
  const l = wa(Array.isArray(t.items) ? t.items : []),
    c = new Set(r.items.map((f) => f.id));
  ((r.newIds = o
    ? new Set(l.filter((f) => !c.has(f.id)).map((f) => f.id))
    : new Set()),
    (r.items = a ? [...r.items, ...l.filter((f) => !c.has(f.id))] : l),
    (r.policy = t.policy || null),
    (r.pagination = a || r.items.length > 100),
    (r.total = Math.max(0, Number(t.total) || 0)),
    (r.stats = t.stats || {}),
    (r.facets = t.facets || {}),
    (r.selected = new Set(
      [...r.selected].filter((f) => r.items.some((m) => m.id === f)),
    )),
    (r.fetchedAt = new Date()),
    (r.failCount = 0),
    Tr(),
    lt(),
    gt(),
    zt(),
    St(),
    Bt(),
    o ||
      Va(`已加载 ${y(r.items.length)} 条资讯，共 ${y(r.total)} 个匹配结果。`));
}
function Tr() {
  const t = i("#category-filter");
  if (!t) return;
  const a = Za(r.facets.categories),
    o = [new Option("全部领域", "")];
  for (const l of a)
    o.push(
      new Option(
        `${nn(l.value)}${l.count != null ? ` (${y(l.count)})` : ""}`,
        l.value,
      ),
    );
  (r.filters.category &&
    !a.some((l) => l.value === r.filters.category) &&
    o.push(new Option(nn(r.filters.category), r.filters.category)),
    t.replaceChildren(...o),
    (t.value = r.filters.category));
}
function vn(t, a = "") {
  const o = e(
    "article",
    `event-card ${a}${Me(t) ? " is-read" : ""}${t.id === r.selectedEvent ? " selected" : ""}`,
  );
  if (((o.dataset.id = t.id), a !== "cluster-card")) {
    const _e = e("input", "event-checkbox");
    ((_e.type = "checkbox"),
      (_e.checked = r.selected.has(t.id)),
      _e.setAttribute("aria-label", `选择资讯：${t.title || "未命名资讯"}`),
      (_e.onchange = () => {
        (_e.checked ? r.selected.add(t.id) : r.selected.delete(t.id), xa());
      }),
      o.append(_e));
  }
  const l = e("div", "event-card-content"),
    c = e("button", "event-open");
  ((c.type = "button"),
    c.setAttribute("aria-label", `阅读资讯：${t.title || "未命名资讯"}`));
  const f = e("div", "event-copy"),
    m = e("div", "event-topline"),
    s = t.sources?.[0],
    g = e("span", Me(t) ? "read-indicator" : "unread-indicator");
  ((g.title = Me(t) ? "已读" : "未读"),
    g.setAttribute("aria-label", Me(t) ? "已读" : "未读"),
    m.append(
      g,
      e("span", "event-source", s?.name || Ke(s?.platform)),
      e("span", "source-platform", Ke(s?.platform)),
      e("span", "category-label", nn(t.category)),
    ));
  const h = e("span", `importance${Lt(t) >= 80 ? " high" : ""}`, String(Lt(t)));
  ((h.title = `重要度 ${Lt(t)} / 100`),
    h.setAttribute("aria-label", `重要度 ${Lt(t)}`),
    m.append(h),
    f.append(m, e("h3", "", t.title || "未命名资讯")),
    t.summary && f.append(e("p", "event-summary", t.summary)),
    c.append(f));
  const k = r.settings.show_images ? sn(t) : [];
  if (k.length) {
    const _e = Pt(k[0], "", "event-thumbnail");
    (k.length > 1
      ? _e.append(e("span", "media-count", `${k.length} 张`))
      : k[0].kind === "thumbnail" &&
        _e.append(e("span", "media-count", "视频")),
      c.append(_e),
      o.classList.add("has-media"));
  }
  ((c.onclick = () => _n(t.id)), l.append(c));
  const Y = e("div", "event-bottomline"),
    G = e("div", "event-meta"),
    pe = rn(t, !0),
    L = e("span", `event-time${Ft(t) ? "" : " uncertain"}`, pe);
  ((L.title = `事件发生时间：${rn(t)}`),
    pe.includes(" — ") && o.classList.add("has-time-range"));
  const B = e("span", "event-location", En(t));
  ((B.title = En(t)), G.append(L, B), Y.append(G));
  const O = e("div", "event-actions"),
    de = q("", "icon-button read-button", Me(t) ? "unread" : "check", () =>
      $a(t, !Me(t)),
    );
  (de.setAttribute("aria-label", Me(t) ? "标为未读" : "标为已读"),
    (de.title = Me(t) ? "标为未读" : "标为已读"),
    (de.disabled = r.busyReads.has(t.id)));
  const ce = q(
    "",
    `icon-button bookmark-button${t.bookmarked ? " saved" : ""}`,
    "bookmark",
    () => Sa(t),
  );
  return (
    ce.setAttribute("aria-label", t.bookmarked ? "取消收藏" : "收藏资讯"),
    ce.setAttribute("aria-pressed", String(!!t.bookmarked)),
    (ce.title = t.bookmarked ? "取消收藏" : "收藏"),
    (ce.disabled = r.busyBookmarks.has(t.id)),
    O.append(de, ce),
    Y.append(O),
    l.append(Y),
    o.append(l),
    o
  );
}
function lt() {
  const t = i("#event-list");
  if (!t) return;
  const a = document.activeElement,
    o = a?.closest(".event-card")?.dataset.id,
    l = a?.classList.contains("bookmark-button")
      ? ".bookmark-button"
      : a?.classList.contains("read-button")
        ? ".read-button"
        : a?.classList.contains("event-checkbox")
          ? ".event-checkbox"
          : ".event-open",
    c = t.contains(a),
    f = t.scrollTop,
    m = Vt();
  if ((t.replaceChildren(), !m.length && r.fetchedAt)) {
    const s = ["q", "source", "source_id", "category", "after", "before"].some(
        (k) => r.filters[k],
      ),
      g =
        r.cutoff != null
          ? "这个时刻没有匹配事件"
          : r.section === "bookmarks"
            ? "当前范围内没有收藏"
            : r.section === "archive"
              ? "当前没有归档资讯"
              : gn(r.filters, r.settings) === "unread"
                ? "当前范围已读完"
                : s
                  ? "没有匹配的资讯"
                  : "正在等待整理后的资讯",
      h =
        r.cutoff != null
          ? "拖动时间轴查看后续事件；未知事件时间不进入回放。"
          : r.section === "archive"
            ? "超过保留窗口的资讯会自动进入这里，原文和图片保留。"
            : r.section === "bookmarks"
              ? "在资讯或详情中点击收藏。也可以将阅读窗口切换为全部时间。"
              : "调整筛选或查看全部时间；新采集的原文可直接在原始收件箱阅读。";
    t.append(
      it(
        g,
        h,
        {
          label: r.section === "archive" ? "修改保留规则" : "打开原始收件箱",
          run: () => st(r.section === "archive" ? "settings" : "inbox"),
        },
        r.section === "bookmarks" ? "bookmark" : "inbox",
      ),
    );
  } else m.forEach((s) => t.append(vn(s)));
  ((t.scrollTop = f),
    o &&
      c &&
      (
        Ne(".event-card", t)
          .find((g) => g.dataset.id === o)
          ?.querySelector(l) || t
      ).focus({ preventScroll: !0 }),
    ue("#page-count", `${y(r.total)} 条`),
    ue(
      "#feed-heading",
      r.section === "bookmarks"
        ? "收藏资讯"
        : r.section === "archive"
          ? "已归档资讯"
          : "当前资讯",
    ),
    ue(
      "#feed-description",
      `${r.filters.sort === "event_time" ? "未知时间排在最后" : r.filters.sort === "discovered" ? "按首次收录顺序" : "重要度 / 100"}${r.view === "globe" ? " · 标题优先" : ""}`,
    ),
    ue("#feed-loaded", `已加载 ${y(r.items.length)} / ${y(r.total)}`),
    (i("#load-more").hidden = r.items.length >= r.total || r.cutoff != null),
    ue(
      "#view-coverage",
      r.cutoff != null
        ? `回放显示 ${y(m.length)} 条`
        : `${y(m.length)} 条已加载`,
    ),
    xa());
}
function xa() {
  const t = Vt(),
    a = i("#select-visible");
  a &&
    ((a.checked = t.length > 0 && t.every((o) => r.selected.has(o.id))),
    (a.indeterminate = r.selected.size > 0 && !a.checked),
    (a.disabled = !t.length),
    ue(
      "#selection-count",
      r.selected.size ? `已选 ${y(r.selected.size)} 条` : "",
    ),
    (i("#selection-actions").hidden = !r.selected.size),
    (i("#mark-visible-read").hidden = r.selected.size > 0),
    (i("#mark-visible-read").disabled = !t.some((o) => !Me(o))));
}
function zt() {
  const t = Vt(),
    a = t.filter((l) => Kt(l).length);
  (r.globe?.setEvents(t, r.newIds),
    ue(
      "#map-count",
      `${y(a.length)} 条已定位 · ${y(t.length - a.length)} 条全球性或地点待确认`,
    ));
  const o = i("#map-empty");
  o &&
    ((o.hidden = a.length > 0 || !r.fetchedAt || !!i(".globe-fallback")),
    o.hidden ||
      o.replaceChildren(
        e("strong", "", "此范围暂无可确认位置的资讯"),
        e("span", "", "未知地点的资讯仍可在旁边列表阅读。"),
      ));
}
function _n(t) {
  r.selectedEvent = t;
  const a =
    r.items.find((o) => o.id === t) || r.cluster?.find((o) => o.id === t);
  (r.globe?.setSelected(t),
    a && r.globe?.focus(a),
    Ne(".event-card").forEach((o) =>
      o.classList.toggle("selected", o.dataset.id === t),
    ),
    $t.open(t, a));
}
function Er(t, a) {
  ((r.cluster = t),
    ue("#cluster-title", `${a || "此区域"} · ${y(t.length)} 条资讯`),
    i("#cluster-content").replaceChildren(
      ...t.map((o) => vn(o, "cluster-card")),
    ),
    ut(i("#cluster-dialog")));
}
function ka(t, a) {
  r.overrides.set(t, {
    values: { ...(r.overrides.get(t)?.values || {}), ...a },
    expires: Date.now() + 3e4,
  });
  for (const l of [...r.items, ...(r.cluster || [])])
    l.id === t && Object.assign(l, a);
  $t.current()?.id === t && $t.update({ id: t, ...a });
}
async function $a(t, a, { automatic: o = !1 } = {}) {
  if (!(!t || r.busyReads.has(t.id)))
    return tn([t.id], a, { automatic: o, event: t });
}
async function tn(t, a, { automatic: o = !1, event: l } = {}) {
  if (((t = [...new Set(t)].filter((s) => !r.busyReads.has(s))), !t.length))
    return;
  const c = t.map((s) => ({
    id: s,
    read: Me(
      r.items.find((g) => g.id === s) ||
        (l?.id === s ? l : $t.current()?.id === s ? $t.current() : null),
    ),
  }));
  t.forEach((s) => r.busyReads.add(s));
  const f = [];
  let m = null;
  try {
    for (let g = 0; g < t.length; g += 200) {
      const h = t.slice(g, g + 200);
      try {
        await Qe(
          h.length === 1
            ? `/api/events/${encodeURIComponent(h[0])}/read`
            : "/api/events/read",
          {
            method: h.length === 1 ? "PUT" : "POST",
            body: JSON.stringify(
              h.length === 1 ? { read: a } : { ids: h, read: a },
            ),
          },
        );
      } catch (k) {
        m = k;
        break;
      }
      for (const k of h)
        (ka(k, { read: a, read_at: a ? new Date().toISOString() : null }),
          f.push(k),
          r.selected.delete(k));
    }
    if (m) for (const g of t.filter((h) => !f.includes(h))) r.selected.add(g);
    (lt(), gt(), zt());
    const s = async () => {
      for (const g of [!1, !0]) {
        const h = c
          .filter((k) => k.read === g && f.includes(k.id))
          .map((k) => k.id);
        h.length && (await tn(h, g, { automatic: !0 }));
      }
    };
    (m
      ? $e(
          `已处理 ${y(f.length)} / ${y(t.length)} 条，剩余 ${y(t.length - f.length)} 条保留选择，请重试。${m.message}`,
          f.length ? "撤销已完成部分" : void 0,
          f.length ? s : void 0,
        )
      : (!o || r.settings.hide_read) &&
        $e(
          a
            ? `${f.length === 1 ? "资讯" : `${y(f.length)} 条资讯`}已标为已读${r.settings.hide_read ? "，未读视图已更新" : ""}`
            : "已恢复为未读",
          "撤销",
          s,
        ),
      m ||
        ((r.pagination = !1),
        (r.pendingUpdate = null),
        r.section === "radar"
          ? await Rt.refresh({ silent: !0 })
          : await bt({ silent: !1 })));
  } finally {
    (t.forEach((s) => r.busyReads.delete(s)), lt());
  }
}
async function Sa(t) {
  if (!t || r.busyBookmarks.has(t.id)) return;
  r.busyBookmarks.add(t.id);
  const a = !t.bookmarked;
  try {
    (await Qe(`/api/events/${encodeURIComponent(t.id)}/bookmark`, {
      method: "PUT",
      body: JSON.stringify({ bookmarked: a }),
    }),
      ka(t.id, { bookmarked: a }),
      lt(),
      gt(),
      zt(),
      $e(a ? "已收藏，可在收藏工作区查看" : "已取消收藏"),
      r.section === "radar" && Rt.refresh({ silent: !0 }),
      (r.filters.bookmarked || t.archived) && ((r.pagination = !1), bt()));
  } catch (o) {
    o.status !== 401 && $e(o.message);
  } finally {
    (r.busyBookmarks.delete(t.id), lt());
  }
}
function Hn() {
  const t = r.items
    .map(Ft)
    .filter(Boolean)
    .map((a) => a.getTime());
  return t.length
    ? { min: Math.min(...t), max: Math.max(...t), times: t }
    : null;
}
function gt() {
  if (!i("#timeline-list")) return;
  const t = i("#timeline-list"),
    a = t.scrollTop,
    o = i(".timeline-unknown", t)?.open || !1,
    l = ta(Vt()),
    c = ta(r.items),
    f = c.known.reduce((s, g) => s + g.events.length, 0);
  (t.replaceChildren(),
    ue(
      "#timeline-coverage",
      `已加载 ${y(r.items.length)} / ${y(r.total)} 条资讯，其中 ${y(f)} 条有事件发生时间，${y(c.unknown.length)} 条时间待确认。`,
    ));
  for (const s of l.known) {
    const g = e("section", "timeline-group"),
      h = e("div", "timeline-date");
    h.append(
      e("strong", "", s.date),
      e("span", "", `${y(s.events.length)} 条`),
    );
    const k = e("div", "timeline-events");
    for (const Y of s.events) k.append(vn(Y, "timeline-card"));
    (g.append(h, k), t.append(g));
  }
  if (l.unknown.length && r.cutoff == null) {
    const s = e("details", "timeline-unknown");
    ((s.open = o),
      s.append(
        e("summary", "", `时间待确认 · ${y(l.unknown.length)} 条`),
        e(
          "p",
          "muted",
          "以下资讯没有足够的事件发生时间依据，不使用原帖发布时间代替。",
        ),
      ));
    const g = e("div");
    for (const h of l.unknown) g.append(vn(h, "timeline-card"));
    (s.append(g), t.append(s));
  }
  (l.known.length ||
    t.prepend(
      it(
        r.cutoff != null ? "该回放时刻暂无事件" : "当前没有明确事件时间",
        "原文未说明发生日期的内容保留在时间待确认分组，也可用列表按最近收录阅读。",
        null,
        "timeline",
      ),
    ),
    (t.scrollTop = a));
  const m = Hn();
  if (
    ((i("#replay").disabled = !m),
    (i("#timeline-slider").disabled = !m),
    i("#timeline-bars").replaceChildren(),
    m)
  ) {
    const s = Array(48).fill(0),
      g = Math.max(1, m.max - m.min);
    m.times.forEach(
      (k) => s[Math.min(47, Math.floor(((k - m.min) / g) * 47))]++,
    );
    const h = Math.max(1, ...s);
    (s.forEach((k, Y) => {
      const G = e(
        "span",
        r.cutoff != null && m.min + (Y / 47) * g > r.cutoff ? "beyond" : "",
      );
      ((G.style.height = `${k ? 12 + (k / h) * 88 : 3}%`),
        i("#timeline-bars").append(G));
    }),
      ue("#timeline-start", Ve(m.min)),
      ue("#timeline-end", Ve(m.max)),
      (i("#timeline-slider").value = String(
        r.cutoff == null ? 1e3 : an(((r.cutoff - m.min) / g) * 1e3, 0, 1e3),
      )));
  } else (ue("#timeline-start", "尚无确定时间"), ue("#timeline-end", ""));
  (ue(
    "#timeline-current",
    r.cutoff == null ? "全部已加载事件" : `回放至 ${Ve(r.cutoff, !0)}`,
  ),
    (i("#timeline-return-all").hidden = r.cutoff == null),
    i("#timeline-slider").setAttribute(
      "aria-valuetext",
      r.cutoff == null ? "全部已加载事件" : Ve(r.cutoff, !0),
    ),
    (i("#timeline-load-more").hidden =
      r.items.length >= r.total || r.cutoff != null));
}
function Mn(t) {
  const a = Hn();
  a &&
    ((r.cutoff = a.min + (t / 1e3) * (a.max - a.min)),
    r.globe?.setAutoRotate(!1),
    gt(),
    lt(),
    zt());
}
function vt() {
  (clearInterval(r.replayTimer), (r.replayTimer = null));
  const t = i("#replay");
  t &&
    ((t.innerHTML = `${te("play")}播放`),
    t.setAttribute("aria-label", "播放事件时间回放"));
}
function Nr() {
  if (r.replayTimer) {
    vt();
    return;
  }
  const t = Hn();
  if (!t) return;
  let a =
    r.cutoff == null || r.cutoff >= t.max
      ? 0
      : Number(i("#timeline-slider").value);
  (Mn(a),
    (i("#replay").innerHTML = `${te("pause")}暂停`),
    i("#replay").setAttribute("aria-label", "暂停时间回放"),
    (r.replayTimer = setInterval(() => {
      ((a = Math.min(1e3, a + 25)), Mn(a), a >= 1e3 && vt());
    }, 400)));
}
function Lr() {
  (vt(), (r.cutoff = null), gt(), lt(), zt());
}
let xt = 0;
async function dn() {
  const t = ++xt;
  try {
    const a = await Qe("/api/status");
    if (!r.session || t !== xt) return;
    ((r.status = a),
      (r.statusError = ""),
      St(),
      i("#health-dialog")?.open && Dn());
  } catch (a) {
    if (a.status === 401 || !r.session || t !== xt) return;
    ((r.statusError =
      "采集与整理状态暂不可用；已加载资讯仍可阅读，但上次额度暂不作为当前状态展示。请稍后重试。"),
      St(),
      i("#health-dialog")?.open && Dn());
  }
}
function Aa(t = {}) {
  const a = `${y(t.usage?.items)} / ${y(t.daily_limit)}`,
    o = t.paced_allowance == null ? "未上报" : y(t.paced_allowance);
  return t.state === "budget_pacing"
    ? {
        title: "事件整理按分时额度等待，并非今日额度用尽",
        detail: `今日已用 ${a}；当前分时软上限 ${o}。额度随 UTC 日内时间自动逐步释放，之后会继续尝试整理，完成时间不确定。原文继续收录，可在收件箱阅读。`,
        health:
          "正在等待后续分时额度释放，不是每日硬额度用尽；释放后会继续尝试整理，但无法保证具体完成时间。原文持续收录，可在收件箱阅读。",
      }
    : t.state === "daily_limit"
      ? {
          title: "今日整理硬额度不足下一批",
          detail: `今日已用 ${a}；日额度于 UTC 00:00（北京时间 08:00）重置，重置不代表整理立即完成。原文继续收录，可在收件箱阅读。`,
          health:
            "今日剩余额度不足下一批整理。日额度每日 UTC 00:00（北京时间 08:00）重置，但这不是完成时间承诺。原文继续收录，可在收件箱阅读。",
        }
      : {
          health:
            "日额度每日 UTC 00:00（北京时间 08:00）重置；这只是额度重置，不代表整理在该时刻完成。原文持续收录，可在收件箱阅读。",
        };
}
function St(t = "") {
  if (!i("#connection-label")) return;
  const a =
      !r.statusError && Array.isArray(r.status?.sources)
        ? r.status.sources
        : [],
    o = r.status?.enrichment || {};
  let l = r.fetchedAt ? "healthy" : "checking",
    c = r.fetchedAt ? "服务已连接" : "正在连接";
  (navigator.onLine
    ? r.failCount || t
      ? ((l = "error"), (c = "连接需重试"))
      : r.statusError
        ? ((l = "partial"), (c = "采集整理状态待确认"))
        : a.some((h) =>
            ["partial", "degraded", "error", "offline", "unavailable"].includes(
              h.state,
            ),
          ) && ((l = "partial"), (c = "部分来源需关注"))
    : ((l = "offline"), (c = "当前离线")),
    ue("#connection-label", c),
    (i("#connection-dot").className = `status-dot ${l}`));
  const f = i("#connection-banner");
  ((f.hidden = !(!navigator.onLine || r.failCount || t || r.statusError)),
    f.hidden ||
      (f.textContent = navigator.onLine
        ? r.failCount || t
          ? `${t || "服务器暂时无法连接。"}${r.fetchedAt ? ` 保留 ${hn(r.fetchedAt)}加载的数据。` : ""}`
          : r.statusError
        : "当前离线，保留最近成功加载的数据。恢复连接后继续同步。"));
  const m = i("#quota-banner"),
    s = ["budget_pacing", "daily_limit"].includes(o.state);
  if (
    ((m.hidden = !s || !!r.statusError),
    (m.dataset.state = m.hidden ? "" : o.state),
    s)
  ) {
    const h = Aa(o),
      k = e("div");
    (k.append(e("strong", "", h.title), e("span", "", h.detail)),
      m.replaceChildren(
        k,
        q("阅读原始收件箱", "text-button", "arrow", () => st("inbox")),
      ));
  }
  const g = i("#sidebar-platforms");
  g.replaceChildren();
  for (const h of ["telegram", "x", "youtube"]) {
    const k = a.find((G) => G.platform === h),
      Y = e("span", `sidebar-platform ${k?.state || "checking"}`, Ke(h));
    (k &&
      (Y.title = `${Ke(h)}：${Qt(k.state)}，最近成功 ${hn(k.last_success_at)}`),
      g.append(Y));
  }
  ue(
    "#sync-time",
    r.fetchedAt ? `${Ve(r.fetchedAt, !0).split(" ").pop()} 更新` : "正在同步",
  );
}
function ca() {
  (Dn(), ut(i("#health-dialog")), dn());
}
function Dn() {
  const t = i("#health-content");
  if (!t) return;
  t.replaceChildren();
  const a = r.status;
  if (r.statusError) {
    t.append(it("采集与整理状态暂不可用", r.statusError));
    return;
  }
  if (!a) {
    t.append(it("正在读取服务器状态", "状态来自真实采集结果。"));
    return;
  }
  const o = e("div", "health-platform-grid");
  for (const g of a.sources || []) {
    const h = e("section", "health-platform"),
      k = e("div", "health-platform-title");
    (k.append(
      e("h3", "", Ke(g.platform)),
      e("span", `state-badge ${g.state}`, Qt(g.state)),
    ),
      h.append(
        k,
        e("p", "", `最近成功 ${hn(g.last_success_at)}`),
        e("small", "muted", `${y(g.records)} 条历史记录`),
      ),
      g.error && h.append(e("p", "health-error", g.error)),
      o.append(h));
  }
  t.append(o);
  const l = e("section", "health-processing"),
    c = a.enrichment || {},
    f = c.usage || {};
  l.append(
    e("h3", "", "事件整理"),
    e(
      "span",
      `state-badge ${c.state || "checking"}`,
      c.state === "daily_limit" ? "今日硬额度不足下一批" : Qt(c.state),
    ),
  );
  const m = e("div", "health-stats");
  for (const [g, h] of [
    ["completed", "已整理"],
    ["pending", "待整理"],
    ["failed", "需重试"],
  ]) {
    const k = e("div");
    (k.append(e("strong", "", y(c[g])), e("span", "", h)), m.append(k));
  }
  if (
    (l.append(m),
    c.daily_limit != null || ["budget_pacing", "daily_limit"].includes(c.state))
  ) {
    const g = c.state === "budget_pacing",
      h = e("div", `health-quota${g ? " is-pacing" : ""}`);
    h.append(
      e(
        "strong",
        "",
        `今日整理用量 ${y(f.items)} / ${y(c.daily_limit)}（每日硬额度）`,
      ),
    );
    const k = Number(c.daily_limit),
      Y = c.daily_limit != null && Number.isFinite(k) && k > 0,
      G = Number(f.items);
    if (Y && f.items != null && f.items !== "" && Number.isFinite(G)) {
      const pe = e("progress");
      ((pe.max = k),
        (pe.value = an(G, 0, k)),
        pe.setAttribute("aria-label", "今日已用整理额度（每日硬额度）"),
        h.append(pe));
    }
    if (g || c.paced_allowance != null) {
      const pe = e("div", "health-soft-cap");
      pe.append(
        e(
          "strong",
          "",
          `UTC 日内分时软上限 ${c.paced_allowance == null ? "未上报" : y(c.paced_allowance)} / ${y(c.daily_limit)}`,
        ),
      );
      const L = Number(c.paced_allowance);
      if (Y && c.paced_allowance != null && Number.isFinite(L)) {
        const B = e("progress");
        ((B.max = k),
          (B.value = an(L, 0, k)),
          B.setAttribute("aria-label", "UTC 日内已经释放的分时软上限"),
          pe.append(B));
      }
      (pe.append(
        e(
          "small",
          "",
          "软上限随 UTC 日内时间自动逐步释放，不等于日额度用尽，也不代表整理完成时间。",
        ),
      ),
        h.append(pe));
    }
    (h.append(e("p", "muted", Aa(c).health)), l.append(h));
  }
  (c.error && l.append(e("p", "health-error", c.error)),
    l.append(
      q("阅读未整理的原文", "button secondary", "inbox", () => {
        (i("#health-dialog").close(), st("inbox"));
      }),
    ),
    t.append(l));
  const s = e("div", "health-bottom");
  (s.append(
    e("span", "", `采集调度：${Qt(a.collector?.state)}`),
    q("管理来源", "text-button", "sources", () => {
      (i("#health-dialog").close(), st("sources"));
    }),
  ),
    t.append(
      s,
      e(
        "p",
        "health-footnote",
        `界面版本 2.0 · 服务 ${a.version || "—"} · 北京时间`,
      ),
    ));
}
async function yn() {
  if (r.section === "radar") {
    await Promise.allSettled([Rt.refresh(), dn()]);
    return;
  }
  if (!r.loading) {
    (vt(),
      (r.cutoff = null),
      (r.pagination = !1),
      (r.pendingUpdate = null),
      i("#updates-button") && (i("#updates-button").hidden = !0));
    try {
      (await Ut({ force: !0 }), await Promise.allSettled([bt(), dn()]));
    } catch (t) {
      t.status !== 401 && $e(t.message);
    }
  }
}
async function Rr() {
  const t = i("#export");
  t.disabled = !0;
  try {
    const a = Nn(r.filters);
    (a.delete("offset"), a.set("limit", "200"));
    const o = await Qe(`/api/export?${a}`),
      l = URL.createObjectURL(
        new Blob([JSON.stringify(o, null, 2)], {
          type: "application/json;charset=utf-8",
        }),
      ),
      c = e("a");
    ((c.href = l),
      (c.download = `frontier-events-${on(new Date())}.json`),
      document.body.append(c),
      c.click(),
      c.remove(),
      setTimeout(() => URL.revokeObjectURL(l), 1e3),
      $e(
        `已导出 ${y(o.items?.length ?? o.events?.length ?? Math.min(r.total, 200))} 条资讯（当前筛选共 ${y(r.total)} 条，导出上限 200 条）`,
      ));
  } catch (a) {
    a.status !== 401 && $e(a.message);
  } finally {
    t.isConnected && (t.disabled = !1);
  }
}
document.addEventListener("keydown", (t) => {
  const a =
    ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName) ||
    document.activeElement?.isContentEditable;
  if (t.key === "/" && !a && !document.querySelector("dialog[open]")) {
    const o =
      r.section === "inbox"
        ? i("#inbox-search")
        : ["feed", "archive", "bookmarks"].includes(r.section)
          ? i("#search")
          : null;
    o && !o.closest("[hidden]") && (t.preventDefault(), o.focus());
  }
});
window.addEventListener("online", () => {
  r.session && (St(), Un());
});
window.addEventListener("offline", () => {
  r.session && (vt(), St());
});
document.addEventListener("visibilitychange", () => {
  document.hidden
    ? vt()
    : r.session && Date.now() - r.settingsFetchedAt > 5e3 && Un();
});
window.addEventListener("beforeunload", (t) => {
  wn.isDirty() && (t.preventDefault(), (t.returnValue = ""));
});
async function qr() {
  On.innerHTML =
    '<div class="app-loading"><strong>FRONTIER</strong><span>正在连接资讯工作台…</span></div>';
  try {
    const t = await Qe("/api/auth/me");
    if (!t.authenticated) {
      en();
      return;
    }
    ((r.csrf = t.csrf_token || ""), (r.session = !0), await ga());
  } catch (t) {
    t.status !== 401 ? en(t.message) : i("#login-form") || en();
  }
}
qr();
export { Kt as c, sn as e, Lt as i };

/* FRONTIER_ADDON_BEGIN:first-run */
;(() => {
"use strict";
// FRONTIER P0 scope contracts. Pure functions: NO network and NO derived "personal" claims.

const PLATFORMS = Object.freeze(['telegram', 'x', 'youtube']);

const DECISIONS = Object.freeze(['watch', 'research', 'dismiss']);

const MAX_GLOBAL = 5;

function assertOverview(data) {
  if (!data || !Array.isArray(data.topics) || !Array.isArray(data.global_signals)) {
    throw new TypeError('雷达响应缺少 topics 或 global_signals，无法确定主题匹配。');
  }
  return data;
}

function isFirstRun(data) {
  return assertOverview(data).topics.length === 0;
}

function integerCount(value) {
  return Number.isInteger(value) && value >= 0 ? value : 0;
}

function coverageSummary(data) {
  const overview = assertOverview(data);
  const c = overview.coverage_today;
  if (!c || typeof c !== 'object') {
    return '采集与处理覆盖暂不可核验；先进入雷达创建主题，不代表全站没有消息。';
  }
  const day = typeof c.utc_day === 'string' ? c.utc_day : '日期未知';
  const health = overview.source_target_coverage;
  const currentProcess = health?.success_observation_scope ===
    'current_collector_process_only_not_lifetime';
  const sourceScope = health?.status === 'observed_recent_heartbeat' ?
    `另据近期采集心跳：已配置 ${integerCount(health.configured)} 个目标，` +
    `${integerCount(health.ever_succeeded)} 个${currentProcess ? '本轮采集进程内有成功时间戳' : '在本次心跳有成功时间戳'}，` +
    `${integerCount(health.never_succeeded)} 个${currentProcess ? '本轮采集进程内暂无成功时间戳' : '在本次心跳无成功时间戳'}，` +
    `${integerCount(health.reported_errors)} 个保留最近一次错误状态（YouTube ` +
    `${integerCount(health.reported_errors_by_platform?.youtube)} 个）。` +
    '重启会重置采集进程内计数；无本轮成功时间戳不等于该来源从未成功，也不证明仍持续故障或全球覆盖完整。' :
    '采集目标本身的健康状态尚不可核验，不得推断全部订阅源正常。';
  return `UTC ${day} 全站新增原始记录 ${integerCount(c.raw_new)} 条；其中待处理 ${integerCount(c.pending)}、处理失败 ${integerCount(c.failed)}、视频尚未整理 ${integerCount(c.awaiting_video)}。只统计派生库记录状态；视频标记不等于当前可处理任务，亦不涵盖采集失败或全球全部资讯。` +
    sourceScope;
}

function classifyTopic(topic) {
  if (!topic || typeof topic !== 'object') return { kind: 'invalid', events: [], raw: [], explanation: '主题响应缺失；请刷新。' };
  if (topic.suspended) return { kind: 'suspended', events: [], raw: [], explanation: '主题已因当前档位暂停匹配；保留历史配置和已存判断。' };
  const events = Array.isArray(topic.highlights) ? topic.highlights : [];
  const raw = Array.isArray(topic.raw_leads?.items) ? topic.raw_leads.items : [];
  const total = integerCount(topic.metrics?.total);
  const today = integerCount(topic.metrics?.today_added);
  if (total) return {
    kind: 'matched', events, raw,
    explanation: `近 ${integerCount(topic.metrics?.history_days) || '当前'} 天窗口匹配 ${total} 个已整理事件，其中 UTC 今日首次收录 ${today} 个；推荐仅限此主题。存在事件发生时间未知或可用原文链接缺失时须逐条核验。`,
  };
  if (raw.length) return {
    kind: 'raw-only', events, raw,
    explanation: '已整理事件 0 条；近 48 小时的有限抽样中有未关联事件的原文线索。它们尚未成为已核验的事件，不能进行事件分诊。',
  };
  return {
    kind: 'no-match', events, raw,
    explanation: '该主题在当前计划的时间窗口、平台、重要度和原文 AND 关键词条件下没有匹配事件；近 48 小时有限待整理原文样本也无命中。可放宽关键词/重要度或检查来源处理状态；不代表全球没有事件。',
  };
}

// Only owner-saved topics are allowed to produce personal cards. Never use
// overview.global_signals as fallback; these are editorial high-importance cards.

function personalCards(data, topicId, limit = 3) {
  const overview = assertOverview(data);
  const topic = overview.topics.find(item => item.id === topicId && !item.suspended);
  if (!topic) return [];
  const size = Math.max(0, Math.min(8, Number.isInteger(limit) ? limit : 3));
  return (Array.isArray(topic.highlights) ? topic.highlights : []).slice(0, size)
    .map(card => ({
      ...card, scope: 'personal_topic_match', topic_id: topic.id,
      topic_name: topic.name, source_count: integerCount(card.source_count),
    }));
}

function globalCards(data) {
  const overview = assertOverview(data);
  return overview.global_signals.slice(0, MAX_GLOBAL).map(card => ({
    ...card, scope: 'global_editorial_candidate', personal_relevance: null,
  }));
}

function allowedDecision(card) {
  return card?.scope === 'personal_topic_match'
    && typeof card.topic_id === 'string'
    && typeof card.id === 'string'
    && card.id.length > 0;
}

function safeSourceURL(value) {
  if (typeof value !== 'string') return '';
  try {
    const url = new URL(value);
    if (!['https:', 'http:'].includes(url.protocol) || url.username || url.password) return '';
    return url.href;
  } catch { return ''; }
}

function evidenceStatus(card) {
  const sources = Array.isArray(card?.sources) ? card.sources : [];
  const linked = sources.filter(s => safeSourceURL(s?.url));
  return linked.length
    ? `${linked.length} 个可尝试打开的来源链接（未确认可达，且不代表独立证实）`
    : '没有可安全打开的匹配原文链接，不能以编辑摘要替代原文证据。';
}

/**
 * FRONTIER P0 entry-point patch for existing V110/V143 UI.
 * Does NOT replace its Radar, events, sources, inbox, map or decision logic.
 * A verified empty saved-topics response is the ONLY trigger for this CTA.
 * This file MUST be loaded in addition to (not instead of) historical assets.
 */

const CALLOUT_ID = 'frontier-p0-first-run';

function createFirstRunGuide({
  doc = globalThis.document,
  win = globalThis.window,
  request = globalThis.fetch?.bind(globalThis),
  clock = globalThis,
} = {}) {
  if (!doc || !win || !request) throw new Error('document / window / fetch are required');
  let generation = 0;
  let navNode = null;
  let cancelled = false;
  let dismissed = false;
  let lastRadarResponse = null;
  let refreshTimer;
  let interval;
  let requestController;

  const query = selector => doc.querySelector(selector);
  const remove = () => doc.getElementById(CALLOUT_ID)?.remove();

  function scheduleRefresh(ms = 180) {
    clock.clearTimeout(refreshTimer);
    if (!cancelled) refreshTimer = clock.setTimeout(refresh, ms);
  }

  // The underlying interface is compiled and asynchronous; wait for its
  // existing Radar creation button instead of duplicating topic POST logic.
  function waitForRadarCreate(timeout = 3500) {
    return new Promise(resolve => {
      const found = () => query('#radar-new:not([disabled])')
        || query('#radar-first-run .radar-first-cta:not([disabled])');
      const immediate = found();
      if (immediate) return resolve(immediate);
      let done = false;
      let observer;
      let timer;
      const complete = node => {
        if (done) return;
        done = true;
        observer?.disconnect();
        clock.clearTimeout(timer);
        resolve(node);
      };
      observer = new win.MutationObserver(() => {
        if (cancelled || !doc.getElementById('nav-radar')) return complete(null);
        const button = found();
        if (button) complete(button);
      });
      observer.observe(doc.getElementById('app') || doc.body, { childList: true, subtree: true });
      timer = clock.setTimeout(() => complete(found()), timeout);
    });
  }

  async function goToCreation(ownerQuery) {
    const nav = doc.getElementById('nav-radar');
    if (!nav || cancelled) return;
    dismissed = true;
    remove();
    nav.click(); // Navigate without creating a topic.
    const creation = await waitForRadarCreate();
    if (cancelled) return;
    if (creation) {
      creation.click(); // Existing native form, never a topic POST.
      const focus = query('#radar-topic-query') || query('#radar-topic-name');
      if (focus && ownerQuery) {
        focus.value = ownerQuery;
        focus.dispatchEvent(new win.Event('input', { bubbles: true }));
      }
      focus?.focus?.({ preventScroll: true });
      // One explicit owner action on the entry form is the preview action.
      // Never auto-save a topic or a decision; leave native verification intact.
      const preview = query('#radar-preview-trigger:not([disabled])');
      if (ownerQuery && preview) preview.click();
      else if (ownerQuery) {
        const notice = query('#radar-preview-status');
        if (notice) notice.textContent = '尚未试查；请亲自点击只读试查按钮。';
      }
    } else {
      nav.focus?.();
      // Navigation still succeeded; do not claim form opened without evidence.
    }
  }

  async function refreshDeliveryProof(proof, buildDay, builtProduct) {
    if (cancelled || !proof.isConnected) return;
    try {
      const response = await request('/api/release', {
        credentials:'same-origin', cache:'no-store',
        headers:{Accept:'application/json'},
      });
      if (!response.ok) throw new Error('no audited delivery');
      const data = await response.json();
      if (cancelled || !proof.isConnected) return;
      if (data?.schema !== 'frontier.owner.real-delivery-status.v1') {
        throw new Error('unexpected delivery receipt');
      }
      const last = data.last_independently_verified;
      if (data.today_status === 'VERIFIED_REAL_COMMITTED' &&
          last?.product_release === builtProduct) {
        proof.dataset.delivery = 'verified';
        proof.textContent = '✓ 本页面V145已经独立验收（'+buildDay+'，'+
          (last.backend || '?')+'源码 / '+(last.static || '?')+'前端）';
      } else if (data.today_status === 'COMMITTED_AWAITING_INDEPENDENT_AUDIT' &&
                 data.today_committed_release === builtProduct) {
        proof.dataset.delivery = 'pending';
        proof.textContent = '◌ 今日页面已发布，等待北京时间20:40独立验收。';
      } else if (last?.product_release === builtProduct &&
                 /^20\d{2}-\d{2}-\d{2}$/.test(last.beijing_date || '') &&
                 last.beijing_date < data.beijing_date) {
        const status = data.today_status === 'NOT_VERIFIED_OR_HELD'
          ? '今日发布未核验或已暂停'
          : data.today_status === 'COMMITTED_AWAITING_INDEPENDENT_AUDIT'
          ? '今天其他新版本提交后尚待审计'
          : '今天尚无新版本的独立验收';
        proof.dataset.delivery = 'verified-history';
        proof.textContent = '✓ 本页在 ' + last.beijing_date +
          ' 曾独立验收；' + status + '。历史验收不证明今天已更新。';
      } else {
        proof.dataset.delivery = 'unverified';
        proof.textContent = '本页面尚无正式验收证据；上次已验：'+
          (last?.beijing_date || '暂无')+'。构建包不等于线上已生效。';
      }
      // Notes come only from the independent audit for this EXACT page.
      // Never show a draft/staged candidate changelog as actual delivery.
      proof.parentNode?.querySelector('.frontier-p0-audited-updates')?.remove();
      if (last?.product_release === builtProduct &&
          last.update_source === 'independent_2040_audit_owner_delivery' &&
          Array.isArray(last.actual_updates)) {
        const changes = last.actual_updates
          .filter(value => typeof value === 'string' && value.trim() &&
            value.length <= 180).slice(0, 10);
        if (changes.length) {
          const details = doc.createElement('details');
          details.className = 'frontier-p0-audited-updates';
          details.dataset.auditedUpdates = 'true';
          const summary = doc.createElement('summary');
          summary.textContent = '查看此页面已验版本的 ' + changes.length + ' 项实际更新';
          details.append(summary);
          const list = doc.createElement('ol');
          for (const value of changes) {
            const li = doc.createElement('li');
            li.textContent = value;
            list.append(li);
          }
          details.append(list);
          proof.after(details);
        }
      }
      // 30s native radar sync means even a tab open overnight can notice
      // a truly VERIFIED newer frontend. Never reload during typing.
      proof.parentNode?.querySelector('.frontier-p0-newer-release')?.remove();
      if (data.today_status === 'VERIFIED_REAL_COMMITTED' &&
          /^Frontier-V[0-9]+-[A-Za-z0-9-]+$/.test(last?.product_release || '') &&
          last.beijing_date >= buildDay &&
          last.product_release !== builtProduct) {
        const button = doc.createElement('button');
        button.type = 'button';
        button.className = 'frontier-p0-newer-release';
        button.dataset.updateAvailable = 'true';
        button.textContent = '↻ ' + last.beijing_date +
          ' 的已验新版可用 · 请先保存未提交的内容，再点击加载';
        button.addEventListener('click', () => win.location.reload());
        proof.after(button);
      }
    } catch {
      if (cancelled || !proof.isConnected) return;
      proof.dataset.delivery = 'unverified';
      proof.textContent = '暂时无法核实云端正式版本；构建标签不是部署证明。';
    }
  }

  function beijingSourceClock(value) {
    // A source timestamp needs an explicit timezone; incomplete/naive dates
    // must not be silently interpreted as publication at the browser locale.
    if (typeof value !== 'string' ||
        !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(value)) {
      return null;
    }
    const instant = Date.parse(value);
    if (!Number.isFinite(instant)) return null;
    return {
      instant,
      beijing: new Intl.DateTimeFormat('zh-CN', {
        timeZone:'Asia/Shanghai', year:'numeric', month:'2-digit',
        day:'2-digit', hour:'2-digit', minute:'2-digit', hourCycle:'h23',
      }).format(new Date(instant)),
    };
  }

  function renderOrientationExamples(root, overview) {
    const samples = Array.isArray(overview.orientation_samples) ?
      overview.orientation_samples.slice(0, 3).filter(item =>
        item?.scope === 'global_onboarding_example_not_personal' &&
        typeof item.title === 'string' && item.title.trim() &&
        safeSourceURL(item.source_url)) : [];
    const id = samples.map(item => item.id).join('|');
    const old = root.querySelector('.frontier-p0-examples');
    if (old && old.dataset.sampleIds === id) return;
    old?.remove();
    if (!samples.length) return;
    const section = doc.createElement('details');
    section.className = 'frontier-p0-examples';
    section.dataset.sampleIds = id;
    const summary = doc.createElement('summary');
    summary.textContent = '先看看收录的 ' + samples.length + ' 条近期实例（非你的个人 Top 3）';
    section.append(summary);
    const note = doc.createElement('p');
    note.className = 'frontier-p0-examples-note';
    note.textContent = '仅限最近48小时入库且有对应外链的机器整理样本；近期入库不等于原文近期发表。标题、来源标注时间与链接未被独立核实；不是事实证明，也不代表你的个人兴趣。';
    section.append(note);
    const list = doc.createElement('ol');
    for (const sample of samples) {
      const li = doc.createElement('li');
      const title = doc.createElement('strong');
      title.textContent = sample.title.slice(0, 140);
      const detail = doc.createElement('small');
      detail.textContent = '已收录样本 · ' + String(sample.category || '未知类别').slice(0, 32) +
        ' · 来源标记 ' + String(sample.source_name || '关联外链').slice(0, 50);
      const clocks = doc.createElement('small');
      clocks.className = 'frontier-p0-example-clocks';
      const ingested = beijingSourceClock(sample.original_first_ingested_at);
      const published = sample.original_source_published_status ===
        'publisher_reported_unverified' ?
        beijingSourceClock(sample.original_source_published_at) : null;
      const ageMs = published ? Date.now() - published.instant : null;
      const freshness = published === null ? 'unknown' :
        ageMs < -5 * 60 * 1000 ? 'future' :
        ageMs > 48 * 3600 * 1000 ? 'older' : 'recent';
      clocks.dataset.publicationFreshness = freshness;
      clocks.textContent = '本平台首次入库（北京时间）：' +
        (ingested?.beijing || '未知') + '；' + (
          freshness === 'unknown' ? '来源标注发表时间：未知，不能推断发生时间。' :
          freshness === 'future' ? '来源标注发表时间异常（晚于当前时间），需要本人核查。' :
          '来源标注发表（未经独立核实，北京时间）：' + published.beijing +
          (freshness === 'older' ? '。⚠ 该原文标注发表于48小时前，最近入库不代表近期发表。' :
                                   '。来源标注在近48小时内，仍需本人核对。')
        );
      const link = doc.createElement('a');
      link.href = safeSourceURL(sample.source_url);
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.textContent = '本人选择打开关联来源 ↗';
      link.title = '将访问第三方网站；请自行核实出处，不自动记为已读或判断';
      li.append(title, detail, clocks, link);
      // Literal keyword extracted from the SAME linked completed original,
      // NOT a machine-translated editorial title. Choosing it only fills
      // the local field; preview remains a separate explicit owner click.
      const hint = sample.query_hint;
      if (sample.query_hint_basis ===
          'literal_substring_of_the_same_completed_original_not_personal' &&
          typeof hint === 'string' &&
          /^([一-龥]{3,8}|[A-Za-z][A-Za-z0-9-]{2,26})$/.test(hint)) {
        const tryWord = doc.createElement('button');
        tryWord.type = 'button';
        tryWord.className = 'frontier-p0-example-query';
        tryWord.textContent = '把原文词「' + hint + '」填入试查框';
        tryWord.title = '只填写本页输入框，不发送关键词，不创建个人主题，可自己改写';
        tryWord.addEventListener('click', () => {
          const field = root.querySelector('#frontier-p0-keyword');
          if (!field || !field.isConnected) return;
          if (field.value.trim() && field.value.trim() !== hint) {
            tryWord.textContent = '已保留你输入的关键词，请先清空输入框再选';
            field.focus?.({ preventScroll: true });
            return;
          }
          field.value = hint;
          field.dispatchEvent(new win.Event('input', { bubbles: true }));
          field.focus?.({ preventScroll: true });
          field.scrollIntoView?.({ block: 'nearest' });
          tryWord.textContent = '已填入「' + hint + '」，需要你自己点击只读试查';
        });
        li.append(tryWord);
      }
      list.append(li);
    }
    section.append(list);
    // Show proof of real data above the activation form, but collapsed by
    // default. No topic auto-created and no third-party URL auto-requested.
    // The single real owner action (enter/search) must remain ABOVE the optional
    // evidence examples, especially within a 320px mobile bottom sheet. An
    // expanded example must never bury the activation form under a scroll.
    root.querySelector('.frontier-p0-inline')?.after(section);
  }

  function show(overview) {
    if (dismissed || cancelled || !doc.getElementById('nav-radar')) return remove();
    let root = doc.getElementById(CALLOUT_ID);
    if (!root) {
      root = doc.createElement('section');
      root.id = CALLOUT_ID;
      root.className = 'frontier-p0-first-run';
      root.setAttribute('role', 'region');
      root.setAttribute('aria-labelledby', 'frontier-p0-first-run-title');
      root.innerHTML = `
        <div class="frontier-p0-kicker">YOUR QUESTION · 0 SAVED TOPICS</div>
        <button class="frontier-p0-close" type="button" aria-label="暂时收起首次使用提示">×</button>
        <h2 id="frontier-p0-first-run-title">先建一个你的追踪主题</h2>
        <ol class="frontier-p0-path" aria-label="由本人主动操作的激活路径">
          <li>填词</li><li>试查</li><li>原文</li><li>保存</li><li>判断</li>
        </ol>
        <p class="frontier-p0-lead">你来填真实关键词、主动试查；若有原始链接，先自行核对。只有已整理的主题匹配才能手动分诊；无命中不填假内容。</p>
        <form class="frontier-p0-inline" novalidate>
          <label for="frontier-p0-keyword">先写下一个你真正在意的关键词 / 短语</label>
          <input id="frontier-p0-keyword" name="keyword" maxlength="160" required autocomplete="off" placeholder="例如：Kimi（请换成你真正关心的原文词）" />
          <button type="submit" class="frontier-p0-create">按此关键词只读试查 →</button>
          <p class="frontier-p0-send-notice">只按已收录的同一条原文字面匹配（空格分词须同时命中，不自动翻译）；无命中不代表外界没有消息。只有点击试查才向当前私有云端发送关键词（可能留下请求日志），不创建主题、不自动判断。之后打开原文会访问第三方网站，不愿发送可关闭。</p>
          <p class="frontier-p0-input-error" role="alert" hidden></p>
        </form>
        <details class="frontier-p0-scope"><summary>查看本日收录覆盖与限制</summary><p class="frontier-p0-coverage" aria-live="polite"></p></details>
        <p class="frontier-p0-global-note">全站高分候选 ≠ 你的主题匹配；试查不会保存或自动判断。</p>`;
      root.querySelector('.frontier-p0-inline').addEventListener('submit', event => {
        event.preventDefault();
        const field = root.querySelector('#frontier-p0-keyword');
        const message = root.querySelector('.frontier-p0-input-error');
        const typed = field.value.trim();
        if (!typed || typed.length > 160) {
          message.textContent = '请先输入不超过160字的真实关注词；没有发送任何试查请求。';
          message.hidden = false;
          field.focus();
          return;
        }
        message.hidden = true;
        // The submit is the owner's affirmative read-only preview action.
        // Programmatic native click is a continuation of that ONE action.
        void goToCreation(typed);
      });
      root.querySelector('#frontier-p0-keyword').addEventListener('input', () => {
        root.querySelector('.frontier-p0-input-error').hidden = true;
      });
      root.querySelector('.frontier-p0-close').addEventListener('click', () => {
        dismissed = true;
        remove();
      });
      (doc.body || doc.documentElement).append(root);
      // The user's first real visit has ZERO topics, so this banner must
      // expose real delivery evidence too (the Daily Top 3 panel is hidden).
      const buildDay = doc.querySelector('meta[name="frontier-build-date"]')?.getAttribute('content') || '';
      const builtProduct = doc.querySelector('meta[name="frontier-product-release"]')?.getAttribute('content') || '';
      if (/^20\d{2}-\d{2}-\d{2}$/.test(buildDay) &&
          /^Frontier-V145-[A-Za-z0-9-]+$/.test(builtProduct)) {
        const proof = doc.createElement('p');
        proof.className = 'frontier-p0-delivery';
        proof.dataset.officialRelease = 'true';
        proof.textContent = '正在读取正式部署记录…';
        root.querySelector('.frontier-p0-lead').after(proof);
        root.dataset.deliveryProofAt = String(Date.now());
        void refreshDeliveryProof(proof, buildDay, builtProduct);
      }
    }
    const proof = root.querySelector('[data-official-release="true"]');
    if (proof && Date.now() - Number(root.dataset.deliveryProofAt || 0) >= 300000) {
      root.dataset.deliveryProofAt = String(Date.now());
      const builtDay = doc.querySelector('meta[name="frontier-build-date"]')?.getAttribute('content') || '';
      const builtProduct = doc.querySelector('meta[name="frontier-product-release"]')?.getAttribute('content') || '';
      if (builtDay && builtProduct) void refreshDeliveryProof(proof, builtDay, builtProduct);
    }
    root.querySelector('.frontier-p0-coverage').textContent = coverageSummary(overview);
    const targets = overview.source_target_coverage;
    const warnings = targets?.status === 'observed_recent_heartbeat' ?
      Number(targets.reported_errors) || 0 : 0;
    root.querySelector('.frontier-p0-scope > summary').textContent =
      '查看本日收录覆盖与限制' +
      (warnings > 0 ? '（' + warnings + ' 个采集目标有错误记录）' : '');
    renderOrientationExamples(root, overview);
  }

  async function refresh() {
    if (cancelled) return;
    const nav = doc.getElementById('nav-radar');
    if (!nav) {
      generation++;
      requestController?.abort();
      remove();
      lastRadarResponse = null;
      return;
    }
    const current = ++generation;
    requestController?.abort();
    const controller = new AbortController();
    requestController = controller;
    const timeout = clock.setTimeout(() => controller.abort(), 13000);
    try {
      const response = await request('/api/radar', {
        credentials: 'same-origin',
        cache: 'no-store',
        headers: { Accept: 'application/json' },
        signal: controller.signal,
      });
      if (cancelled || current !== generation) return;
      if (!response.ok) {
        // 401 / 403 / 500 cannot establish 0 topics, so never claim it.
        remove();
        return;
      }
      const json = assertOverview(await response.json());
      if (cancelled || current !== generation || !doc.getElementById('nav-radar')) return;
      lastRadarResponse = json;
      if (isFirstRun(json)) show(json);
      else remove(); // after server accepts a topic, native Radar owns the cards
    } catch {
      if (current === generation) remove(); // unknown, not zero
    } finally {
      clock.clearTimeout(timeout);
    }
  }

  function onMutation() {
    const current = doc.getElementById('nav-radar');
    if (current !== navNode) {
      navNode = current;
      dismissed = false; // new authenticated DOM / logout resets the local hint
      if (current) scheduleRefresh(50);
      else {
        generation++;
        requestController?.abort();
        remove();
      }
    }
  }

  function onNavigation(event) {
    const node = event.target?.closest?.('#nav-radar');
    if (node) {
      // The native Radar first-run UI owns its own prominent create control.
      dismissed = true;
      remove();
    }
    if (event.target?.closest?.('#radar-form-submit, #radar-topic-confirm')) {
      scheduleRefresh(1500); // refresh from server receipt, never guess success
    }
  }

  const observer = new win.MutationObserver(onMutation);
  observer.observe(doc.getElementById('app') || doc.body, { childList: true, subtree: true });
  doc.addEventListener('click', onNavigation, true);
  doc.addEventListener('visibilitychange', () => {
    if (!doc.hidden && doc.getElementById('nav-radar')) scheduleRefresh(200);
  });
  onMutation();
  interval = clock.setInterval(() => {
    if (doc.getElementById('nav-radar') && !dismissed) refresh();
  }, 30000);

  return {
    refresh,
    getLastOverview: () => lastRadarResponse,
    destroy() {
      cancelled = true;
      generation++;
      requestController?.abort();
      clock.clearTimeout(refreshTimer);
      clock.clearInterval(interval);
      observer.disconnect();
      doc.removeEventListener('click', onNavigation, true);
      remove();
    },
  };
}

if (typeof document !== 'undefined' && typeof window !== 'undefined') {
  createFirstRunGuide();
}

})();
/* FRONTIER_ADDON_END:first-run */

/* FRONTIER_ADDON_BEGIN:daily-top3 */
;(() => {
"use strict";
/**
 * FRONTIER P0 daily personal action feed: pure, fail-closed server-contract
 * interpretation. No global_signals, no client inference, no side effects.
 * The UI operates ONLY on /api/radar/daily after authentication.
 */

const DAILY_PANEL_ID = 'frontier-daily-panel';

const DAILY_ACTIONS = Object.freeze({
  watch: '持续关注',
  research: '深入研究',
  dismiss: '暂时忽略',
});

const DAILY_USEFULNESS = Object.freeze({
  useful: '值得看',
  noise: '没帮助',
});

const isDailyUsefulness = value =>
  value === null || Object.hasOwn(DAILY_USEFULNESS, value);

const DAILY_CHANGES = Object.freeze({
  initial_baseline: '首轮候选 · 历史基线',
  new_event: '上次复盘后首次入库',
  new_original_on_existing_event: '已有事件 · 新增匹配原文',
});

const DAILY_TOPIC_STATES = Object.freeze({
  ready: '有待人工判断的候选',
  suspended: '主题暂停',
  processing: '命中原文仍在处理',
  processing_failed: '匹配原文处理失败',
  not_linked_to_event: '原文尚未关联事件',
  no_raw_in_window: '窗口内未见新入库',
  no_keyword_match: '入库原文无关键词匹配',
  filtered: '原文被内容过滤',
  missing_evidence_link: '缺少安全可打开原文',
  no_actionable_change: '暂无线索需再次分诊',
});
const isString = x => typeof x === 'string' && !!x.trim();
const isObject = x => x !== null && typeof x === 'object' && !Array.isArray(x);

/**
 * Same-origin deep link into the native V120 event detail/dossier, NOT the
 * server's raw-source URL. The explicit 'from=daily' route flag tells the
 * recovered native reader not to auto-mark as read when opening this link.
 * The dossier remains owner-scoped, authenticated and editable by that UI.
 */

function nativeDossierHref(eventId) {
  if (!isString(eventId) || eventId.length > 256) {
    throw new TypeError('缺少可核验事件ID，不能打开个人证据包。');
  }
  return '/?event=' + encodeURIComponent(eventId) + '&from=daily';
}

/** Browser URL navigation is never used to retrieve originals automatically. */

function safeDailyURL(value) {
  if (!isString(value) || /[\\\u0000-\u0020\u007f]/.test(value)) return '';
  try {
    const parsed = new URL(value);
    const authority = value.replace(/^https?:\/\//i, '').split(/[/?#]/, 1)[0];
    if (!['https:', 'http:'].includes(parsed.protocol) ||
        parsed.username || parsed.password || authority.includes('@')) return '';
    const host = parsed.hostname.toLowerCase().replace(/\.$/, '');
    if (!host || host === 'localhost' || host.endsWith('.localhost') ||
        host.endsWith('.local') || host.endsWith('.internal') ||
        /^(127\.|10\.|192\.168\.|169\.254\.|0\.|172\.(1[6-9]|2[0-9]|3[01])\.)/.test(host) ||
        /^\[?(::1|::ffff:127\.)/.test(host)) return '';
    return parsed.href;
  } catch {
    return '';
  }
}

function safeDailyEvidence(entry) {
  if (!Array.isArray(entry?.evidence?.originals)) return [];
  return entry.evidence.originals.slice(0, 3)
    .map(item => ({ ...item, safe_url: safeDailyURL(item?.url) }))
    .filter(item => item.safe_url);
}
/** Explain where a manual outbound link actually goes before the click.
 * This is URL parsing only, NEVER a fetch, availability check, provenance
 * attestation or independent verification of the claim. */

function dailySourceDestination(value) {
  const safe = safeDailyURL(value);
  if (!safe) return null;
  const parsed = new URL(safe);
  const host = parsed.hostname.toLowerCase().replace(/\.$/, '');
  const platforms = ['x.com', 'twitter.com', 't.me', 'telegram.me',
    'youtube.com', 'youtu.be'];
  const platformPage = platforms.some(domain =>
    host === domain || host.endsWith('.' + domain));
  return {
    origin: parsed.origin,
    source_kind: platformPage
      ? '平台来源页面 · 是否为一手发布、是否独立核实均未知'
      : '来源网站页面 · 是否为一手发布、是否独立核实均未知',
    transport: parsed.protocol === 'http:'
      ? 'HTTP · 连接未加密，谨慎离站'
      : 'HTTPS · 仅说明网址协议，不证明页面真实性',
  };
}

function assertDailyResponse(payload) {
  if (!isObject(payload) || !Array.isArray(payload.topics) ||
      !Array.isArray(payload.today_top3) ||
      payload.today_top3.length > 3) {
    throw new TypeError('每日雷达缺少可信的 topics/today_top3，不能据此推断无变化。');
  }
  const topics = new Map();
  for (const topic of payload.topics) {
    if (!isObject(topic) || !isString(topic.id) || !isString(topic.name) ||
        !isObject(topic.status) || !isString(topic.status.code) ||
        !isString(topic.status.explanation) || topics.has(topic.id)) {
      throw new TypeError('主题状态响应不完整或重复，无法验证无匹配状态。');
    }
    topics.set(topic.id, topic);
  }
  if (!topics.size && payload.today_top3.length) {
    throw new TypeError('没有个人主题却返回个人候选，不能展示。');
  }
  const ids = new Set();
  for (const item of payload.today_top3) {
    const topic = item?.topic;
    const event = item?.event;
    const action = item?.actions?.decision;
    const feedbackAction = item?.actions?.usefulness;
    const evidence = item?.evidence;
    if (!isObject(topic) || !isString(topic.id) || !topics.has(topic.id) ||
        topics.get(topic.id).suspended === true ||
        !isObject(event) || !isString(event.id) || !isString(event.title) ||
        !isObject(item.change) || !isString(item.change.kind) ||
        !isString(item.change.description) ||
        !isString(item.why_watch) ||
        !isObject(evidence) || !Array.isArray(evidence.originals) ||
        evidence.claim_verified !== false ||
        !isDailyUsefulness(event.usefulness) ||
        !isObject(action) || action.method !== 'POST' ||
        action.event_id !== event.id ||
        action.path !== `/api/radar/topics/${topic.id}/decisions` ||
        !Array.isArray(action.allowed_values) ||
        !Object.keys(DAILY_ACTIONS).every(v => action.allowed_values.includes(v)) ||
        !isObject(feedbackAction) || feedbackAction.method !== 'POST' ||
        feedbackAction.event_id !== event.id ||
        feedbackAction.path !== `/api/radar/topics/${topic.id}/usefulness` ||
        feedbackAction.independent_of_decision !== true ||
        !Array.isArray(feedbackAction.allowed_values) ||
        !Object.keys(DAILY_USEFULNESS).every(v => feedbackAction.allowed_values.includes(v)) ||
        !feedbackAction.allowed_values.includes(null) ||
        !safeDailyEvidence(item).length || ids.has(event.id)) {
      throw new TypeError('今日个人候选缺少匹配主题、可打开的对应原文或安全决策合同。');
    }
    ids.add(event.id);
  }
  return payload;
}

function topicStateRows(payload) {
  return assertDailyResponse(payload).topics.map(topic => {
    const status = topic.status;
    const raw = isObject(topic.raw) ? topic.raw : null;
    return {
      id: topic.id,
      name: topic.name,
      code: status.code,
      label: DAILY_TOPIC_STATES[status.code] || '服务器返回其他主题状态',
      explanation: status.explanation,
      baseline: topic.since_baseline?.description || '',
      raw: raw && {
        matching: validCount(raw.matching_originals),
        waiting: validCount(raw.pending_or_processing),
        failed: validCount(raw.matching_by_state?.failed),
        seen: validCount(raw.raw_ingested_on_selected_platforms),
      },
    };
  });
}

function validCount(value) {
  return Number.isSafeInteger(value) && value >= 0 ? value : null;
}

function safeText(value, max = 480) {
  return isString(value) ? value.trim().slice(0, max) : '';
}

function clockText(value, { label = '时间未提供', timezone = 'Asia/Shanghai' } = {}) {
  if (!isString(value)) return label;
  const time = new Date(value);
  if (!Number.isFinite(time.getTime())) return label;
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: timezone, year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(time) + '（北京时间）';
}
/** Server-declared model time is a *clue*, not independently proven occurrence.
 * Do not turn a day/month into a midnight timestamp, or a planned date into
 * an assertion that the event already happened. Date-only civil values carry
 * the source's calendar day; timezone conversion of their synthetic 00:00
 * UTC representation would distort the original meaning.
 */
const UNKNOWN_OCCURRENCE = '发生时间未知 · 不以原文发布时间代替';
function civilDate(value) {
  if (!isString(value) || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return '';
  const date = new Date(value + 'T00:00:00Z');
  return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === value
    ? value : '';
}
function calendarLabel(value, monthOnly = false) {
  const date = civilDate(value);
  if (!date) return '';
  const [year, month, day] = date.split('-');
  return monthOnly ? `${year}年${Number(month)}月`
    : `${year}年${Number(month)}月${Number(day)}日`;
}

function occurrenceText(event) {
  if (!isObject(event) || !isString(event.event_occurred_at)) {
    return UNKNOWN_OCCURRENCE;
  }
  const status = event.event_time_status;
  const precision = event.event_time_precision;
  if (!['explicit', 'inferred', 'scheduled'].includes(status) ||
      !['exact', 'day', 'month', 'range'].includes(precision)) {
    return UNKNOWN_OCCURRENCE;
  }
  let when = '';
  if (precision === 'exact') {
    // ISO clock only; JS Date also accepts many ambiguous free-form strings.
    if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(event.event_occurred_at)) {
      return UNKNOWN_OCCURRENCE;
    }
    when = clockText(event.event_occurred_at, {label:''});
  } else if (precision === 'day' || precision === 'month') {
    when = calendarLabel(event.event_civil_start, precision === 'month');
    if (when) when += precision === 'day' ? '（仅日期，无具体时分）' : '（仅月份）';
  } else {
    const start = calendarLabel(event.event_civil_start);
    const end = calendarLabel(event.event_civil_end);
    if (start && end && event.event_civil_start <= event.event_civil_end) {
      when = start === end ? start + '（仅日期范围）'
        : start + ' 至 ' + end + '（仅日期范围）';
    }
  }
  if (!when) return UNKNOWN_OCCURRENCE;
  const statusNote = status === 'scheduled' ? '计划时间，不能当作已经发生'
    : status === 'inferred' ? '推断时间，尚未独立核实'
    : '资料标记时间，尚未独立核实';
  return `${when} · ${statusNote}`;
}

function displayDailyState(payload) {
  const data = assertDailyResponse(payload);
  if (!data.topics.length) return 'first-run';
  return data.today_top3.length ? 'actionable' : 'no-actionable';
}
/** The owner alone labels practical usefulness. Neither a watch/research
 * decision nor an LLM score constitutes human feedback. Reversal is explicit. */

function usefulnessReceipt(receipt, topicId, eventId, value) {
  if (!isObject(receipt) || receipt.topic_id !== topicId ||
      receipt.event_id !== eventId || receipt.value !== value ||
      !isDailyUsefulness(value) ||
      (value === null ? receipt.rated_at !== null : !isString(receipt.rated_at)) ||
      typeof receipt.updated !== 'boolean' ||
      !Number.isSafeInteger(receipt.owner_revision) || receipt.owner_revision < 0) {
    throw new TypeError('服务端价值反馈回执与本人的当前事件不一致，不能宣称保存。');
  }
  return receipt;
}

function decisionReceipt(receipt, topicId, eventId, decision) {
  if (!isObject(receipt) || receipt.topic_id !== topicId ||
      receipt.event_id !== eventId || receipt.decision !== decision ||
      !isString(receipt.decided_at) ||
      !Number.isSafeInteger(receipt.owner_revision) || receipt.owner_revision < 0) {
    throw new TypeError('服务端写入回执与当前候选不匹配，不能宣称已保存。');
  }
  return receipt;
}


/**
 * V142: an explicitly manually recorded single-user baseline, NOT a usage
 * analytics agent. The browser stores only opaque identifiers, dates, duration
 * and a few user-entered counts/boolean declarations: never source URLs,
 * keywords, original text, login credentials or inferred human actions.
 * Fields match the separately audited owner_pilot_gate.py JSON contract.
 */

const OWNER_PILOT_LOCAL_KEY = 'frontier.v142.manual-owner-pilot.v1';

const OWNER_PILOT_SCHEMA = 'frontier.owner-pilot.manual-v1';

function emptyOwnerPilot() {
  return {
    schema: OWNER_PILOT_SCHEMA,
    provenance: 'manual_self_report_not_independently_verified',
    sessions: [], reviews: [], willingness: [], external_receipt_verified: false,
  };
}
const isOwnerPilotDate = value => {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const d = new Date(value + 'T00:00:00Z');
  return Number.isFinite(d.getTime()) && d.toISOString().slice(0, 10) === value;
};
const boundedOwnerInt = (value, maximum = 86400) =>
  Number.isSafeInteger(value) && value >= 0 && value <= maximum;
const ownerPilotRef = ref => typeof ref === 'string' &&
  /^[A-Za-z0-9_.-]{1,64}$/.test(ref);
const PILOT_FLAGS = Object.freeze([
  'owner_confirmed_original_opened', 'owner_confirmed_decision_saved',
  'owner_confirmed_no_prompt', 'owner_confirmed_comparable_task',
  'key_miss', 'claimed_independence_without_check',
  'fabricated_occurrence_time',
]);

function ownerPilotDay(date = new Date()) {
  if (!(date instanceof Date) || !Number.isFinite(date.getTime())) {
    throw new TypeError('日期不可信，不能记录人工试验。');
  }
  const pieces = Object.fromEntries(new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(date).filter(p => ['year','month','day'].includes(p.type))
    .map(p => [p.type,p.value]));
  const day = [pieces.year,pieces.month,pieces.day].join('-');
  if (!isOwnerPilotDate(day)) throw new TypeError('无法确认北京时间日期。');
  return day;
}

/** Refuse to repair a corrupt or another-schema browser record silently. */

function assertOwnerPilot(pilot) {
  const fields = ['schema','provenance','sessions','reviews','willingness','external_receipt_verified'];
  if (!isObject(pilot) || Object.keys(pilot).length !== fields.length ||
    fields.some(k => !Object.hasOwn(pilot,k)) || pilot.schema !== OWNER_PILOT_SCHEMA ||
    pilot.provenance !== 'manual_self_report_not_independently_verified' ||
    pilot.external_receipt_verified !== false ||
    !Array.isArray(pilot.sessions) || pilot.sessions.length > 90 ||
    !Array.isArray(pilot.reviews) || !Array.isArray(pilot.willingness) ||
    pilot.reviews.length > 90 || pilot.willingness.length > 90) {
    throw new TypeError('本地试验记录结构异常，不会覆盖或推断其内容。');
  }
  const refs = new Set();
  const sessionFields = ['session_ref','day','old_seconds','frontier_seconds',
    'reviewed_items','noise_items','explicit_page_actions',...PILOT_FLAGS];
  for (const s of pilot.sessions) {
    if (!isObject(s) || Object.keys(s).length !== sessionFields.length ||
      sessionFields.some(k => !Object.hasOwn(s,k)) || !ownerPilotRef(s.session_ref) ||
      refs.has(s.session_ref) || !isOwnerPilotDate(s.day) ||
      !boundedOwnerInt(s.old_seconds) || s.old_seconds < 1 ||
      !boundedOwnerInt(s.frontier_seconds) || s.frontier_seconds < 1 ||
      !boundedOwnerInt(s.reviewed_items, 20000) ||
      !boundedOwnerInt(s.noise_items, 20000) ||
      s.noise_items > s.reviewed_items ||
      !boundedOwnerInt(s.explicit_page_actions, 20000) ||
      PILOT_FLAGS.some(key => typeof s[key] !== 'boolean')) {
      throw new TypeError('本地真人手填会话无效或重复，不能悄悄修复。');
    }
    refs.add(s.session_ref);
  }
  // Only the sessions section is editable through V142; when importing a
  // manually extended complete owner-pilot JSON, preserve valid prior sections.
  if (pilot.reviews.length !== 0 || pilot.willingness.length !== 0) {
    throw new TypeError('本地试验格式含外部复核或价格字段，请用独立工具处理。');
  }
  return pilot;
}

function parseOwnerPilotJSON(text) {
  if (text === null || text === undefined || text === '') return emptyOwnerPilot();
  if (typeof text !== 'string' || text.length > 350000) {
    throw new TypeError('本地记录过大或不是JSON，已拒绝覆盖。');
  }
  return assertOwnerPilot(JSON.parse(text));
}
function manualNumber(value, {min=0,max=1440,decimal=false}={}) {
  const raw = String(value ?? '').trim();
  if (!(decimal ? /^(?:\d+)(?:\.\d{1,2})?$/.test(raw) : /^\d+$/.test(raw))) {
    throw new TypeError('用时和计数需要明确填写数字，未保存。');
  }
  const number = Number(raw);
  if (!Number.isFinite(number) || number < min || number > max) {
    throw new RangeError('用时或计数超过可记录范围，未保存。');
  }
  return number;
}
/** No metrics or booleans are filled by the server/app; every input is human. */

function makeOwnerPilotSession(input, {day,sessionRef} = {}) {
  if (!isObject(input) || !isOwnerPilotDate(day) || !ownerPilotRef(sessionRef)) {
    throw new TypeError('本次记录需要真实北京日期与匿名记录ID。');
  }
  const oldMinutes = manualNumber(input.old_minutes, {min:0.1,max:1440,decimal:true});
  const currentMinutes = manualNumber(input.frontier_minutes, {min:0.1,max:1440,decimal:true});
  const reviewed = manualNumber(input.reviewed_items, {max:20000});
  const noise = manualNumber(input.noise_items, {max:20000});
  const actions = manualNumber(input.explicit_page_actions, {max:20000});
  if (noise > reviewed) throw new RangeError('没帮助数量不能超过本人实评数量。');
  const result = {
    session_ref:sessionRef, day,
    old_seconds:Math.round(oldMinutes * 60),
    frontier_seconds:Math.round(currentMinutes * 60),
    reviewed_items:reviewed, noise_items:noise,
    explicit_page_actions:actions,
  };
  for (const flag of PILOT_FLAGS) {
    if (typeof input[flag] !== 'boolean') {
      throw new TypeError('本人确认项必须是明确的布尔值，未保存。');
    }
    result[flag] = input[flag];
  }
  if (result.old_seconds < 1 || result.frontier_seconds < 1) {
    throw new RangeError('计时不能为零。');
  }
  return result;
}

function appendOwnerPilotSession(pilot, entry, todayDay) {
  const previous = assertOwnerPilot(pilot);
  if (!isOwnerPilotDate(todayDay) || entry?.day !== todayDay || 
    previous.sessions.length >= 90) {
    throw new TypeError('只能手动记录今天、不允许未来日期或超过90条。');
  }
  const next = { ...previous, sessions:[...previous.sessions, entry] };
  return assertOwnerPilot(next);
}
/** Deliberately no extrapolation when <3 distinct observed days. */

function ownerPilotView(pilot, todayDay) {
  assertOwnerPilot(pilot);
  if (!isOwnerPilotDate(todayDay)) throw new TypeError('需要确定北京日期');
  const observed = pilot.sessions.filter(s => s.day <= todayDay);
  const eligible = observed.filter(s =>
    s.owner_confirmed_no_prompt &&
    s.owner_confirmed_comparable_task &&
    s.owner_confirmed_original_opened &&
    s.owner_confirmed_decision_saved);
  const byDay = new Map();
  for (const s of eligible) {
    if (!byDay.has(s.day)) byDay.set(s.day, []);
    byDay.get(s.day).push(s);
  }
  const days = byDay.size;
  const middle = sorted => sorted.length % 2 ?
    sorted[(sorted.length-1)/2] :
    (sorted[sorted.length/2-1]+sorted[sorted.length/2])/2;
  // Each natural day contributes one median. Multiple sessions on one date
  // cannot dominate the self-reported value conclusion across three dates.
  const dailyMedian = metric => [...byDay.values()].map(rows =>
    middle(rows.map(metric).sort((a,b)=>a-b))).sort((a,b)=>a-b);
  const savings = dailyMedian(s=>s.old_seconds-s.frontier_seconds);
  const rel = dailyMedian(s=>(s.old_seconds-s.frontier_seconds)/s.old_seconds);
  const riskCount = observed.filter(s => s.key_miss ||
    s.claimed_independence_without_check || s.fabricated_occurrence_time).length;
  // A single explicitly reported critical miss invalidates a positive value
  // claim; preserve all raw self-reports for honest subsequent review.
  const sufficient = eligible.length >= 3 && days >= 3 && riskCount === 0;
  return {
    recorded:observed.length,
    valid_pairs:eligible.length,
    distinct_days:days,
    risk_records:riskCount,
    safe_for_value_claim:riskCount===0,
    enough_days_for_comparison:sufficient,
    median_seconds_saved:sufficient ? middle(savings) : null,
    median_relative_saved:sufficient ? middle(rel) : null,
    aggregation:'median_per_beijing_day_then_median_across_days_manual_only',
    // A calculator may show a self-report signal; neither a valid user session,
    // reliable external original nor legal revenue has been independently checked.
    independently_verified:false,
    revenue_verified:false,
  };
}


// V144 optional explicit append-only owner ledger uses existing authenticated
// session and CSRF. Calling this model never transmits a user request.

const OWNER_PILOT_CLOUD_PATH = '/api/owner/pilot';

const OWNER_PILOT_CLOUD_SESSION_PATH = '/api/owner/pilot/sessions';

function assertOwnerPilotCloudPayload(payload,todayDay=ownerPilotDay()) {
  const pilot=assertOwnerPilot(payload);
  if (!isOwnerPilotDate(todayDay) || pilot.sessions.some(s=>s.day>todayDay)) {
    throw new TypeError('云端记录来自未来日期；拒绝隐式修复或导入。');
  }
  return pilot;
}

// Compare actual canonical data independent of Python JSON key order.
// Never compare only sample counts, otherwise two different same-size
// backups could look identical to a browser after a failed write.
const ownerSortFields = value => {
  if (Array.isArray(value)) return value.map(ownerSortFields);
  if (isObject(value)) return Object.fromEntries(Object.keys(value).sort()
    .map(key => [key,ownerSortFields(value[key])]));
  return value;
};

function sameOwnerPilotContent(left, right) {
  assertOwnerPilot(left);
  assertOwnerPilot(right);
  return JSON.stringify(ownerSortFields(left)) === JSON.stringify(ownerSortFields(right));
}

function sameOwnerPilotSessionContent(left,right) {
  const a=emptyOwnerPilot();
  const b=emptyOwnerPilot();
  a.sessions=[left];
  b.sessions=[right];
  return sameOwnerPilotContent(a,b);
}

/**
 * Human-in-control "今天我该处理哪三件事" panel for frozen V120.
 * Mounts above the original feed/Radar; leaves old globe, map, subscriptions,
 * evidence, inbox and native Radar event/decision flows intact.
 * All facts and actionable entries come ONLY from authenticated /api/radar/daily.
 */

function createDailyPanel({
  doc = globalThis.document,
  win = globalThis.window,
  request = globalThis.fetch?.bind(globalThis),
  clock = globalThis,
} = {}) {
  if (!doc || !win || !request) throw new Error('document/window/fetch required for daily panel');
  let destroyed = false;
  let navNode = null;
  let generation = 0;
  let data = null;
  let loadController = null;
  let refreshTimer = null;
  let refreshInterval = null;
  let errorText = '';
  const decisionsPending = new Set();
  const usefulnessPending = new Set();

  const $ = selector => doc.querySelector(selector);
  const el = (tag, cls = '', text = '') => {
    const node = doc.createElement(tag);
    if (cls) node.className = cls;
    if (text) node.textContent = text;
    return node;
  };
  const txt = (v, n = 360) => safeText(v, n);
  const isAuthenticatedDOM = () => Boolean($('#nav-radar') && $('.main-shell'));
  // Existing Radar/Inbox/source panes own the entire flexible viewport.
  // Show this dashboard ONLY on Feed, otherwise a large sibling can reduce
  // native Radar's flex height to zero despite display:block.
  const isVisibleView = () => Boolean($('#nav-feed[aria-current="page"]'));
  const remove = () => doc.getElementById(DAILY_PANEL_ID)?.remove();
  const isCurrent = (scope) => !destroyed && navNode === $('#nav-radar') && generation === scope;

  function jumpRadar() {
    const nav = $('#nav-radar');
    if (nav) {
      nav.click(); // Open the existing native Radar; do not replace its evidence tools.
      nav.focus?.({ preventScroll: true });
    }
  }
  function panel() {
    if (!isAuthenticatedDOM()) return null;
    const main = $('.main-shell');
    let root = doc.getElementById(DAILY_PANEL_ID);
    if (!root) {
      root = el('section', 'frontier-daily-dashboard');
      root.id = DAILY_PANEL_ID;
      root.setAttribute('aria-labelledby', 'frontier-daily-title');
      root.setAttribute('role', 'region');
    }
    if (root.parentNode !== main) {
      const feed = main.querySelector('#feed-workspace');
      if (feed) main.insertBefore(root, feed);
      else main.insertBefore(root, main.children[1] || null);
    }
    root.hidden = !isVisibleView();
    return root;
  }
  function smallButton(label, className, onClick) {
    const button = el('button', className, label);
    button.type = 'button';
    button.addEventListener('click', onClick);
    return button;
  }
  function appendAuditedNotes(parent, record) {
    if (record?.update_source !== 'independent_2040_audit_owner_delivery' ||
        !Array.isArray(record.actual_updates)) return;
    const updates = record.actual_updates
      .filter(message => typeof message === 'string' && message.trim() &&
        message.length <= 180).slice(0, 10);
    if (!updates.length) return;
    const section = el('details', 'frontier-daily-audited-updates');
    section.dataset.auditedUpdates = 'true';
    section.append(el('summary','',
      '查看此页面已验版本的 ' + updates.length + ' 项实际更新'));
    const items = el('ol');
    for (const message of updates) items.append(el('li', '', message));
    section.append(items);
    parent.append(section);
  }
  function hero(root, state, summary) {
    const head = el('div', 'frontier-daily-hero');
    const headline = el('div', 'frontier-daily-headline');
    headline.append(el('span', 'frontier-daily-eyebrow', 'PRIVATE INTELLIGENCE  /  DAILY BRIEF'));
    const h = el('h2', '', '今天我该处理哪三件事？');
    h.id = 'frontier-daily-title';
    headline.append(h, el('p', 'frontier-daily-subtitle', summary));
    // Build identity is baked into the dated HTML by the actual candidate
    // composer, never inferred from story times or an unverified network claim.
    const buildDate = doc.querySelector('meta[name="frontier-build-date"]')?.getAttribute('content');
    const product = doc.querySelector('meta[name="frontier-product-release"]')?.getAttribute('content') || '';
    if (buildDate && /^20\d{2}-\d{2}-\d{2}$/.test(buildDate)) {
      const validRelease = /^Frontier-V145-[A-Za-z0-9-]+$/.test(product) &&
        product.includes(buildDate.replaceAll('-', ''));
      const label = validRelease ? ' · V145 · 构建标识 ' + product.split('-').at(-1) : '';
      const stamp = el('small', 'frontier-daily-build-stamp',
        `本页面构建 ${buildDate}${label} · 正式生效以云端审计为准；不代表来源当日发表或已核实`);
      if (validRelease) stamp.title = product;
      headline.append(stamp);
    }
    const releaseId = doc.querySelector('meta[name="frontier-product-release"]')?.getAttribute('content') || '';
    if (buildDate && /^Frontier-V145-[A-Za-z0-9-]+$/.test(releaseId)) {
      const proof = el('p', 'frontier-daily-official', '正在核查云端正式发行及20:40独立审计…');
      proof.dataset.officialRelease = 'true';
      headline.append(proof);
      const scope = generation;
      void (async () => {
        try {
          const response = await request('/api/release', {
            credentials: 'same-origin', cache: 'no-store',
            headers: { Accept: 'application/json' },
          });
          if (!response.ok) throw new Error('official evidence unavailable');
          const observation = await response.json();
          if (!isCurrent(scope) || !proof.isConnected) return;
          const actual = observation?.last_independently_verified;
          if (observation?.schema !== 'frontier.owner.real-delivery-status.v1') {
            throw new Error('official evidence contract changed');
          }
          if (observation.today_status === 'VERIFIED_REAL_COMMITTED' &&
              actual?.product_release === releaseId) {
            proof.dataset.delivery = 'verified';
            proof.textContent = '✓ 今日正式交付已独立核验 · ' +
              (actual.backend || '?') + ' 后端 · ' + (actual.static || '?') +
              ' 页面 · HTTP ' + (actual.http || '?');
            appendAuditedNotes(headline, actual);
          } else if (observation.today_status === 'COMMITTED_AWAITING_INDEPENDENT_AUDIT' &&
                     observation.today_committed_release === releaseId) {
            proof.dataset.delivery = 'pending';
            proof.textContent = '○ 今日正式版本已提交 · 20:40 独立审计尚未确认';
          } else if (actual?.product_release === releaseId &&
                     /^20\d{2}-\d{2}-\d{2}$/.test(actual.beijing_date || '') &&
                     actual.beijing_date < observation.beijing_date) {
            // A page verified yesterday is still historically verified after
            // midnight. But that old receipt does NOT verify today's rollout.
            const today = observation.today_status === 'NOT_VERIFIED_OR_HELD'
              ? '今天发布未核验或已暂停'
              : observation.today_status === 'COMMITTED_AWAITING_INDEPENDENT_AUDIT'
              ? '今天有其他版本已提交、等待独立审计'
              : '今天尚无独立验收的新版本';
            proof.dataset.delivery = 'verified-history';
            proof.textContent = '✓ 本页已于 ' + actual.beijing_date +
              ' 独立验收 · ' + today + '；历史验收不等于今天部署成功';
            appendAuditedNotes(headline, actual);
          } else {
            proof.dataset.delivery = 'unverified';
            const last = actual?.beijing_date ? '；上次已验 ' +
              actual.beijing_date + ' / ' + (actual.product_release || '').split('-')[1] : '';
            proof.textContent = '此浏览器构建尚无今日正式验收证明' + last +
              '；不可当作已部署版本';
          }
          // Long-open tabs do NOT update their HTML/JS merely because the
          // cloud deployed a new version. Offer a user-controlled reload only
          // after real independent audit, never auto-discard unsaved notes.
          if (observation.today_status === 'VERIFIED_REAL_COMMITTED' &&
              /^Frontier-V[0-9]+-[A-Za-z0-9-]+$/.test(actual?.product_release || '') &&
              actual.beijing_date >= buildDate && actual.product_release !== releaseId) {
            const reload = smallButton(
              '↻ 已验 ' + actual.beijing_date + ' 新版可用 · 请先保存草稿，再点击加载',
              'frontier-daily-reload-new', () => win.location.reload());
            reload.dataset.updateAvailable = 'true';
            headline.append(reload);
          }
        } catch {
          if (!isCurrent(scope) || !proof.isConnected) return;
          proof.dataset.delivery = 'unverified';
          proof.textContent = '正式验收记录暂时无法读取；本页面构建信息不等于部署成功';
        }
      })();
    }
    const badge = el('span', 'frontier-daily-state');
    badge.dataset.dailyState = state;
    badge.textContent = state === 'actionable' ? '● 可逐项处理' :
      state === 'no-actionable' ? '○ 等待有效变化' : '◇ 待验证';
    const tools = el('div', 'frontier-daily-tools');
    const refresh = smallButton('↻ 同步服务端', 'frontier-daily-refresh', () => refreshData());
    refresh.dataset.dailyRefresh = 'true';
    tools.append(badge, refresh, smallButton('进入原生雷达 ↗', 'frontier-daily-radar', jumpRadar));
    head.append(headline, tools);
    root.append(head);
  }
  function infoRow(term, value) {
    const row = el('div', 'frontier-daily-clock');
    row.append(el('dt', '', term), el('dd', '', value));
    return row;
  }
  function placeWarning(root, text, alert = false) {
    const line = el('p', alert ? 'frontier-daily-error' : 'frontier-daily-trust', text);
    if (alert) line.setAttribute('role', 'alert');
    root.append(line);
    return line;
  }
  function renderProcessing(root, snapshot) {
    const rows = topicStateRows(snapshot);
    const heading = el('div', 'frontier-daily-empty-body');
    const feature = el('div', 'frontier-daily-empty-lead');
    feature.append(el('span', 'frontier-daily-empty-symbol', '○'),
      el('h3', '', '此刻没有可核对原文的个人待决定事件'));
    feature.append(el('p', '', '不是自动判定「世界没有变化」。下列原因来自服务器对各个已保存主题、检索时间窗与原文处理状态的真实检查。'));
    heading.append(feature);
    const statuses = el('div', 'frontier-daily-status-list');
    statuses.setAttribute('aria-label', '各个人主题服务端状态');
    for (const item of rows) {
      const cell = el('article', 'frontier-daily-topic-status');
      cell.dataset.dailyTopic = item.id;
      cell.dataset.dailyStatus = item.code;
      const row = el('div', 'frontier-daily-topic-row');
      row.append(el('strong', '', txt(item.name, 120)),
        el('span', 'frontier-daily-topic-badge', item.label));
      cell.append(row, el('p', '', txt(item.explanation, 350)));
      if (item.raw) {
        const facts = [
          item.raw.seen === null ? '' : `该平台窗口入库 ${item.raw.seen}`,
          item.raw.matching === null ? '' : `词项匹配 ${item.raw.matching}`,
          item.raw.waiting === null ? '' : `待处理 ${item.raw.waiting}`,
          item.raw.failed === null ? '' : `失败 ${item.raw.failed}`,
        ].filter(Boolean);
        if (facts.length) cell.append(el('small', '', facts.join('  /  ')));
      }
      if (item.baseline) cell.append(el('small', 'frontier-daily-baseline', txt(item.baseline, 240)));
      statuses.append(cell);
    }
    heading.append(statuses);
    root.append(heading);
  }
  function evidenceList(item, into) {
    const originals = safeDailyEvidence(item);
    const box = el('div', 'frontier-daily-originals');
    box.append(el('div', 'frontier-daily-section-label', '03  /  打开匹配原文再决定'));
    // A displayed outbound URL is a lead, not independent corroboration.
    // The server caps this list at three, so count only *displayed* safe links,
    // never claim a complete global or multi-publisher source inventory.
    const sourceLead = originals.length === 1
      ? '本卡展示 1 条可点原文线索 · 尚无多链接比对，先由你核验'
      : `本卡展示 ${originals.length} 条可点原文线索 · 多条链接不代表独立报道，仍需亲自核验`;
    const quality = el('p', 'frontier-daily-source-quality', sourceLead);
    quality.dataset.safeOriginalLinksShown = String(originals.length);
    box.append(quality);
    const links = el('div', 'frontier-daily-source-list');
    for (const [i, source] of originals.entries()) {
      const link = el('a', 'frontier-daily-source');
      link.href = source.safe_url;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.dataset.dailySource = String(i);
      const primary = el('span', 'frontier-daily-source-name');
      primary.append(el('b', '', txt(source.source_name, 64) ||
        txt(source.platform, 40) || '原始来源'), el('i', '', '↗'));
      const destination = dailySourceDestination(source.safe_url);
      // safeDailyEvidence has already excluded unsafe URLs; fail closed if
      // an unexpectedly invalid URL reaches this render path.
      if (!destination) continue;
      link.append(primary,
        el('small', 'frontier-daily-source-destination',
          `将前往：${destination.origin} · ${destination.transport}`),
        el('small', 'frontier-daily-source-kind', destination.source_kind),
        el('small', '', `原文标记发表：${clockText(source.source_published_at)}`));
      links.append(link);
    }
    box.append(links, el('p', 'frontier-daily-source-caveat',
      '链接展示前只做离线网址筛选；未替你访问网页，未验证可达、内容真实性、一手性、转载独立性或授权。'));
    into.append(box);
  }
  function setDecisionMessage(card, status, value) {
    const target = card.querySelector('.frontier-daily-decision-state');
    target.dataset.state = status;
    target.setAttribute('role', status === 'error' ? 'alert' : 'status');
    target.textContent = value;
  }
  function toggleButtons(card, busy, choice) {
    for (const button of card.querySelectorAll('[data-daily-decision]')) {
      button.disabled = busy;
      button.setAttribute('aria-pressed', String(choice === button.dataset.dailyDecision));
    }
    card.setAttribute('aria-busy', String(busy));
  }
  async function serverError(response) {
    let message = '';
    try {
      const data = await response.json();
      message = txt(data?.message || data?.error?.message || data?.error, 130);
    } catch {}
    if (response.status === 401) return '登录已失效，请重新登录后同步。';
    if (response.status === 403) return 'CSRF 或登录状态已变化，请刷新登录状态再尝试。';
    if (response.status === 409) return '主题或事件状态已变化，请同步最新个人候选。';
    if (response.status === 429) return '操作频率较高，请稍后重试。';
    return message || `服务暂时无法完成请求（HTTP ${response.status}）。`;
  }
  async function decide(item, value, card) {
    const topicId = item.topic.id;
    const eventId = item.event.id;
    const key = topicId + '/' + eventId;
    if (decisionsPending.has(key) || !isAuthenticatedDOM()) return;
    decisionsPending.add(key);
    const scope = generation;
    let last = card.dataset.savedDecision || item.event.decision || '';
    toggleButtons(card, true, last);
    setDecisionMessage(card, 'saving', `正在向服务器保存「${DAILY_ACTIONS[value]}」…`);
    try {
      const me = await request('/api/auth/me', {
        method: 'GET', credentials: 'same-origin', cache: 'no-store',
        headers: { Accept: 'application/json' },
      });
      if (!me.ok) throw new Error(await serverError(me));
      const auth = await me.json();
      if (auth?.authenticated !== true || typeof auth.csrf_token !== 'string' ||
          !auth.csrf_token) throw new Error('登录态未提供合法 CSRF，未提交写入。');
      if (!isCurrent(scope)) return;
      const res = await request(item.actions.decision.path, {
        method: 'POST', credentials: 'same-origin', cache: 'no-store',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': auth.csrf_token,
          Accept: 'application/json',
        },
        body: JSON.stringify({ event_id: eventId, decision: value }),
      });
      if (!res.ok) throw new Error(await serverError(res));
      const receipt = decisionReceipt(await res.json(), topicId, eventId, value);
      if (!isCurrent(scope) || !card.isConnected) return;
      last = value;
      card.dataset.savedDecision = value;
      const at = clockText(receipt.decided_at);
      setDecisionMessage(card, 'saved', `✓ 已写入服务器：${DAILY_ACTIONS[value]} · ${at}。再次修改需明确点击；同步后可能退出待处理列表。`);
    } catch (error) {
      if (isCurrent(scope) && card.isConnected) {
        setDecisionMessage(card, 'error',
          `未确认保存：${txt(error?.message, 160) || '请求失败'}。当前选择未自动更改。`);
      }
    } finally {
      decisionsPending.delete(key);
      if (isCurrent(scope) && card.isConnected) toggleButtons(card, false, last);
    }
  }
  function setUsefulnessMessage(card, status, message) {
    const messageNode = card.querySelector('.frontier-daily-usefulness-state');
    messageNode.dataset.state = status;
    messageNode.setAttribute('role', status === 'error' ? 'alert' : 'status');
    messageNode.textContent = message;
  }
  function toggleUsefulnessButtons(card, busy, choice) {
    for (const button of card.querySelectorAll('[data-daily-usefulness]')) {
      button.disabled = busy;
      button.setAttribute('aria-pressed',
        String(choice === button.dataset.dailyUsefulness));
    }
    card.querySelector('.frontier-daily-usefulness')?.setAttribute('aria-busy', String(busy));
  }
  async function rate(item, nextValue, card) {
    const topicId = item.topic.id;
    const eventId = item.event.id;
    const key = topicId + '/' + eventId;
    if (usefulnessPending.has(key) || !isAuthenticatedDOM()) return;
    const currentValue = card.dataset.savedUsefulness || null;
    usefulnessPending.add(key);
    const scope = generation;
    toggleUsefulnessButtons(card, true, currentValue);
    setUsefulnessMessage(card, 'saving', nextValue === null ?
      '正在撤销本人价值评价…' : `正在保存本人评价「${DAILY_USEFULNESS[nextValue]}」…`);
    try {
      const me = await request('/api/auth/me', {
        method: 'GET', credentials: 'same-origin', cache: 'no-store',
        headers: { Accept: 'application/json' },
      });
      if (!me.ok) throw new Error(await serverError(me));
      const auth = await me.json();
      if (auth?.authenticated !== true || typeof auth.csrf_token !== 'string' ||
          !auth.csrf_token) throw new Error('登录态未提供有效 CSRF，未提交评价。');
      if (!isCurrent(scope)) return;
      const response = await request(item.actions.usefulness.path, {
        method: 'POST', credentials: 'same-origin', cache: 'no-store',
        headers: {
          'Content-Type': 'application/json', 'X-CSRF-Token': auth.csrf_token,
          Accept: 'application/json',
        },
        body: JSON.stringify({ event_id: eventId, value: nextValue }),
      });
      if (!response.ok) throw new Error(await serverError(response));
      const receipt = usefulnessReceipt(await response.json(),
        topicId, eventId, nextValue);
      if (!isCurrent(scope) || !card.isConnected) return;
      card.dataset.savedUsefulness = nextValue || '';
      setUsefulnessMessage(card, 'saved', nextValue === null ?
        '✓ 已经服务端确认撤销价值评价；不影响已有分诊。' :
        `✓ 已保存个人价值评价「${DAILY_USEFULNESS[nextValue]}」 · ${clockText(receipt.rated_at)}。不影响分诊。`);
    } catch (error) {
      if (isCurrent(scope) && card.isConnected) {
        setUsefulnessMessage(card, 'error',
          `价值评价未确认保存：${txt(error?.message, 160) || '请求失败'}；原选择不变。`);
      }
    } finally {
      usefulnessPending.delete(key);
      if (isCurrent(scope) && card.isConnected) {
        toggleUsefulnessButtons(card, false, card.dataset.savedUsefulness || null);
      }
    }
  }

  function renderCard(item, index) {
    const card = el('li', 'frontier-daily-card');
    card.dataset.dailyEvent = item.event.id;
    card.dataset.dailyTopic = item.topic.id;
    const top = el('div', 'frontier-daily-card-top');
    top.append(el('span', 'frontier-daily-card-rank', String(index + 1).padStart(2, '0')));
    const markers = el('div', 'frontier-daily-markers');
    markers.append(el('span', 'frontier-daily-topic-tag', txt(item.topic.name, 75)));
    markers.append(el('span', 'frontier-daily-change-tag',
      DAILY_CHANGES[item.change.kind] || '变化类型待核对'));
    top.append(markers);
    card.append(top);
    const headline = el('h3', 'frontier-daily-card-title', txt(item.event.title, 230));
    card.append(headline);
    if (safeText(item.event.editorial_summary)) {
      const editorial = el('details', 'frontier-daily-card-summary');
      editorial.append(el('summary', '', '可展开编辑摘要（非原文证据）'),
        el('p', '', txt(item.event.editorial_summary, 350)));
      card.append(editorial);
    }
    const contrast = el('div', 'frontier-daily-change-box');
    contrast.append(el('div', 'frontier-daily-section-label', '01  /  发现什么变化'),
      el('p', '', txt(item.change.description, 280)));
    card.append(contrast);
    const why = el('div', 'frontier-daily-why');
    why.append(el('div', 'frontier-daily-section-label', '02  /  为什么要看'));
    const reason = txt(item.why_watch, 100);
    why.append(el('p', '', reason + (item.why_watch.length > 100 ? '…' : '')));
    if (item.why_watch.length > 100) {
      const more = el('details', 'frontier-daily-reason-expand');
      more.append(el('summary', '', '完整的服务端排序依据'),
        el('p', '', txt(item.why_watch, 1400)));
      why.append(more);
    }
    card.append(why);
    const timeBlock = el('div', 'frontier-daily-time-block');
    timeBlock.append(el('p', 'frontier-daily-occurrence',
      '事件时间线索：' + occurrenceText(item.event)));
    const timeDetails = el('details', 'frontier-daily-time-details');
    timeDetails.append(el('summary', '', '核对发生 / 发布 / 收录三钟'));
    const times = el('dl', 'frontier-daily-clocks');
    times.append(
      infoRow('事件时间线索（未经独立核实）', occurrenceText(item.event)),
      infoRow('关联原文最早发表标记', clockText(item.event.source_published_at)),
      infoRow('事件首次入库', clockText(item.event.first_ingested_at)),
      infoRow('最新匹配原文入库', clockText(item.change.latest_matching_original_at)),
    );
    timeDetails.append(times);
    timeBlock.append(timeDetails);
    card.append(timeBlock);
    // Native V120 handles ?event= after authentication, opens detail-dialog
    // with the real owner-scoped dossier. This is a same-origin keyboard link,
    // never a parallel evidence store or silent decision/read action.
    const dossier = el('a', 'frontier-daily-dossier-link',
      '打开个人证据包并可设置下次复查 ↗');
    dossier.href = nativeDossierHref(item.event.id);
    dossier.target = '_blank';
    dossier.rel = 'noopener noreferrer';
    dossier.dataset.dailyDossier = item.event.id;
    dossier.setAttribute('aria-label',
      '打开' + txt(item.event.title, 100) + '的个人证据包并可设置下次复查（新标签，不会自动标已读）');
    card.append(dossier, el('p', 'frontier-daily-dossier-note',
      '在原生事件详情中核对出处、保存判断与复查日；新标签开启，不自动标已读。'));
    evidenceList(item, card);
    const action = el('div', 'frontier-daily-actions');
    action.append(el('div', 'frontier-daily-section-label', '04  /  阅读后由你决定'));
    const buttons = el('div', 'frontier-daily-decision-buttons');
    for (const [decision, label] of Object.entries(DAILY_ACTIONS)) {
      const button = smallButton(label, 'frontier-daily-decision frontier-daily-decision-' + decision,
        () => decide(item, decision, card));
      button.dataset.dailyDecision = decision;
      button.setAttribute('aria-pressed', String(item.event.decision === decision));
      buttons.append(button);
    }
    action.append(buttons);
    const feedback = el('p', 'frontier-daily-decision-state', item.event.decision ?
      `服务器当前记录：${DAILY_ACTIONS[item.event.decision] || '已有人工决定'}；有新原文时可重新判断。` :
      '尚无个人决定。点击后才提交持久化写入；不会自动标已读或替你复盘。');
    feedback.setAttribute('role', 'status');
    action.append(feedback);
    card.append(action);
    // A second explicit human axis, never inferred from the decision:
    // useful/noise is the existing owner-scoped /api/radar/.../usefulness.
    const usefulness = el('section', 'frontier-daily-usefulness');
    usefulness.setAttribute('aria-label', '本人评价此情报是否有帮助，与分诊行动独立');
    usefulness.append(el('div', 'frontier-daily-section-label',
      '05  /  这条信息对我有帮助吗？'));
    usefulness.append(el('p', 'frontier-daily-usefulness-note',
      '只评价对你是否有用，不评价事件真伪；不自动由关注、研究或忽略推断。'));
    const valueButtons = el('div', 'frontier-daily-usefulness-buttons');
    const initialValue = item.event.usefulness;
    card.dataset.savedUsefulness = initialValue || '';
    for (const [value, label] of Object.entries(DAILY_USEFULNESS)) {
      const button = smallButton(label, 'frontier-daily-usefulness-button',
        () => rate(item, (card.dataset.savedUsefulness || null) === value ?
          null : value, card));
      button.dataset.dailyUsefulness = value;
      button.setAttribute('aria-pressed', String(initialValue === value));
      button.title = '再次点击已选项即可撤销评价';
      valueButtons.append(button);
    }
    usefulness.append(valueButtons);
    const valueState = el('p', 'frontier-daily-usefulness-state',
      initialValue ? `服务器当前保存：${DAILY_USEFULNESS[initialValue]}；点已选项可撤销。` :
        '尚未评价；需要你主动点击才记录，未评价不计作无帮助。');
    valueState.setAttribute('role', 'status');
    usefulness.append(valueState);
    card.append(usefulness);
    return card;
  }

  // V142: optional, explicitly local-only manual baseline. Cannot mutate
  // Radar or infer source availability, human actions, or legal payment.
  function renderOwnerPilot(root) {
    const box = el('details', 'frontier-daily-owner-pilot');
    box.dataset.ownerPilot = 'true';
    const caption = el('summary', '', '自己实测：旧方法与 FRONTIER 各用多久？（手填或本页计时）');
    box.append(caption);
    const body = el('div', 'frontier-daily-owner-pilot-body');
    box.append(body);
    root.append(box);
    const status = el('p', 'frontier-daily-owner-pilot-state');
    status.setAttribute('role', 'status');
    let last;
    function load() {
      return parseOwnerPilotJSON(win.localStorage?.getItem(OWNER_PILOT_LOCAL_KEY));
    }
    function readback() {
      try {
        const pilot = load();
        const stats = ownerPilotView(pilot, ownerPilotDay());
        const line = el('p', 'frontier-daily-owner-pilot-counts',
          '本浏览器已有 ' + stats.recorded + ' 条本人手填记录；符合明确同任务、无提示、主动开原文及保存决策的配对 ' +
          stats.valid_pairs + ' 条 / ' + stats.distinct_days + ' 个北京时间自然日。');
        const value = el('p', 'frontier-daily-owner-pilot-counts',
          stats.risk_records > 0 ?
            '⚠ 本人记录中有 ' + stats.risk_records + ' 次关键漏报、伪造发生时间或来源独立性误导。停止正面节时结论，请先核实风险及原文；即使人工填了三天也不能据此宣称有价值。' :
          stats.enough_days_for_comparison ?
            '按北京时间自然日先汇总的自报中位节省：' + Math.round(stats.median_seconds_saved) + ' 秒 / ' +
            (stats.median_relative_saved*100).toFixed(1) + '%；未经独立证实，不是实际收入。' :
            '配对不足三个不同自然日：不计算节时结论；分钟由本人手填或主动计时填入，未获得独立核实。');
        if (stats.risk_records) {
          value.dataset.state = 'risk';
          value.setAttribute('role','alert');
        }
        last?.remove();
        const current = el('div', 'frontier-daily-owner-pilot-overview');
        current.append(line,value);
        body.prepend(current);
        last = current;
        return pilot;
      } catch(error) {
        const note = txt(error?.message, 170) || '浏览器私有存储不可用';
        status.dataset.state = 'error';
        status.textContent = '无法验证本地旧记录，不会覆盖：' + note;
        throw error;
      }
    }
    body.append(el('p', 'frontier-daily-owner-pilot-note',
      '计时仅在本页内存；数字只有你明确保存时才写入当前浏览器未加密localStorage，默认不上传服务器，不含原文、账号、关键词或URL。退出登录（含手机退出）立即清空本地数字。你可自己下载私有JSON，或在下方再次明确确认可选云端备份；云端数字也未加密，绝不自动上传或同步。其他浏览器只能由你本人主动从云端恢复或选择本地JSON导入。其他同源脚本可能读取本地数字，不要在共享设备使用。'));
    try {
      readback();
    } catch {
      body.append(status);
      return; // Never overwrite corrupted local evidence.
    }
    const form = el('form', 'frontier-daily-owner-pilot-form');
    form.noValidate = true;
    const numeric = (name, label, {min = '0', step = '1', value=''} = {}) => {
      const block = el('label', 'frontier-daily-owner-pilot-field');
      block.append(el('span', '', label));
      const input = el('input');
      input.type = 'number';
      input.name = name;
      input.required = true;
      input.min = min;
      input.max = name.includes('minutes') ? '1440' : '20000';
      input.step = step;
      if (value) input.value = value;
      block.append(input);
      form.append(block);
      return input;
    };
    const oldTime = numeric('old_minutes', '旧方法实用分钟', {min: '0.1', step: '0.1'});
    const newTime = numeric('frontier_minutes', '本次 FRONTIER 实用分钟', {min: '0.1', step: '0.1'});
    // Optional ephemeral side-by-side wall-clock timers. The owner starts,
    // pauses and explicitly copies a reading into either editable field.
    // Timers are neither evidence of task equivalence nor verified savings.
    // They never write localStorage or call the backend.
    const timerBox = el('fieldset', 'frontier-daily-owner-timers');
    timerBox.append(el('legend', '', '可选：分别手动计时，填入本次研究分钟'));
    timerBox.append(el('p', 'frontier-daily-owner-timer-note',
      '页面计时含你主动打开原文的时间；离开研究请手动暂停。' +
      '只有你点击「填入」才改上方数字，仍可手工更正。关闭页面/退出登录会丢失未填入的计时；不是独立核实的省时证据。'));
    const watches = [
      {kind:'old',label:'旧方法',input:oldTime,elapsed:0,started:null},
      {kind:'frontier',label:'FRONTIER',input:newTime,elapsed:0,started:null},
    ];
    let tickHandle = null;
    const milliseconds = state => state.elapsed +
      (state.started === null ? 0 : Math.max(0, Date.now() - state.started));
    const displayMinutes = elapsed => (elapsed / 60000).toFixed(1);
    const timerMessage = el('p', 'frontier-daily-owner-timer-state',
      '计时只在本页内存中进行；没有自动写入任何研究分钟。');
    timerMessage.setAttribute('role', 'status');
    function renderWatches() {
      if (!timerBox.isConnected && tickHandle !== null) {
        clock.clearInterval(tickHandle);
        tickHandle = null;
        return; // No background interval after logout, feed removal or tab teardown.
      }
      for (const state of watches) {
        const duration = milliseconds(state);
        state.display.textContent = displayMinutes(duration) + ' 分（' +
          (state.started === null ? '已暂停' : '计时中') + '）';
        state.start.disabled = state.started !== null;
        state.pause.disabled = state.started === null;
        state.fill.disabled = state.started !== null || duration < 6000 || duration > 86400000;
        state.reset.disabled = state.started !== null || duration <= 0;
      }
    }
    function armTick() {
      if (tickHandle === null) {
        tickHandle = clock.setInterval(() => renderWatches(), 500);
      }
    }
    function disarmTick() {
      if (watches.every(state => state.started === null) && tickHandle !== null) {
        clock.clearInterval(tickHandle);
        tickHandle = null;
      }
    }
    function clearWatches() {
      for (const state of watches) {
        state.elapsed = 0;
        state.started = null;
      }
      disarmTick();
      renderWatches();
    }
    for (const state of watches) {
      const row = el('div', 'frontier-daily-owner-timer-row');
      row.dataset.timerKind = state.kind;
      row.append(el('strong', '', state.label));
      state.display = el('output', 'frontier-daily-owner-timer-clock');
      state.display.setAttribute('aria-live','off');
      state.start = smallButton('开始', 'frontier-daily-owner-timer-start', () => {
        if (watches.some(other => other !== state && other.started !== null)) {
          timerMessage.textContent = '另一种方法仍在计时。请先手动暂停，避免两次研究时间重叠。';
          return;
        }
        if (state.started !== null) return;
        state.started = Date.now();
        armTick();
        renderWatches();
        timerMessage.textContent = '正在计时 ' + state.label +
          '；打开第三方原文仍计时，离开研究请自行暂停。';
      });
      state.pause = smallButton('暂停', 'frontier-daily-owner-timer-pause', () => {
        if (state.started === null) return;
        state.elapsed += Math.max(0, Date.now() - state.started);
        state.started = null;
        disarmTick();
        renderWatches();
        timerMessage.textContent = state.label + ' 计时已暂停。' +
          '你可以继续计时、填入或手工输入另一组可比时间。';
      });
      state.fill = smallButton('填入上方', 'frontier-daily-owner-timer-fill', () => {
        if (state.started !== null) return;
        const value = Number(displayMinutes(state.elapsed));
        if (!Number.isFinite(value) || value < 0.1 || value > 1440) {
          timerMessage.textContent = '本次计时不足6秒或超过24小时，未改写手填数字。';
          return;
        }
        state.input.value = value.toFixed(1);
        state.input.dispatchEvent(new win.Event('input', {bubbles:true}));
        timerMessage.textContent = '已将 ' + state.label + ' 本页计时 ' +
          value.toFixed(1) + ' 分填入表单，尚未保存。可以手动修正。';
        renderWatches();
      });
      state.reset = smallButton('计时归零', 'frontier-daily-owner-timer-reset', () => {
        if (state.started !== null) return;
        state.elapsed = 0;
        renderWatches();
        timerMessage.textContent = state.label +
          ' 的未填入计时已归零，上方手填数字没有修改。';
      });
      row.append(state.display,state.start,state.pause,state.fill,state.reset);
      timerBox.append(row);
    }
    timerBox.append(timerMessage);
    form.append(timerBox);
    renderWatches();
    // Instant, local-only, non-persistent feedback. Never infer verified savings.
    const instant = el('output', 'frontier-daily-owner-pilot-instant');
    instant.setAttribute('aria-live', 'polite');
    instant.textContent = '先填两次真实用时，即时查看本次本人自报差额；不会发送或自动保存。';
    form.append(instant);
    function updateInstant() {
      const a = Number(oldTime.value), b = Number(newTime.value);
      if (!oldTime.value.trim() || !newTime.value.trim() || !Number.isFinite(a) ||
          !Number.isFinite(b) || a < 0.1 || b < 0.1 || a > 1440 || b > 1440) {
        instant.dataset.trend = 'missing';
        instant.textContent = '先填两次真实用时，即时查看本次本人自报差额；不会发送或自动保存。';
        return;
      }
      const diff = a - b;
      const magnitude = Math.abs(diff).toFixed(1);
      instant.dataset.trend = diff > 0 ? 'saved' : diff < 0 ? 'slower' : 'same';
      instant.textContent = '本次由本人确认的记录：旧 ' + a.toFixed(1) + ' 分 → FRONTIER ' + b.toFixed(1) +
        ' 分；' + (diff > 0 ? '少用 ' + magnitude + ' 分（' +
        ((diff/a)*100).toFixed(1) + '%）' : diff < 0 ? '多用 ' + magnitude +
        ' 分' : '用时持平') + '。仅本人确认的手填/本页计时，未经独立验证，不代表收入。';
    }
    oldTime.addEventListener('input', updateInstant);
    newTime.addEventListener('input', updateInstant);
    const reviewed = numeric('reviewed_items', '本次本人明确评了几条', {value:'0'});
    const noise = numeric('noise_items', '其中亲自判断「没帮助」几条', {value:'0'});
    const acts = numeric('explicit_page_actions', '本人明确点击/激活步骤数', {value:'0'});
    const flags = [
      ['owner_confirmed_comparable_task', '我确认新旧两次是同一个可比的真实研究任务'],
      ['owner_confirmed_no_prompt', '本次无需他人提示才完成'],
      ['owner_confirmed_original_opened', '我亲自实际打开并查看了真实第三方原文'],
      ['owner_confirmed_decision_saved', '我亲自保存决定，且看到服务端明确回执'],
      ['key_miss', '本次发现了关键遗漏（勾选表示确有问题）'],
      ['claimed_independence_without_check', '发现页面把转载当独立来源证明（有问题才勾）'],
      ['fabricated_occurrence_time', '发现页面把猜测时间当已发生（有问题才勾）'],
    ];
    const checks = new Map();
    const flagsBox = el('div', 'frontier-daily-owner-pilot-flags');
    for (const [name, label] of flags) {
      const wrap = el('label', 'frontier-daily-owner-pilot-check');
      const input = el('input');
      input.type = 'checkbox';
      input.name = name;
      checks.set(name,input);
      wrap.append(input,el('span', '', label));
      flagsBox.append(wrap);
    }
    form.append(flagsBox);
    const acknowledge = el('label', 'frontier-daily-owner-pilot-check frontier-daily-owner-pilot-confirm');
    const acknowledged = el('input');
    acknowledged.type = 'checkbox';
    acknowledged.required = true;
    acknowledge.append(acknowledged, el('span', '',
      '以上数字与勾选由本人真实确认（分钟可由本页计时主动填入）；我理解未勾选不等于已独立证实「无问题」。'));
    form.append(acknowledge);
    const controls = el('div', 'frontier-daily-owner-pilot-controls');
    const save = el('button', 'frontier-daily-owner-pilot-save', '明确保存到本浏览器');
    save.type = 'submit';
    // Daily manual evidence is deliberately erased from localStorage on logout.
    // Make the existing *optional* backup discoverable only after a real local
    // save, without opening it or sending any cloud request automatically.
    const backupShortcut = smallButton('我已保存本地 → 自己选择备份云端',
      'frontier-daily-owner-pilot-backup-shortcut', () => {
        cloud.open = true;
        status.dataset.state = 'saved';
        status.textContent = '已展开可选云端备份。仍需你本人明确点击备份并确认；未自动上传。';
        cloud.querySelector('summary')?.focus?.({ preventScroll:true });
      });
    // Rehydrate visibility after a same-day local save plus ordinary page reload.
    // Previous-day-only local records cannot be backdated into a cloud backup.
    const refreshBackupShortcut = () => {
      backupShortcut.hidden = !load().sessions.some(session => session.day === ownerPilotDay());
    };
    refreshBackupShortcut();
    const download = smallButton('下载完整私有JSON', 'frontier-daily-owner-pilot-export', () => {
      try {
        const existing = load();
        if (!existing.sessions.length) {
          status.dataset.state='error';
          status.textContent='没有任何已保存的本人记录，不能导出虚构结果。';
          return;
        }
        const encoded = JSON.stringify(existing, null, 2) + '\n';
        const blob = new Blob([encoded], {type:'application/json'});
        const href = win.URL.createObjectURL(blob);
        const a = el('a');
        a.href = href;
        a.download = 'frontier-owner-pilot-manual-' + ownerPilotDay() + '.json';
        body.append(a);
        a.click();
        a.remove();
        clock.setTimeout(()=>win.URL.revokeObjectURL(href), 3000);
        status.dataset.state='saved';
        status.textContent='已请求浏览器下载本人自报JSON；请自行确认下载完成。该文件不含原文或关键词。';
      } catch(error) {
        status.dataset.state='error';
        status.textContent='未确认导出：' + (txt(error?.message,160) || '下载不可用');
      }
    });
    const clear = smallButton('清空本浏览器手填记录', 'frontier-daily-owner-pilot-clear', () => {
      if (!win.confirm?.('真的清空本浏览器的全部本人自报试验记录吗？先下载JSON备份。')) return;
      try {
        const existing = load();
        win.localStorage.removeItem(OWNER_PILOT_LOCAL_KEY);
        if (win.localStorage.getItem(OWNER_PILOT_LOCAL_KEY) !== null) {
          throw new Error('浏览器未确认删除');
        }
        readback();
        refreshBackupShortcut();
        status.dataset.state='saved';
        status.textContent='已清空本浏览器 ' + existing.sessions.length +
          ' 条人工记录；云端Radar数据完全未修改。';
      } catch(error) {
        status.dataset.state='error';
        status.textContent='未确认清空：' + (txt(error?.message, 130) || '操作失败');
      }
    });
    const importWrap = el('label', 'frontier-daily-owner-pilot-import');
    importWrap.append(el('span', '', '手动恢复本人曾下载的私有JSON（未选择文件绝不导入）'));
    const file = el('input');
    file.type = 'file';
    file.accept = '.json,application/json';
    file.setAttribute('aria-label','选择本人明确保存的匿名试验JSON文件');
    importWrap.append(file);
    const importBtn = smallButton('确认导入此本地备份', 'frontier-daily-owner-pilot-import-confirm', async () => {
      status.dataset.state = 'saving';
      status.textContent = '正在验证所选择的私有文件，不会上传云端…';
      try {
        const chosen = file.files?.[0];
        if (!chosen || chosen.size < 1 || chosen.size > 350000 ||
            !chosen.name.toLowerCase().endsWith('.json')) {
          throw new Error('请选择1个小于350KB的本人私有JSON文件。');
        }
        const imported = parseOwnerPilotJSON(await chosen.text());
        const previous = load();
        if (previous.sessions.length && !win.confirm?.(
              '导入将覆盖本浏览器现有的' + previous.sessions.length + '条私人试验记录。请先下载备份，确定覆盖？')) {
          status.dataset.state = 'error';
          status.textContent = '本人没有确认覆盖，原有本地记录保持不变。';
          return;
        }
        // The person selected a local file and explicitly clicked import.
        // Never POST its bytes to the server or infer a real human session.
        const raw = JSON.stringify(imported);
        win.localStorage.setItem(OWNER_PILOT_LOCAL_KEY, raw);
        if (win.localStorage.getItem(OWNER_PILOT_LOCAL_KEY) !== raw) {
          throw new Error('浏览器未回读相同的本地备份。');
        }
        readback();
        refreshBackupShortcut();
        file.value = '';
        status.dataset.state = 'saved';
        status.textContent = '✓ 本人选定的私有备份已在当前浏览器回读确认；未同步服务器，真人真伪仍待核。';
      } catch(error) {
        status.dataset.state = 'error';
        status.textContent = '没有确认导入：' + (txt(error?.message,180) || '本地文件无效或存储失败');
      }
    });
    importWrap.append(importBtn);
    controls.append(save,backupShortcut,download,clear);
    form.append(importWrap);
    form.append(controls);
    form.addEventListener('submit', event => {
      event.preventDefault();
      status.dataset.state='saving';
      status.textContent='正在验证本次本人手填数据…';
      try {
        if (!acknowledged.checked) throw new Error('须明确确认数据来自本人真实手填。');
        if (typeof win.crypto?.randomUUID !== 'function') {
          throw new Error('浏览器不支持生成匿名记录ID，本次未保存。');
        }
        if (watches.some(state => state.started !== null)) {
          throw new Error('请先暂停本页计时，再核对并保存两次可比研究分钟。');
        }
        const previous = load();
        const day = ownerPilotDay();
        const values = {
          old_minutes:oldTime.value, frontier_minutes:newTime.value,
          reviewed_items:reviewed.value, noise_items:noise.value,
          explicit_page_actions:acts.value,
        };
        for (const [name,input] of checks) values[name]=input.checked;
        const entry=makeOwnerPilotSession(values,{
          day, sessionRef:'manual-'+win.crypto.randomUUID(),
        });
        const next=appendOwnerPilotSession(previous,entry,day);
        const raw=JSON.stringify(next);
        win.localStorage.setItem(OWNER_PILOT_LOCAL_KEY,raw);
        const confirmed=win.localStorage.getItem(OWNER_PILOT_LOCAL_KEY);
        if (confirmed!==raw || parseOwnerPilotJSON(confirmed).sessions.length!==next.sessions.length) {
          throw new Error('浏览器未返回一致的本地保存回执。');
        }
        readback();
        form.reset();
        clearWatches();
        updateInstant();
        reviewed.value = '0';
        noise.value = '0';
        acts.value = '0';
        status.dataset.state='saved';
        refreshBackupShortcut();
        status.textContent='✓ 本浏览器已保存手工记录，尚未备份云端；退出登录将清除本地数字。可自己选择备份云端或下载私有JSON；不代表已证实省时或真实收入。';
      } catch(error) {
        status.dataset.state='error';
        status.textContent='未确认保存：' + (txt(error?.message,180) || '数据不合规') + '。请修改后再明确点击。';
      }
    });
    // V144: completely optional manual, owner-scoped backup. Merely
    // rendering this closed details panel makes ZERO cloud requests. Existing
    // local-only saving, JSON file import/export and logout erase are intact.
    // The backend may not yet be available on the officially deployed V132.
    const cloud = el('details', 'frontier-daily-owner-cloud');
    cloud.dataset.ownerCloud = 'true';
    cloud.append(el('summary', '', '可选：本人主动备份至云端，跨日恢复（不会自动同步）'));
    const cloudBody=el('div', 'frontier-daily-owner-cloud-body');
    cloudBody.append(el('p', 'frontier-daily-owner-cloud-caveat',
      '默认只保存在本浏览器。只有你点击并确认「备份」才将北京时间今天尚未提交的本人匿名数字、日期与风险勾选追加到云端SQLite（服务器保存数字不加密）；旧日未提交记录不能事后冒充当天补传，请保留私人JSON。没有账号令牌、关注词、原文或URL。云端备份在退出后保留，当前浏览器本地副本仍立即清除。恢复、清除各需本人点击确认；不证明数字或新闻真伪，也不是支付系统。'));
    const cloudButtons=el('div','frontier-daily-owner-cloud-controls');
    const cloudStatus=el('p','frontier-daily-owner-cloud-state');
    cloudStatus.setAttribute('role','status');
    const scope=generation;
    let busy=false;
    const cloudFetch=async() => {
      const response=await request(OWNER_PILOT_CLOUD_PATH,{
        method:'GET',credentials:'same-origin',cache:'no-store',
        headers:{Accept:'application/json'},
      });
      if(!response.ok) throw new Error(await serverError(response));
      const result=assertOwnerPilotCloudPayload(await response.json(),ownerPilotDay());
      if(!isCurrent(scope)) throw new Error('登录态已经发生变化；不导入跨登录备份。');
      return result;
    };
    const cloudWrite=async(method,path,payload) => {
      const me=await request('/api/auth/me',{
        method:'GET',credentials:'same-origin',cache:'no-store',
        headers:{Accept:'application/json'},
      });
      if(!me.ok) throw new Error(await serverError(me));
      const auth=await me.json();
      if(!isCurrent(scope) || auth?.authenticated!==true ||
         typeof auth.csrf_token!=='string' || !auth.csrf_token) {
        throw new Error('登录态或CSRF已变更，不提交任何新的云端写入。');
      }
      const response=await request(path,{
        method,credentials:'same-origin',cache:'no-store',
        headers:{Accept:'application/json','Content-Type':'application/json',
          'X-CSRF-Token':auth.csrf_token},
        body:JSON.stringify(payload),
      });
      if(!response.ok) throw new Error(await serverError(response));
      const result=await response.json();
      if(!isCurrent(scope)) throw new Error('登录状态已变更，不认可云端回执。');
      return result;
    };
    const cloudAction=action=>async()=>{
      if(busy || !isAuthenticatedDOM()) return;
      busy=true;
      for(const b of cloudButtons.querySelectorAll('button')) b.disabled=true;
      cloudStatus.dataset.state='saving';
      cloudStatus.textContent='正在处理你明确发起的云端操作；不自动计时或判断原文…';
      try {
        const message=await action();
        if(!isCurrent(scope)) return;
        cloudStatus.dataset.state='saved';
        cloudStatus.textContent=message;
      } catch(error) {
        if(!isCurrent(scope)) return;
        cloudStatus.dataset.state='error';
        cloudStatus.textContent='云端操作未确认：'+(txt(error?.message,180)||'服务不可用')+
          '。云端可能已部分追加；本浏览器本地记录不变，可本人再次读取核实。';
      } finally {
        busy=false;
        for(const b of cloudButtons.querySelectorAll('button')) b.disabled=false;
      }
    };
    const backup=smallButton('我确认：只将今天未备份的本人记录提交云端',
      'frontier-daily-owner-cloud-save',()=>{});
    const restore=smallButton('本人主动从云端恢复到当前浏览器',
      'frontier-daily-owner-cloud-restore',()=>{});
    const discard=smallButton('确认清空本人云端匿名记录',
      'frontier-daily-owner-cloud-delete',()=>{});
    backup.addEventListener('click',cloudAction(async()=>{
      const current=load(); // reject corrupted local state without auto repair
      if(!current.sessions.length) {
        throw new Error('本浏览器没有任何你明确保存的手填记录，不能凭空上传。');
      }
      const today=ownerPilotDay();
      const todayItems=current.sessions.filter(s=>s.day===today);
      if(!todayItems.length) {
        return '今天没有本浏览器已保存的手填记录，不能用过往日期补作新的真实观察。';
      }
      if(!win.confirm?.(
         '仅把北京时间今天尚未提交的真实本人手填匿名时间和风险数字追加到私人云端SQLite（未加密存储）。不自动同步或核验原文，确认提交？')) {
        return '本人取消云端备份；没有发送数字。';
      }
      const before=await cloudFetch();
      const existing=new Map(before.sessions.map(s=>[s.session_ref,s]));
      for(const s of todayItems) {
        const old=existing.get(s.session_ref);
        if(old && !sameOwnerPilotSessionContent(old,s)) {
          throw new Error('云端已有相同匿名编号但内容不同，拒绝静默覆盖；请人工核对JSON。');
        }
      }
      const missing=todayItems.filter(s=>!existing.has(s.session_ref));
      const pastUnbacked=current.sessions.filter(s=>
        s.day<today && !existing.has(s.session_ref)).length;
      if(!missing.length) {
        return '云端已有今天本浏览器的全部 '+todayItems.length+
          ' 条匿名记录，无重复上传。'+
          (pastUnbacked?'另有 '+pastUnbacked+' 条旧日仅存本地，请下载私有JSON。':'');
      }
      for(const entry of missing) {
        if(!isCurrent(scope)) throw new Error('登录态改变，停止后续数据提交。');
        const saved=await cloudWrite('POST',OWNER_PILOT_CLOUD_SESSION_PATH,{
          session:entry,owner_consent:true,manual_confirmation:true,
        });
        if(saved?.saved!==true || saved.session_ref!==entry.session_ref ||
           saved.day!==entry.day || saved.independently_verified!==false) {
          throw new Error('云端单条保存回执与本人记录不一致。');
        }
      }
      const after=await cloudFetch(); // actual GET, not merely trust POST 200
      const delivered=new Map(after.sessions.map(s=>[s.session_ref,s]));
      if(!missing.every(s=>delivered.has(s.session_ref) &&
          sameOwnerPilotSessionContent(delivered.get(s.session_ref),s))) {
        throw new Error('备份后真实云端回读不一致，不能宣称保存成功。');
      }
      return '✓ 已人工提交 '+missing.length+' 条今天的新记录；实际回读云端共 '+
        after.sessions.length+' 条本人匿名自报。不代表独立真实性或收入。'+
        (pastUnbacked?'还有 '+pastUnbacked+' 条旧日未提交记录，只能保留本地私人JSON。':'');
    }));
    restore.addEventListener('click',cloudAction(async()=>{
      const current=load();
      const remote=await cloudFetch();
      if(!remote.sessions.length) return '云端没有你的人工匿名记录，未改变本浏览器。';
      if(!win.confirm?.(
         '将本人云端 '+remote.sessions.length+' 条匿名手填数字复制到当前浏览器。'+
         (current.sessions.length?'会覆盖本地现有 '+current.sessions.length+
          ' 条，请先下载JSON备份。':'')+' 你确定恢复？')) {
        return '本人取消恢复；当前浏览器数据未变。';
      }
      if(!isCurrent(scope)) throw new Error('登录状态已变化，取消本地恢复。');
      const raw=JSON.stringify(remote);
      win.localStorage.setItem(OWNER_PILOT_LOCAL_KEY,raw);
      if(win.localStorage.getItem(OWNER_PILOT_LOCAL_KEY)!==raw ||
         !sameOwnerPilotContent(load(),remote)) {
        throw new Error('浏览器没有回读相同的私人云端数据。');
      }
      readback();
      refreshBackupShortcut();
      return '✓ 本人确认的云端 '+remote.sessions.length+
        ' 条数字已经实际恢复并回读到当前浏览器；云端未自动写入。';
    }));
    discard.addEventListener('click',cloudAction(async()=>{
      const before=await cloudFetch();
      if(!before.sessions.length) return '云端原本没有你的匿名记录，未执行删除。';
      if(!win.confirm?.('永久清空云端 '+before.sessions.length+
         ' 条本人匿名时间数据？此操作不删除当前浏览器本地记录，建议先导出JSON。')) {
        return '本人取消清除，云端数据未改变。';
      }
      if(!isCurrent(scope)) throw new Error('登录态变化，停止发送删除。');
      const deleted=await cloudWrite('DELETE',OWNER_PILOT_CLOUD_PATH,{confirm_delete:true});
      if(deleted?.deleted!==true || deleted.deleted_sessions!==before.sessions.length) {
        throw new Error('云端删除回执数量不一致；须再次人工核实。');
      }
      const verify=await cloudFetch();
      if(verify.sessions.length) throw new Error('删除后云端仍有记录。');
      return '✓ 本人云端备份已删除，并重新读取确认0条；当前浏览器本地记录未动。';
    }));
    cloudButtons.append(backup,restore,discard);
    cloudBody.append(cloudButtons,cloudStatus);
    cloud.append(cloudBody);
    body.append(form,cloud,status);
  }

  function renderData(snapshot) {
    const state = displayDailyState(snapshot);
    if (state === 'first-run') {
      remove(); // Existing verified first-run CTA remains the sole 0-topic prompt.
      return;
    }
    const root = panel();
    if (!root) return;
    // Keep the owner's unsaved form during 60s read-only server refresh.
    const previousPilot = root.querySelector('[data-owner-pilot="true"]');
    root.replaceChildren();
    const count = snapshot.today_top3.length;
    hero(root, state, state === 'actionable' ?
      `来自你保存的 ${snapshot.topics.length} 个主题，优先显示 ${count} 条待人工核对的候选；不是今日全球新闻榜，也不保证事件发生在今天。` :
      `已读取你保存的 ${snapshot.topics.length} 个主题，当前没有能作为新决定的安全原文候选。以下显示真正的服务器状态与处理盲区。`);
    if (state === 'actionable') {
      const grid = el('ol', 'frontier-daily-cards');
      grid.setAttribute('aria-label', '最多三条有原文证据的个人行动候选');
      snapshot.today_top3.forEach((item, index) => grid.append(renderCard(item, index)));
      root.append(grid);
      const summary = topicStateRows(snapshot);
      if (summary.some(x => x.code !== 'ready')) {
        const extra = el('details', 'frontier-daily-other-topics');
        extra.append(el('summary', '', '其余主题的处理/无匹配状态'));
        const info = el('div', 'frontier-daily-other-list');
        summary.filter(x => x.code !== 'ready').forEach(x =>
          info.append(el('p', '', `${txt(x.name, 70)} · ${x.label}：${txt(x.explanation, 260)}`)));
        extra.append(info);
        root.append(extra);
      }
    } else {
      renderProcessing(root, snapshot);
    }
    const pipe = snapshot.pipeline;
    if (pipe && typeof pipe === 'object') {
      const meta = el('details', 'frontier-daily-pipeline');
      const current = pipe.enrichment || {};
      const counts = [
        validCount(current.pending) === null ? '' : `待处理 ${current.pending}`,
        validCount(current.processing) === null ? '' : `处理中 ${current.processing}`,
        validCount(current.failed) === null ? '' : `失败 ${current.failed}`,
        validCount(current.awaiting_video) === null ? '' : `视频尚未整理记录 ${current.awaiting_video}`,
      ].filter(Boolean);
      meta.append(el('summary', '', '采集与整理状态（独立观察）  /  ' +
        (counts.join(' · ') || '无可核验计数')));
      const p = el('div', 'frontier-daily-pipeline-content');
      p.append(el('p', '', '整理进程：' + txt(current.state, 50) +
        '；状态记录：' + clockText(current.updated_at) + '。未见心跳不等于已证明采集停止。'));
      const sources = Array.isArray(pipe.sources) ? pipe.sources : [];
      for (const s of sources) {
        p.append(el('p', '', `${txt(s.platform, 45)}：${txt(s.state, 35) || '未知'}` +
          (s.error ? ` · ${txt(s.error, 110)}` : '')));
      }
      p.append(el('p', '', '视频尚未整理是派生库累计记录状态，不等于仍在运行或仍符合48小时原视频发布时间处理窗口的任务；超期历史原文可能保留未整理标签。')); 
      if (pipe.scope) p.append(el('p', '', txt(pipe.scope, 500)));
      meta.append(p);
      root.append(meta);
    }
    if (previousPilot) root.append(previousPilot);
    else renderOwnerPilot(root);
    placeWarning(root, '范围说明：只展示已登录用户保存的主题匹配，最多 3 条；服务端按规则排序，不是事实真实性概率。时间为不同钟，不将「入库/发布」冒充「发生」。全站 global_signals 不参与这里的个人三件事。');
    if (errorText) placeWarning(root, errorText, true);
  }
  function renderFailure() {
    if (!isAuthenticatedDOM()) return remove();
    if (data) {
      renderData(data);
      const root = panel();
      if (root && root.isConnected) placeWarning(root, '上次可信快照仍显示，但最新读取失败；请勿将此状态当作实时结果。', true);
      return;
    }
    const root = panel();
    if (!root) return;
    root.replaceChildren();
    hero(root, 'unavailable', '服务端个人候选尚未核验，不能假定主题数或今日事件数。');
    placeWarning(root, errorText || '读取每日雷达失败，请重新同步。', true);
  }
  async function refreshData() {
    if (destroyed || !isAuthenticatedDOM()) return;
    const scope = generation;
    loadController?.abort();
    const controller = new AbortController();
    loadController = controller;
    const timeout = clock.setTimeout(() => controller.abort(), 12000);
    const promise = (async () => {
      try {
        const response = await request('/api/radar/daily', {
          method: 'GET', credentials: 'same-origin', cache: 'no-store',
          headers: { Accept: 'application/json' }, signal: controller.signal,
        });
        if (!isCurrent(scope) || controller.signal.aborted) return;
        if (response.status === 401) {
          data = null;
          errorText = '';
          remove();
          return;
        }
        if (!response.ok) throw new Error(await serverError(response));
        const verified = assertDailyResponse(await response.json());
        if (!isCurrent(scope) || controller.signal.aborted) return;
        data = verified;
        errorText = '';
        renderData(data);
      } catch (error) {
        if (!isCurrent(scope) || controller.signal.aborted) return;
        errorText = txt(error?.message, 200) || '读取失败，请重新同步。';
        renderFailure();
      } finally {
        clock.clearTimeout(timeout);
      }
    })();
    return promise;
  }
  function scheduleRefresh(ms = 300) {
    clock.clearTimeout(refreshTimer);
    if (!destroyed) refreshTimer = clock.setTimeout(refreshData, ms);
  }
  function domChange() {
    const nowNav = $('#nav-radar');
    if (navNode !== nowNav) {
      navNode = nowNav;
      generation += 1;
      loadController?.abort();
      data = null;
      errorText = '';
      remove();
      if (nowNav) scheduleRefresh(90);
    } else {
      const root = doc.getElementById(DAILY_PANEL_ID);
      if (root) {
        // Native single-page navigation may replace the content tree.
        if (root.parentNode !== $('.main-shell')) panel();
        root.hidden = !isVisibleView();
      }
    }
  }
  function clickHandler(event) {
    if (event.target?.closest?.('#logout, #mobile-logout')) {
      // V142: both real desktop and mobile logout must revoke access to the
      // unencrypted browser-local manual trial, not just hide its DOM. Users
      // can only recover via an explicit backup file, never server inference.
      try {
        win.localStorage.removeItem(OWNER_PILOT_LOCAL_KEY);
      } catch {
        // Browser may prohibit storage; do not claim a successful wipe.
      }
      generation++;
      loadController?.abort();
      data = null;
      remove();
    }
    if (event.target?.closest?.('#radar-form-submit, #radar-topic-confirm, #radar-topic-delete')) {
      scheduleRefresh(1800); // Only server read may establish new saved-topic state.
    }
    if (event.target?.closest?.('#nav-feed, #nav-radar')) {
      clock.setTimeout(domChange, 0);
    }
  }

  const observer = new win.MutationObserver(domChange);
  observer.observe($('#app') || doc.body, { childList: true, subtree: true, attributes: true,
    attributeFilter: ['aria-current'] });
  doc.addEventListener('click', clickHandler, true);
  doc.addEventListener('visibilitychange', () => {
    if (!doc.hidden && isAuthenticatedDOM()) scheduleRefresh(120);
  });
  domChange();
  refreshInterval = clock.setInterval(() => {
    if (isAuthenticatedDOM() && !doc.hidden) refreshData();
  }, 60000);

  return {
    refresh: refreshData,
    getLastDaily: () => data,
    destroy() {
      destroyed = true;
      generation++;
      loadController?.abort();
      clock.clearTimeout(refreshTimer);
      clock.clearInterval(refreshInterval);
      observer.disconnect();
      doc.removeEventListener('click', clickHandler, true);
      remove();
    },
  };
}

if (typeof document !== 'undefined' && typeof window !== 'undefined') {
  createDailyPanel();
}

})();
/* FRONTIER_ADDON_END:daily-top3 */

/* FRONTIER_ADDON_BEGIN:pro-compare */
;(() => {
"use strict";
/**
 * Server-contract guards for frozen dossier revision comparisons.
 * Never infer causality, source independence, URL reachability or missing dates.
 * No write method, no local storage, no network code.
 */

const FIELD_ORDER = Object.freeze([
  ["judgment", "我的判断"],
  ["falsification", "反证条件"],
  ["support", "支持或疑问"],
  ["next_step", "下一步"],
  ["review_on", "复查日"],
]);

const SOURCE_PROPS = Object.freeze({
  sha256: "原文 SHA-256",
  platform: "平台",
  source_id: "订阅标识",
  name: "出处名称",
  url: "出处链接",
  title: "原文标题（正文未随比较接口返回）",
  published_at: "出处发布时间",
  first_ingested_at: "首次收录时间",
});

const TIME_STATUSES = Object.freeze({
  explicit: "原文明确提及（仍需核对）",
  inferred: "按上下文推定（尚未核实）",
  scheduled: "计划发生（不表示已发生）",
  unknown: "未知 · 缺少足够依据",
});

const object = v => v !== null && typeof v === "object" && !Array.isArray(v);
const positiveVersion = v => Number.isSafeInteger(v) && v > 0;
const nonnegative = v => Number.isSafeInteger(v) && v >= 0;
const fail = () => { throw new Error("服务器返回的研判历史／比较结构不符合当前接口约定；为避免错比已停止展示。"); };

function readHistory(json, eventId) {
  if (!object(json) || json.event_id !== eventId || !Array.isArray(json.history)) fail();
  const versions = new Set();
  const history = json.history.map(v => {
    if (!object(v) || !positiveVersion(v.version) || versions.has(v.version)) fail();
    if (v.created_at != null && typeof v.created_at !== "string") fail();
    versions.add(v.version);
    return { version: v.version, saved_at: v.created_at || null };
  });
  return history.sort((a, b) => b.version - a.version);
}

function recentPair(history) {
  return history.length >= 2
    ? { from: history[1].version, to: history[0].version }
    : null;
}

function validPair(history, from, to) {
  return positiveVersion(from) && positiveVersion(to) && from < to
    && history.some(v => v.version === from) && history.some(v => v.version === to);
}

/** Link validation is local only; never contacts a remote host or verifies availability. */

function safeSourceUrl(source) {
  if (!object(source) || source.link_status !== "not_checked") return null;
  const raw = source.url;
  if (typeof raw !== "string" || raw.length > 4096 ||
      !/^https?:\/\//i.test(raw) || /[\u0000-\u0020\u007f\\]/.test(raw)) return null;
  try {
    const url = new URL(raw);
    if (!["https:", "http:"].includes(url.protocol) || !url.hostname ||
        url.username || url.password || url.host.includes("@") || url.hash) return null;
    const h = url.hostname.toLowerCase().replace(/\.$/, "");
    if (h.includes(":") || h === "localhost" || h.endsWith(".localhost") ||
        h.endsWith(".local") || h.endsWith(".internal") || h.endsWith(".lan") ||
        h.endsWith(".home") || h === "home.arpa" || h.endsWith(".home.arpa") ||
        ["nip.io", "sslip.io", "lvh.me", "localtest.me"].some(x => h === x || h.endsWith("." + x))) return null;
    if (/^\d+(?:\.\d+){3}$/.test(h)) {
      const n = h.split(".").map(Number);
      if (n[0] === 0 || n[0] === 10 || n[0] === 127 || n[0] >= 224 ||
          (n[0] === 169 && n[1] === 254) || (n[0] === 192 && n[1] === 168) ||
          (n[0] === 172 && n[1] >= 16 && n[1] <= 31) ||
          (n[0] === 100 && n[1] >= 64 && n[1] <= 127) ||
          (n[0] === 192 && n[1] === 0) ||
          (n[0] === 198 && [18, 19].includes(n[1]))) return null;
    }
    // Fail closed for credential-bearing URLs. Does not imply other URLs are safe to redistribute.
    const secret = /^(?:token|auth|key|apikey|sig|signature|password|secret|session|sessionid|accesstoken|clientsecret|authorization|credential|ticket|code|jwt)$/i;
    if ([...url.searchParams.keys()].some(k => secret.test(k.replace(/[-_]/g, "")))) return null;
    return url.href;
  } catch {
    return null;
  }
}

function checkSource(source) {
  if (!object(source) || typeof source.record_id !== "string" || !source.record_id ||
      !["not_checked", "unavailable"].includes(source.link_status) ||
      (source.sha256 != null && (typeof source.sha256 !== "string" ||
        !/^[a-fA-F0-9]{64}$/.test(source.sha256)))) fail();
}

function readComparison(json, eventId, from, to) {
  if (!object(json) || json.event_id !== eventId ||
      json.from_version !== from || json.to_version !== to ||
      typeof json.from_saved_at !== "string" || typeof json.to_saved_at !== "string" ||
      !Array.isArray(json.field_changes) || !Array.isArray(json.changed_field_keys) ||
      !object(json.source_changes) || !object(json.event_occurrence)) fail();

  const fields = new Map();
  for (const v of json.field_changes) {
    if (!object(v) || !FIELD_ORDER.some(([key]) => key === v.key) || fields.has(v.key) ||
        typeof v.before !== "string" || typeof v.after !== "string" ||
        typeof v.changed !== "boolean" || v.changed !== (v.before !== v.after)) fail();
    fields.set(v.key, v);
  }
  if (fields.size !== FIELD_ORDER.length) fail();
  const changedKeys = FIELD_ORDER.filter(([key]) => fields.get(key).changed).map(([key]) => key);
  if (json.changed_field_keys.length !== changedKeys.length ||
      !json.changed_field_keys.every(key => changedKeys.includes(key))) fail();
  const sources = json.source_changes;
  if (!nonnegative(sources.from_count) || !nonnegative(sources.to_count) ||
      !nonnegative(sources.unchanged_count) ||
      sources.independence_status !== "unknown" ||
      !Array.isArray(sources.added) || !Array.isArray(sources.removed) ||
      !Array.isArray(sources.updated)) fail();
  sources.added.forEach(checkSource);
  sources.removed.forEach(checkSource);
  sources.updated.forEach(u => {
    if (!object(u) || typeof u.record_id !== "string" ||
        !Array.isArray(u.changed_properties) ||
        !u.changed_properties.every(k => Object.hasOwn(SOURCE_PROPS, k)) ||
        !object(u.before) || !object(u.after) ||
        u.before.record_id !== u.record_id || u.after.record_id !== u.record_id) fail();
    checkSource(u.before);
    checkSource(u.after);
  });
  const occurrence = json.event_occurrence;
  if (!object(occurrence.before) || !object(occurrence.after) ||
      typeof occurrence.changed !== "boolean") fail();
  return { ...json, fields, changedKeys };
}

function readable(value, fallback = "未知／未提供") {
  return typeof value === "string" && value.trim() ? value : fallback;
}

function occurredStatus(raw) {
  return typeof raw === "string" && Object.hasOwn(TIME_STATUSES, raw)
    ? TIME_STATUSES[raw] : TIME_STATUSES.unknown;
}

/**
 * Isolated, additive enhancement of the EXISTING dossier history <details>.
 * All facts are owner-scoped GET responses from the existing dossier endpoint.
 * This layer neither creates a second evidence store nor writes any changes.
 */

const COMPARE_CLASS = "frontier-compare";

function createDossierComparisonUI({
  doc = globalThis.document,
  win = globalThis.window,
  request = globalThis.fetch?.bind(globalThis),
  clock = globalThis,
} = {}) {
  if (!doc || !win || !request) throw new Error("document, window and fetch required");
  const entries = new Map();
  let stopped = false;
  const el = (tag, className = "", value) => {
    const node = doc.createElement(tag);
    if (className) node.className = className;
    if (value !== undefined) node.textContent = String(value);
    return node;
  };
  const append = (target, ...nodes) => { target.append(...nodes); return target; };
  const iso = value => readable(value, "保存时间未提供");
  const labelV = value => "v" + value;

  function messageFor(err, type) {
    if (err?.name === "AbortError") return "请求已取消；未作任何判断。";
    if (err?.status === 401) return "会话已失效；请重新登录后打开事件，不能据此判断历史为空。";
    if (err?.status === 403) return "当前不能读取研判历史或比较；不能据此推断没有保存版本。本页面没有购买入口。";
    if (err?.status === 404) return type === "comparison"
      ? "这对修订不存在或不属于当前用户；请刷新版本列表后重新选择。"
      : "此事件或历史无法访问；未展示假历史。";
    return (type === "comparison" ? "版本比较未完成：" : "历史版本读取未完成：")
      + (err?.message || "请检查连接，稍后主动重试。");
  }

  function createSource(source) {
    const card = el("article", "frontier-compare-source");
    append(card, el("div", "frontier-compare-record", "原始记录 ID · " + readable(source.record_id)));
    const meta = el("p", "frontier-compare-source-meta");
    meta.textContent = "平台：" + readable(source.platform)
      + "　出处：" + readable(source.name)
      + "　订阅标识：" + readable(source.source_id);
    append(card, meta);
    const sha = el("div", "frontier-compare-sha");
    append(sha, el("strong", "", "冻结 SHA-256："));
    append(sha, el("code", "", readable(source.sha256, "未提供 SHA-256")));
    append(card, sha);
    append(card, el("p", "frontier-compare-times",
      "原文发布时间：" + readable(source.published_at)
      + "　·　首次收录：" + readable(source.first_ingested_at)));
    const safe = safeSourceUrl(source);
    if (safe) {
      const link = el("a", "frontier-compare-link", "打开出处（链接可达性未检查） ↗");
      link.href = safe;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.referrerPolicy = "no-referrer";
      append(card, link);
    } else {
      append(card, el("p", "frontier-compare-link-unavailable",
        "安全出处链接不可用；不提供跳转。"));
    }
    return card;
  }

  function renderSourceGroup(parent, name, records, kind) {
    const group = el("details", "frontier-compare-source-group");
    const summary = el("summary", "", name + " · " + records.length + " 条");
    append(group, summary);
    if (records.length) {
      group.open = true;
      for (const source of records) {
        if (kind !== "updated") {
          append(group, createSource(source));
          continue;
        }
        const updated = el("article", "frontier-compare-update");
        append(updated, el("h5", "", "记录 " + source.record_id + " · 属性发生变更"));
        const labels = [...new Set(source.changed_properties)]
          .map(key => SOURCE_PROPS[key]);
        append(updated, el("p", "frontier-compare-props", "后端列出的变更字段：" + labels.join("、")));
        const pair = el("div", "frontier-compare-columns");
        const before = el("div", "frontier-compare-col");
        const after = el("div", "frontier-compare-col");
        append(before, el("h6", "", "较早版本"), createSource(source.before));
        append(after, el("h6", "", "较新版本"), createSource(source.after));
        append(pair, before, after);
        append(updated, pair);
        append(group, updated);
      }
    } else {
      append(group, el("p", "frontier-compare-no-delta", "这类记录没有变化。"));
    }
    append(parent, group);
  }

  function renderTime(item, label) {
    const box = el("div", "frontier-compare-col frontier-compare-time");
    append(box, el("h4", "", label));
    append(box, el("p", "frontier-compare-time-state", occurredStatus(item.event_time_status)));
    const start = readable(item.event_time_start, "未知（未提供发生时间）");
    const end = readable(item.event_time_end, "未明确结束时间");
    append(box, el("p", "", "起始：" + start), el("p", "", "结束：" + end));
    append(box, el("p", "frontier-compare-times",
      "精度：" + readable(item.event_time_precision, "未知")));
    if (typeof item.event_time_evidence === "string" && item.event_time_evidence.trim()) {
      append(box, el("h5", "", "保存时的时间依据（未自动核真）"),
        el("blockquote", "frontier-compare-value", item.event_time_evidence));
    }
    if (typeof item.event_time_note === "string" && item.event_time_note.trim()) {
      append(box, el("p", "frontier-compare-note", "原有备注：" + item.event_time_note));
    }
    return box;
  }

  function renderResult(state, data) {
    const target = state.result;
    target.replaceChildren();
    target.hidden = false;
    append(target, el("h3", "", "保存版本比较：v" + data.from_version + " → v" + data.to_version));
    append(target, el("p", "frontier-compare-subtitle",
      "仅对比两个已保存版本的本人文字与冻结来源；未使用未保存草稿，也不解释判断改变的原因。"));
    const info = el("p", "frontier-compare-summary");
    info.textContent = "人工字段变更：" + data.changedKeys.length + " / " + FIELD_ORDER.length
      + "　·　冻结原始记录：" + data.source_changes.from_count
      + " → " + data.source_changes.to_count + " 条";
    append(target, info);
    append(target, el("p", "frontier-compare-saved",
      "较早版本保存于：" + iso(data.from_saved_at) + "　·　较新版本保存于：" + iso(data.to_saved_at)));

    const fields = el("section", "frontier-compare-block");
    append(fields, el("h4", "", "01 · 人工结论、反证与支持疑问"));
    append(fields, el("p", "frontier-compare-caution",
      "以下仅为当时本人填写的文字。文字变化不自动表明事实已证实或被推翻。"));
    const fieldRow = ([key, label]) => {
      const source = data.fields.get(key);
      const row = el("div", "frontier-compare-field");
      row.dataset.field = key;
      row.dataset.changed = String(source.changed);
      const heading = el("h5", "", label + " · " + (source.changed ? "有文字变化" : "文字未变化"));
      append(row, heading);
      const pair = el("div", "frontier-compare-columns");
      for (const [side, value] of [["较早 v" + data.from_version, source.before],
        ["较新 v" + data.to_version, source.after]]) {
        const col = el("div", "frontier-compare-col");
        append(col, el("h6", "", side));
        append(col, el("p", "frontier-compare-value",
          value.trim() ? value : "未填写（该保存版本中为空）"));
        append(pair, col);
      }
      append(row, pair);
      return row;
    };
    for (const field of FIELD_ORDER.slice(0, 3)) append(fields, fieldRow(field));
    const extras = el("details", "frontier-compare-extra");
    extras.open = data.fields.get("next_step").changed || data.fields.get("review_on").changed;
    append(extras, el("summary", "", "其它人工字段：下一步、复查日"));
    for (const field of FIELD_ORDER.slice(3)) append(extras, fieldRow(field));
    append(fields, extras);
    append(target, fields);

    const occurrence = el("section", "frontier-compare-block");
    append(occurrence, el("h4", "", "02 · 事件发生时间"
      + (data.event_occurrence.changed ? " · 冻结字段有变化" : " · 冻结字段未变化")));
    append(occurrence, el("p", "frontier-compare-caution",
      "事件发生时间 ≠ 原文发布时间 ≠ 首次收录时间。未知就是未知；计划与推定均不等于已发生。"));
    const timePair = el("div", "frontier-compare-columns");
    append(timePair, renderTime(data.event_occurrence.before, "较早 v" + data.from_version),
      renderTime(data.event_occurrence.after, "较新 v" + data.to_version));
    append(occurrence, timePair);
    append(target, occurrence);

    const evidence = el("section", "frontier-compare-block");
    const delta = data.source_changes;
    append(evidence, el("h4", "", "03 · 冻结原文记录：新增／移除／更新"));
    append(evidence, el("p", "frontier-compare-summary",
      "新增 " + delta.added.length + "　·　移除 " + delta.removed.length
      + "　·　更新 " + delta.updated.length + "　·　未变 " + delta.unchanged_count));
    append(evidence, el("p", "frontier-compare-caution",
      "原文记录条数 ≠ 独立证实数量；记录或 SHA-256 改变，也不代表来源独立或真伪得到验证。"
      + " 仅显示后端冻结出处索引，不提供原文正文或自动臆测的变化原因。"));
    renderSourceGroup(evidence, "新增的原文记录", delta.added, "added");
    renderSourceGroup(evidence, "移除的原文记录", delta.removed, "removed");
    renderSourceGroup(evidence, "同 ID 但属性更新的原文记录", delta.updated, "updated");
    append(target, evidence);
    append(target, el("p", "frontier-compare-footer",
      "后端提示：" + readable(data.notice, "仅供保存版本之间核对；未做线上链接或独立证实检查。")));
    const close = el("button", "button secondary frontier-compare-back", "收起比较结果 · 返回本主题历史");
    close.type = "button";
    close.addEventListener("click", () => {
      target.hidden = true;
      state.status.textContent = "已收起比较结果。仍在本主题历史版本中，可重新选择比较。";
      state.go.focus();
    });
    append(target, close);
  }

  function setChoice(state, history, initial) {
    const { fromSelect, toSelect, go } = state;
    const previous = { from: Number(fromSelect.value), to: Number(toSelect.value) };
    const recent = recentPair(history);
    const selected = !initial && validPair(history, previous.from, previous.to)
      ? previous : recent;
    for (const [select, wanted] of [[fromSelect, selected?.from], [toSelect, selected?.to]]) {
      select.replaceChildren();
      for (const revision of history) {
        const option = el("option", "", "v" + revision.version
          + " · " + iso(revision.saved_at));
        option.value = String(revision.version);
        append(select, option);
      }
      if (wanted !== undefined) select.value = String(wanted);
      select.disabled = history.length < 2;
    }
    go.disabled = history.length < 2;
    if (!recent) {
      state.result.hidden = true;
      state.result.replaceChildren();
      state.status.textContent = history.length === 0
        ? "此主题尚无已保存研判版本：需要至少两版才能比较，不会凭空生成历史。"
        : "此主题只有 1 个已保存版本：至少需要两版才可比较；不会伪造第二版。";
      return;
    }
    state.status.textContent = "找到 " + history.length + " 个保存版本；默认选中最近两版，"
      + "尚未比较。请主动点击「比较这两版」。";
  }

  async function fetchJson(path, signal) {
    const response = await request(path, {
      method: "GET", credentials: "same-origin", cache: "no-store",
      headers: { Accept: "application/json" }, signal,
    });
    if (!response || !response.ok) {
      const err = new Error("HTTP " + (response?.status || "未知"));
      err.status = response?.status;
      throw err;
    }
    return response.json();
  }

  async function loadHistory(state) {
    if (stopped || !doc.contains(state.historyElement)) return;
    const id = ++state.historySequence;
    state.historyAbort?.abort();
    state.compareSequence++;
    state.compareAbort?.abort();
    state.result.hidden = true;
    state.result.replaceChildren();
    const controller = new AbortController();
    state.historyAbort = controller;
    state.status.textContent = "正在从当前账户读取此事件的保存版本…";
    state.go.disabled = true;
    state.fromSelect.disabled = state.toSelect.disabled = true;
    const timeout = clock.setTimeout(() => controller.abort(), 13000);
    try {
      const result = readHistory(await fetchJson(
        "/api/events/" + encodeURIComponent(state.eventId) + "/dossier", controller.signal
      ), state.eventId);
      if (stopped || id !== state.historySequence || !doc.contains(state.historyElement)) return;
      const initial = state.savedHistory === null;
      state.savedHistory = result;
      setChoice(state, result, initial);
    } catch (error) {
      if (stopped || id !== state.historySequence) return;
      state.savedHistory = null; // stale history does not imply no history
      state.status.textContent = messageFor(error, "history");
      state.fromSelect.disabled = state.toSelect.disabled = state.go.disabled = true;
      state.result.hidden = true;
    } finally {
      clock.clearTimeout(timeout);
    }
  }

  async function compare(state) {
    if (!state.savedHistory) return;
    const from = Number(state.fromSelect.value), to = Number(state.toSelect.value);
    if (!validPair(state.savedHistory, from, to)) {
      state.status.textContent = "请选择同一主题真实存在的两版，并确保较早版本 < 较新版本。未发送请求。";
      state.result.hidden = true;
      return;
    }
    const requestId = ++state.compareSequence;
    state.compareAbort?.abort();
    const controller = new AbortController();
    state.compareAbort = controller;
    state.go.disabled = true;
    state.status.textContent = "正在只读比较 v" + from + " 与 v" + to + "…";
    state.result.hidden = true;
    state.result.replaceChildren();
    const timeout = clock.setTimeout(() => controller.abort(), 13000);
    try {
      const path = "/api/events/" + encodeURIComponent(state.eventId)
        + "/dossier/compare?from=" + from + "&to=" + to;
      const data = readComparison(await fetchJson(path, controller.signal), state.eventId, from, to);
      if (stopped || requestId !== state.compareSequence ||
          !doc.contains(state.historyElement)) return;
      renderResult(state, data);
      state.status.textContent = "已显示 v" + from + " → v" + to
        + " 的冻结差异；不代表事实核验、来源独立或当前草稿内容。";
    } catch (error) {
      if (stopped || requestId !== state.compareSequence) return;
      state.status.textContent = messageFor(error, "comparison");
      state.result.hidden = true;
    } finally {
      clock.clearTimeout(timeout);
      if (!stopped && requestId === state.compareSequence) {
        state.go.disabled = !state.savedHistory
          || !validPair(state.savedHistory, from, to);
      }
    }
  }

  function bind(historyElement) {
    const dossier = historyElement.closest(".dossier[data-event-id]");
    const eventId = dossier?.dataset.eventId;
    if (!eventId || entries.has(historyElement)) return;
    // Help users discover comparison without replacing the native history entry.
    const nativeSummary = historyElement.querySelector(":scope > summary");
    const hint = el("span", "frontier-compare-history-hint", " · 可比较两个保存版本");
    nativeSummary?.append(hint);
    const panel = el("section", COMPARE_CLASS);
    panel.setAttribute("aria-label", "本主题两个保存版本的只读比较");
    append(panel, el("h4", "", "比较两个保存版本"));
    append(panel, el("p", "frontier-compare-intro",
      "从这条事件已保存的研判历史中选两版；默认最近两版但不会自动作出比较／判断。"));
    const controls = el("div", "frontier-compare-controls");
    const select = side => {
      const label = el("label", "frontier-compare-picker",
        side === "from" ? "较早保存版本" : "较新保存版本");
      const input = el("select", "");
      input.disabled = true;
      input.dataset.side = side;
      append(label, input);
      append(controls, label);
      return input;
    };
    const fromSelect = select("from");
    const toSelect = select("to");
    const go = el("button", "button primary frontier-compare-go", "比较这两版（只读）");
    go.type = "button";
    go.disabled = true;
    append(controls, go);
    const refresh = el("button", "button secondary frontier-compare-refresh", "刷新保存版本");
    refresh.type = "button";
    append(controls, refresh);
    const status = el("p", "frontier-compare-status", "展开历史后读取可用版本。");
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    const result = el("div", "frontier-compare-result");
    result.hidden = true;
    append(panel, controls, status,
      el("p", "frontier-compare-disclaimer",
        "仅比较本人已保存的文字与冻结证据。原文条数不等于独立证实，链接是否在线未检查。"),
      result);
    append(historyElement, panel);
    const state = {
      eventId, historyElement, panel, status, result, fromSelect, toSelect, go,
      savedHistory: null, historySequence: 0, compareSequence: 0,
      historyAbort: null, compareAbort: null, timer: null, listObserver: null,
      toggleHandler: null, hint,
    };
    entries.set(historyElement, state);

    function onSelection() {
      state.compareSequence++;
      state.compareAbort?.abort();
      state.result.hidden = true;
      state.result.replaceChildren();
      const from = Number(fromSelect.value), to = Number(toSelect.value);
      state.go.disabled = !state.savedHistory || !validPair(state.savedHistory, from, to);
      state.status.textContent = state.go.disabled
        ? "应选较早版本 < 较新版本，且都必须存在于服务器返回的本主题历史中。"
        : "已改选 v" + from + " → v" + to + "；尚未比较，请主动点击比较。";
    }
    fromSelect.addEventListener("change", onSelection);
    toSelect.addEventListener("change", onSelection);
    go.addEventListener("click", () => compare(state));
    refresh.addEventListener("click", () => loadHistory(state));

    // Native history list renders asynchronously and re-renders after saves.
    const nativeList = historyElement.querySelector(".dossier-history-list");
    if (nativeList) {
      state.listObserver = new win.MutationObserver(() => {
        clock.clearTimeout(state.timer);
        state.timer = clock.setTimeout(() => loadHistory(state), 80);
      });
      state.listObserver.observe(nativeList, { childList: true });
    }
    state.toggleHandler = () => {
      if (historyElement.open) loadHistory(state);
      else if (state.compareAbort) {
        state.compareSequence++;
        state.compareAbort.abort();
        state.go.disabled = !state.savedHistory
          || !validPair(state.savedHistory, Number(fromSelect.value), Number(toSelect.value));
      }
    };
    historyElement.addEventListener("toggle", state.toggleHandler);
    if (historyElement.open) loadHistory(state);
  }

  function cleanup(state) {
    state.historySequence++;
    state.compareSequence++;
    state.historyAbort?.abort();
    state.compareAbort?.abort();
    clock.clearTimeout(state.timer);
    state.listObserver?.disconnect();
    state.hint.remove();
    state.historyElement.removeEventListener("toggle", state.toggleHandler);
    entries.delete(state.historyElement);
  }

  function scan() {
    if (stopped) return;
    for (const [historyElement, state] of entries) {
      if (!doc.contains(historyElement)) cleanup(state);
    }
    for (const historyElement of doc.querySelectorAll(".dossier[data-event-id] .dossier-history")) {
      bind(historyElement);
    }
  }

  // The original V120 dossier DOM is mounted on demand inside event detail dialogs.
  const observer = new win.MutationObserver(scan);
  observer.observe(doc.body || doc.documentElement, { childList: true, subtree: true });
  scan();
  return {
    scan,
    destroy() {
      stopped = true;
      observer.disconnect();
      for (const state of [...entries.values()]) {
        cleanup(state);
        state.panel.remove();
      }
    },
  };
}

if (typeof document !== "undefined" && typeof window !== "undefined") {
  createDossierComparisonUI();
}

})();
/* FRONTIER_ADDON_END:pro-compare */

/* FRONTIER_ADDON_BEGIN:pro-markdown */
;(() => {
"use strict";
/**
 * V133 frozen personal Dossier Markdown download, read-only.
 * All URLs originate from authenticated same-origin IDs and explicit revision integers.
 */

function validDossierEventId(value) {
  return typeof value === 'string' && /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$/.test(value);
}

function hasPrivateMarkdownEntitlement(plans) {
  return plans && typeof plans === 'object' &&
    ['pro', 'analyst'].includes(plans.current_plan_id) &&
    plans.current_plan?.limits?.dossier_write_enabled === true;
}

function dossierVersions(payload, requestedId) {
  if (!validDossierEventId(requestedId) || !payload || typeof payload !== 'object' ||
      payload.event_id !== requestedId || !Array.isArray(payload.history)) {
    throw Error('研判历史与当前事件不匹配');
  }
  const versions = payload.history
    .map(item => item && typeof item.version === 'number' ? item.version : NaN)
    .filter(value => Number.isSafeInteger(value) && value >= 1);
  return [...new Set(versions)].sort((a, b) => b - a).slice(0, 12);
}

function markdownHref(eventId, version) {
  if (!validDossierEventId(eventId) || !Number.isSafeInteger(version) || version < 1) {
    throw Error('非法事件或研判版本');
  }
  return '/api/events/' + encodeURIComponent(eventId) +
    '/dossier/revisions/' + version + '/export?format=markdown';
}

/**
 * V133: bring existing per-version Dossier export into the actual native detail UI.
 * This is NOT a new dossier implementation and never mutates the frozen revision.
 */

function createPrivateMarkdownDownloads({
  doc = globalThis.document,
  win = globalThis.window,
  request = globalThis.fetch?.bind(globalThis),
  clock = globalThis,
} = {}) {
  if (!doc || !win || !request) throw Error('浏览器依赖缺失');
  let disposed = false;
  let loadedFor = null;
  let generation = 0;
  let inflight = null;
  let timer = null;
  let periodic = null;
  const ID = 'frontier-v133-private-markdown';
  const $ = selector => doc.querySelector(selector);
  const alive = (id, gen) =>
    !disposed && generation === gen && $('#detail-dialog')?.open === true &&
    $('#detail-content')?.dataset.id === id;

  function remove() {
    doc.getElementById(ID)?.remove();
  }

  function mount() {
    if ($('#detail-dialog')?.open !== true) return null;
    const region = $('#detail-dialog .dossier-export-chooser');
    if (!region) return null;
    let root = doc.getElementById(ID);
    if (!root) {
      root = doc.createElement('section');
      root.id = ID;
      root.className = 'frontier-v133-private-markdown';
      root.setAttribute('aria-label', '冻结个人证据 Markdown 私人下载');
      region.append(root);
    }
    return root;
  }

  function el(tag, cls, contents) {
    const node = doc.createElement(tag);
    if (cls) node.className = cls;
    if (contents !== undefined) node.textContent = contents;
    return node;
  }

  function render(id, versions, entitled, error = '') {
    const root = mount();
    if (!root) return;
    root.replaceChildren();
    root.append(el('h4', '', '私人证据留档  /  Markdown'));
    root.append(el('p', 'frontier-v133-md-note',
      '按保存时版本下载本人笔记与出处索引。发生时间缺失仍标未知；不同来源不等于独立证实。' +
      '仅限个人离线保存，版权或外发需另行逐项核验。'));
    if (error) {
      const msg = el('p', 'frontier-v133-md-error', error);
      msg.setAttribute('role', 'status');
      root.append(msg);
      return;
    }
    if (!entitled) {
      root.append(el('p', 'frontier-v133-md-state',
        '此功能仅供 Pro/Analyst 内测使用；当前不提供付费升级入口。'));
      return;
    }
    if (!versions.length) {
      root.append(el('p', 'frontier-v133-md-state',
        '尚无本人保存的研判版本。请先在此事件的人工研判表单保存一次。'));
      return;
    }
    const links = el('div', 'frontier-v133-md-links');
    for (const version of versions) {
      const anchor = el('a', 'frontier-v133-md-link', '↓ 下载冻结 v' + version + '（私有 .md）');
      anchor.href = markdownHref(id, version);
      anchor.setAttribute('download', '');
      anchor.dataset.frontierMarkdownVersion = String(version);
      anchor.title = '仅供本人下载，不是已核实/可转发的研究报告';
      anchor.addEventListener('click', async event => {
        // Chromium/WebKit may reject a direct attachment in a modal dialog.
        // The explicit user click fetches the *exact* frozen revision, then
        // initiates a same-origin in-memory blob download, never an auto-send.
        event.preventDefault();
        anchor.setAttribute('aria-busy', 'true');
        const previous = anchor.textContent;
        anchor.textContent = '正在核对冻结 v' + version + '…';
        try {
          const res = await request(markdownHref(id, version), {
            credentials: 'same-origin', cache: 'no-store',
            headers: { Accept: 'text/markdown' },
          });
          if (!res.ok || !String(res.headers?.get?.('content-type') || '').includes('text/markdown')) {
            throw Error('服务端拒绝了私人 Markdown 导出');
          }
          const cd = String(res.headers?.get?.('content-disposition') || '');
          const match = /^attachment; filename="(frontier-dossier-v(\d+)-[a-f0-9]{12}\.md)"$/.exec(cd);
          if (!match || Number(match[2]) !== version) throw Error('下载的版本标识不正确');
          const body = await res.arrayBuffer();
          if (!body.byteLength || body.byteLength > 500000 ||
              $('#detail-content')?.dataset.id !== id || !anchor.isConnected) {
            throw Error('空数据、过大或研判卡已切换');
          }
          const declaredSHA = String(res.headers?.get?.('x-frontier-export-sha256') || '');
          if (!/^[a-f0-9]{64}$/.test(declaredSHA)) throw Error('下载没有服务端校验码');
          if (win.crypto?.subtle) {
            const actual = Array.from(new Uint8Array(await win.crypto.subtle.digest('SHA-256', body)))
              .map(b => b.toString(16).padStart(2, '0')).join('');
            if (actual !== declaredSHA) throw Error('冻结版内容未通过SHA-256核验');
          }
          const blob = new win.Blob([body], { type: 'text/markdown;charset=utf-8' });
          const url = win.URL.createObjectURL(blob);
          const save = doc.createElement('a');
          save.href = url; save.download = match[1]; save.hidden = true;
          root.append(save);
          save.click();
          // Chromium defers attachment streaming until after the click task.
          // Keep both the anchor AND its Blob URL alive until transfer begins.
          clock.setTimeout(() => {
            save.remove();
            win.URL.revokeObjectURL(url);
          }, 25000);
          anchor.textContent = '✓ 已请求下载冻结 v' + version;
        } catch (error) {
          anchor.textContent = '下载未成功：' + String(error?.message || '请重试').slice(0, 65);
        } finally {
          anchor.removeAttribute('aria-busy');
          clock.setTimeout(() => {
            if (anchor.isConnected) anchor.textContent = previous;
          }, 4000);
        }
      });
      links.append(anchor);
      const copy = el('button', 'frontier-v133-md-copy', '复制 v' + version + '（备用）');
      copy.type = 'button';
      copy.dataset.frontierMarkdownCopy = String(version);
      copy.onclick = async () => {
        copy.disabled = true;
        try {
          const res = await request(markdownHref(id, version), { credentials: 'same-origin', cache: 'no-store' });
          if (!res.ok || !String(res.headers?.get?.('content-type')).includes('text/markdown')) throw Error('服务端拒绝导出');
          const value = await res.text();
          if (!value || value.length > 350000 || $('#detail-content')?.dataset.id !== id) throw Error('冻结版不可用');
          try { await win.navigator.clipboard.writeText(value); copy.textContent = '✓ 已复制 v' + version; }
          catch {
            const area = el('textarea', 'frontier-v133-md-manual-copy');
            area.readOnly = true; area.value = value;
            root.querySelector('.frontier-v133-md-manual-copy')?.remove();
            root.append(area); area.focus(); area.select();
            copy.textContent = '请手动复制下方 v' + version;
          }
        } catch { copy.textContent = '复制失败，请选择直接下载'; }
        finally { copy.disabled = false; }
      };
      links.append(copy);
    }
    root.append(links);
    root.append(el('p', 'frontier-v133-md-meta',
      '下载只读，不会改变服务器的研判、原文或复盘水位。' +
      '如服务器拒绝下载，请检查当前内测权限或保存版本中的待脱敏内容。'));
  }

  async function refresh(force = false) {
    const detail = $('#detail-content');
    const id = detail?.dataset.id;
    if (!validDossierEventId(id) || $('#detail-dialog')?.open !== true) {
      loadedFor = null;
      generation += 1;
      inflight?.abort();
      remove();
      return;
    }
    if (!force && loadedFor === id && doc.getElementById(ID)) return;
    loadedFor = id;
    generation += 1;
    const gen = generation;
    inflight?.abort();
    const controller = new AbortController();
    inflight = controller;
    render(id, [], true, '正在读取保存的研判版本…');
    try {
      const planRes = await request('/api/plans', {
        credentials: 'same-origin', cache: 'no-store',
        headers: { Accept: 'application/json' }, signal: controller.signal,
      });
      if (!planRes.ok) throw Error('无法确认当前内测权限（HTTP ' + planRes.status + '）');
      const plans = await planRes.json();
      if (!alive(id, gen)) return;
      const entitled = hasPrivateMarkdownEntitlement(plans);
      if (!entitled) {
        render(id, [], false);
        return;
      }
      const res = await request('/api/events/' + encodeURIComponent(id) + '/dossier', {
        credentials: 'same-origin', cache: 'no-store',
        headers: { Accept: 'application/json' }, signal: controller.signal,
      });
      if (!res.ok) throw Error('研判版本读取失败（HTTP ' + res.status + '）');
      const versions = dossierVersions(await res.json(), id);
      if (alive(id, gen)) render(id, versions, true);
    } catch (error) {
      if (alive(id, gen)) {
        render(id, [], true, '无法显示可下载版本：' +
          (error?.name === 'AbortError' ? '请求被取消' : String(error?.message || '请重试')));
      }
    }
  }

  function schedule(ms = 90) {
    if (disposed) return;
    clock.clearTimeout(timer);
    timer = clock.setTimeout(() => refresh(false), ms);
  }

  const observer = new win.MutationObserver(() => {
    const id = $('#detail-content')?.dataset.id;
    if ($('#detail-dialog')?.open !== true || !validDossierEventId(id)) {
      if (loadedFor !== null) schedule(60);
    } else if (loadedFor !== id || !doc.getElementById(ID)) {
      schedule(60);
    }
  });
  observer.observe(doc.body, { subtree: true, childList: true, attributes: true,
    attributeFilter: ['open', 'data-id'] });

  const onClick = event => {
    if (event.target?.closest?.('#detail-dialog .dossier-write-actions button, #detail-dialog .dossier-refresh-actions button')) {
      // Native save may fail; always reread from server, never assume success.
      clock.setTimeout(() => refresh(true), 800);
    }
  };
  doc.addEventListener('click', onClick, true);
  schedule(80);
  periodic = clock.setInterval(() => {
    if ($('#detail-dialog')?.open) refresh(true);
  }, 20000);
  return {
    refresh: () => refresh(true),
    destroy() {
      disposed = true;
      generation++;
      inflight?.abort();
      observer.disconnect();
      doc.removeEventListener('click', onClick, true);
      clock.clearTimeout(timer);
      clock.clearInterval(periodic);
      remove();
    },
  };
}

if (typeof document !== 'undefined' && typeof window !== 'undefined') {
  createPrivateMarkdownDownloads();
}

})();
/* FRONTIER_ADDON_END:pro-markdown */

/* FRONTIER_ADDON_BEGIN:review-focus */
;(() => {
"use strict";
/**
 * V133 isolated, read-only Analyst review-focus contract.
 * Radar's native seven-day queue ALREADY EXISTS; this is only the overdue/
 * today/tomorrow evidence-first handoff. No global_signals or AI due inference.
 */

const REVIEW_FOCUS_ID = 'frontier-review-focus';

const FOCUS_LIMIT = 8;
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const string = value => typeof value === 'string' && value.trim().length > 0;

const text = (value, cap = 260) => string(value) ? value.trim().slice(0, cap) : '';

function isoDay(value) {
  if (typeof value !== 'string' || !/^(?!0000)\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
}

function shiftDay(day, n) {
  if (!isoDay(day) || !Number.isInteger(n)) return null;
  return new Date(Date.parse(`${day}T00:00:00Z`) + n * 86400000).toISOString().slice(0, 10);
}

function daysFrom(day, today) {
  return (Date.parse(`${day}T00:00:00Z`) - Date.parse(`${today}T00:00:00Z`)) / 86400000;
}

const dueLabel = item => item.days_until < 0 ? `逾期 ${-item.days_until} 天` :
  item.days_until === 0 ? '今天到期' : '明天应复查';

const dueReason = item =>
  `本人最新保存的研判 v${item.version} 将复查日设为 ${item.review_on}（北京时间），${dueLabel(item)}；不是新原文自动触发，也不是全站热度任务。`;

/** Fail closed on missing/contradictory date fields; never fabricate due dates. */

function reviewFocusContract(value) {
  if (!object(value) || typeof value.enabled !== 'boolean' ||
      value.timezone !== 'Asia/Shanghai' || !isoDay(value.today) ||
      !isoDay(value.through) || shiftDay(value.today, 7) !== value.through ||
      value.limit !== 50 || typeof value.has_revisions !== 'boolean' ||
      !Array.isArray(value.items) || value.items.length > value.limit) {
    throw new TypeError('复查接口契约不完整，不能判定个人复查是否到期。');
  }
  if (!value.enabled) {
    if (value.items.length) throw new TypeError('无队列权益的响应不应携带任务。');
    return {enabled:false, today:value.today, tomorrow:shiftDay(value.today, 1),
      hasRevisions:false, chosen:[], remainder:0, future:0, total:0, capped:false};
  }
  const seen = new Set();
  const accepted = [];
  for (const entry of value.items) {
    if (!object(entry) || !string(entry.event_id) || !string(entry.title) ||
        !Number.isSafeInteger(entry.version) || entry.version < 1 ||
        !isoDay(entry.review_on) || !Number.isInteger(entry.days_until) ||
        !['overdue','today','upcoming'].includes(entry.status) ||
        daysFrom(entry.review_on, value.today) !== entry.days_until ||
        entry.days_until > 7 ||
        entry.status !== (entry.days_until < 0 ? 'overdue' : entry.days_until === 0 ? 'today' : 'upcoming') ||
        seen.has(entry.event_id)) {
      throw new TypeError('个人复查任务与服务端日期或最新修订不一致，请重新同步。');
    }
    seen.add(entry.event_id);
    accepted.push(entry);
  }
  const focus = accepted.filter(item => item.days_until <= 1);
  return {
    enabled:true, today:value.today, tomorrow:shiftDay(value.today, 1),
    hasRevisions:value.has_revisions, chosen:focus.slice(0, FOCUS_LIMIT),
    remainder:Math.max(0, focus.length - FOCUS_LIMIT), future:accepted.length-focus.length,
    total:accepted.length, capped:accepted.length === 50,
  };
}

/** Include only explicitly saved topic watermarks, never treat them as due dates. */

function ownerTopicWatermarks(payload) {
  if (!object(payload) || !Array.isArray(payload.topics) ||
      !object(payload.plan) || !string(payload.plan.id)) {
    throw new TypeError('个人主题水位未核验。');
  }
  return payload.topics.map(topic => {
    if (!object(topic) || !string(topic.id) || !string(topic.name)) {
      throw new TypeError('个人主题缺少真实标识。');
    }
    const date = topic.last_reviewed_at;
    if (date !== null && date !== undefined &&
        (!string(date) || !Number.isFinite(Date.parse(date)) || !/(?:Z|[+-]\d\d:\d\d)$/.test(date))) {
      throw new TypeError('个人主题复盘时间不是有效时区时间。');
    }
    return {id:topic.id, name:text(topic.name, 70),
      reviewedAt:date || null, suspended:topic.suspended === true};
  });
}

/** Exact latest owner revision check; never borrow another revision's originals. */

function verifyLatestDossier(row, latest) {
  return object(latest) && latest.event_id === row.event_id &&
    latest.version === row.version && object(latest.fields) &&
    latest.fields.review_on === row.review_on;
}

/** HTTPS/HTTP public navigation only; never fetch links to validate reachability. */

function safeOriginalLink(value) {
  if (!string(value) || value.length > 2048 || /[\s\\\u007f]/.test(value) ||
      !/^https?:\/\//i.test(value)) return null;
  try {
    const url = new URL(value);
    const rawAuthority = value.replace(/^https?:\/\//i, '').split(/[/?#]/, 1)[0];
    if (!['http:', 'https:'].includes(url.protocol) || !rawAuthority ||
        rawAuthority.includes('@') || url.username || url.password) return null;
    const host = url.hostname.toLowerCase().replace(/\.$/, '').replace(/^\[|\]$/g, '');
    if (!host || host.includes(':') || !host.includes('.') ||
        /^(?:\d+\.){3}\d+$/.test(host) || /^\d+$/.test(host) ||
        /(?:^|\.)(?:localhost|local|internal|lan|home|home\.arpa|nip\.io|sslip\.io|lvh\.me|localtest\.me)$/.test(host)) return null;
    return url.href;
  } catch { return null; }
}

function frozenEvidence(row, revision) {
  if (!object(revision) || revision.version !== row.version ||
      !object(revision.fields) || revision.fields.review_on !== row.review_on ||
      !object(revision.evidence) || !Array.isArray(revision.evidence.records) ||
      revision.evidence.records.length > 10000) {
    throw new TypeError('不可变研判版本与复查任务不一致；不展示其来源。');
  }
  const evidence = revision.evidence.records.filter(record =>
    object(record) && typeof record.record_id === 'string' &&
    record.link_status === 'not_checked' && safeOriginalLink(record.url));
  return evidence.slice(0, 2).map(record => ({
    recordId: text(record.record_id, 120), name:text(record.name, 90) || '关联原文',
    platform:text(record.platform, 20), href:safeOriginalLink(record.url),
  }));
}

function beijingTime(value) {
  if (!string(value)) return '尚未人工复盘';
  const d = new Date(value);
  if (!Number.isFinite(d.getTime())) return '时间未核对';
  return new Intl.DateTimeFormat('zh-CN', {
    year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',
    timeZone:'Asia/Shanghai', hour12:false,
  }).format(d) + '（北京时间）';
}

/**
 * Editable ESM, read-only runtime: compact "now / tomorrow" evidence handoff.
 * Native Radar already renders the complete seven-day queue; do NOT replace it.
 * Mount inside its pane, keep native dossier, native queue, daily Top3 separate.
 */

function createReviewFocus({
  doc = globalThis.document, win = globalThis.window,
  request = globalThis.fetch?.bind(globalThis), clock = globalThis,
} = {}) {
  if (!doc || !win || !request) throw new Error('document/window/fetch required');
  const el = (tag, cls = '', content = '') => {
    const node = doc.createElement(tag);
    if (cls) node.className = cls;
    if (content) node.textContent = content;
    return node;
  };
  const button = (label, cls, fn) => {
    const node = el('button', cls, label);
    node.type = 'button'; node.addEventListener('click', fn); return node;
  };
  const root = el('section', 'fr-review-focus');
  root.id = REVIEW_FOCUS_ID;
  root.setAttribute('role', 'region');
  root.setAttribute('aria-labelledby', 'fr-review-title');
  let stopped = false, observer = null, navRef = null, generation = 0;
  let controller = null, loaded = false, snapshot = null, status = 'idle';
  let feedback = '', selected = [], skipped = 0, watermarkRequest = 0;
  let previousRead = null, watermarkOpen = false;

  function current(scope) { return !stopped && scope === generation && navRef === doc.querySelector('#nav-radar'); }
  function isAuthenticated() { return !!doc.querySelector('#nav-radar') && !!doc.querySelector('.main-shell'); }
  function readyPane() {
    const pane = doc.getElementById('radar-pane');
    return pane?.isConnected && !pane.hidden ? pane : null;
  }
  function insert() {
    const nav = doc.querySelector('#nav-radar');
    if (nav !== navRef) {
      generation++; controller?.abort(); controller = null;
      loaded = false; snapshot = null; selected = []; feedback = ''; status = 'idle';
      previousRead = null; navRef = nav;
      root.remove();
    }
    if (!isAuthenticated()) return root.remove();
    const pane = doc.getElementById('radar-pane');
    if (!pane) return;
    // Native V132 re-renders pane via replaceChildren; node's listeners survive.
    if (root.parentElement !== pane) {
      const hero = pane.querySelector('.radar-hero');
      if (hero) hero.after(root);
      else pane.prepend(root);
    }
    root.hidden = pane.hidden;
    if (!pane.hidden && !loaded && !controller) refresh();
  }
  function nativeDossier(row) {
    const target = Array.from(doc.querySelectorAll('#radar-review-due .radar-review-item'))
      .find(item => item.dataset.eventId === row.event_id);
    const native = target?.querySelector('button.radar-review-open');
    if (native) return native.click();
    // V132 supports ?section=radar&event=ID as a native detail deep link.
    const url = new URL(win.location.href);
    url.searchParams.set('section', 'radar');
    url.searchParams.set('event', row.event_id);
    win.location.assign(url.href);
  }
  function goTop3() {
    doc.getElementById('nav-feed')?.click();
    clock.setTimeout(() => {
      const panel = doc.getElementById('frontier-daily-panel');
      if (panel && !panel.hidden) {
        panel.scrollIntoView?.({block:'start',behavior:'smooth'});
        panel.querySelector('h2')?.setAttribute('tabindex', '-1');
        panel.querySelector('h2')?.focus?.({preventScroll:true});
      }
    }, 120);
  }
  function container(title, message, role = 'status') {
    const notice = el('p', 'fr-review-notice', `${title} · ${message}`);
    notice.setAttribute('role', role);
    root.append(notice);
  }
  function buildHeader() {
    const head = el('div', 'fr-review-head');
    const copy = el('div', 'fr-review-head-copy');
    copy.append(el('span', 'fr-review-eyebrow', 'PERSONAL DOSSIER  /  NEXT REVIEW'));
    const h = el('h2', '', '明日应复查 · 本人保存的研判');
    h.id = 'fr-review-title';
    copy.append(h, el('p', '', '只看本人最新研判中明确保存了复查日的事项：逾期、今日和明日。完整未来 7 天清单仍在下方原生 Radar 中。'));
    const actions = el('div', 'fr-review-head-actions');
    actions.append(button('↻ 同步保存版本', 'fr-review-btn fr-review-secondary', refresh),
      button('今日 Top 3 ↗', 'fr-review-btn fr-review-quiet', goTop3));
    head.append(copy, actions);
    root.append(head);
  }
  function recordCard({row, originals, evidenceError}) {
    const card = el('article', 'fr-review-card');
    card.dataset.reviewEvent = row.event_id;
    card.dataset.reviewDay = row.review_on;
    const meta = el('div', 'fr-review-card-meta');
    meta.append(el('strong', 'fr-review-due-tag', dueLabel(row)),
      el('time', 'fr-review-calendar', `${row.review_on} · 北京时间 · v${row.version}`));
    card.append(meta, el('h3', 'fr-review-card-title', text(row.title, 240) || '无标题事件'));
    card.append(el('p', 'fr-review-reason', dueReason(row)));
    const judgment = text(row.judgment, 180);
    if (judgment) card.append(el('p', 'fr-review-note', `上次本人判断：${judgment}`));
    const falsification = text(row.falsification, 120);
    card.append(el('p', 'fr-review-condition', `需重新核对的反证条件：${falsification || '未写明；请进入研判卡自行补充。'}`));
    const evidence = el('div', 'fr-review-evidence');
    evidence.append(el('span', 'fr-review-section-label', '保存该版本时已链接的原文（仅离线安全 URL）'));
    if (originals.length) {
      const links = el('div', 'fr-review-links');
      for (const src of originals) {
        const a = el('a', 'fr-review-original', `${src.name}${src.platform ? ` · ${src.platform}` : ''} ↗`);
        a.href = src.href; a.target = '_blank'; a.rel = 'noopener noreferrer';
        a.title = `原始记录 ${src.recordId}，链接可达性未检查`;
        links.append(a);
      }
      evidence.append(links);
    } else evidence.append(el('p', 'fr-review-no-source', evidenceError ||
      '保存时没有可安全导航的原文链接；不能用全站新闻或其他事件链接填空。请在详情检查原文。'));
    evidence.append(el('small', 'fr-review-caveat',
      '链接未联网核查；内容真实、转载独立性、授权与时效均未知。'));
    card.append(evidence);
    const actions = el('div', 'fr-review-row-actions');
    actions.append(button('打开原生证据与研判 ↗', 'fr-review-btn fr-review-primary', () => nativeDossier(row)));
    card.append(actions);
    return card;
  }
  function renderWatermarkArea() {
    const details = el('details', 'fr-review-watermark');
    details.open = watermarkOpen;
    details.append(el('summary', '', '主题 review_at 复盘水位（不是到期日期；展开后读取本人保存值）'));
    const area = el('div', 'fr-review-watermark-body');
    details.append(area);
    const load = async () => {
      const scope = ++watermarkRequest;
      area.replaceChildren(el('p', '', '正在读取本人主题复盘水位…'));
      try {
        const raw = await getJSON('/api/radar', controller?.signal);
        const topics = ownerTopicWatermarks(raw);
        if (!current(generation) || scope !== watermarkRequest || !details.isConnected) return;
        area.replaceChildren();
        if (!topics.length) area.append(el('p', '', '暂无本人保存的主题；dossier 复查日与主题水位是两条独立时间线。'));
        for (const topic of topics) area.append(el('p', '',
          `${topic.name}：${beijingTime(topic.reviewedAt)}${topic.suspended ? ' · 当前档位暂停' : ''}`));
        area.append(el('small', '', '只有主动点击原生“结束本轮复盘”并经服务器保存，review_at 才会前进；本视图不依据水位猜测下一次到期。'));
      } catch (error) {
        if (scope !== watermarkRequest || !details.isConnected) return;
        area.replaceChildren(el('p', 'fr-review-error',
          `无法核对主题水位：${text(error.message, 140)}。不会将其视为零或补造截止日。`));
      }
    };
    details.addEventListener('toggle', () => {
      watermarkOpen = details.open;
      if (details.open && !area.dataset.loaded) {
        area.dataset.loaded = 'true'; load();
      }
    });
    root.append(details);
  }
  function render() {
    if (!isAuthenticated()) return root.remove();
    root.replaceChildren(); buildHeader();
    if (status === 'loading') container('正在同步', '读取服务端本人复查日及最新修订，不会自动推进水位。');
    else if (status === 'error') {
      container('未能验证复查清单', feedback || '服务器无可信响应；不能显示“0件到期”。', 'alert');
    } else if (status === 'forbidden' || snapshot?.enabled === false) {
      container('当前权限不含集中复查队列',
        'Analyst 内测开放集中列表；Pro 可继续在单条原生 dossier 中读取与人工修改保存的复查日。无付费/切换入口。');
    } else if (status === 'ready' && snapshot) {
      const counts = el('p', 'fr-review-counts',
        `服务端今日 ${snapshot.today} · 明日 ${snapshot.tomorrow} · 本面板重点复核 ${selected.length} 条` +
        (snapshot.capped ? ' · 服务端 50 条上限已触及，可能有更多未显示' : ''));
      root.append(counts);
      if (!selected.length) {
        container('此刻没有逾期／今日／明日的可核验研判安排',
          snapshot.hasRevisions ?
            `已有人工研判；当前服务端未来 7 天队列中另有 ${snapshot.future} 条安排在明日以后。这里不将未知日期、全站热度或主题复盘水位当成明日任务。` :
            '尚未保存带复查日的个人研判；请在原生事件 dossier 中人工填写并保存。');
      } else {
        const list = el('div', 'fr-review-cards');
        for (const entry of selected) list.append(recordCard(entry));
        root.append(list);
      }
      if (snapshot.remainder || snapshot.future || skipped) {
        const info = [];
        if (snapshot.remainder) info.push(`另有 ${snapshot.remainder} 条焦点任务未逐行展开`);
        if (snapshot.future) info.push(`未来 2–7 天还有 ${snapshot.future} 条`);
        if (skipped) info.push(`${skipped} 条在二次核验时发现版本变化或读取失败，已隐藏并要求刷新`);
        root.append(el('p', 'fr-review-rest', `${info.join('；')}。下方原生“待复核研判”仍可查看完整服务端队列。`));
      }
      if (feedback) container('版本核验注意', feedback, 'alert');
    }
    if (status !== 'loading' && status !== 'forbidden') renderWatermarkArea();
    root.append(el('p', 'fr-review-footnote',
      '此视图只有 GET、打开原文和跳转；不会保存决定、自动延期、提醒推送或把今日 Top 3 变成本人复查任务。复查日按北京时间日界，原文首次收录另按 UTC 统计。'));
  }

  async function getJSON(path, signal) {
    const response = await request(path, {method:'GET',credentials:'same-origin',cache:'no-store',
      headers:{Accept:'application/json'}, signal});
    if (response.status === 401) { const error = new Error('登录已失效，请重新登录。'); error.status=401; throw error; }
    if (response.status === 403) { const error = new Error('当前会话无读取权限。'); error.status=403; throw error; }
    if (!response.ok) { const error = new Error(`HTTP ${response.status}，请检查服务端状态。`); error.status=response.status; throw error; }
    return response.json();
  }
  async function hydrate(row, scope, signal) {
    const latest = await getJSON(`/api/events/${encodeURIComponent(row.event_id)}/dossier`, signal);
    if (!current(scope) || !verifyLatestDossier(row, latest)) return null;
    try {
      const frozen = await getJSON(`/api/events/${encodeURIComponent(row.event_id)}/dossier/revisions/${row.version}`, signal);
      return {row, originals:frozenEvidence(row, frozen), evidenceError:''};
    } catch (error) {
      if (error.status === 401 || error.status === 403) throw error;
      return {row, originals:[], evidenceError:
        '保存版本的冻结原文暂不可读取；未代用当前事件或其他事件的原文。请进入原生研判卡核对。'};
    }
  }
  async function refresh() {
    if (stopped || !isAuthenticated() || !readyPane()) return;
    const scope = ++generation;
    watermarkRequest++; controller?.abort();
    const active = new AbortController(); controller = active;
    const timer = clock.setTimeout(() => active.abort(), 16000);
    loaded = true; status = 'loading'; feedback = ''; selected = []; skipped = 0;
    render();
    try {
      const queue = reviewFocusContract(await getJSON('/api/radar/reviews', active.signal));
      if (!current(scope) || active.signal.aborted) return;
      snapshot = queue;
      if (!queue.enabled) { status = 'forbidden'; render(); return; }
      // Bounded enrichment (max eight). One owner-scoped latest check and one
      // immutable version read per row; no additional user/business mutations.
      const results = await Promise.allSettled(queue.chosen.map(row => hydrate(row, scope, active.signal)));
      if (!current(scope) || active.signal.aborted) return;
      for (const result of results) {
        if (result.status === 'fulfilled' && result.value) selected.push(result.value);
        else {
          skipped++;
          if (result.status === 'rejected' && [401,403].includes(result.reason?.status)) {
            throw result.reason;
          }
        }
      }
      if (skipped) feedback = '已保存研判可能在其他窗口更改，或部分版本暂无法读取；这些行不会冒充当前到期。';
      status = 'ready'; render();
    } catch (error) {
      if (!current(scope) || active.signal.aborted) return;
      snapshot = null; selected=[];
      status = error.status === 403 ? 'forbidden' : 'error';
      feedback = text(error.message, 220) || '请求失败'; render();
    } finally {
      clock.clearTimeout(timer);
      if (controller === active) controller = null;
    }
  }
  function onNavigation(event) {
    if (event.target?.closest?.('#nav-radar')) {
      clock.setTimeout(() => { insert(); if (readyPane()) refresh(); }, 160);
    }
    if (event.target?.closest?.('#logout')) {
      generation++; controller?.abort(); snapshot = null;
      selected=[]; loaded=false; status='idle'; root.remove();
    }
  }
  function onDetailClosed(event) {
    if (event.target?.id === 'detail-dialog' && readyPane()) refresh();
  }
  function start() {
    if (stopped || observer) return;
    doc.addEventListener('click', onNavigation, true);
    doc.addEventListener('close', onDetailClosed, true);
    let queued = false;
    observer = new win.MutationObserver(() => {
      // Native V132 replaces whole pane; ignore child changes inside our UI.
      if (navRef === doc.querySelector('#nav-radar') &&
          root.parentElement === doc.getElementById('radar-pane')) return;
      if (queued) return;
      queued = true;
      clock.setTimeout(() => { queued = false; insert(); }, 20);
    });
    observer.observe(doc.getElementById('app') || doc.body, {childList:true,subtree:true});
    insert();
  }
  function destroy() {
    stopped=true; generation++; controller?.abort(); watermarkRequest++;
    observer?.disconnect(); observer=null;
    doc.removeEventListener('click', onNavigation, true);
    doc.removeEventListener('close', onDetailClosed, true);
    root.remove();
  }
  return {start, refresh, destroy, root};
}

if (typeof document !== "undefined" && typeof window !== "undefined") { createReviewFocus().start(); }

})();
/* FRONTIER_ADDON_END:review-focus */

/* FRONTIER_ADDON_BEGIN:evidence-changes */
;(() => {
"use strict";
/** V134 current-local-evidence vs latest owner-frozen dossier, fail-closed UI contract.
 * This deliberately does NOT interpret user's falsification or source counts as truth.
 */

const CHANGE_CLASS = 'fr-evidence-changes';
const obj = v => v !== null && typeof v === 'object' && !Array.isArray(v);
const int = v => Number.isSafeInteger(v) && v >= 0;
const zoned = v => typeof v === 'string' && v.length < 80 &&
  /(?:Z|[+-]\d\d:\d\d)$/i.test(v) && Number.isFinite(Date.parse(v));
const fail = () => { throw new TypeError('保存基线／当前出处变化契约无法核对，停止展示，不能宣称无新增。'); };

const short = (s, n = 230) => typeof s === 'string' ? s.trim().slice(0, n) : '';

/** Navigation gate; does not fetch, resolve DNS or verify site ownership. */

function originalLink(value) {
  if (typeof value !== 'string' || value.length > 2048 ||
      /[\u0000-\u0020\u007f\\]/.test(value) ||
      !/^https?:\/\//i.test(value)) return null;
  try {
    const url = new URL(value);
    if (!['http:', 'https:'].includes(url.protocol) ||
        url.username || url.password || value.split('://')[1]?.split('/')[0].includes('@') ||
        url.hash || !url.hostname) return null;
    const h = url.hostname.toLowerCase().replace(/\.$/, '').replace(/^\[|\]$/g, '');
    if (!h.includes('.') || h.includes(':') ||
        /^(?:\d+\.?)+$/.test(h) ||
        /(?:^|\.)(?:localhost|local|internal|lan|home|home\.arpa|nip\.io|sslip\.io|lvh\.me|localtest\.me)$/.test(h)) return null;
    const secret = /^(?:token|auth|key|apikey|accesskey|accesskeyid|keypairid|sig|signature|password|secret|session|sessionid|accesstoken|clientsecret|authorization|credential|ticket|code|jwt)$/i;
    if ([...url.searchParams.keys()].some(k => secret.test(k.replace(/[-_]/g, '')))) return null;
    return url.href;
  } catch { return null; }
}

function checkItem(row, expected) {
  if (!obj(row) || row.kind !== expected || !short(row.record_id, 120) ||
      typeof row.platform !== 'string' || typeof row.source_name !== 'string' ||
      row.link_status !== 'not_checked' || !originalLink(row.url) ||
      !/^[0-9a-f]{64}$/.test(row.sha256) ||
      (expected === 'existing_record_content_or_link_changed' &&
        !/^[0-9a-f]{64}$/.test(row.previous_sha256)) ||
      !['unknown', 'publisher_reported_unverified'].includes(row.publication_status) ||
      (row.publication_status === 'unknown' && row.published_at !== null) ||
      (row.publication_status !== 'unknown' && !zoned(row.published_at)) ||
      (row.first_ingested_at !== null && !zoned(row.first_ingested_at)) ||
      ![true, false, null].includes(row.ingested_after_save)) fail();
}

/** Only a complete bounded scan permits a no-change statement. */

function readEvidenceChanges(raw, eventId, version) {
  if (!obj(raw) || raw.event_id !== eventId || raw.base_version !== version ||
      !zoned(raw.base_saved_at) || !zoned(raw.computed_at) ||
      raw.basis !== 'owner_frozen_evidence_vs_current_linked_completed_records' ||
      !obj(raw.personal) || !obj(raw.truth) || !obj(raw.changes) ||
      typeof raw.notice !== 'string') fail();
  for (const k of ['judgment', 'falsification', 'support', 'review_on']) {
    if (typeof raw.personal[k] !== 'string') fail();
  }
  const truth = raw.truth;
  if (truth.event_occurred_at !== null ||
      truth.event_time_status !== 'not_determined_in_this_view' ||
      truth.independent_confirmation !== 'unknown' ||
      truth.claim_verified !== false || truth.falsification_detected !== false ||
      truth.human_judgment_changed !== false) fail();
  const c = raw.changes;
  if (!['complete', 'scan_limited'].includes(c.status) ||
      !int(c.baseline_count) || !int(c.scanned_count) || c.scanned_count > 500) fail();
  for (const [group, classification, count] of [
    ['new_links', 'new_to_frozen_link_candidate', 'new_link_count'],
    ['same_url_variants', 'same_url_different_local_text', 'same_url_variant_count'],
    ['edited_records', 'existing_record_content_or_link_changed', 'edited_record_count'],
  ]) {
    if (!Array.isArray(c[group]) || c[group].length > 6) fail();
    c[group].forEach(item => checkItem(item, classification));
    if (c.status === 'scan_limited' ? c[group].length > 0 :
        !int(c[count]) || c[count] < c[group].length) fail();
  }
  for (const key of ['new_link_count', 'same_url_variant_count', 'edited_record_count',
    'exact_repeat_count', 'unverifiable_count']) {
    if (c.status === 'complete' ? !int(c[key]) : c[key] !== null) fail();
  }
  if (c.status === 'complete' &&
      c.new_link_count + c.same_url_variant_count + c.edited_record_count +
      c.exact_repeat_count + c.unverifiable_count > c.scanned_count) fail();
  return raw;
}

const DATE_UNKNOWN = '未知（未证明出处发布时间）';

function collectedSinceSaved(row) {
  if (row.ingested_after_save === true) return '此记录首次收录晚于本人保存时刻；不是首发时间';
  if (row.ingested_after_save === false) return '首次收录不晚于本人保存；何时关联本事件未知';
  return '首次收录时刻无法核验';
}

/** One explicit, read-only action inside the existing native dossier history.
 * Covers Pro + Analyst; Analyst review-focus already links here. No new queue.
 */

function createEvidenceChangesUI({
  doc = globalThis.document,
  win = globalThis.window,
  request = globalThis.fetch?.bind(globalThis),
  clock = globalThis,
} = {}) {
  if (!doc || !win || !request) throw new Error('document/window/fetch required');
  const live = new Map();
  let stopped = false;
  const el = (tag, cls = '', val) => {
    const node = doc.createElement(tag);
    if (cls) node.className = cls;
    if (val !== undefined) node.textContent = String(val);
    return node;
  };
  function append(parent, ...nodes) { parent.append(...nodes); return parent; }
  function btn(value, fn) {
    const b = el('button', 'button secondary fr-change-go', value);
    b.type = 'button';
    b.addEventListener('click', fn);
    return b;
  }
  function valid(state, sequence) {
    return !stopped && state.generation === sequence && doc.contains(state.history);
  }
  async function getJSON(url, signal) {
    const response = await request(url, {method:'GET', credentials:'same-origin',
      cache:'no-store', headers:{Accept:'application/json'}, signal});
    if (!response?.ok) {
      const error = new Error('GET ' + (response?.status || '未知错误'));
      error.status = response?.status;
      throw error;
    }
    return response.json();
  }
  function renderSource(item) {
    const box = el('article', 'fr-change-source');
    box.dataset.record = item.record_id;
    const href = originalLink(item.url);
    const heading = el('strong', '', short(item.source_name, 90) || '记录出处未注明');
    append(box, heading);
    append(box, el('p', 'fr-change-meta', '记录 ' + short(item.record_id, 120) +
      ' · ' + short(item.platform, 30)));
    append(box, el('p', 'fr-change-meta',
      '出处发布时间：' + (item.published_at || DATE_UNKNOWN) +
      '（' + (item.publication_status === 'unknown' ? '未知' : '平台标注、未核真') + '）'));
    append(box, el('p', 'fr-change-meta',
      '首次收录：' + (item.first_ingested_at || '未知') +
      '；' + collectedSinceSaved(item)));
    if (item.previous_sha256) {
      append(box, el('p', 'fr-change-meta',
        '同记录冻结正文 SHA-256：' + item.previous_sha256.slice(0, 14) +
        '… → 当前 ' + item.sha256.slice(0, 14) +
        '…（不是内容真实性验证）'));
    }
    const a = el('a', 'fr-change-link', '打开本地关联的原始出处 ↗');
    a.href = href; a.target = '_blank'; a.rel = 'noopener noreferrer';
    a.referrerPolicy = 'no-referrer';
    append(box, a);
    return box;
  }
  function renderGroup(target, label, samples, count, caveat) {
    if (!count) return;
    const group = el('div', 'fr-change-group');
    append(group, el('h5', '', label + ' · ' + count + ' 条'));
    append(group, el('p', 'fr-change-note', caveat));
    for (const item of samples) append(group, renderSource(item));
    if (count > samples.length) append(group, el('p', 'fr-change-note',
      '仅展示前 ' + samples.length + ' 条；实际匹配数量已单独计数，不冒充全部展示。'));
    append(target, group);
  }
  function renderResult(state, data) {
    const output = state.output;
    output.replaceChildren();
    output.hidden = false;
    append(output, el('h4', '', '本人已保存 v' + data.base_version + ' → 本地当前出处'));
    append(output, el('p', 'fr-change-intro',
      '基线：' + data.base_saved_at + '；本次本地计算：' + data.computed_at +
      '。这是冻结集合与当前已关联原文的差异，不是两个已保存版本的比较。'));
    const personal = el('section', 'fr-change-personal');
    append(personal, el('h5', '', '本人保存的判断／已知反证条件（未自动检验）'));
    append(personal, el('p', 'fr-change-saved', '当时本人判断：' +
      (data.personal.judgment || '未填写')));
    append(personal, el('p', 'fr-change-falsification', '当时写下的反证条件：' +
      (data.personal.falsification || '未填写；需要本人补充')));
    append(personal, el('p', 'fr-change-saved', '当时支持／疑问：' +
      (data.personal.support || '未填写')));
    append(output, personal);
    const c = data.changes;
    if (c.status === 'scan_limited') {
      append(output, el('p', 'fr-change-warning',
        '本地记录触及 ' + c.scanned_count +
        ' 条扫描上限，无法判断此次有哪些真正差异；不显示“零新增”或截断的新增来源。'));
    } else {
      append(output, el('p', 'fr-change-summary',
        '新 URL 原文候选 ' + c.new_link_count +
        ' · 同 URL 内容差异 ' + c.same_url_variant_count +
        ' · 同记录内容／链接变更 ' + c.edited_record_count +
        ' · 精确重复 ' + c.exact_repeat_count +
        ' · 不可安全跳转 ' + c.unverifiable_count));
      if (!(c.new_link_count || c.same_url_variant_count || c.edited_record_count ||
            c.exact_repeat_count || c.unverifiable_count)) {
        append(output, el('p', 'fr-change-empty',
          '相对上次冻结版，本地已完成且关联此事件的记录未见可辨变化；不代表外部世界没有新证据。'));
      }
      renderGroup(output, '新增 URL 的本地原文候选', c.new_links, c.new_link_count,
        '与冻结版的链接、足够长的全文没有发现精确重复；不是首发，也不等于独立证实。');
      renderGroup(output, '同一 URL 的本地文本变体', c.same_url_variants,
        c.same_url_variant_count, '观察到本地文本不同，不证明发布者修改了在线网页或撤回原主张。');
      renderGroup(output, '相同记录 ID 的内容／链接变化', c.edited_records,
        c.edited_record_count, '同一记录在派生库中的内容或链接变化；不是第二个独立出处。');
      if (c.exact_repeat_count) append(output, el('p', 'fr-change-repeats',
        '精确重复候选 ' + c.exact_repeat_count +
        ' 条：同 URL 且完整文字相同，或不同 URL 的较长正文完全相同。未作为新增出处展示，不能据此反推所有转载关系。'));
      if (c.unverifiable_count) append(output, el('p', 'fr-change-warning',
        '另有 ' + c.unverifiable_count +
        ' 条本地记录无法安全核对链接或结构，未加入可点击新增来源。'));
    }
    append(output, el('p', 'fr-change-notice',
      '事件发生时间：此视图不判断（未知不能用发布时间／收录时间代填）。' +
      '来源独立性：未知；主张核实：否。反证是否满足：未检测。判断版本：未改变。'));
    append(output, el('small', 'fr-change-notice', data.notice));
  }
  async function inspect(state) {
    const sequence = ++state.generation;
    state.abort?.abort();
    const controller = new AbortController();
    state.abort = controller;
    const timeout = clock.setTimeout(() => controller.abort(), 14000);
    state.go.disabled = true;
    state.status.textContent = '正从服务器读取本人最新保存版本与当前关联原文；不会更改判断。';
    state.output.hidden = true;
    state.output.replaceChildren();
    try {
      const path = '/api/events/' + encodeURIComponent(state.eventId) + '/dossier';
      const head = await getJSON(path, controller.signal);
      if (!valid(state, sequence)) return;
      if (!head || head.event_id !== state.eventId ||
          !Number.isSafeInteger(head.version) || head.version < 0) {
        throw new TypeError('最新版本无法核验');
      }
      if (head.version === 0) {
        state.status.textContent = '该事件尚无本人保存的研判；请先在原生研判卡人工保存，不能虚构昨日判断。';
        return;
      }
      const url = path + '/changes?version=' + head.version;
      const checked = readEvidenceChanges(await getJSON(url, controller.signal),
        state.eventId, head.version);
      if (!valid(state, sequence)) return;
      renderResult(state, checked);
      state.status.textContent = checked.changes.status === 'complete'
        ? '已按最新保存 v' + head.version + ' 核对本地来源差异（只读）；如有更新可主动再核对。'
        : '保存版本已找到，但扫描被截断：变化未知，未展示虚假零值。';
    } catch (error) {
      if (!valid(state, sequence)) return;
      const msg = error?.name === 'AbortError' ? '请求已取消；未验证是否有变化。'
        : error?.status === 401 ? '会话已失效，请重新登录；不能视为无新来源。'
        : error?.status === 403 ? '当前权限无法读取 Pro／Analyst 复核差异（无购买入口）。'
        : error?.status === 409 ? '保存版本已在其它会话变更，请重新主动核对。'
        : error?.status === 404 ? '找不到本人保存的研判，不能替用其它用户历史。'
        : '无法校验当前差异：' + short(error?.message, 180);
      state.status.textContent = msg;
      state.output.hidden = true;
    } finally {
      clock.clearTimeout(timeout);
      if (valid(state, sequence)) state.go.disabled = false;
    }
  }
  function bind(history) {
    const dossier = history.closest('.dossier[data-event-id]');
    const eventId = dossier?.dataset.eventId;
    if (!eventId || live.has(history)) return;
    const panel = el('section', CHANGE_CLASS);
    panel.setAttribute('aria-label', '上次本人研判至本地当前的出处变化');
    append(panel, el('h4', '', '上次判断后，有哪些可重新核对的原文？'));
    append(panel, el('p', 'fr-change-intro',
      '不重复上方“比较两版”功能：即使目前仅保存一版，也可手动核对其后本地证据集合变化。'));
    const go = btn('对照最新保存版与现在（只读）', () => inspect(state));
    const status = el('p', 'fr-change-status', '尚未读取当前差异；展开历史后点击按钮核对。');
    status.setAttribute('role', 'status');
    const output = el('div', 'fr-change-result');
    output.hidden = true;
    append(panel, go, status, output);
    history.append(panel);
    const state = {history, eventId, go, status, output, panel,
      generation: 0, abort: null, listObserver: null, toggle: null};
    live.set(history, state);
    const list = history.querySelector('.dossier-history-list');
    if (list) {
      state.listObserver = new win.MutationObserver(() => {
        if (state.output.hidden) return;
        state.generation++;
        state.abort?.abort();
        state.output.hidden = true;
        state.status.textContent = '历史修订可能已变化；旧差异已隐藏，请重新点击核对最新版本。';
      });
      state.listObserver.observe(list, {childList:true});
    }
    state.toggle = () => {
      if (!history.open) {
        state.generation++;
        state.abort?.abort();
        state.output.hidden = true;
        state.status.textContent = '历史已收起，前次差异已隐藏；重新打开后主动核对。';
        state.go.disabled = false;
      }
    };
    history.addEventListener('toggle', state.toggle);
  }
  function cleanup(state) {
    state.generation++;
    state.abort?.abort();
    state.listObserver?.disconnect();
    state.history.removeEventListener('toggle', state.toggle);
    state.panel.remove();
    live.delete(state.history);
  }
  function scan() {
    if (stopped) return;
    for (const [history, state] of live) if (!doc.contains(history)) cleanup(state);
    for (const history of doc.querySelectorAll('.dossier[data-event-id] .dossier-history')) {
      bind(history);
    }
  }
  const observer = new win.MutationObserver(scan);
  observer.observe(doc.body || doc.documentElement, {childList:true, subtree:true});
  scan();
  return {scan, destroy() { stopped=true; observer.disconnect();
    for (const state of [...live.values()]) cleanup(state); }};
}
if (typeof document !== 'undefined' && typeof window !== 'undefined') {
  createEvidenceChangesUI();
}

})();
/* FRONTIER_ADDON_END:evidence-changes */
