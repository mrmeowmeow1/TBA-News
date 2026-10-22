// Frontend logic smoke test. Runs the real static/app.js against a minimal DOM stub (no browser needed):
//   node tests/frontend_smoke.js
// It checks logic (rendering, states, request de-duplication), not visual layout.
'use strict';
const fs = require('fs'), path = require('path'), vm = require('vm'), assert = require('assert');
class Node_ {
    constructor(tag) {
        this.tagName = String(tag).toUpperCase();
        this.children = [];
        this.attrs = {};
        this.listeners = {};
        this.className = '';
        this.hidden = false;
        this.style = {};
        this.dataset = {};
        this.parent = null;
        this._text = '';
        this.href = '';
        this.src = '';
        this.title = '';
        const self = this;
        this.classList = { add: c => { if (!self.className.split(' ').includes(c))
                self.className = (self.className + ' ' + c).trim(); }, remove: c => { self.className = self.className.split(' ').filter(x => x !== c).join(' '); }, toggle: (c, f) => { f ? self.classList.add(c) : self.classList.remove(c); }, contains: c => self.className.split(' ').includes(c) };
    }
    get textContent() { return this.children.length ? this.children.map(c => c.textContent).join('') : this._text; }
    set textContent(v) { this.children = []; this._text = String(v); }
    get firstChild() { if (!this.children.length)
        this.append(new Node_('#text')); return this.children[0]; }
    append(...nodes) { for (const n of nodes) {
        const node = typeof n === 'string' ? Object.assign(new Node_('#text'), { _text: n }) : n;
        node.parent = this;
        this.children.push(node);
    } }
    replaceChildren(...nodes) { this.children = []; this._text = ''; this.append(...nodes); }
    remove() { if (this.parent)
        this.parent.children = this.parent.children.filter(c => c !== this); this.parent = null; }
    setAttribute(k, v) { this.attrs[k] = String(v); }
    getAttribute(k) { return this.attrs[k]; }
    removeAttribute(k) { delete this.attrs[k]; if (k === 'src')
        this.src = ''; }
    addEventListener(t, fn) { (this.listeners[t] = this.listeners[t] || []).push(fn); }
    focus() { }
    querySelectorAll() { return []; }
    querySelector() { return null; }
    find(pred, out = []) { if (pred(this))
        out.push(this); this.children.forEach(c => c.find(pred, out)); return out; }
    byClass(c) { return this.find(n => n.classList.contains(c)); }
}
const click = n => (n.listeners.click || []).forEach(f => f({ target: n }));
const flush = () => new Promise(r => setTimeout(r, 0));
const registry = {};
const document = { activeElement: null, body: new Node_('body'), listeners: {},
    querySelector: s => (registry[s] = registry[s] || new Node_('div')), querySelectorAll: () => [],
    createElement: t => new Node_(t), createTextNode: t => Object.assign(new Node_('#text'), { _text: t }),
    addEventListener(t, fn) { (this.listeners[t] = this.listeners[t] || []).push(fn); } };
// --- scripted backend ----------------------------------------------------------------------------
const ITEMS = ['a', 'b', 'c'].map((k, i) => ({ id: k.repeat(20), title: `Story ${k}`, source: 'Example Times', url: `https://news.google.com/rss/articles/${k}`, published: '2026-10-14T10:00:00+00:00', description: 'Open this story for a short summary and its original source.', category: 'top', image: null }));
const calls = [];
let articleHandler = () => { throw new Error('no handler'); };
const json = (status, body) => ({ ok: status < 400, status, json: async () => body });
let recHandler = () => json(404, {});
const recCalls = [];
async function fetchMock(url, options) {
    calls.push(url);
    if (url.startsWith('/api/recommendations/')) {
        recCalls.push({ url, options });
        return recHandler(url, options);
    }
    if (url.startsWith('/api/news'))
        return json(200, { items: ITEMS, updated: 'now', cached: false });
    if (url.startsWith('/api/article/'))
        return articleHandler(url);
    throw new Error('unexpected fetch ' + url);
}
const ARTICLE = { summary_type: 'article', intro: 'Lead sentence of the story.', points: ['Point one.', 'Point two.'], background: ['Earlier context.'], next: ['A hearing is scheduled for next month.'], details: { names: ['Meera Kulkarni'], figures: ['₹8,400 crore'], dates: ['March 2027'] }, summary: 'x', message: null, retryable: false, source_words: 620, summary_words: 197 };
const UNAVAILABLE = { summary_type: 'unavailable', intro: '', points: [], background: [], next: [], details: {}, summary: '', message: 'The publisher restricted access to this article. Use the button below to read the original story.', retryable: true, reason: 'blocked' };
const DESCRIPTION = { summary_type: 'description', intro: 'Publisher description text.', points: [], background: [], next: [], details: {}, summary: 'Publisher description text.', message: 'The full article text could not be read, so this is the publisher\'s own short description, not a summary of the article.', retryable: true };
const ctx = vm.createContext({ document, fetch: fetchMock, console, URLSearchParams, AbortController, Date, Object, Promise, setTimeout, Map, Math, JSON,
    localStorage: { _d: {}, getItem(k) { return this._d[k] ?? null; }, setItem(k, v) { this._d[k] = v; } } });
ctx.window = ctx;
vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'static', 'app.js'), 'utf8'), ctx);
const $ = s => registry[s];
const articleCalls = () => calls.filter(c => c.startsWith('/api/article/'));
const results = [];
async function test(name, fn) { try {
    await fn();
    results.push([name, true]);
}
catch (e) {
    results.push([name, false, e]);
} }
(async () => {
    await flush();
    await test('feed renders one card per story with a placeholder underneath the image', async () => {
        const cards = $('#newsGrid').children;
        assert.strictEqual(cards.length, 3);
        const visual = cards[0].children[0];
        assert.ok(visual.byClass('card-glyph').length === 1 && visual.byClass('visual-caption').length === 1, 'placeholder drawn');
        const img = visual.find(n => n.tagName === 'IMG')[0];
        assert.strictEqual(img.loading, 'lazy');
        assert.ok(img.src.endsWith('/api/image/' + ITEMS[0].id));
    });
    await test('card image: load fades in; error removes image once and keeps placeholder (no loop)', async () => {
        const visual = $('#newsGrid').children[1].children[0];
        const img = visual.find(n => n.tagName === 'IMG')[0];
        img.onload();
        assert.ok(img.classList.contains('loaded'));
        const bad = $('#newsGrid').children[2].children[0].find(n => n.tagName === 'IMG')[0];
        bad.onerror();
        assert.strictEqual(bad.onerror, null);
        assert.strictEqual($('#newsGrid').children[2].children[0].find(n => n.tagName === 'IMG').length, 0);
        assert.strictEqual($('#newsGrid').children[2].children[0].byClass('card-glyph').length, 1);
    });
    let openFirst = () => { const readBtn = $('#newsGrid').children[0].find(n => n.className === 'read-btn')[0]; click(readBtn); };
    await test('loading indicator shows while the overview is pending; duplicate opens share one request', async () => {
        let release;
        articleHandler = () => new Promise(r => { release = () => r(json(200, ARTICLE)); });
        openFirst();
        const box = $('#modalSummary');
        assert.strictEqual(box.attrs['aria-busy'], 'true');
        assert.strictEqual(box.byClass('qr-loading').length, 1);
        assert.strictEqual($('#summaryLabel').textContent, 'LOADING…');
        assert.strictEqual($('#modalFigure').hidden, true);
        closeAndReopen();
        assert.strictEqual(articleCalls().length, 1, 'only one in-flight request');
        release();
        await flush();
    });
    function closeAndReopen() { click($('#closeModal')); openFirst(); }
    await test('article overview renders headings, bullets and chips; header/save/original still work', async () => {
        const box = $('#modalSummary');
        assert.strictEqual(box.attrs['aria-busy'], 'false');
        assert.strictEqual($('#summaryLabel').textContent, 'ARTICLE SUMMARY');
        assert.strictEqual($('#modalNote').hidden, true);
        assert.strictEqual(box.byClass('qr-intro')[0].textContent, 'Lead sentence of the story.');
        assert.deepStrictEqual(box.byClass('qr-block').map(b => b.children[0].textContent), ['Key developments', 'Background', 'What’s next', 'Names & places mentioned', 'Figures', 'Dates']);
        assert.strictEqual(box.byClass('qr-chip').length, 3);
        assert.ok(box.byClass('qr-meta')[0].textContent.includes('620-word'));
        assert.strictEqual($('#modalTitle').textContent, 'Story a');
        assert.ok($('#modalMeta').textContent.startsWith('Example Times · '));
        assert.strictEqual($('#readOriginal').href, ITEMS[0].url);
        assert.strictEqual($('#modalSave').textContent, '☆ Save story');
        click($('#modalSave'));
        assert.strictEqual($('#modalSave').textContent, '★ Saved');
        click($('#modalSave'));
        assert.strictEqual($('#modalSave').textContent, '☆ Save story');
    });
    await test('reopening a summarised article uses the client cache (no new request)', async () => {
        const before = articleCalls().length;
        closeAndReopen();
        await flush();
        assert.strictEqual(articleCalls().length, before);
        assert.strictEqual($('#summaryLabel').textContent, 'ARTICLE SUMMARY');
    });
    await test('modal image: hidden until it loads, hidden again on error, one-shot error handler', async () => {
        const img = $('#modalImage'), fig = $('#modalFigure');
        assert.ok(img.src.endsWith('/api/image/' + ITEMS[0].id));
        assert.strictEqual(fig.hidden, true);
        img.onload();
        assert.strictEqual(fig.hidden, false);
        closeAndReopen();
        assert.strictEqual(fig.hidden, true);
        img.onerror();
        assert.strictEqual(fig.hidden, true);
        assert.strictEqual(img.onerror, null);
    });
    const openSecond = () => click($('#newsGrid').children[1].find(n => n.className === 'read-btn')[0]);
    await test('unavailable: honest message, original link kept, retry refetches with ?retry=1 and recovers', async () => {
        articleHandler = () => json(200, UNAVAILABLE);
        openSecond();
        await flush();
        assert.strictEqual($('#summaryLabel').textContent, 'ARTICLE UNAVAILABLE');
        assert.strictEqual($('#modalNote').hidden, false);
        assert.ok($('#modalNote').textContent.includes('restricted access'));
        assert.strictEqual($('#readOriginal').href, ITEMS[1].url);
        const retry = $('#modalSummary').byClass('qr-retry')[0];
        assert.ok(retry, 'retry button');
        articleHandler = () => json(200, ARTICLE);
        click(retry);
        assert.strictEqual($('#summaryLabel').textContent, 'LOADING…');
        await flush();
        assert.ok(articleCalls().at(-1).endsWith('?retry=1'));
        assert.strictEqual($('#summaryLabel').textContent, 'ARTICLE SUMMARY');
        assert.strictEqual($('#modalNote').hidden, true);
    });
    await test('description-only result is clearly labelled and not styled as a full summary', async () => {
        articleHandler = () => json(200, DESCRIPTION);
        click($('#closeModal'));
        click($('#newsGrid').children[2].find(n => n.className === 'read-btn')[0]);
        await flush();
        assert.strictEqual($('#summaryLabel').textContent, 'PUBLISHER DESCRIPTION');
        assert.ok($('#modalNote').textContent.includes('not a summary of the article'));
        assert.strictEqual($('#modalSummary').byClass('qr-block').length, 0);
        assert.strictEqual($('#modalSummary').byClass('qr-intro')[0].textContent, 'Publisher description text.');
        assert.ok($('#modalSummary').byClass('qr-retry').length === 1);
    });
    await test('network failure shows an error with retry; an expired story advises refreshing and offers no retry', async () => {
        click($('#closeModal'));
        articleHandler = () => Promise.reject(new Error('Failed to fetch'));
        click($('#newsGrid').children[2].find(n => n.className === 'read-btn')[0]);
        await flush();
        assert.strictEqual($('#summaryLabel').textContent, 'COULD NOT LOAD');
        assert.ok($('#modalSummary').textContent.includes('could not be loaded'));
        assert.strictEqual($('#modalSummary').byClass('qr-retry').length, 1);
        articleHandler = () => json(404, { error: 'Story expired. Refresh the feed and try again.' });
        click($('#modalSummary').byClass('qr-retry')[0]);
        await flush();
        assert.ok($('#modalSummary').textContent.includes('expired'));
        assert.strictEqual($('#modalSummary').byClass('qr-retry').length, 0);
    });
    await test('a slow response for a previous story never overwrites the current one', async () => {
        click($('#closeModal'));
        let releaseC;
        articleHandler = () => new Promise(r => { releaseC = () => r(json(200, { ...ARTICLE, intro: 'STALE STORY C' })); });
        click($('#newsGrid').children[2].find(n => n.className === 'read-btn')[0]); // story c: request left pending
        click($('#closeModal'));
        openSecond(); // story b: served from client cache
        const shown = $('#modalSummary').textContent;
        releaseC();
        await flush();
        assert.strictEqual($('#modalTitle').textContent, 'Story b');
        assert.strictEqual($('#modalSummary').textContent, shown);
        assert.ok(!$('#modalSummary').textContent.includes('STALE'));
    });
    await test('untrusted text is rendered as text, never as markup', async () => {
        click($('#closeModal'));
        articleHandler = () => json(200, { ...ARTICLE, intro: '<img src=x onerror=alert(1)>', points: ['<script>alert(1)</script>'] });
        // use a fresh item id so the client cache does not answer
        ITEMS.push({ id: 'd'.repeat(20), title: 'Story d', source: 'X', url: 'https://x.example/d', published: null, description: '', category: 'top' });
        vm.runInContext("openArticle(" + JSON.stringify(ITEMS.at(-1)) + ")", ctx);
        await flush();
        const box = $('#modalSummary');
        assert.strictEqual(box.find(n => n.tagName === 'IMG' || n.tagName === 'SCRIPT').length, 0);
        assert.ok(box.textContent.includes('<img src=x onerror=alert(1)>'));
    });
    // ---------------------------------------------------------------------------------------------
    // AI/ML additions: topic tag, sentiment pill, duplicate grouping, filters, insights, related stories
    // ---------------------------------------------------------------------------------------------
    const mk = (k, extra) => ({ id: k.repeat(20), title: `ML story ${k}`, source: `Pub ${k}`, url: `https://pub-${k}.example/s`, published: '2026-10-14T10:00:00+00:00', description: 'Open this story for a short summary and its original source.', category: 'top', image: null, ...extra });
    const NEG = { available: true, label: 'Negative', score: -0.5, confidence: null, method: 'vader+news-lexicon', score_kind: 'lexicon_polarity', financial: false, note: null };
    const ML_ITEMS = [
        mk('1', { topic: { label: 'Technology', score: 0.19, matched: ['ai', 'chip'] }, sentiment: NEG, story: { id: 'g1', size: 2, lead: true }, also_covered_by: [{ id: '2'.repeat(20), title: 'Same story, other words', source: 'Other Pub', url: 'https://other.example/x', published: null }, { id: '9'.repeat(20), title: 'Bad link story', source: 'Odd Pub', url: 'javascript:alert(1)', published: null }] }),
        mk('2', { topic: { label: 'Technology', score: 0.18, matched: [] }, sentiment: NEG, story: { id: 'g1', size: 2, lead: false } }),
        mk('3', { category: 'sports', topic: { label: 'General', score: null, matched: [] }, sentiment: { available: false, label: null }, story: { id: 'g3', size: 1, lead: true }, also_covered_by: [] }),
        mk('4', { category: 'business', topic: { label: 'Business', score: 0.16, matched: ['sensex'] }, sentiment: { available: true, label: 'Positive', score: null, confidence: 0.91, method: 'transformers:x', financial: true, note: 'Sentiment is a text classification result about the wording, not investment advice.' }, story: { id: 'g4', size: 1, lead: true } }),
    ];
    const setItems = () => { vm.runInContext('state.items=' + JSON.stringify(ML_ITEMS) + ';state.visible=9;state.topic="all";state.group=true;state.saved=false;render()', ctx); };
    const cardsNow = () => $('#newsGrid').children;
    const change = (id, value) => $(id).listeners.change[0]({ target: { value } });
    await test('cards: detected topic replaces the generic tag; sentiment pill and "+N sources" appear; General keeps the feed name', async () => {
        click($('#closeModal'));
        setItems();
        assert.strictEqual(cardsNow().length, 3, 'the second copy of a duplicated story is collapsed');
        const first = cardsNow()[0];
        assert.strictEqual(first.byClass('category-tag')[0].textContent, 'Technology');
        const pill = first.byClass('sent-pill')[0];
        assert.ok(pill.className.includes('sent-negative') && pill.textContent === 'Negative');
        assert.ok(pill.title.includes('lexicon polarity -0.50') && !pill.title.includes('confidence'), 'a lexicon score is never called confidence');
        assert.strictEqual(first.byClass('group-count')[0].textContent, '+1 source');
        const plain = cardsNow()[1];
        assert.strictEqual(plain.byClass('category-tag')[0].textContent, 'Sports');
        assert.strictEqual(plain.byClass('sent-pill').length, 0, 'no pill when sentiment is unavailable');
        assert.strictEqual(plain.byClass('group-count').length, 0);
        assert.ok(plain.find(n => n.className === 'read-btn').length === 1 && first.byClass('small-icon').length === 1, 'quick read and save buttons remain');
    });
    await test('model confidence is shown only when the backend really provides it', async () => {
        const pill = cardsNow()[2].byClass('sent-pill')[0];
        assert.ok(pill.className.includes('sent-positive'));
        assert.ok(pill.title.includes('model confidence 91%'));
        assert.ok(pill.title.includes('not investment advice'));
    });
    await test('duplicate grouping can be switched off; topic filter narrows the feed', async () => {
        change('#groupSelect', 'all');
        assert.strictEqual(cardsNow().length, 4);
        change('#groupSelect', 'group');
        assert.strictEqual(cardsNow().length, 3);
        change('#topicSelect', 'Technology');
        assert.strictEqual(cardsNow().length, 1);
        assert.strictEqual($('#resultCount').textContent, '1');
        change('#groupSelect', 'all');
        assert.strictEqual(cardsNow().length, 2);
        change('#topicSelect', 'General');
        assert.strictEqual(cardsNow().length, 1);
        change('#topicSelect', 'all');
        change('#groupSelect', 'group');
        assert.strictEqual(cardsNow().length, 3);
    });
    await test('feed items without ML fields (old bookmarks, failed enrichment) render exactly as before', async () => {
        vm.runInContext('state.items=' + JSON.stringify(ITEMS.slice(0, 3)) + ';render()', ctx);
        assert.strictEqual(cardsNow().length, 3);
        assert.strictEqual(cardsNow()[0].byClass('category-tag')[0].textContent, 'Top stories');
        assert.strictEqual(cardsNow()[0].byClass('sent-pill').length, 0);
        vm.runInContext('state.topic="Sports";render()', ctx);
        assert.strictEqual(cardsNow().filter(n => n.className === 'news-card').length, 0);
        assert.strictEqual(cardsNow()[0].className, 'empty-state', 'a filter with no matches shows the normal empty state');
        vm.runInContext('state.topic="all";render()', ctx);
    });
    const REC = { items: [{ ...mk('5'), topic: { label: 'Technology' }, recommendation: { score: 0.3, reasons: ['Similar keywords', 'Same topic: Technology'], fallback: false } }, { ...mk('6'), recommendation: { score: 0.2, reasons: ['Similar keywords'], fallback: false } }], fallback: false };
    await test('modal shows topic, headline tone, article tone, financial note, also-covered-by links (https only) and related stories', async () => {
        articleHandler = () => json(200, { ...ARTICLE, sentiment: { available: true, label: 'Neutral', score: 0.02, confidence: null, financial: false, note: null } });
        recHandler = () => json(200, REC);
        setItems();
        vm.runInContext('openArticle(' + JSON.stringify(ML_ITEMS[0]) + ')', ctx);
        const rows = () => $('#modalInsights').byClass('insight-row').map(r => r.textContent);
        assert.ok(rows().some(t => t.includes('Technology') && t.includes('keyword similarity 0.19') && t.includes('matched: ai, chip')));
        assert.ok(rows().some(t => t.includes('Headline tone') && t.includes('Negative') && t.includes('lexicon polarity -0.50')));
        assert.ok(!rows().join(' ').includes('Article tone'), 'article tone waits for the article text');
        await flush();
        assert.ok(rows().some(t => t.includes('Article tone') && t.includes('Neutral')));
        assert.ok(!rows().join(' ').toLowerCase().includes('confidence'));
        const also = $('#modalAlso');
        assert.strictEqual(also.hidden, false);
        const links = also.find(n => n.tagName === 'A');
        assert.strictEqual(links.length, 1, 'the javascript: link is rendered as plain text, not a link');
        assert.strictEqual(links[0].href, 'https://other.example/x');
        assert.strictEqual(links[0].rel, 'noopener noreferrer');
        assert.ok(also.textContent.includes('Odd Pub'));
        assert.strictEqual($('#modalRelated').hidden, false);
        assert.strictEqual($('#modalRelated').byClass('rec-item').length, 2);
        assert.ok($('#modalRelated').textContent.includes('Related stories') && $('#modalRelated').textContent.includes('Same topic: Technology'));
    });
    await test('financial wording carries the "not investment advice" note; real model confidence is labelled as such', async () => {
        vm.runInContext('openArticle(' + JSON.stringify(ML_ITEMS[3]) + ')', ctx);
        await flush();
        assert.ok($('#modalInsights').byClass('insight-note')[0].textContent.includes('not investment advice'));
        assert.ok($('#modalInsights').textContent.includes('model confidence 91%'));
        assert.strictEqual($('#modalAlso').hidden, true);
    });
    await test('related request is a POST carrying only saved story titles; clicking a related story opens it', async () => {
        click($('#closeModal'));
        vm.runInContext('bookmarks["' + 'z'.repeat(20) + '"]={id:"' + 'z'.repeat(20) + '",title:"My saved cricket story",source:"S",url:"https://s.example/z"}', ctx);
        recCalls.length = 0;
        vm.runInContext('relatedCache.clear()', ctx);
        vm.runInContext('openArticle(' + JSON.stringify(ML_ITEMS[0]) + ')', ctx);
        await flush();
        const call = recCalls.at(-1);
        assert.strictEqual(call.options.method, 'POST');
        assert.deepStrictEqual(JSON.parse(call.options.body), { saved_titles: ['My saved cricket story'] });
        assert.ok(call.url.endsWith('/api/recommendations/' + ML_ITEMS[0].id));
        click($('#modalRelated').byClass('rec-item')[0]);
        await flush();
        assert.strictEqual($('#modalTitle').textContent, 'ML story 5');
        assert.strictEqual($('#readOriginal').href, 'https://pub-5.example/s');
        vm.runInContext('delete bookmarks["' + 'z'.repeat(20) + '"]', ctx);
    });
    await test('related stories are cached per story (no repeat request) and a failing endpoint just hides the section', async () => {
        const before = recCalls.length;
        vm.runInContext('openArticle(' + JSON.stringify(ML_ITEMS[0]) + ')', ctx);
        await flush();
        assert.strictEqual(recCalls.length, before, 'served from the client cache');
        recHandler = () => json(500, {});
        vm.runInContext('openArticle(' + JSON.stringify(mk('7')) + ')', ctx);
        await flush();
        assert.strictEqual($('#modalRelated').hidden, true);
        recHandler = () => Promise.reject(new Error('Failed to fetch'));
        vm.runInContext('openArticle(' + JSON.stringify(mk('8')) + ')', ctx);
        await flush();
        assert.strictEqual($('#modalRelated').hidden, true);
        recHandler = () => json(200, { items: [], fallback: false, message: 'not_enough_articles' });
        vm.runInContext('openArticle(' + JSON.stringify(mk('a')) + ')', ctx);
        await flush();
        assert.strictEqual($('#modalRelated').hidden, true);
    });
    await test('slow related-stories response for a previous story never appears under the current one', async () => {
        let releaseRec;
        recHandler = () => new Promise(r => { releaseRec = () => r(json(200, REC)); });
        vm.runInContext('openArticle(' + JSON.stringify(mk('b')) + ')', ctx);
        recHandler = () => json(200, { items: [], fallback: false });
        vm.runInContext('openArticle(' + JSON.stringify(mk('c')) + ')', ctx);
        await flush();
        releaseRec();
        await flush();
        assert.strictEqual($('#modalTitle').textContent, 'ML story c');
        assert.strictEqual($('#modalRelated').hidden, true);
    });
    await test('fallback recommendations are labelled honestly', async () => {
        recHandler = () => json(200, { items: [{ ...mk('d'), recommendation: { score: null, reasons: ['Recent story from your feed'], fallback: true } }], fallback: true });
        vm.runInContext('openArticle(' + JSON.stringify(mk('e')) + ')', ctx);
        await flush();
        assert.ok($('#modalRelated').textContent.includes('More from your feed'));
        assert.ok(!$('#modalRelated').textContent.includes('Related stories'));
    });
    await test('AI summaries are labelled; a transient AI failure offers a retry and is not cached client-side', async () => {
        recHandler = () => json(200, { items: [] });
        articleHandler = () => json(200, { ...ARTICLE, summary_method: 'ai', ai: { used: true }, ai_retryable: false, message: 'AI-generated from the publisher\'s article text (m).' });
        vm.runInContext('openArticle(' + JSON.stringify(mk('f')) + ')', ctx);
        await flush();
        assert.strictEqual($('#summaryLabel').textContent, 'AI SUMMARY');
        assert.ok($('#modalNote').textContent.startsWith('AI-generated'));
        assert.ok($('#modalSummary').byClass('qr-meta')[0].textContent.startsWith('AI overview'));
        articleHandler = () => json(200, { ...ARTICLE, summary_type: 'partial', summary_method: 'ai', ai_retryable: false });
        vm.runInContext('openArticle(' + JSON.stringify(mk('g')) + ')', ctx);
        await flush();
        assert.strictEqual($('#summaryLabel').textContent, 'PARTIAL AI SUMMARY');
        articleHandler = () => json(200, { ...ARTICLE, summary_method: 'extractive', ai_retryable: true, message: 'AI summary unavailable (the AI service timed out), so this overview is built from the article\'s own sentences.' });
        vm.runInContext('openArticle(' + JSON.stringify(mk('h')) + ')', ctx);
        await flush();
        assert.strictEqual($('#summaryLabel').textContent, 'ARTICLE SUMMARY');
        assert.ok($('#modalNote').textContent.includes('AI summary unavailable'));
        const retry = $('#modalSummary').byClass('qr-retry')[0];
        assert.ok(retry && retry.textContent.includes('AI summary again'));
        const before = articleCalls().length;
        vm.runInContext('closeArticle()', ctx);
        vm.runInContext('openArticle(' + JSON.stringify(mk('h')) + ')', ctx);
        await flush();
        assert.strictEqual(articleCalls().length, before + 1, 'not cached, so the next open asks the server again');
        articleHandler = () => json(200, { ...ARTICLE, summary_method: 'ai', ai_retryable: false });
        click($('#modalSummary').byClass('qr-retry')[0]);
        await flush();
        assert.ok(articleCalls().at(-1).endsWith('?retry=1'));
        assert.strictEqual($('#summaryLabel').textContent, 'AI SUMMARY');
    });
    await test('ML text from the server is always rendered as text, never markup', async () => {
        const evil = mk('i', { topic: { label: '<img src=x onerror=alert(1)>', score: 0.1, matched: ['<b>x</b>'] }, sentiment: { ...NEG, label: 'Negative' }, also_covered_by: [{ id: 'j'.repeat(20), title: '<script>alert(1)</script>', source: '<i>s</i>', url: 'https://ok.example/x' }] });
        articleHandler = () => json(200, ARTICLE);
        vm.runInContext('openArticle(' + JSON.stringify(evil) + ')', ctx);
        await flush();
        const root = $('#modalInsights');
        assert.strictEqual(root.find(n => n.tagName === 'IMG' || n.tagName === 'SCRIPT' || n.tagName === 'B').length, 0);
        assert.strictEqual($('#modalAlso').find(n => n.tagName === 'SCRIPT').length, 0);
        assert.ok(root.textContent.includes('<img src=x onerror=alert(1)>'));
    });
    const failed = results.filter(r => !r[1]);
    results.forEach(([n, ok, e]) => console.log((ok ? 'PASS  ' : 'FAIL  ') + n + (ok ? '' : '\n      ' + (e && e.stack || e).toString().split('\n').slice(0, 4).join('\n      '))));
    console.log(`\n${results.length - failed.length}/${results.length} passed`);
    process.exit(failed.length ? 1 : 0);
})();
