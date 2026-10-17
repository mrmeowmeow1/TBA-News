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
        ctx.font = '700 25px Arial, sans-serif';
        ctx.fillText(shorten(item?.topic?.label || item?.category || 'NEWS', 32).toUpperCase(), 74, 480);
        const title = shorten(item?.title || 'News update', 360);
        let size = 61, lines = [];
        while (size >= 39) {
            ctx.font = `700 ${size}px Arial, sans-serif`;
            lines = splitText(ctx, title, 925, 5);
            // Prevent an overlong one-line word from overflowing the edge.
            if ((lines.length <= 4 && lines.every(l => ctx.measureText(l).width <= 930)) || size === 39)
                break;
            size -= 4;
        }
        ctx.fillStyle = '#f5f8ff';
        lines.slice(0, 5).forEach((line, index) => ctx.fillText(line, 70, 580 + index * (size + 14)));
        const footerTop = 903;
        ctx.fillStyle = '#2b4360';
        rounded(ctx, 65, footerTop, 950, 1.5, 1);
        ctx.fill();
        ctx.fillStyle = '#ced9e7';
        ctx.font = '600 26px Arial, sans-serif';
        const published = item?.published ? new Date(item.published) : null;
        const date = published && Number.isFinite(published.getTime()) ? published.toLocaleDateString('en-IN', { dateStyle: 'medium' }) : 'Date unavailable';
        ctx.fillText(shorten(item?.source || 'News source', 65), 72, 960);
        ctx.textAlign = 'right';
        ctx.fillText(date, 1007, 960);
        ctx.textAlign = 'left';
        const url = safeUrl(item);
        ctx.fillStyle = '#91b7fa';
        ctx.font = '20px Arial, sans-serif';
        ctx.fillText('Read the full story at the original source', 72, 1012);
        if (url) {
            ctx.fillStyle = '#cad5e5';
            ctx.font = '17px Arial, sans-serif';
            const host = new URL(url).hostname;
            ctx.textAlign = 'right';
            ctx.fillText(host, 1007, 1012);
            ctx.textAlign = 'left';
        }
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
            const link = safeUrl(item);
            const data = { title: shorten(item.title, 200), text: `${shorten(item.title, 180)} — ${shorten(item.source, 70)}` };
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
    window.TBAShare = { share, createCard };
})();
