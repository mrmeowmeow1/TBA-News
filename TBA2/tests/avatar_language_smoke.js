'use strict';
// Offline DOM smoke test for the actual static/avatar.js (no browser or server needed).
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const nodes = {};
function node(id) {
    if (!nodes[id]) {
        const handlers = {};
        nodes[id] = { id, textContent: '', hidden: false, disabled: false, value: '', lang: '',
            classList: { set: new Set(), add(s) { this.set.add(s); }, remove(s) { this.set.delete(s); } },
            dataset: {}, style: {}, handlers,
            addEventListener(evt, cb) { handlers[evt] = cb; },
            setAttribute(k, v) { this[k] = v; },
            focus() { document.activeElement = this; },
            click() { handlers.click?.({ target: this }); },
            change() { handlers.change?.({ target: this }); }
        };
    }
    return nodes[id];
}
const document = { body: { style: {} }, activeElement: { focus() { } }, getElementById: node, addEventListener() { } };
node('avatarLanguage').value = 'en';
node('avatarVoice').value = 'browser';
node('newsAvatar').hidden = true;
let currentLang = 'en';
let lastRequest = null;
const fetch = async (url, opts) => {
    if (url === '/api/avatar/voice/status')
        return { ok: true, json: async () => ({ providers: { piper: false, parler: false } }) };
    lastRequest = { url, body: JSON.parse(opts.body) };
    const lang = lastRequest.body.language;
    let text = 'This is an English news briefing.';
    let language = 'en-IN';
    if (lang === 'hi') { text = 'यह हिंदी में खबर है।'; language = 'hi-IN'; }
    if (lang === 'mr') { text = 'ही मराठीतील बातमी आहे.'; language = 'mr-IN'; }
    if (lang === 'bho') { text = 'ई भोजपुरी में खबर बा।'; language = 'bho-IN'; }
    if (lang === 'ml') { text = 'ഇത് മലയാളത്തിലെ വാർത്തയാണ്.'; language = 'ml-IN'; }
    return { ok: true, json: async () => ({ text, language, fallback: false, source_type: 'article', notice: 'Available text' }) };
};
let lastSpeech = null;
class Utterance {
    constructor(txt) { this.text = txt; this.lang = ''; }
}
const speech = { cancel() { }, paused: false, speaking: false, getVoices() { return [{ lang: 'en-IN' }, { lang: 'hi-IN', name: 'Swara Female' }, { lang: 'mr-IN', name: 'Aarohi Female' }, { lang: 'bho-IN', name: 'Swara Bhojpuri' }, { lang: 'ml-IN', name: 'Sobhana Female' }]; }, speak(u) { lastSpeech = u; u.onstart?.(); }, pause() { this.paused = true; }, resume() { this.paused = false; } };
const window = { speechSynthesis: speech, addEventListener() { }, TBAAvatar: null };
const context = { window, document, fetch, AbortController, SpeechSynthesisUtterance: Utterance, console };
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../static/avatar.js'), 'utf8'), context);
const flush = () => new Promise(resolve => setImmediate(resolve));
(async () => {
    await window.TBAAvatar.open({ id: 'a'.repeat(20), title: 'Test news title' });
    await flush();
    assert.equal(lastRequest.url, '/api/avatar/narration/' + 'a'.repeat(20));
    assert.equal(lastRequest.body.language, 'en');
    assert.match(node('avatarTranscript').textContent, /English news briefing/);
    assert.equal(node('avatarPlay').disabled, false);
    node('avatarPlay').click();
    assert.equal(lastSpeech.lang, 'en-IN');
    assert.equal(nodes.avatarFigure.classList.set.has('is-speaking'), true);
    node('avatarLanguage').value = 'hi';
    node('avatarLanguage').change();
    await flush();
    assert.equal(lastRequest.body.language, 'hi');
    assert.equal(node('avatarTranscript').lang, 'hi');
    node('avatarPlay').click();
    assert.equal(lastSpeech.lang, 'hi-IN'); // explicit system female voice selected
    node('avatarLanguage').value = 'mr';
    node('avatarLanguage').change();
    await flush();
    assert.equal(lastRequest.body.language, 'mr');
    assert.equal(node('avatarTranscript').lang, 'mr');
    node('avatarPlay').click();
    assert.equal(lastSpeech.lang, 'mr-IN');
    node('avatarLanguage').value = 'bho';
    node('avatarLanguage').change();
    await flush();
    assert.equal(lastRequest.body.language, 'bho');
    assert.equal(node('avatarTranscript').lang, 'bho');
    node('avatarPlay').click();
    assert.equal(lastSpeech.lang, 'bho-IN');
    node('avatarLanguage').value = 'ml';
    node('avatarLanguage').change();
    await flush();
    assert.equal(lastRequest.body.language, 'ml');
    assert.equal(node('avatarTranscript').lang, 'ml');
    node('avatarPlay').click();
    assert.equal(lastSpeech.lang, 'ml-IN');
    window.TBAAvatar.close();
    assert.equal(node('newsAvatar').hidden, true);
    console.log('PASS avatar UI: English default, Hindi, Marathi, Bhojpuri, Malayalam, playback languages, close');
})().catch(err => { console.error(err); process.exitCode = 1; });
