'use strict';
(() => {
    // Render a branded, square share image locally; no external JS service is used.
    // Official TBA logo: load once, use text only if the asset cannot load.
    let logoPromise;
    function loadBrandLogo() {
        if (!logoPromise) {
            logoPromise = new Promise(resolve => {
                const image = new Image();
                image.onload = () => resolve(image);
                image.onerror = () => resolve(null);
                image.src = '/static/assets/tba-logo.webp';
            });
        }
        return logoPromise;
    }
    const WIDTH = 1080;
    const HEIGHT = 1080;
    const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
    const shorten = (text, max = 240) => String(text || '').trim().slice(0, max);
    const safeUrl = item => {
        try {
            const url = new URL(item?.url || '');
            return /^https?:$/.test(url.protocol) ? url.href : '';
        }
        catch (_) {
            return '';
        }
    };
    const getStoryShareUrl = item => {
        if (typeof window !== 'undefined' && window.location && window.location.origin && item?.id) {
            return `${window.location.origin}/story/${encodeURIComponent(item.id)}`;
        }
        return safeUrl(item) || (typeof window !== 'undefined' && window.location?.href ? window.location.href : 'https://tba.news');
    };
    function splitText(ctx, text, maxWidth, maxLines) {
        const words = String(text || '').trim().split(/\s+/);
        const lines = [];
        let line = '';
        for (const word of words) {
            const trial = line ? `${line} ${word}` : word;
            if (ctx.measureText(trial).width > maxWidth && line) {
                lines.push(line);
                line = word;
            }
            else {
                line = trial;
            }
        }
        if (line)
            lines.push(line);
        if (lines.length > maxLines) {
            const out = lines.slice(0, maxLines);
            let last = out[maxLines - 1];
            while (last.length && ctx.measureText(last + '…').width > maxWidth) {
                last = last.slice(0, -1);
            }
            out[maxLines - 1] = last + '…';
            return out;
        }
        return lines;
    }
    async function loadImage(item, card) {
        const existing = card?.querySelector?.('.card-visual img.loaded');
        if (existing?.complete && existing.naturalWidth > 180)
            return existing;
        if (!item?.id || !/^[0-9a-f]{20}$/.test(String(item.id)))
            return null;
        return await new Promise(resolve => {
            const img = new Image();
            img.decoding = 'async';
            img.onload = () => resolve(img.naturalWidth > 180 ? img : null);
            img.onerror = () => resolve(null);
            img.src = `/api/image/${encodeURIComponent(item.id)}`;
        });
    }
    function rounded(ctx, x, y, w, h, r) {
        ctx.beginPath();
        if (typeof ctx.roundRect === 'function')
            ctx.roundRect(x, y, w, h, r);
        else
            ctx.rect(x, y, w, h);
    }
    function getSummaryText(item, cardElement) {
        if (item?.summary && typeof item.summary === 'string' && item.summary.trim())
            return item.summary.trim();
        if (item?.intro && typeof item.intro === 'string' && item.intro.trim())
            return item.intro.trim();
        if (typeof window !== 'undefined' && window.articleCache && item?.id) {
            const cached = window.articleCache.get(item.id);
            if (cached?.intro && typeof cached.intro === 'string' && cached.intro.trim())
                return cached.intro.trim();
            if (cached?.summary && typeof cached.summary === 'string' && cached.summary.trim())
                return cached.summary.trim();
        }
        const fromDom = cardElement?.querySelector?.('.description')?.textContent;
        if (fromDom && typeof fromDom === 'string' && fromDom.trim()) {
            const clean = fromDom.trim();
            if (!clean.includes('Open this story for a short summary'))
                return clean;
        }
        if (item?.description && typeof item.description === 'string' && item.description.trim()) {
            const clean = item.description.replace(/<[^>]*>/g, '').trim();
            if (clean && !clean.includes('Open this story for a short summary'))
                return clean;
        }
        return 'Read the verified news report, key developments, and full audio narration on TBA.';
    }
    async function createCard(item, cardElement) {
        const canvas = document.createElement('canvas');
        canvas.width = WIDTH;
        canvas.height = HEIGHT;
        const ctx = canvas.getContext('2d');
        if (!ctx)
            throw Error('Canvas is unavailable in this browser.');
        ctx.fillStyle = '#122032';
        ctx.fillRect(0, 0, WIDTH, HEIGHT);
        // Magazine/news graphic style, independent of light/dark website theme.
        const image = await loadImage(item, cardElement);
        if (image) {
            try {
                const iw = image.naturalWidth, ih = image.naturalHeight;
                const scale = Math.max(WIDTH / iw, 410 / ih);
                const drawWidth = iw * scale, drawHeight = ih * scale;
                ctx.drawImage(image, (WIDTH - drawWidth) / 2, (410 - drawHeight) / 2, drawWidth, drawHeight);
                const shade = ctx.createLinearGradient(0, 210, 0, 425);
                shade.addColorStop(0, 'rgba(18,32,50,0.08)');
                shade.addColorStop(1, 'rgba(18,32,50,1)');
                ctx.fillStyle = shade;
                ctx.fillRect(0, 200, WIDTH, 225);
            }
            catch (_) { /* Image failed: keep the polished text-only design. */ }
        }
        else {
            const shade = ctx.createLinearGradient(0, 0, 980, 440);
            shade.addColorStop(0, '#233f66');
            shade.addColorStop(1, '#477fbb');
            ctx.fillStyle = shade;
            ctx.fillRect(0, 0, WIDTH, 425);
            ctx.fillStyle = 'rgba(255,255,255,.09)';
            ctx.beginPath();
            ctx.arc(875, 145, 265, 0, Math.PI * 2);
            ctx.fill();
            ctx.beginPath();
            ctx.arc(925, 260, 185, 0, Math.PI * 2);
            ctx.fill();
        }
        // Use the same TBA logo used in the header (with a graceful fallback).
        const logo = await loadBrandLogo();
        if (logo) {
            ctx.fillStyle = '#ffffff';
            rounded(ctx, 65, 40, 223, 78, 14);
            ctx.fill();
            ctx.drawImage(logo, 76, 50, 200, 68);
        } else {
            ctx.fillStyle = '#ffffff';
            ctx.font = '800 54px Arial, sans-serif';
            ctx.fillText('TBA', 70, 92);
        }
        ctx.textAlign = 'right';
        ctx.font = '600 22px Arial, sans-serif';
        ctx.fillText('YOUR DAILY EDIT', 1008, 85);
        ctx.textAlign = 'left';
        ctx.fillStyle = '#91b7fa';
        ctx.font = '700 24px Arial, sans-serif';
        ctx.fillText(shorten(item?.topic?.label || item?.category || 'NEWS', 32).toUpperCase(), 70, 450);

        // Headline / Title
        const title = shorten(item?.title || 'News update', 360);
        let size = 48, lines = [];
        while (size >= 34) {
            ctx.font = `700 ${size}px Arial, sans-serif`;
            lines = splitText(ctx, title, 925, 3);
            if ((lines.length <= 3 && lines.every(l => ctx.measureText(l).width <= 930)) || size === 34)
                break;
            size -= 2;
        }
        ctx.fillStyle = '#f5f8ff';
        const titleStartY = 495;
        lines.slice(0, 3).forEach((line, index) => ctx.fillText(line, 70, titleStartY + index * (size + 10)));

        // News Summary Box
        const titleBottom = titleStartY + (lines.length - 1) * (size + 10) + 12;
        const boxTop = Math.max(595, titleBottom + 16);
        const boxHeight = Math.max(145, 875 - boxTop);
        const boxWidth = 940;
        const boxX = 70;

        ctx.fillStyle = 'rgba(21, 37, 58, 0.9)';
        rounded(ctx, boxX, boxTop, boxWidth, boxHeight, 14);
        ctx.fill();

        if (typeof ctx.stroke === 'function') {
            ctx.strokeStyle = 'rgba(145, 183, 250, 0.28)';
            ctx.lineWidth = 1.5;
            ctx.stroke();
        }

        // Left accent bar
        ctx.fillStyle = '#3b82f6';
        rounded(ctx, boxX, boxTop, 6, boxHeight, 3);
        ctx.fill();

        // Label inside summary box
        ctx.fillStyle = '#3b82f6';
        ctx.beginPath();
        ctx.arc(boxX + 26, boxTop + 28, 4.5, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = '#91b7fa';
        ctx.font = '700 17px Arial, sans-serif';
        ctx.fillText('STORY SUMMARY · KEY TAKEAWAY', boxX + 40, boxTop + 34);

        // Summary text
        const summaryText = getSummaryText(item, cardElement);
        ctx.fillStyle = '#e6effa';
        ctx.font = '500 23px Arial, sans-serif';
        const maxSummaryLines = Math.min(4, Math.max(2, Math.floor((boxHeight - 52) / 32)));
        const summaryLines = splitText(ctx, summaryText, boxWidth - 65, maxSummaryLines);
        summaryLines.forEach((sLine, sIdx) => {
            ctx.fillText(sLine, boxX + 26, boxTop + 72 + sIdx * 32);
        });

        // Footer
        const footerTop = 898;
        ctx.fillStyle = '#2b4360';
        rounded(ctx, 70, footerTop, 940, 1.5, 1);
        ctx.fill();

        ctx.fillStyle = '#ffffff';
        ctx.font = '700 25px Arial, sans-serif';
        const published = item?.published ? new Date(item.published) : null;
        const date = published && Number.isFinite(published.getTime()) ? published.toLocaleDateString('en-IN', { dateStyle: 'medium' }) : 'Date unavailable';
        ctx.fillText(shorten(item?.source || 'News source', 65), 72, 948);
        ctx.textAlign = 'right';
        ctx.fillStyle = '#ced9e7';
        ctx.font = '600 22px Arial, sans-serif';
        ctx.fillText(date, 1007, 948);
        ctx.textAlign = 'left';

        const url = getStoryShareUrl(item);
        ctx.fillStyle = '#91b7fa';
        ctx.font = '600 20px Arial, sans-serif';
        ctx.fillText('Read full story & audio briefing on TBA', 72, 990);
        if (url) {
            try {
                const host = new URL(url).hostname;
                ctx.fillStyle = '#cad5e5';
                ctx.font = '600 19px Arial, sans-serif';
                ctx.textAlign = 'right';
                ctx.fillText(host, 1007, 990);
                ctx.textAlign = 'left';
            }
            catch (_) { }
        }

        ctx.fillStyle = '#8fa3bc';
        ctx.font = '16px Arial, sans-serif';
        ctx.fillText('🔗 ' + shorten(url || 'https://tba.news', 75), 72, 1030);

        return new Promise((resolve, reject) => canvas.toBlob(blob => blob ? resolve(blob) : reject(Error('Could not prepare the image')), 'image/png'));
    }
    function download(blob, name) {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = name;
        document.body.append(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
    }
    function buildSocialLinks(item, summaryText) {
        const url = getStoryShareUrl(item);
        const title = shorten(item?.title || 'News story', 200);
        const source = shorten(item?.source || 'TBA', 60);
        const summary = shorten(summaryText || item?.description || '', 280);

        const fullMessage = `📰 *${title}* (${source})\n\n${summary ? summary + '\n\n' : ''}🔗 Read full story & audio on TBA:\n${url}`;
        const tweetText = `${shorten(title, 130)}${summary ? ' — ' + shorten(summary, 90) : ''}`;

        return {
            whatsapp: `https://api.whatsapp.com/send?text=${encodeURIComponent(fullMessage)}`,
            twitter: `https://twitter.com/intent/tweet?text=${encodeURIComponent(tweetText)}&url=${encodeURIComponent(url)}`,
            linkedin: `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(url)}`,
            telegram: `https://t.me/share/url?url=${encodeURIComponent(url)}&text=${encodeURIComponent(fullMessage)}`,
            facebook: `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(url)}`,
            reddit: `https://reddit.com/submit?url=${encodeURIComponent(url)}&title=${encodeURIComponent(title)}`,
            email: `mailto:?subject=${encodeURIComponent(title)}&body=${encodeURIComponent(fullMessage)}`,
            fullMessage,
            url
        };
    }
    async function share(item, cardElement, button) {
        if (!item)
            return;
        const original = button?.textContent || '↗ Share';
        if (button) {
            button.disabled = true;
            button.textContent = 'Preparing…';
        }
        try {
            const blob = await createCard(item, cardElement);
            const name = `tba-story-${String(item.id || 'share').slice(0, 12)}.png`;
            const file = typeof File === 'function' ? new File([blob], name, { type: 'image/png' }) : null;
            const link = getStoryShareUrl(item);
            const summary = getSummaryText(item, cardElement);
            const data = {
                title: shorten(item.title, 200),
                text: `${shorten(item.title, 140)}${summary ? ' — ' + shorten(summary, 120) : ''} (${shorten(item.source, 50)})`
            };
            if (file)
                data.files = [file];
            if (link)
                data.url = link;
            if (file && navigator.share && navigator.canShare?.({ files: [file] })) {
                try {
                    await navigator.share(data);
                    return;
                }
                catch (err) {
                    if (err?.name === 'AbortError')
                        return;
                }
            }
            // Desktop fallback: always give the real shareable PNG; copy the link if possible.
            download(blob, name);
            let copied = false;
            if (link && navigator.clipboard?.writeText) {
                try {
                    await navigator.clipboard.writeText(link);
                    copied = true;
                }
                catch (_) { }
            }
            if (button)
                button.textContent = copied ? '✓ Image + link' : '✓ Image saved';
            setTimeout(() => { if (button?.isConnected)
                button.textContent = original; }, 2400);
        }
        catch (err) {
            if (button)
                button.textContent = 'Retry share';
            console.warn('Could not create news share card:', err);
        }
        finally {
            if (button)
                button.disabled = false;
        }
    }
    let currentShareItem = null;
    let currentBlob = null;
    let toastTimer = null;
    function showToast(msg) {
        if (typeof document === 'undefined' || typeof document.getElementById !== 'function')
            return;
        const toast = document.getElementById('shareFeedbackToast');
        if (!toast)
            return;
        toast.textContent = msg;
        toast.hidden = false;
        clearTimeout(toastTimer);
        toastTimer = setTimeout(() => { toast.hidden = true; }, 2800);
    }
    function closeShareModal() {
        if (typeof document === 'undefined' || typeof document.getElementById !== 'function')
            return;
        const modal = document.getElementById('shareModal');
        if (modal)
            modal.hidden = true;
        if (typeof document.body !== 'undefined' && document.body?.style)
            document.body.style.overflow = '';
        currentShareItem = null;
        currentBlob = null;
    }
    async function openShareModal(item, cardElement, button) {
        if (typeof document === 'undefined' || typeof document.getElementById !== 'function') {
            return share(item, cardElement, button);
        }
        const modal = document.getElementById('shareModal');
        if (!modal) {
            return share(item, cardElement, button);
        }
        currentShareItem = item;
        currentBlob = null;

        const summary = getSummaryText(item, cardElement);
        const titleEl = document.getElementById('shareStoryTitle');
        if (titleEl) titleEl.textContent = item?.title || 'Story headline';

        const metaEl = document.getElementById('shareStoryMeta');
        if (metaEl) {
            const pub = item?.published ? new Date(item.published) : null;
            const dateStr = pub && Number.isFinite(pub.getTime()) ? pub.toLocaleDateString('en-IN', { dateStyle: 'medium' }) : '';
            metaEl.textContent = `${item?.source || 'News source'}${dateStr ? ' · ' + dateStr : ''}`;
        }

        const summaryEl = document.getElementById('shareSummaryText');
        if (summaryEl) summaryEl.textContent = summary;

        const links = buildSocialLinks(item, summary);
        const setHref = (id, href) => {
            const el = document.getElementById(id);
            if (el) el.href = href;
        };
        setHref('shareWhatsApp', links.whatsapp);
        setHref('shareX', links.twitter);
        setHref('shareLinkedIn', links.linkedin);
        setHref('shareTelegram', links.telegram);
        setHref('shareFacebook', links.facebook);
        setHref('shareReddit', links.reddit);
        setHref('shareEmail', links.email);

        const loading = document.getElementById('shareCardLoading');
        const img = document.getElementById('shareCardImg');
        if (loading) {
            loading.hidden = false;
            loading.textContent = 'Rendering summary card…';
        }
        if (img) img.hidden = true;

        const toast = document.getElementById('shareFeedbackToast');
        if (toast) toast.hidden = true;

        modal.hidden = false;
        if (document.body?.style)
            document.body.style.overflow = 'hidden';

        const dlBtn = document.getElementById('shareDownloadBtn');
        const copyLinkBtn = document.getElementById('shareCopyLinkBtn');
        const copySummaryBtn = document.getElementById('shareCopySummaryBtn');
        const nativeBtn = document.getElementById('shareNativeBtn');

        if (copyLinkBtn) {
            copyLinkBtn.onclick = async () => {
                try {
                    if (navigator.clipboard?.writeText) {
                        await navigator.clipboard.writeText(links.url);
                        showToast('✓ Story link copied to clipboard!');
                    }
                }
                catch (_) {
                    showToast('Link: ' + links.url);
                }
            };
        }
        if (copySummaryBtn) {
            copySummaryBtn.onclick = async () => {
                try {
                    if (navigator.clipboard?.writeText) {
                        await navigator.clipboard.writeText(links.fullMessage);
                        showToast('✓ Summary and link copied to clipboard!');
                    }
                }
                catch (_) {
                    showToast('Copied summary and link!');
                }
            };
        }

        try {
            const blob = await createCard(item, cardElement);
            if (currentShareItem?.id !== item?.id)
                return;
            currentBlob = blob;
            const objUrl = URL.createObjectURL(blob);
            if (img) {
                img.src = objUrl;
                img.hidden = false;
            }
            if (loading) loading.hidden = true;

            const fileName = `tba-story-${String(item?.id || 'share').slice(0, 12)}.png`;
            if (dlBtn) {
                dlBtn.onclick = () => {
                    download(blob, fileName);
                    showToast('✓ Card image downloaded (PNG)!');
                };
            }
            if (nativeBtn) {
                if (typeof navigator !== 'undefined' && navigator.share) {
                    nativeBtn.hidden = false;
                    nativeBtn.onclick = async () => {
                        const file = typeof File === 'function' ? new File([blob], fileName, { type: 'image/png' }) : null;
                        const data = { title: shorten(item.title, 200), text: links.fullMessage, url: links.url };
                        if (file && navigator.canShare?.({ files: [file] }))
                            data.files = [file];
                        try {
                            await navigator.share(data);
                        }
                        catch (e) {
                            if (e?.name !== 'AbortError') console.warn(e);
                        }
                    };
                }
                else {
                    nativeBtn.hidden = true;
                }
            }
        }
        catch (err) {
            if (loading) loading.textContent = 'Could not generate card image.';
            console.warn('Card preview generation failed:', err);
        }

        // Asynchronous enrichment if article summary was not yet cached
        if (item?.id && !item.summary && typeof fetch === 'function' && (!window.articleCache || !window.articleCache.has(item.id))) {
            fetch(`/api/article/${encodeURIComponent(item.id)}`).then(r => r.ok ? r.json() : null).then(async (data) => {
                if (!data || currentShareItem?.id !== item.id) return;
                const freshSummary = data.intro || data.summary;
                if (!freshSummary) return;
                item.summary = freshSummary;
                if (summaryEl) summaryEl.textContent = freshSummary;
                const freshLinks = buildSocialLinks(item, freshSummary);
                setHref('shareWhatsApp', freshLinks.whatsapp);
                setHref('shareX', freshLinks.twitter);
                setHref('shareLinkedIn', freshLinks.linkedin);
                setHref('shareTelegram', freshLinks.telegram);
                setHref('shareFacebook', freshLinks.facebook);
                setHref('shareReddit', freshLinks.reddit);
                setHref('shareEmail', freshLinks.email);
                try {
                    const freshBlob = await createCard(item, cardElement);
                    if (currentShareItem?.id !== item.id) return;
                    currentBlob = freshBlob;
                    if (img) img.src = URL.createObjectURL(freshBlob);
                } catch (_) { }
            }).catch(() => { });
        }
    }

    if (typeof document !== 'undefined' && typeof document.getElementById === 'function') {
        const initShareModalEvents = () => {
            const closeBtn = document.getElementById('closeShareModal');
            if (closeBtn) closeBtn.onclick = closeShareModal;
            const modal = document.getElementById('shareModal');
            if (modal) {
                modal.onclick = e => {
                    if (e.target && e.target.dataset && e.target.dataset.shareClose)
                        closeShareModal();
                };
            }
        };
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', initShareModalEvents);
        } else {
            initShareModalEvents();
        }
    }

    window.TBAShare = { share, createCard, openShareModal, closeShareModal, buildSocialLinks, getSummaryText, getStoryShareUrl };
})();
