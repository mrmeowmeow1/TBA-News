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
    return { ok: true, json: async () => ({ text: lang === 'hi' ? 'यह हिंदी में खबर है।' : 'This is an English news briefing.',
            language: lang === 'hi' ? 'hi-IN' : 'en-IN', fallback: false, source_type: 'article', notice: 'Available text' }) };
};
let lastSpeech = null;
class Utterance {
    constructor(txt) { this.text = txt; this.lang = ''; }
}
const speech = { cancel() { }, paused: false, speaking: false, getVoices() { return [{ lang: 'en-IN' }, { lang: 'hi-IN', name: 'Swara Female' }]; }, speak(u) { lastSpeech = u; u.onstart?.(); }, pause() { this.paused = true; }, resume() { this.paused = false; } };
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
    window.TBAAvatar.close();
    assert.equal(node('newsAvatar').hidden, true);
    console.log('PASS avatar UI: English default, switch to Hindi, playback languages, close');
})().catch(err => { console.error(err); process.exitCode = 1; });
