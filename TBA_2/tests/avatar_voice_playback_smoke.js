'use strict';
// Tests real static/avatar.js without browser/network. Only checks control flow, not audio quality.
const fs = require('fs'), vm = require('vm'), path = require('path'), assert = require('node:assert/strict');
const nodes = {};
function node(id) {
    if (!nodes[id]) {
        const handlers = {};
        nodes[id] = { id, hidden: false, disabled: false, textContent: '', lang: '', value: '', dataset: {},
            handlers, style: { setProperty() { } },
            classList: { s: new Set(), add(...ks) { ks.forEach(k => this.s.add(k)); }, remove(...ks) { ks.forEach(k => this.s.delete(k)); } },
            setAttribute(k, v) { this[k] = v; }, removeAttribute() { }, addEventListener(name, cb) { handlers[name] = cb; },
            focus() { document.activeElement = this; }, click() { handlers.click?.(); }, change() { handlers.change?.(); }
        };
    }
    return nodes[id];
}
const document = { body: { style: {} }, activeElement: { focus() { } }, getElementById: node, addEventListener() { } };
node('avatarLanguage').value = 'en';
node('avatarNarratorPreset').value = 'en:edge-swara';
node('newsAvatar').hidden = true;
const calls = [];
let translationOk = true;
let audioRequests = 0;
const fetch = async (url, options) => {
    calls.push({ url, options });
    if (url === '/api/avatar/voice/status')
        return { ok: true, json: async () => ({ providers: { piper: true, parler: false, 'edge-swara': true, 'edge-madhur': true } }) };
    if (url.startsWith('/api/avatar/narration/')) {
        const lang = JSON.parse(options.body).language;
        return { ok: true, json: async () => ({ text: lang === 'hi' && translationOk ? 'आज की प्रमुख खबर के बारे में जानते हैं।' : 'Today we cover the most important news story.', language: lang === 'hi' && translationOk ? 'hi-IN' : 'en-IN', fallback: lang === 'hi' && !translationOk, notice: 'Using accessible article.' }) };
    }
    if (url.startsWith('/api/avatar/voice/')) {
        audioRequests++;
        const selected = JSON.parse(options.body).provider;
        assert.ok(['piper', 'edge-swara', 'edge-madhur'].includes(selected));
        return { ok: true, headers: { get: name => ({ 'X-TBA-Voice': selected, 'X-TBA-Language': JSON.parse(options.body).language })[name] }, blob: async () => ({ type: selected.startsWith('edge-') ? 'audio/mpeg' : 'audio/wav', size: 512 }) };
    }
    throw Error('unexpected URL ' + url);
};
let lastSpeech;
class Utterance {
    constructor(text) { this.text = text; }
}
const speech = { cancel() { }, getVoices() { return [{ name: 'English standard', lang: 'en-IN' }, { name: 'Swara Female', lang: 'hi-IN' }]; }, speak(u) { lastSpeech = u; u.onstart?.(); }, paused: false, speaking: true, pause() { this.paused = true; }, resume() { this.paused = false; } };
class AudioMock {
    constructor(src) { this.src = src; this.paused = true; this.currentTime = 0; this.ended = false; this.playbackRate = 1; }
    play() { this.paused = false; this.onplay?.(); return Promise.resolve(); }
    pause() { this.paused = true; this.onpause?.(); }
    load() { }
    removeAttribute() { this.src = ''; }
}
let made = 0;
const urls = { createObjectURL() { return 'blob:audio-' + (++made); }, revokeObjectURL() { } };
const window = { speechSynthesis: speech, addEventListener() { } };
const context = { window, document, fetch, AbortController, SpeechSynthesisUtterance: Utterance, Audio: AudioMock, URL: urls, console,
    requestAnimationFrame: () => 1, cancelAnimationFrame() { }, Uint8Array };
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../static/avatar.js'), 'utf8'), context);
const flush = () => new Promise(resolve => setTimeout(resolve, 0));
(async () => {
    window.TBAAvatar.open({ id: 'a'.repeat(20), title: 'Test title' });
    await flush();
    await flush();
    assert.equal(node('avatarVoiceRow').hidden, false, 'English gender choices must be visible too');
    node('avatarPlay').click();
    await flush();
    assert.equal(audioRequests, 1);
    assert.equal(JSON.parse(calls.at(-1).options.body).language, 'en');
    console.log('PASS English uses selected neural narrator');
    node('avatarLanguage').value = 'hi';
    node('avatarLanguage').change();
    await flush();
    assert.equal(node('avatarVoiceRow').hidden, false);
    assert.match(node('avatarTranscript').textContent, /आज की प्रमुख खबर/);
    node('avatarPlay').click();
    await flush();
    await flush();
    assert.equal(audioRequests, 2);
    assert.equal(JSON.parse(calls.at(-1).options.body).provider, 'edge-swara');
    assert.equal(node('avatarFigure').classList.s.has('neural-talking'), true);
    assert.match(node('avatarState').textContent, /Hindi narration/);
    node('avatarPause').click();
    assert.equal(node('avatarPause').textContent, '▶ Resume');
    node('avatarPause').click();
    assert.equal(node('avatarPause').textContent, '⏸ Pause');
    node('avatarStop').click();
    node('avatarPlay').click();
    await flush();
    assert.equal(audioRequests, 2, 'replay must reuse downloaded MP3');
    console.log('PASS Hindi neural MP3 generation, pause, resume and cached replay');
    translationOk = false;
    node('avatarLanguage').value = 'en';
    node('avatarLanguage').change();
    await flush();
    node('avatarLanguage').value = 'hi';
    node('avatarLanguage').change();
    await flush();
    const before = audioRequests;
    node('avatarVoiceSample').click();
    await flush();
    await flush();
    assert.equal(audioRequests, before + 1, 'English voice preview must work even when Hindi translation fails');
    assert.equal(calls.at(-1).url, '/api/avatar/voice/sample');
    assert.match(node('avatarState').textContent, /Playing Hindi narration/i,
        'Hindi preview must play even while article text has English fallback');
    node('avatarPlay').click();
    await flush();
    assert.equal(audioRequests, before + 2, 'English fallback must request the selected neural voice');
    assert.equal(JSON.parse(calls.at(-1).options.body).language, 'en');
    assert.equal(JSON.parse(calls.at(-1).options.body).provider, 'edge-swara');
    console.log('PASS failed Hindi translation retains gender choice using English neural voice');
    window.TBAAvatar.close();
    assert.equal(node('newsAvatar').hidden, true);
    console.log('3/3 avatar female voice tests passed');
})().catch(e => { console.error(e); process.exitCode = 1; });
