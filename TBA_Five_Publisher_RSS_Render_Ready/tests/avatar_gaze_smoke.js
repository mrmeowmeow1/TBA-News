'use strict';
// Offline test for smooth pupil-following in the actual TBA avatar.js.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const nodes = {};
const handlers = {};
const eventHandlers = {};
let pupilTransform = '';
let lidOpacity = '0';
const whites = { getBoundingClientRect() { return { left: 100, top: 100, width: 180, height: 60 }; } };
const pupils = { setAttribute(k, v) { if (k === 'transform')
        pupilTransform = v; } };
const lid = { setAttribute(k, v) { if (k === 'opacity')
        lidOpacity = v; } };
const figure = { querySelector(selector) { return ({ '#pupils': pupils, '#eyeWhites': whites, '#blinkL': lid, '#blinkR': lid })[selector] || null; },
    classList: { add() { }, remove() { } }, style: { setProperty() { } }, closest() { return { contains() { return true; } }; } };
function el(id) {
    if (id === 'avatarFigure')
        return figure;
    if (!nodes[id]) {
        const ownHandlers = {};
        nodes[id] = { id, hidden: false, disabled: false, textContent: '', value: '', dataset: {}, lang: '', style: {},
            addEventListener(type, cb) { ownHandlers[type] = cb; }, setAttribute(key, val) { this[key] = val; },
            focus() { }, click() { ownHandlers.click?.(); }, change() { ownHandlers.change?.(); },
            classList: { add() { }, remove() { } }, ownHandlers };
    }
    return nodes[id];
}
const document = { getElementById: el, body: { style: {} }, activeElement: { focus() { } }, addEventListener() { } };
const window = { speechSynthesis: { cancel() { }, getVoices() { return []; } },
    addEventListener(type, cb) { eventHandlers[type] = cb; },
    removeEventListener(type, cb) { if (eventHandlers[type] === cb)
        delete eventHandlers[type]; },
    matchMedia() { return { matches: false }; } };
let nextFrame = 1;
const frames = new Map();
function requestAnimationFrame(cb) { let n = nextFrame++; frames.set(n, cb); return n; }
function cancelAnimationFrame(id) { frames.delete(id); }
function tick(time) { const batch = [...frames.entries()]; frames.clear(); for (const [, cb] of batch)
    cb(time); }
let timestamp = 0;
const performance = { now() { return timestamp; } };
const fetch = async (url, options) => {
    if (url === '/api/avatar/voice/status')
        return { ok: true, json: async () => ({ providers: { piper: false, parler: false } }) };
    return { ok: true, json: async () => ({ text: 'Example article summary.', language: 'en-IN', notice: 'Available publisher text' }) };
};
el('avatarLanguage').value = 'en';
el('avatarVoice').value = 'browser';
el('newsAvatar').hidden = true;
const context = { window, document, fetch, console, performance, requestAnimationFrame, cancelAnimationFrame,
    AbortController, SpeechSynthesisUtterance: class {
        constructor(t) { this.text = t; }
    } };
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../static/avatar.js'), 'utf8'), context);
window.TBAAvatar.open({ id: 'abcd1234', title: 'Cursor interaction test' });
assert.equal(typeof eventHandlers.pointermove, 'function', 'pointer listener should be attached on open');
tick(timestamp += 16);
assert.match(pupilTransform, /translate\(0.00 0.00\)/, 'eyes should be centered before first pointer');
eventHandlers.pointermove({ clientX: 350, clientY: 130, pointerType: 'mouse' });
for (let i = 0; i < 25; i++)
    tick(timestamp += 16);
let coords = pupilTransform.match(/translate\(([-\d.]+) ([-\d.]+)\)/);
assert(coords && Number(coords[1]) > 6 && Math.abs(Number(coords[2])) < 1, `look right: ${pupilTransform}`);
eventHandlers.pointermove({ clientX: 0, clientY: 130, pointerType: 'mouse' });
for (let i = 0; i < 35; i++)
    tick(timestamp += 16);
coords = pupilTransform.match(/translate\(([-\d.]+) ([-\d.]+)\)/);
assert(coords && Number(coords[1]) < -6, `look left: ${pupilTransform}`);
eventHandlers.blur();
for (let i = 0; i < 30; i++)
    tick(timestamp += 16);
coords = pupilTransform.match(/translate\(([-\d.]+) ([-\d.]+)\)/);
assert(Math.abs(Number(coords[1])) < 0.12, `reset after blur: ${pupilTransform}`);
window.TBAAvatar.close();
assert.equal(pupilTransform, 'translate(0 0)', 'close resets gaze');
assert.equal(eventHandlers.pointermove, undefined, 'close removes pointer listener');
assert.equal(lidOpacity, '0', 'close clears blink');
assert.equal(frames.size, 0, 'close cancels RAF work');
console.log('PASS avatar gaze follows pointer left/right and eases to center');
console.log('PASS close removes listeners, clears blink and cancels animation');
