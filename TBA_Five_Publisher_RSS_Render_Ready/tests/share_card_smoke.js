'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const elements = [];
const context2d = new Proxy({}, { get(target, key) {
        if (key === 'measureText')
            return txt => ({ width: String(txt).length * 26 });
        if (key === 'createLinearGradient')
            return () => ({ addColorStop() { } });
        if (key === 'roundRect')
            return () => { };
        if (key === 'fillText' || key === 'fillRect' || key === 'beginPath' || key === 'arc' || key === 'fill' || key === 'drawImage')
            return () => { };
        return target[key];
    }, set(target, key, value) { target[key] = value; return true; } });
const document = {
    body: { append(n) { elements.push(n); } },
    createElement(tag) {
        if (tag === 'canvas')
            return { getContext() { return context2d; }, toBlob(cb) { cb({ type: 'image/png', size: 8192 }); } };
        if (tag === 'a')
            return { click() { this.clicked = true; }, remove() { } };
        throw Error('unknown ' + tag);
    }
};
const URLmock = Object.assign(class URLMock extends URL {
}, { createObjectURL() { return 'blob:foo'; }, revokeObjectURL() { } });
const window = {};
const fileData = [];
class FileMock {
    constructor(data, name, options) { this.name = name; this.type = options.type; fileData.push(this); }
}
class ImageMock {
    set src(value) { this.onerror(); }
}
const nav = { canShare(data) { return !!data.files; }, async share(data) { this.lastShare = data; } };
const ctx = { window, document, URL: URLmock, File: FileMock, Image: ImageMock, navigator: nav, console, setTimeout(cb) { cb(); } };
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../static/share.js'), 'utf8'), ctx);
const item = { id: 'a'.repeat(20), title: 'New science discovery', url: 'https://news.google.com/rss/articles/test', source: 'Example News', category: 'science', published: '2026-10-15T08:00:00Z' };
const button = { textContent: '↗ Share', disabled: false, isConnected: true };
(async () => {
    await window.TBAShare.share(item, null, button);
    assert.equal(nav.lastShare.url, item.url);
    assert.equal(nav.lastShare.files[0].type, 'image/png');
    assert.equal(nav.lastShare.files[0].name, 'tba-story-aaaaaaaaaaaa.png');
    assert.equal(button.disabled, false);
    assert.equal(elements.length, 0, 'native web share should not download separately');
    console.log('PASS native web share sends branded PNG and original story URL');
    nav.canShare = () => false;
    nav.lastShare = null;
    const clipboard = [];
    nav.clipboard = { writeText: async (url) => { clipboard.push(url); } };
    await window.TBAShare.share(item, null, button);
    assert.equal(elements[0].download, 'tba-story-aaaaaaaaaaaa.png');
    assert.deepEqual(clipboard, [item.url]);
    console.log('PASS desktop fallback downloads the PNG and copies story link');
    const blob = await window.TBAShare.createCard({ ...item, url: 'javascript:alert(1)', title: 'Very long ' + ('title '.repeat(60)) });
    assert.equal(blob.type, 'image/png');
    console.log('PASS safe URL validation and long headline handling');

    // Test summary extraction and card creation with news summary
    const summaryItem = { ...item, summary: 'Breakthrough in clean energy storage using sodium-ion batteries.' };
    const summaryText = window.TBAShare.getSummaryText(summaryItem, null);
    assert.equal(summaryText, summaryItem.summary);
    const summaryCardBlob = await window.TBAShare.createCard(summaryItem, null);
    assert.equal(summaryCardBlob.type, 'image/png');
    console.log('PASS news summary extraction and summary card rendering');

    // Test social media platforms sharing links
    const socialLinks = window.TBAShare.buildSocialLinks(summaryItem, summaryText);
    assert.ok(socialLinks.whatsapp.includes('whatsapp.com/send'));
    assert.ok(socialLinks.whatsapp.includes(encodeURIComponent(item.url)));
    assert.ok(socialLinks.twitter.includes('twitter.com/intent/tweet'));
    assert.ok(socialLinks.twitter.includes(encodeURIComponent(item.url)));
    assert.ok(socialLinks.linkedin.includes('linkedin.com/sharing'));
    assert.ok(socialLinks.linkedin.includes(encodeURIComponent(item.url)));
    assert.ok(socialLinks.telegram.includes('t.me/share/url'));
    assert.ok(socialLinks.telegram.includes(encodeURIComponent(item.url)));
    assert.ok(socialLinks.facebook.includes('facebook.com/sharer'));
    assert.ok(socialLinks.facebook.includes(encodeURIComponent(item.url)));
    assert.ok(socialLinks.reddit.includes('reddit.com/submit'));
    assert.ok(socialLinks.reddit.includes(encodeURIComponent(item.url)));
    assert.ok(socialLinks.email.startsWith('mailto:'));
    assert.ok(socialLinks.fullMessage.includes(summaryItem.summary));
    console.log('PASS social media sharing links for WhatsApp, X, LinkedIn, Telegram, Facebook, Reddit, Email');

    // Test sharing when in browser environment with window.location.origin
    window.location = { origin: 'https://tba.news', href: 'https://tba.news/' };
    const siteStoryUrl = window.TBAShare.getStoryShareUrl(item);
    assert.equal(siteStoryUrl, 'https://tba.news/story/' + item.id);
    const siteLinks = window.TBAShare.buildSocialLinks(summaryItem, summaryText);
    assert.ok(siteLinks.whatsapp.includes(encodeURIComponent(siteStoryUrl)));
    assert.ok(siteLinks.twitter.includes(encodeURIComponent(siteStoryUrl)));
    assert.ok(siteLinks.telegram.includes(encodeURIComponent(siteStoryUrl)));
    assert.ok(siteLinks.fullMessage.includes(siteStoryUrl));
    console.log('PASS website story card URL generation and social links point to TBA website story page');
})().catch(err => { console.error(err); process.exitCode = 1; });
