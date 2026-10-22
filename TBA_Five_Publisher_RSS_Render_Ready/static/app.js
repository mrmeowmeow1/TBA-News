'use strict';
const $ = (s) => document.querySelector(s);
const els = { grid: $('#newsGrid'), count: $('#resultCount'), section: $('#sectionTitle'), title: $('#pageTitle'), sub: $('#pageSub'), search: $('#searchInput'), notice: $('#notice'), more: $('#moreBtn'), modal: $('#articleModal') };
const categoryNames = { top: 'Top stories', world: 'World', nation: 'India', business: 'Business', technology: 'Technology', entertainment: 'Entertainment', sports: 'Sports', science: 'Science', health: 'Health' };
const icons = { top: '◈', world: '◎', nation: '⌂', business: '▥', technology: '⌘', entertainment: '✧', sports: '◉', science: '✳', health: '♡' };
const STORAGE = 'tba-bookmarks-v1';
const PREVIOUS_STORAGE = 'innews-bookmarks-v1';
let bookmarks = {};
try {
    bookmarks = JSON.parse(localStorage.getItem(STORAGE) || localStorage.getItem(PREVIOUS_STORAGE) || '{}') || {};
}
catch {
    bookmarks = {};
}
let state = { category: 'top', query: '', items: [], visible: 9, sort: 'newest', topic: 'all', group: true, saved: false, loading: false, controller: null, selected: null, requestId: 0 };
let lastFocus = null;
function el(tag, className, text) { const e = document.createElement(tag); if (className)
    e.className = className; if (text !== undefined)
    e.textContent = text; return e; }
function age(date) { if (!date)
    return 'Date unavailable'; const diff = Math.max(0, Date.now() - Date.parse(date)); if (!Number.isFinite(diff))
    return 'Date unavailable'; const h = Math.floor(diff / 3600000); return h < 1 ? 'Just now' : h < 24 ? `${h}h ago` : `${Math.floor(h / 24)}d ago`; }
function dateText(date) { return date ? new Date(date).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : 'Date unavailable'; }
function saveBookmarks() { try {
    localStorage.setItem(STORAGE, JSON.stringify(bookmarks));
}
catch { } $('#savedCount').textContent = Object.keys(bookmarks).length; }
function toggleBookmark(item) { if (bookmarks[item.id])
    delete bookmarks[item.id];
else
    bookmarks[item.id] = item; saveBookmarks(); render(); if (state.selected?.id === item.id)
    $('#modalSave').textContent = bookmarks[item.id] ? '★ Saved' : '☆ Save story'; }
function orderedItems() { let list = (state.saved ? Object.values(bookmarks) : state.items).filter(x => !state.query || (!state.saved) || `${x.title} ${x.source}`.toLowerCase().includes(state.query.toLowerCase())); if (!state.saved && state.group)
    list = list.filter(x => !x.story || x.story.lead); if (state.topic !== 'all')
    list = list.filter(x => x.topic?.label === state.topic); return list.sort((a, b) => state.sort === 'source' ? a.source.localeCompare(b.source) : (state.sort === 'oldest' ? 1 : -1) * ((Date.parse(a.published) || 0) - (Date.parse(b.published) || 0))); }
function render() { const list = orderedItems(); els.count.textContent = list.length; els.grid.replaceChildren(); if (!list.length) {
    const empty = el('div', 'empty-state');
    empty.append(el('span', 'empty-icon', state.saved ? '☆' : '⌕'), el('h3', '', state.saved ? 'Nothing saved just yet' : 'No stories found'), el('p', '', state.saved ? 'Bookmark stories to build your reading list.' : 'Try another category or search term.'));
    els.grid.append(empty);
    els.more.hidden = true;
    return;
} for (const item of list.slice(0, state.visible)) {
    els.grid.append(card(item));
} els.more.hidden = list.length <= state.visible; }
function topicLabel(item) { const t = item.topic && item.topic.label; return t && t !== 'General' ? t : (categoryNames[item.category] || 'News'); }
function sentimentText(s) { if (!s || !s.available || !s.label)
    return null; const parts = [s.label]; if (typeof s.confidence === 'number')
    parts.push(`model confidence ${Math.round(s.confidence * 100)}%`);
else if (typeof s.score === 'number')
    parts.push(`lexicon polarity ${s.score > 0 ? '+' : ''}${s.score.toFixed(2)}`); return parts.join(' · '); }
function sentimentPill(item) { const s = item.sentiment; if (!s || !s.available || !s.label)
    return null; const pill = el('span', `sent-pill sent-${s.label.toLowerCase()}`, s.label); pill.title = `Headline tone: ${sentimentText(s)}. ${s.note || 'Describes the wording, not whether the news is good or bad.'}`; return pill; }
function card(item) { const card = el('article', 'news-card'); const visual = el('div', `card-visual visual-${item.category}`); const fallback = () => { visual.replaceChildren(el('span', 'card-glyph', icons[item.category] || '◈'), el('span', 'visual-caption', 'TBA / DAILY EDIT')); }; fallback(); if (item.id) {
    const img = el('img');
    img.alt = 'Article image';
    img.loading = 'lazy';
    img.decoding = 'async';
    img.onload = () => img.classList.add('loaded');
    // The proxy can be refused by a publisher/CDN even if its public photo loads
    // in a visitor's browser. Try the feed's validated HTTPS photo once, then
    // leave the designed placeholder instead of showing a broken image.
    let triedSource = false;
    img.referrerPolicy = 'no-referrer';
    img.onerror = () => {
        if (!triedSource && /^https:\/\/[^\s]+$/i.test(item.image || '')) {
            triedSource = true;
            img.src = item.image;
            return;
        }
        img.onerror = null; img.remove();
    };
    img.src = '/api/image/' + encodeURIComponent(item.id);
    visual.append(img);
} const body = el('div', 'card-body'); const top = el('div', 'card-top'); const tag = el('span', 'category-tag', topicLabel(item)); tag.title = item.topic && item.topic.label && item.topic.label !== 'General' ? 'Topic detected from the headline by keyword similarity' : ''; const meta = el('div', 'card-meta'); const pill = sentimentPill(item); if (pill)
    meta.append(pill); meta.append(el('span', 'card-time', age(item.published))); top.append(tag, meta); const heading = el('h3', '', item.title); const description = el('p', 'description', item.description || 'Read the story and view its original source.'); const bottom = el('div', 'card-bottom'); const source = el('span', 'source', item.source || 'News source'); source.title = item.source || ''; if (item.story && item.story.size > 1) {
    const more = item.story.size - 1;
    source.append(' ', el('b', 'group-count', `+${more} source${more > 1 ? 's' : ''}`));
    source.title = `${item.source || 'News source'} — ${more} other publisher${more > 1 ? 's' : ''} cover this story`;
} const actions = el('div', 'card-actions'); const save = el('button', `small-icon ${bookmarks[item.id] ? 'saved' : ''}`, bookmarks[item.id] ? '★' : '☆'); save.type = 'button'; save.title = bookmarks[item.id] ? 'Remove bookmark' : 'Bookmark'; save.setAttribute('aria-label', save.title); save.addEventListener('click', () => toggleBookmark(item)); const shareBtn = el('button', 'share-btn', '↗ Share'); shareBtn.type = 'button'; shareBtn.title = 'Share a branded news image and the story link'; shareBtn.setAttribute('aria-label', 'Share news card'); shareBtn.addEventListener('click', () => (window.TBAShare?.openShareModal ? window.TBAShare.openShareModal(item, card, shareBtn) : window.TBAShare?.share(item, card, shareBtn))); const read = el('button', 'read-btn', 'Quick read ↗'); read.addEventListener('click', () => openArticle(item)); const avatarTry = el('button', 'avatar-try-btn', '✦ Try me'); avatarTry.type = 'button'; avatarTry.title = 'Listen to this story in English or Hindi'; avatarTry.addEventListener('click', () => window.TBAAvatar?.open(item)); actions.append(save, shareBtn, avatarTry, read); bottom.append(source, actions); body.append(top, heading, description, bottom); card.append(visual, body); return card; }
function skeleton() { els.grid.replaceChildren(); for (let i = 0; i < 6; i++)
    els.grid.append(el('div', 'skeleton')); els.more.hidden = true; els.count.textContent = '…'; }
function showNotice(msg) { els.notice.textContent = msg; els.notice.hidden = !msg; }
async function fetchStories(force = false) { state.saved = false; state.visible = 9; state.requestId++; const current = state.requestId; if (state.controller)
    state.controller.abort(); state.controller = new AbortController(); state.loading = true; skeleton(); showNotice(''); const qs = new URLSearchParams({ category: state.category }); if (state.query)
    qs.set('q', state.query); if (force)
    qs.set('refresh', '1'); try {
    const res = await fetch('/api/news?' + qs, { signal: state.controller.signal });
    const data = await res.json();
    if (!res.ok)
        throw Error(data.error || 'Unable to fetch news.');
    if (current !== state.requestId)
        return;
    state.items = data.items || [];
    if (data.stale)
        showNotice('Showing previously fetched stories: the news source is temporarily unavailable.');
    render();
}
catch (e) {
    if (e.name === 'AbortError' || current !== state.requestId)
        return;
    state.items = [];
    render();
    showNotice(e.message + ' Please use Refresh to try again.');
}
finally {
    if (current === state.requestId)
        state.loading = false;
} }
function updateHead() { let name = state.saved ? 'Saved stories' : state.query ? `Search results` : categoryNames[state.category]; $('#crumbCurrent').textContent = name; els.section.firstChild.textContent = state.saved ? 'Your reading list ' : state.query ? `Results for “${state.query}” ` : state.category === 'top' ? "Today's headlines " : `${name} headlines `; if (state.saved) {
    els.title.replaceChildren(document.createTextNode('Your stories.'));
    els.sub.textContent = 'Everything you bookmarked, ready when you are.';
}
else {
    els.title.innerHTML = state.query ? 'Explore the <em>headlines.</em>' : state.category === 'top' ? 'Stay curious.<br><em>Stay informed.</em>' : `${name}.<br><em>In focus.</em>`;
    els.sub.textContent = 'A clearer perspective on what’s happening around the world — one story at a time.';
} document.querySelectorAll('.nav-item').forEach(btn => btn.classList.toggle('active', state.saved ? btn.id === 'savedNav' : btn.dataset.category === state.category)); $('#searchInput').value = state.query; }
function selectCategory(cat) { state.category = cat; state.query = ''; state.saved = false; updateHead(); fetchStories(); closeMenu(); }
function showSaved() { state.requestId++; state.controller?.abort(); state.saved = true; state.query = ''; state.visible = 9; updateHead(); render(); closeMenu(); }
function closeMenu() { $('#sidebar').classList.remove('open'); $('#scrim').classList.remove('show'); }
const articleCache = new Map(), inflight = new Map();
try { if (typeof window !== 'undefined') window.articleCache = articleCache; } catch (_) { }
const LABELS = { loading: 'LOADING…', ai: 'AI SUMMARY', ai_partial: 'PARTIAL AI SUMMARY', article: 'ARTICLE SUMMARY', partial: 'PARTIAL ARTICLE SUMMARY', description: 'PUBLISHER DESCRIPTION', unavailable: 'ARTICLE UNAVAILABLE', error: 'COULD NOT LOAD' };
function setLabel(type) { $('#summaryLabel').textContent = LABELS[type] || LABELS.article; }
function setNote(text) { const note = $('#modalNote'); note.textContent = text || ''; note.hidden = !text; }
function showModalImage(item) {
    const fig = $('#modalFigure'), img = $('#modalImage');
    fig.hidden = true;
    img.referrerPolicy = 'no-referrer';
    let triedSource = false;
    img.onload = () => { if (state.selected?.id === item.id) fig.hidden = false; };
    img.onerror = () => {
        if (!triedSource && /^https:\/\/[^\s]+$/i.test(item.image || '')) {
            triedSource = true;
            img.src = item.image;
            return;
        }
        img.onerror = null;
        fig.hidden = true;
        img.removeAttribute('src');
    };
    img.src = '/api/image/' + encodeURIComponent(item.id);
}
function renderLoading() { const box = $('#modalSummary'); box.setAttribute('aria-busy', 'true'); setLabel('loading'); setNote(''); const row = el('div', 'qr-loading'); row.setAttribute('role', 'status'); row.append(el('span', 'qr-spinner'), el('span', '', 'Reading the article and preparing an overview…')); box.replaceChildren(row); }
function retryButton(item, text) { const b = el('button', 'outline-btn qr-retry', text || '↻ Try again'); b.type = 'button'; b.addEventListener('click', () => loadOverview(item, true)); return b; }
function block(title, content) { const wrap = el('div', 'qr-block'); wrap.append(el('h4', '', title), content); return wrap; }
function listOf(values) { const ul = el('ul', 'qr-list'); values.forEach(v => ul.append(el('li', '', v))); return ul; }
function chips(values) { const row = el('div', 'qr-chips'); values.forEach(v => row.append(el('span', 'qr-chip', v))); return row; }
function renderOverview(item, data) {
    const box = $('#modalSummary');
    box.setAttribute('aria-busy', 'false');
    box.replaceChildren();
    setLabel(data.summary_method === 'ai' ? (data.summary_type === 'partial' ? 'ai_partial' : 'ai') : data.summary_type);
    setNote(data.message);
    renderInsights(item, data);
    if (data.summary_type === 'unavailable') {
        if (data.retryable)
            box.append(retryButton(item));
        return;
    }
    box.append(el('p', 'qr-intro', data.intro || data.summary));
    if (data.summary_type === 'description') {
        if (data.retryable)
            box.append(retryButton(item, '↻ Try the full article again'));
        return;
    }
    if (data.points?.length)
        box.append(block('Key developments', listOf(data.points)));
    if (data.background?.length)
        box.append(block('Background', listOf(data.background)));
    if (data.next?.length)
        box.append(block('What’s next', listOf(data.next)));
    const d = data.details || {};
    if (d.names?.length)
        box.append(block('Names & places mentioned', chips(d.names)));
    if (d.figures?.length)
        box.append(block('Figures', chips(d.figures)));
    if (d.dates?.length)
        box.append(block('Dates', chips(d.dates)));
    if (data.source_words)
        box.append(el('p', 'qr-meta', data.summary_method === 'ai' ? `AI overview of about ${data.summary_words} words, written from a ${data.source_words}-word article.` : `Overview of about ${data.summary_words} words, selected from a ${data.source_words}-word article.`));
    if (data.ai_retryable)
        box.append(retryButton(item, '↻ Try the AI summary again'));
}
function insightRow(key, value) { const row = el('div', 'insight-row'); row.append(el('span', 'insight-key', key), el('span', 'insight-val', value)); return row; }
function renderInsights(item, data) {
    const box = $('#modalInsights');
    box.replaceChildren();
    const t = item.topic;
    if (t && t.label) {
        box.append(insightRow('Topic', t.label === 'General' ? 'General (no clear topic detected)' : `${t.label}${t.score != null ? ` · keyword similarity ${t.score.toFixed(2)}` : ''}${t.matched && t.matched.length ? ` · matched: ${t.matched.join(', ')}` : ''}`));
    }
    const h = sentimentText(item.sentiment);
    if (h)
        box.append(insightRow('Headline tone', h));
    const a = data && sentimentText(data.sentiment);
    if (a)
        box.append(insightRow('Article tone', a));
    const note = (data && data.sentiment && data.sentiment.note) || (item.sentiment && item.sentiment.note);
    if (note)
        box.append(el('p', 'insight-note', note));
    box.hidden = !box.children.length;
}
function renderAlso(item) {
    const box = $('#modalAlso');
    box.replaceChildren();
    const list = item.also_covered_by || [];
    if (list.length) {
        const ul = el('ul', 'qr-list');
        list.forEach(o => { const li = el('li'); if (/^https:\/\//.test(o.url || '')) {
            const a = el('a', 'also-link', `${o.source}: ${o.title}`);
            a.href = o.url;
            a.target = '_blank';
            a.rel = 'noopener noreferrer';
            li.append(a);
        }
        else
            li.textContent = `${o.source}: ${o.title}`; ul.append(li); });
        box.append(el('h4', '', 'Also covered by'), ul);
    }
    box.hidden = !list.length;
}
const relatedCache = new Map();
function renderRelated(item, data) {
    const box = $('#modalRelated');
    box.replaceChildren();
    const list = (data && data.items) || [];
    if (list.length) {
        const wrap = el('div', 'rec-list');
        list.forEach(r => { const b = el('button', 'rec-item'); b.type = 'button'; b.append(el('span', 'rec-title', r.title), el('span', 'rec-meta', `${r.source} · ${(r.recommendation && r.recommendation.reasons || []).join(' · ')}`)); b.addEventListener('click', () => openArticle(r)); wrap.append(b); });
        box.append(el('h4', '', data.fallback ? 'More from your feed' : 'Related stories'), wrap);
    }
    box.hidden = !list.length;
}
function loadRelated(item) {
    renderRelated(item, null);
    const done = data => { if (state.selected?.id === item.id)
        renderRelated(item, data); };
    if (relatedCache.has(item.id)) {
        done(relatedCache.get(item.id));
        return;
    }
    const saved = Object.values(bookmarks).filter(b => b && b.id !== item.id && typeof b.title === 'string').map(b => b.title).slice(0, 10);
    fetch('/api/recommendations/' + encodeURIComponent(item.id), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ saved_titles: saved }) }).then(r => r.ok ? r.json() : null).then(data => { if (data) {
        relatedCache.set(item.id, data);
    } done(data); }).catch(() => { });
}
function renderError(item, err) { const box = $('#modalSummary'); box.setAttribute('aria-busy', 'false'); setLabel('error'); setNote(''); box.replaceChildren(el('p', 'qr-empty', err.expired ? 'This story has expired from the feed. Refresh the feed and try again.' : (err.message && err.message !== 'Failed to fetch' ? err.message : 'The overview could not be loaded. Check your connection and try again.'))); if (!err.expired)
    box.append(retryButton(item)); }
function fetchOverview(id, retry) { const key = id + (retry ? ':retry' : ''); if (inflight.has(key))
    return inflight.get(key); const p = fetch('/api/article/' + encodeURIComponent(id) + (retry ? '?retry=1' : '')).then(async (r) => { const data = await r.json().catch(() => ({})); if (!r.ok)
    throw Object.assign(new Error(data.error || 'The overview could not be loaded.'), { expired: r.status === 404 }); return data; }).finally(() => inflight.delete(key)); inflight.set(key, p); return p; }
function loadOverview(item, retry = false) {
    const hit = articleCache.get(item.id);
    if (hit && !retry) {
        renderOverview(item, hit);
        return;
    }
    renderLoading();
    fetchOverview(item.id, retry).then(data => { if (state.selected?.id !== item.id)
        return; if ((data.summary_type === 'article' || data.summary_type === 'partial') && !data.ai_retryable)
        articleCache.set(item.id, data); renderOverview(item, data); }).catch(err => { if (state.selected?.id === item.id)
        renderError(item, err); });
}
function openArticle(item) { if (els.modal.hidden)
    lastFocus = document.activeElement; state.selected = item; els.modal.hidden = false; document.body.style.overflow = 'hidden'; els.modal.querySelectorAll('.modal-panel').forEach(n => { n.scrollTop = 0; }); $('#modalMeta').textContent = `${item.source} · ${dateText(item.published)}`; $('#modalTitle').textContent = item.title; $('#readOriginal').href = item.url; $('#modalSave').textContent = bookmarks[item.id] ? '★ Saved' : '☆ Save story'; $('#closeModal').focus(); showModalImage(item); renderInsights(item, null); renderAlso(item); loadOverview(item); loadRelated(item); }
function closeArticle() { els.modal.hidden = true; document.body.style.overflow = ''; state.selected = null; lastFocus?.focus(); }
document.querySelectorAll('[data-category]').forEach(b => b.addEventListener('click', () => selectCategory(b.dataset.category)));
$('#savedNav').addEventListener('click', showSaved);
$('#sortSelect').addEventListener('change', e => { state.sort = e.target.value; render(); });
$('#topicSelect').addEventListener('change', e => { state.topic = e.target.value; state.visible = 9; render(); });
$('#groupSelect').addEventListener('change', e => { state.group = e.target.value === 'group'; state.visible = 9; render(); });
$('#searchForm').addEventListener('submit', e => { e.preventDefault(); state.query = els.search.value.trim().slice(0, 100); state.saved = false; updateHead(); fetchStories(); });
$('#refreshBtn').addEventListener('click', () => { if (state.saved)
    render();
else
    fetchStories(true); });
els.more.addEventListener('click', () => { state.visible += 9; render(); });
$('#themeBtn').addEventListener('click', () => { document.body.classList.toggle('dark'); try {
    localStorage.setItem('tba-theme', document.body.classList.contains('dark') ? 'dark' : 'light');
}
catch { } });
$('#menuBtn').addEventListener('click', () => { $('#sidebar').classList.add('open'); $('#scrim').classList.add('show'); });
$('#scrim').addEventListener('click', closeMenu);
$('#closeModal').addEventListener('click', closeArticle);
els.modal.addEventListener('click', e => { if (e.target.dataset.close)
    closeArticle(); });
$('#modalSave').addEventListener('click', () => { if (state.selected)
    toggleBookmark(state.selected); });
$('#modalShare').addEventListener('click', () => { if (state.selected)
    (window.TBAShare?.openShareModal ? window.TBAShare.openShareModal(state.selected, null, $('#modalShare')) : window.TBAShare?.share(state.selected, null, $('#modalShare'))); });
document.addEventListener('keydown', e => { if (e.key === 'Escape') {
    const sm = typeof $ === 'function' ? $('#shareModal') : null;
    if (sm && !sm.hidden)
        window.TBAShare?.closeShareModal?.();
    else if (!els.modal.hidden)
        closeArticle();
    else
        closeMenu();
} if (e.key === '/' && els.modal.hidden && !['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName)) {
    e.preventDefault();
    els.search.focus();
} if (e.key === 'Tab' && !els.modal.hidden) {
    const buttons = [...els.modal.querySelectorAll('button,a')];
    if (e.shiftKey && document.activeElement === buttons[0]) {
        e.preventDefault();
        buttons.at(-1).focus();
    }
    else if (!e.shiftKey && document.activeElement === buttons.at(-1)) {
        e.preventDefault();
        buttons[0].focus();
    }
} });
$('#dateLabel').textContent = new Date().toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long' });
try {
    if ((localStorage.getItem('tba-theme') || localStorage.getItem('innews-theme')) === 'dark')
        document.body.classList.add('dark');
}
catch { }
saveBookmarks();
updateHead();
fetchStories();

function checkSharedStory() {
    let shared = null;
    const scriptEl = typeof document !== 'undefined' && typeof document.getElementById === 'function'
        ? document.getElementById('sharedStoryData')
        : (typeof $ === 'function' ? $('#sharedStoryData') : null);
    if (scriptEl) {
        try {
            shared = JSON.parse(scriptEl.textContent || '{}');
        } catch (_) { }
    }
    if (!shared && typeof window !== 'undefined' && window.location) {
        const pathMatch = (window.location.pathname || '').match(/\/story\/([0-9a-f]{20})/i);
        const paramMatch = new URLSearchParams(window.location.search || '').get('story');
        const id = pathMatch ? pathMatch[1] : (paramMatch && /^[0-9a-f]{20}$/i.test(paramMatch) ? paramMatch : null);
        if (id) {
            shared = { id };
        }
    }
    if (shared && shared.id) {
        if (shared.title && shared.url) {
            openArticle(shared.item || shared);
        } else {
            fetch('/api/article/' + encodeURIComponent(shared.id))
                .then(r => r.ok ? r.json() : null)
                .then(data => {
                    if (data && typeof openArticle === 'function') {
                        const reconstructed = {
                            id: shared.id,
                            title: data.title || 'News story',
                            source: data.source || 'TBA',
                            url: data.original_url || data.source_url || '',
                            published: data.published || '',
                            description: data.summary || data.intro || ''
                        };
                        openArticle(reconstructed);
                    }
                })
                .catch(() => { });
        }
    }
}
checkSharedStory();
