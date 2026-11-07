import test from 'node:test';
import assert from 'node:assert/strict';
import { coordinates, eventTime, knownEventTime, makeQuery, safeURL, replayItems, importance, normalizeFacets } from '../src/model.js';

test('unknown event dates never become publication dates or enter replay', () => {
  const unknown = { event_time_start: null, event_time_status: 'unknown', source_published_at: '2026-10-18T08:00:00Z' };
  assert.equal(eventTime(unknown), '事件时间待确认');
  assert.equal(knownEventTime(unknown), null);
  assert.deepEqual(replayItems([unknown], Date.now()), []);
});

test('inferred and scheduled dates retain their uncertainty labels', () => {
  assert.match(eventTime({ event_time_start: '2026-10-18T08:00:00Z', event_time_precision: 'day', event_time_status: 'inferred' }), /^推定 /);
  assert.match(eventTime({ event_time_start: '2026-10-18T08:00:00Z', event_time_precision: 'day', event_time_status: 'scheduled' }), /^预计 /);
});

test('date filters use inclusive China calendar days with exclusive next-day boundary', () => {
  const query = makeQuery({ after: '2026-10-18', before: '2026-10-18', sort: 'event_time' });
  assert.equal(query.get('after'), '2026-10-17T16:00:00.000Z');
  assert.equal(query.get('before'), '2026-10-18T16:00:00.000Z');
});

test('country/world events do not fabricate a point from missing or coercible coordinates', () => {
  assert.deepEqual(coordinates({ location_status: 'global', locations: [{ latitude: 0, longitude: 0 }] }), []);
  assert.deepEqual(coordinates({ location_status: 'unknown', locations: [{ latitude: 1, longitude: 1 }] }), []);
  assert.deepEqual(coordinates({ location_status: 'located', locations: [{ latitude: null, longitude: null }, { latitude: '0', longitude: '0' }, { latitude: 91, longitude: 0 }, { latitude: 0, longitude: Infinity }] }), []);
  assert.equal(coordinates({ location_status: 'located', locations: [{ latitude: 0, longitude: 0 }] }).length, 1);
});

test('external source URLs reject script/data/file schemes', () => {
  assert.equal(safeURL('javascript:alert(1)'), null);
  assert.equal(safeURL('data:text/html,<script>alert(1)</script>'), null);
  assert.equal(safeURL('file:///etc/passwd'), null);
  assert.equal(safeURL('//untrusted.test'), null);
  assert.equal(safeURL('https://t.me/test/1'), 'https://t.me/test/1');
});

test('replay is governed by event time, excluding unknown records', () => {
  const events = [
    { id: 'a', event_time_start: '2026-01-01', event_time_status: 'explicit', event_time_precision: 'day' },
    { id: 'b', event_time_start: '2026-03-01', event_time_status: 'explicit', event_time_precision: 'day' },
    { id: 'c', event_time_start: null, event_time_status: 'unknown' }
  ];
  assert.deepEqual(replayItems(events, Date.parse('2026-02-01')).map((e) => e.id), ['a']);
  assert.equal(replayItems(events, null).length, 3);
});

test('importance clamps malformed values without affecting source text', () => {
  assert.equal(importance({ importance: 190 }), 100);
  assert.equal(importance({ importance: -4 }), 0);
  assert.equal(importance({ importance: 'bad' }), 0);
});

test('facets support agreed array contract without inserting markup', () => {
  assert.deepEqual(normalizeFacets([{ value: 'ai', count: 9 }]), [{ value: 'ai', count: 9 }]);
  assert.deepEqual(normalizeFacets(['chips']), [{ value: 'chips', count: null }]);
});
