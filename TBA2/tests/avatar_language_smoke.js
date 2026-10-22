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
node('avatarNarratorPreset').value = 'en:edge-swara';
node('newsAvatar').hidden = true;
let currentLang = 'en';
let lastRequest = null;
const audioCalls = [];
const fetch = async (url, opts) => {
    if (url === '/api/avatar/voice/status')
        return { ok: true, json: async () => ({ providers: { 'edge-swara': true, 'edge-madhur': true } }) };
    if (url.startsWith('/api/avatar/voice/')) {
        const body = JSON.parse(opts.body);
        audioCalls.push({ url, body });
        return { ok: true, headers: { get(k) { return ({ 'X-TBA-Voice': body.provider, 'X-TBA-Language': body.language })[k]; } }, blob: async () => ({ size: 800, type: 'audio/mpeg' }) };
    }
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
class AudioMock {
  constructor() { this.paused = true; this.ended = false; this.currentTime = 0; }
  play() { this.paused = false; this.onplay?.(); return Promise.resolve(); }
  pause() { this.paused = true; this.onpause?.(); }
  removeAttribute() { } load() { }
}
const context = { window, document, fetch, AbortController, SpeechSynthesisUtterance: Utterance, console, Audio: AudioMock, URL: {createObjectURL: () => 'blob:test', revokeObjectURL() { }}, requestAnimationFrame:()=>1, cancelAnimationFrame() { }, Uint8Array }; 
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../static/avatar.js'), 'utf8'), context);
const flush = () => new Promise(resolve => setImmediate(resolve));
(async () => {
    await window.TBAAvatar.open({ id: 'a'.repeat(20), title: 'Test news title' });
    await flush();
    assert.equal(node('femaleAvatarWrap').hidden, false);
    assert.equal(node('defaultAvatarWrap').hidden, true);
    assert.equal(node('tatyaAvatarWrap').hidden, true);
    assert.match(node('avatarEyebrow').textContent, /PRINCESS LUNA/i);
    assert.equal(lastRequest.url, '/api/avatar/narration/' + 'a'.repeat(20));
    assert.equal(lastRequest.body.language, 'en');
    assert.match(node('avatarTranscript').textContent, /English news briefing/);
    assert.equal(node('avatarPlay').disabled, false);
    node('avatarPlay').click();
    await flush();
    assert.equal(audioCalls.at(-1).body.language, 'en');
    assert.equal(nodes.avatarFigure.classList.set.has('is-speaking'), true);
    node('avatarLanguage').value = 'hi';
    node('avatarLanguage').change();
    await flush();
    assert.equal(node('femaleAvatarWrap').hidden, false);
    assert.equal(node('defaultAvatarWrap').hidden, true);
    assert.equal(node('tatyaAvatarWrap').hidden, true);
    assert.match(node('avatarEyebrow').textContent, /PRINCESS LUNA/i);
    assert.equal(lastRequest.body.language, 'hi');
    assert.equal(node('avatarTranscript').lang, 'hi');
    node('avatarPlay').click();
    await flush();
    assert.equal(audioCalls.at(-1).body.language, 'hi'); // explicit system female voice selected
    node('avatarLanguage').value = 'mr';
    node('avatarLanguage').change();
    await flush();
    assert.equal(node('defaultAvatarWrap').hidden, true);
    assert.equal(node('tatyaAvatarWrap').hidden, false);
    assert.match(node('avatarEyebrow').textContent, /TATYA VINCHU/i);
    assert.equal(lastRequest.body.language, 'mr');
    assert.equal(node('avatarTranscript').lang, 'mr');
    node('avatarPlay').click();
    await flush();
    assert.equal(audioCalls.at(-1).body.language, 'mr');
    node('avatarLanguage').value = 'bho';
    node('avatarLanguage').change();
    await flush();
    assert.equal(node('femaleAvatarWrap').hidden, false);
    assert.equal(node('defaultAvatarWrap').hidden, true);
    assert.equal(node('tatyaAvatarWrap').hidden, true);
    assert.match(node('avatarEyebrow').textContent, /PRINCESS LUNA/i);
    assert.equal(lastRequest.body.language, 'bho');
    assert.equal(node('avatarTranscript').lang, 'bho');
    node('avatarPlay').click();
    await flush();
    assert.equal(audioCalls.at(-1).body.language, 'bho');
    node('avatarLanguage').value = 'ml';
    node('avatarLanguage').change();
    await flush();
    assert.equal(node('femaleAvatarWrap').hidden, false);
    assert.equal(node('defaultAvatarWrap').hidden, true);
    assert.equal(node('tatyaAvatarWrap').hidden, true);
    assert.match(node('avatarEyebrow').textContent, /PRINCESS LUNA/i);
    assert.equal(lastRequest.body.language, 'ml');
    assert.equal(node('avatarTranscript').lang, 'ml');
    node('avatarPlay').click();
    await flush();
    assert.equal(audioCalls.at(-1).body.language, 'ml');

    // Test female narrator (Princess Luna) activation
    node('avatarNarratorPreset').value = 'ml:edge-swara';
    node('avatarNarratorPreset').change();
    await flush();
    assert.equal(node('femaleAvatarWrap').hidden, false, 'Female avatar must be visible when female narrator selected');
    assert.equal(node('defaultAvatarWrap').hidden, true, 'Default male avatar must be hidden when female narrator selected');
    assert.equal(node('tatyaAvatarWrap').hidden, true, 'Tatya must be hidden for non-Marathi');
    assert.match(node('avatarEyebrow').textContent, /PRINCESS LUNA/i);

    // Switch to male narrator
    node('avatarNarratorPreset').value = 'ml:edge-madhur';
    node('avatarNarratorPreset').change();
    await flush();
    assert.equal(node('femaleAvatarWrap').hidden, true, 'Female avatar must be hidden when male narrator selected');
    assert.equal(node('defaultAvatarWrap').hidden, false, 'Default male avatar must be visible when male narrator selected');
    assert.equal(node('tatyaAvatarWrap').hidden, true);
    assert.equal(node('avatarEyebrow').textContent, 'TBA · AI NEWS PRESENTER');

    // Switch to Marathi with female voice selected -> Tatya Vinchu overrides
    node('avatarNarratorPreset').value = 'ml:edge-swara';
    node('avatarNarratorPreset').change();
    node('avatarLanguage').value = 'mr';
    node('avatarLanguage').change();
    await flush();
    assert.equal(node('tatyaAvatarWrap').hidden, false, 'Tatya must override for Marathi');
    assert.equal(node('femaleAvatarWrap').hidden, true);
    assert.equal(node('defaultAvatarWrap').hidden, true);
    assert.match(node('avatarEyebrow').textContent, /TATYA VINCHU/i);

    // New one-step chooser: every requested language has female and male neural voices.
    for (const [choice, language, provider] of [
        ['hi:edge-swara', 'hi', 'edge-swara'],
        ['hi:edge-madhur', 'hi', 'edge-madhur'],
        ['mr:edge-swara', 'mr', 'edge-swara'],
        ['mr:edge-madhur', 'mr', 'edge-madhur'],
        ['bho:edge-swara', 'bho', 'edge-swara'],
        ['bho:edge-madhur', 'bho', 'edge-madhur'],
        ['ml:edge-swara', 'ml', 'edge-swara'],
        ['ml:edge-madhur', 'ml', 'edge-madhur'],
        ['en:edge-swara', 'en', 'edge-swara'],
        ['en:edge-madhur', 'en', 'edge-madhur'],
    ]) {
        node('avatarNarratorPreset').value = choice;
        node('avatarNarratorPreset').change();
        await flush();
        assert.equal(node('avatarLanguage').value, language, `language for ${choice}`);
        assert.equal(node('avatarNarratorPreset').value.split(':')[1], provider, `voice for ${choice}`);
        assert.equal(lastRequest.body.language, language, `backend request for ${choice}`);
        assert.equal(node('avatarNarratorPreset').value, choice, `menu stays selected: ${choice}`);
    }
    // Switching the language using the original dropdown must also sync the new chooser.
    node('avatarLanguage').value = 'mr';
    node('avatarLanguage').change();
    await flush();
    assert.equal(node('avatarNarratorPreset').value, 'mr:edge-madhur');
    // There is no second visible voice selector to override these presets.
    assert.ok(!node('avatarVoice').handlers.change);
    assert.equal(node('avatarNarratorPreset').value, 'mr:edge-madhur');
    window.TBAAvatar.close();
    assert.equal(node('newsAvatar').hidden, true);
    console.log('PASS avatar UI: all 5 languages × female/male presets, single-choice online narrator, synced selectors, avatars, close');
})().catch(err => { console.error(err); process.exitCode = 1; });
