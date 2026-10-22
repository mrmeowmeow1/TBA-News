'use strict';
// Regression: switch voices without a Flask restart, including English fallback.
const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict'), path = require('node:path');
const els = {};
function el(id) {
    if (els[id])
        return els[id];
    const listeners = {};
    return els[id] = {
        id, value: '', textContent: '', disabled: false, hidden: false, lang: '', selectedOptions: [], handlers: listeners,
        dataset: {}, style: { setProperty() { } },
        classList: { flags: new Set(), add(...v) { v.forEach(x => this.flags.add(x)); }, remove(...v) { v.forEach(x => this.flags.delete(x)); } },
        addEventListener(t, fn) { listeners[t] = fn; }, click() { listeners.click?.(); }, change() { listeners.change?.(); },
        focus() { }, setAttribute() { }, removeAttribute() { }, load() { },
    };
}
el('avatarLanguage').value = 'hi';
el('avatarVoice').value = 'edge-swara';
el('newsAvatar').hidden = true;
const document = { getElementById: el, body: { style: {} }, activeElement: { focus() { } }, addEventListener() { } };
const requests = [], audios = [];
let translationAvailable = true;
let deferNextBlob = false;
let deferredResolve;
const fetch = async (url, options = {}) => {
    if (url === '/api/avatar/voice/status')
        return { ok: true, json: async () => ({ providers: { 'edge-swara': true, 'edge-madhur': true } }) };
    const body = JSON.parse(options.body);
    if (url.startsWith('/api/avatar/narration/')) {
        return { ok: true, json: async () => ({ text: body.language === 'hi' && translationAvailable ? 'यह एक समाचार का सारांश है।' : 'Here is a concise news overview.', language: body.language === 'hi' && translationAvailable ? 'hi-IN' : 'en-IN', fallback: !translationAvailable && body.language === 'hi', notice: 'Available source overview.' }) };
    }
    if (url.startsWith('/api/avatar/voice/')) {
        requests.push({ url, body });
        const provider = body.provider, language = body.language;
        let blob;
        if (deferNextBlob) {
            deferNextBlob = false;
            blob = () => new Promise(resolve => { deferredResolve = () => resolve({ size: 123, type: 'audio/mpeg' }); });
        }
        else
            blob = async () => ({ size: 123, type: 'audio/mpeg' });
        return { ok: true, headers: { get(name) { return ({ 'X-TBA-Voice': provider, 'X-TBA-Language': language })[name]; } }, blob };
    }
    throw Error('Unexpected URL ' + url);
};
class AudioMock {
    constructor(src) { this.src = src; this.paused = true; this.currentTime = 0; this.ended = false; audios.push(this); }
    play() { this.paused = false; this.onplay?.(); return Promise.resolve(); }
    pause() { this.paused = true; this.onpause?.(); }
    removeAttribute() { this.src = ''; }
    load() { }
}
const speech = { cancel() { }, getVoices() { return []; }, speaking: false };
const window = { speechSynthesis: speech, addEventListener() { } };
const ctx = { window, document, fetch, AbortController, Audio: AudioMock, URL: { createObjectURL: () => `blob:test-${audios.length}`, revokeObjectURL() { } }, console,
    requestAnimationFrame: () => 1, cancelAnimationFrame() { }, Uint8Array };
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../static/avatar.js'), 'utf8'), ctx);
const flush = async () => { await new Promise(setImmediate); await new Promise(setImmediate); };
(async () => {
    window.TBAAvatar.open({ id: 'a'.repeat(20), title: 'A test headline' });
    await flush();
    el('avatarPlay').click();
    await flush();
    assert.equal(requests.at(-1).body.provider, 'edge-swara');
    assert.equal(requests.at(-1).body.language, 'hi');
    assert.match(el('avatarState').textContent, /Swara.*female.*Hindi/i);
    const old = audios.at(-1);
    el('avatarVoice').value = 'edge-madhur';
    el('avatarVoice').change();
    await flush();
    assert.equal(old.paused, true, 'switch must stop the old MP3');
    assert.equal(requests.at(-1).body.provider, 'edge-madhur');
    assert.match(el('avatarState').textContent, /Madhur.*male.*Hindi/i);
    assert.equal(audios.at(-1).paused, false);
    assert.equal(requests.length, 2, 'new narrator must trigger a new backend request');
    console.log('PASS Female to male Hindi switch plays immediately without restarting Flask');
    // Hindi translation outage: the same selected gender must work in English.
    translationAvailable = false;
    el('avatarLanguage').value = 'en';
    el('avatarLanguage').change();
    await flush();
    el('avatarLanguage').value = 'hi';
    el('avatarLanguage').change();
    await flush();
    assert.match(el('avatarState').textContent, /English briefing ready/);
    el('avatarPlay').click();
    await flush();
    assert.equal(requests.at(-1).body.provider, 'edge-madhur');
    assert.equal(requests.at(-1).body.language, 'en');
    assert.match(el('avatarState').textContent, /Prabhat.*male.*English/i);
    el('avatarVoice').value = 'edge-swara';
    el('avatarVoice').change();
    await flush();
    assert.equal(requests.at(-1).body.provider, 'edge-swara');
    assert.equal(requests.at(-1).body.language, 'en');
    assert.match(el('avatarState').textContent, /Neerja.*female.*English/i);
    console.log('PASS English translation fallback switches between male and female neural voices');
    // Old body that resolves after a newer voice is selected is ignored.
    el('avatarStop').click();
    deferNextBlob = true;
    el('avatarVoice').value = 'edge-madhur';
    el('avatarVoice').change();
    el('avatarPlay').click();
    await flush();
    const amountBefore = audios.length;
    el('avatarVoice').value = 'edge-swara';
    el('avatarVoice').change();
    await flush();
    deferredResolve();
    await flush();
    assert.equal(audios.length, amountBefore + 1, 'late response must not replace the new voice');
    assert.match(el('avatarState').textContent, /Neerja.*female.*English/i);
    console.log('PASS Slow previous voice response cannot overwrite latest selection');
    window.TBAAvatar.close();
})().catch(e => { console.error(e); process.exitCode = 1; });
