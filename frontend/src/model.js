export const SOURCE_LABELS = { telegram: 'Telegram', x: 'X', twitter: 'X', youtube: 'YouTube' };
export const CATEGORY_LABELS = {
  ai: '人工智能', artificial_intelligence: '人工智能', technology: '科技', tech: '科技',
  science: '科学', space: '太空', aerospace: '航天', business: '商业', finance: '金融',
  geopolitics: '全球动态', politics: '政经', energy: '能源', climate: '气候', health: '生命科学',
  biotech: '生物科技', biotechnology: '生物科技', robotics: '机器人', chips: '芯片',
  semiconductors: '半导体', security: '安全', other: '其他', general: '综合'
};
export const categoryLabel = (v) => CATEGORY_LABELS[String(v || '').toLowerCase()] || v || '待分类';
export const sourceLabel = (v) => SOURCE_LABELS[String(v || '').toLowerCase()] || v || '来源';
export const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, Number(v) || 0));
export const importance = (event) => Math.round(clamp(event?.importance, 0, 100));
export const validDate = (value) => {
  if (!value) return null;
  const date = new Date(value);
  return Number.isFinite(date.getTime()) ? date : null;
};
const dateFormatter = new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit' });
const timeFormatter = new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false });
export const formatDate = (value, withTime = false) => {
  const date = validDate(value);
  return date ? (withTime ? timeFormatter : dateFormatter).format(date) : '尚未确认';
};
export function eventTime(event, compact = false) {
  const start = validDate(event?.event_time_start);
  if (!start || event?.event_time_precision === 'unknown' || event?.event_time_status === 'unknown') return '事件时间待确认';
  const status = event.event_time_status === 'scheduled' ? '预计 ' : event.event_time_status === 'inferred' ? '推定 ' : '';
  if (event.event_time_precision === 'month') {
    return status + new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', year: 'numeric', month: 'long' }).format(start);
  }
  const base = formatDate(start, event.event_time_precision === 'exact' && compact);
  const end = validDate(event.event_time_end);
  if (end && event.event_time_precision === 'range') return `${status}${base} — ${formatDate(end)}`;
  return status + base + (event.event_time_precision === 'exact' && !compact ? ` ${new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', hour: '2-digit', minute: '2-digit', hour12: false }).format(start)}` : '');
}
export function knownEventTime(event) {
  return event?.event_time_status !== 'unknown' && event?.event_time_precision !== 'unknown' ? validDate(event?.event_time_start) : null;
}
export function coordinates(event) {
  if (event?.location_status === 'unknown' || event?.location_status === 'global') return [];
  return (Array.isArray(event?.locations) ? event.locations : []).filter((l) =>
    typeof l.latitude === 'number' && typeof l.longitude === 'number' &&
    Number.isFinite(l.latitude) && Number.isFinite(l.longitude) &&
    Math.abs(l.latitude) <= 90 && Math.abs(l.longitude) <= 180 && l.status !== 'unknown'
  );
}
export function locationLabel(event) {
  const locations = coordinates(event);
  if (locations.length) return [...new Set(locations.map((l) => l.name || l.country_code || '已定位'))].join(' · ');
  return event?.location_status === 'global' ? '全球性事件' : '地点待确认';
}
export function safeURL(value) {
  try {
    const url = new URL(String(value));
    return ['https:', 'http:'].includes(url.protocol) ? url.href : null;
  } catch { return null; }
}
export function normalizeFacets(value) {
  if (Array.isArray(value)) return value.map((v) => typeof v === 'string' ? { value: v, count: null } : { value: String(v.value ?? v.name ?? ''), count: Number.isFinite(v.count) ? v.count : null }).filter((v) => v.value);
  if (value && typeof value === 'object') return Object.entries(value).map(([name, count]) => ({ value: name, count }));
  return [];
}
export function makeQuery(filters, offset = 0) {
  const q = new URLSearchParams({ sort: filters.sort || 'importance', limit: '100', offset: String(offset) });
  for (const key of ['q', 'source', 'category']) if (filters[key]) q.set(key, filters[key]);
  if (filters.bookmarked) q.set('bookmarked', '1');
  // Browser date inputs represent China calendar days; before is exclusive.
  if (filters.after) q.set('after', new Date(`${filters.after}T00:00:00+08:00`).toISOString());
  if (filters.before) {
    const before = new Date(`${filters.before}T00:00:00+08:00`);
    before.setUTCDate(before.getUTCDate() + 1);
    q.set('before', before.toISOString());
  }
  return q;
}
export const stateLabel = (state) => ({ healthy: '运行正常', running: '运行中', idle: '待机', partial: '部分可用', degraded: '需要关注', checking: '检查中', offline: '离线', disabled: '未启用', error: '异常', unavailable: '暂不可用', pending: '等待处理', ready: '已就绪', daily_limit: '今日整理额度已用完', rate_limited: '请求较多，等待重试', paused: '已暂停' }[state] || state || '待检查');
export function elapsed(value) {
  const date = validDate(value);
  if (!date) return '尚无成功记录';
  const minutes = Math.max(0, Math.floor((Date.now() - date.getTime()) / 60000));
  if (minutes < 1) return '刚刚';
  if (minutes < 60) return `${minutes} 分钟前`;
  if (minutes < 1440) return `${Math.floor(minutes / 60)} 小时前`;
  return `${Math.floor(minutes / 1440)} 天前`;
}
export function replayItems(items, cutoff) {
  if (cutoff == null) return items;
  return items.filter((event) => { const d = knownEventTime(event); return d && d.getTime() <= cutoff; });
}
