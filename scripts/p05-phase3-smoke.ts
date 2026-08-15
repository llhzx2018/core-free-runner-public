import assert from 'node:assert/strict';
import pg from 'pg';
import { FakeGscAdapter } from './src/server/phase1/providers.js';
import { syncGsc } from './src/server/phase1/sync.js';
import { crawlSite, createNetworkFetcher } from './src/server/phase1/crawler.js';

const databaseUrl = process.env.DATABASE_URL;
const adminUsername = process.env.VF_ADMIN_USERNAME;
const adminPassword = process.env.VF_ADMIN_PASSWORD;
const base = process.env.PHASE3_BASE_URL ?? 'http://127.0.0.1:3105';
if (!databaseUrl || !adminUsername || !adminPassword) throw new Error('PHASE3_ENV_REQUIRED');

const { Pool } = pg;
const pool = new Pool({ connectionString: databaseUrl });
let cookie = '';
let csrf = '';

async function request(path, method = 'GET', body) {
  const response = await fetch(base + path, {
    method,
    headers: {
      ...(cookie ? { cookie } : {}),
      ...(csrf ? { 'x-csrf-token': csrf } : {}),
      'content-type': 'application/json',
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const json = await response.json().catch(() => ({}));
  return { response, json };
}

async function login() {
  const response = await fetch(base + '/api/auth/login', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ username: adminUsername, password: adminPassword }),
  });
  assert.equal(response.status, 200, 'admin login');
  cookie = response.headers.get('set-cookie')?.split(';', 1)[0] ?? '';
  const json = await response.json();
  csrf = json.csrfToken;
  assert.ok(cookie && csrf, 'session + csrf');
}

try {
  const health = await request('/api/health');
  assert.equal(health.response.status, 200, 'health');
  assert.equal(health.json.version, '1.0.0');
  assert.equal(health.json.schema, 1);
  await login();

  let x = await request('/api/projects', 'POST', { name: 'Phase 3 Synthetic Project' });
  assert.equal(x.response.status, 201);
  const projectId = x.json.project.id;
  x = await request('/api/websites', 'POST', {
    projectId,
    name: 'Phase 3 Synthetic Site',
    url: 'https://example.test/',
    businessValue: 'HIGH',
    language: 'zh-CN',
    countryCode: 'US',
    siteType: 'CONTENT',
  });
  assert.equal(x.response.status, 201);
  const websiteId = x.json.website.id;

  x = await request('/api/providers/accounts', 'POST', { provider: 'GSC', externalAccountId: 'phase3-gsc@example.test', displayName: 'Phase 3 GSC' });
  const gscAccount = x.json.account.id;
  x = await request(`/api/providers/accounts/${gscAccount}/discover`, 'POST', { kind: 'GSC' });
  const gscProperty = x.json.properties[0].id;
  x = await request('/api/data-sources', 'POST', { websiteId, propertyId: gscProperty });
  const gscSource = x.json.dataSource.id;

  x = await request(`/api/data-sources/${gscSource}/sync`, 'POST', { from: '2026-08-12', to: '2026-08-14' });
  assert.equal(x.json.result.state, 'FRESH');
  assert.equal(x.json.result.pages, 2, 'GSC pagination');
  assert.equal(x.json.result.finality, 'PRELIMINARY', 'GSC finality');
  let factCount = Number((await pool.query('SELECT count(*) c FROM search_observation_daily WHERE website_id=$1', [websiteId])).rows[0].c);
  assert.equal(factCount, 3);
  await request(`/api/data-sources/${gscSource}/sync`, 'POST', { from: '2026-08-12', to: '2026-08-14' });
  assert.equal(Number((await pool.query('SELECT count(*) c FROM search_observation_daily WHERE website_id=$1', [websiteId])).rows[0].c), 3, 'repeat sync idempotent');
  assert.equal(Number((await pool.query('SELECT count(DISTINCT source_key) c FROM search_observation_daily WHERE website_id=$1', [websiteId])).rows[0].c), 3, 'source keys unique');

  const empty = await syncGsc(pool, {
    dataSourceId: gscSource,
    websiteId,
    adapter: new FakeGscAdapter([]),
    from: '2026-08-15',
    to: '2026-08-15',
    pageSize: 2,
  });
  assert.equal(empty.state, 'FRESH');
  assert.equal(empty.inserted, 0, 'empty provider result inserts no synthetic zero row');
  assert.equal(Number((await pool.query('SELECT count(*) c FROM search_observation_daily WHERE website_id=$1', [websiteId])).rows[0].c), 3, 'missing row is not absolute zero');

  let firstPage = true;
  const interruptedAdapter = {
    async discoverProperties() { return []; },
    async fetchSearch() {
      if (firstPage) {
        firstPage = false;
        return {
          rows: [{ date: '2026-08-16', query: 'phase3 interrupted', page: 'https://example.test/interrupted', country: 'US', device: 'DESKTOP', clicks: 9, impressions: 90, ctr: 0.1, position: 7, finality: 'FINAL' }],
          nextCursor: 'next', state: 'FRESH', finality: 'FINAL',
        };
      }
      throw Object.assign(new Error('TRANSIENT'), { code: 'TRANSIENT' });
    },
  };
  const interrupted = await syncGsc(pool, { dataSourceId: gscSource, websiteId, adapter: interruptedAdapter, from: '2026-08-16', to: '2026-08-16', pageSize: 1 });
  assert.equal(interrupted.state, 'FAILED');
  assert.equal(Number((await pool.query('SELECT count(*) c FROM search_observation_daily WHERE website_id=$1', [websiteId])).rows[0].c), 3, 'interrupted sync rolls back partial facts');

  x = await request(`/api/data-sources/${gscSource}/sync`, 'POST', { fixtureFailure: 'PARTIAL' });
  assert.equal(x.json.result.state, 'PARTIAL');
  x = await request(`/api/opportunities/rebuild/${websiteId}`, 'POST', {});
  assert.equal(x.json.count, 0, 'partial source cannot create business opportunities');

  x = await request(`/api/data-sources/${gscSource}/sync`, 'POST', { fixtureFailure: 'RATE_LIMIT' });
  assert.equal(x.json.result.state, 'RATE_LIMITED');
  let source = (await pool.query('SELECT state,next_retry_at FROM data_sources WHERE id=$1', [gscSource])).rows[0];
  assert.equal(source.state, 'RATE_LIMITED');
  assert.ok(source.next_retry_at, '429 schedules retry');

  x = await request(`/api/data-sources/${gscSource}/sync`, 'POST', { fixtureFailure: 'TRANSIENT' });
  assert.equal(x.json.result.state, 'FAILED');
  source = (await pool.query('SELECT state,next_retry_at FROM data_sources WHERE id=$1', [gscSource])).rows[0];
  assert.equal(source.state, 'FAILED');
  assert.ok(source.next_retry_at, '5xx/transient schedules retry');
  x = await request(`/api/alerts/rebuild/${websiteId}`, 'POST', {});
  assert.ok(x.json.items.some((a) => a.type === 'DATA_SOURCE_DISCONNECT'));
  assert.ok(!x.json.items.some((a) => a.type === 'TRAFFIC_DROP'), 'failed source does not manufacture traffic drop');

  await request(`/api/data-sources/${gscSource}/sync`, 'POST', {});
  await pool.query("UPDATE data_sources SET state='STALE',last_good_at=now()-interval '48 hours' WHERE id=$1", [gscSource]);
  x = await request(`/api/alerts/rebuild/${websiteId}`, 'POST', {});
  assert.ok(x.json.items.some((a) => a.type === 'LONG_STALE_SYNC'));
  assert.ok(!x.json.items.some((a) => a.type === 'TRAFFIC_DROP'), 'stale source does not manufacture traffic drop');
  await request(`/api/data-sources/${gscSource}/sync`, 'POST', {});

  x = await request('/api/providers/accounts', 'POST', { provider: 'GA4', externalAccountId: 'phase3-ga4@example.test', displayName: 'Phase 3 GA4' });
  const gaAccount = x.json.account.id;
  x = await request(`/api/providers/accounts/${gaAccount}/discover`, 'POST', { kind: 'GA4' });
  const gaProperty = x.json.properties[0].id;
  x = await request('/api/data-sources', 'POST', { websiteId, propertyId: gaProperty });
  const gaSource = x.json.dataSource.id;
  x = await request(`/api/data-sources/${gaSource}/sync`, 'POST', {});
  assert.equal(x.json.result.state, 'FRESH');

  for (const path of ['/api/dashboard', '/api/website-center?limit=20', '/api/keywords?limit=20', '/api/pages?limit=20', '/api/search?q=Phase%203', '/api/opportunities', '/api/alerts', '/api/audit/history', '/api/settings']) {
    x = await request(path);
    assert.equal(x.response.status, 200, path);
  }
  const search = await request('/api/search?q=Phase%203');
  assert.equal(search.json.serverSide, true);
  assert.ok(search.json.items.length >= 2, 'global search finds project/website');

  x = await request(`/api/opportunities/rebuild/${websiteId}`, 'POST', {});
  assert.ok(Array.isArray(x.json.items));
  x = await request('/api/audit/single', 'POST', { websiteId, url: 'https://example.test/page', status: 200, html: '<html><head><title>Phase 3</title><meta name="description" content="fixture"></head><body><h1>Phase 3</h1></body></html>' });
  assert.equal(x.response.status, 200);

  const fixtureRoot = 'https://example.test/';
  x = await request('/api/audit/site', 'POST', {
    websiteId,
    websiteUrl: fixtureRoot,
    budget: 20,
    maxDepth: 3,
    seeds: [{ url: fixtureRoot, source: 'SITEMAP' }],
    fixtures: {
      'https://example.test/robots.txt': { status: 200, body: 'User-agent: *\nDisallow: /private\nSitemap: https://example.test/sitemap.xml' },
      'https://example.test/sitemap.xml': { status: 404, body: 'missing' },
      'https://example.test/': { status: 200, body: '<html><head><title>Home</title><meta name="description" content="fixture"></head><body><h1>Home</h1><a href="/private">Private</a><a href="/missing">Missing</a></body></html>' },
      'https://example.test/private': { status: 200, body: '<html><head><title>Private</title><meta name="description" content="fixture"></head><body><h1>Private</h1></body></html>' },
      'https://example.test/missing': { status: 404, body: '<html><title>Missing</title></html>' },
    },
  });
  assert.equal(x.response.status, 200);
  assert.ok(x.json.findings.some((f) => f.ruleKey === 'ROBOTS_DISALLOW'), 'whole-site crawl must integrate robots.txt');
  assert.ok(x.json.findings.some((f) => f.ruleKey === 'SITEMAP_ERROR'), 'whole-site crawl must integrate sitemap status');

  const timeoutCrawl = await crawlSite({
    websiteUrl: 'https://example.test/',
    seeds: [{ url: 'https://example.test/timeout', source: 'SEED' }],
    fetcher: async () => { throw new Error('TIMEOUT'); },
    budget: 5,
  });
  assert.equal(timeoutCrawl.pages[0]?.state, 'FAILED');
  assert.equal(timeoutCrawl.pages[0]?.error, 'TIMEOUT');

  const limited = await crawlSite({
    websiteUrl: 'https://example.test/',
    seeds: [{ url: 'https://example.test/', source: 'SEED' }],
    fetcher: async (url) => ({ status: 200, url, body: '<a href="/a">a</a><a href="/b">b</a>' }),
    budget: 1,
  });
  assert.equal(limited.state, 'PARTIAL');
  assert.ok(limited.checkpoint.pending.length >= 1, 'crawl checkpoint retained');
  const resumed = await crawlSite({
    websiteUrl: 'https://example.test/',
    seeds: [],
    fetcher: async (url) => ({ status: 200, url, body: '<html><title>ok</title></html>' }),
    budget: 10,
    resume: limited.checkpoint,
  });
  assert.ok(resumed.pages.length >= 1, 'crawl resumes from checkpoint');

  const networkFetcher = createNetworkFetcher({
    resolver: async () => [{ address: '203.0.113.9', family: 4 }],
    fetchImpl: async (url) => {
      if (String(url) === 'https://safe.example/') return new Response('', { status: 302, headers: { location: 'http://169.254.169.254/latest/meta-data/' } });
      return new Response('<html></html>', { status: 200, headers: { 'content-type': 'text/html' } });
    },
  });
  await assert.rejects(() => networkFetcher('https://safe.example/'), /SSRF_BLOCKED|REDIRECT_OUT_OF_SCOPE_OR_SSRF/);

  x = await request('/api/segments', 'POST', { websiteId, name: 'Phase 3 Segment', rules: [{ type: 'PREFIX', value: '/blog' }] });
  assert.equal(x.response.status, 201);
  x = await request('/api/changes', 'POST', { websiteId, changeType: 'TITLE_CHANGE', description: 'phase3 synthetic change' });
  assert.equal(x.response.status, 201);

  const schema = (await pool.query('SELECT schema_identity,schema_version FROM schema_metadata WHERE singleton=true')).rows[0];
  assert.equal(schema.schema_identity, 'VF-SEO-SCHEMA@1');
  assert.equal(schema.schema_version, 1);
  factCount = Number((await pool.query('SELECT count(*) c FROM search_observation_daily WHERE website_id=$1', [websiteId])).rows[0].c);
  assert.equal(factCount, 3);

  console.log(JSON.stringify({
    result: 'PASS',
    projectId,
    websiteId,
    gscSource,
    gaSource,
    searchFacts: factCount,
    gates: ['CORE_FUNCTIONAL', 'FAKE_GSC_GA4', 'SYNC_RETRY_IDEMPOTENCY', 'CRAWLER_SAFETY'],
  }));
} finally {
  await pool.end();
}
