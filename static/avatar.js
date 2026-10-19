"use strict";
(() => {
    const get = id => document.getElementById(id);
    const panel = get('newsAvatar');
    const stage = get('avatarFigure');
    const speech = window.speechSynthesis;
    const languageSelect = get('avatarLanguage');
    const voiceSelect = get('avatarVoice');
    let active = null, transcript = '', narrationLang = 'en-IN', utterance = null;
    let generation = 0, voiceGeneration = 0, lastFocus = null, pending = null, audioPending = null;
    let player = null, playerUrl = null, playerKey = null, pendingSample = false;
    let context = null, analyser = null, mediaSource = null, raf = 0;
    const voicesAvailable = { 'edge-swara': false, 'edge-madhur': false };
    // Interactive gaze stays entirely in the browser. No camera, tracking API,
    // uploaded cursor data, extra package or server endpoint is necessary.
    function createGazeController() {
        const eyes = stage?.querySelector?.('#pupils');
        const whites = stage?.querySelector?.('#eyeWhites');
        const leftLid = stage?.querySelector?.('#blinkL');
        const rightLid = stage?.querySelector?.('#blinkR');
        const prefersReducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)');
        if (!eyes || !whites || typeof requestAnimationFrame !== 'function') {
            return { start() { }, stop() { } };
        }
        const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
        const clock = () => (typeof performance !== 'undefined' ? performance.now() : Date.now());
        let enabled = false, frameId = 0, previous = 0;
        let currentX = 0, currentY = 0, targetX = 0, targetY = 0;
        let blinkAt = 0, blinkStarted = 0;
        function aimAt(clientX, clientY) {
            // eyeWhites does not move with the pupil transform. Its screen rectangle
            // also tracks the existing CSS head animation, avoiding gaze jitter.
            const bounds = whites.getBoundingClientRect();
            if (!bounds.width || !bounds.height)
                return;
            const centerX = bounds.left + bounds.width / 2;
            const centerY = bounds.top + bounds.height / 2;
            const dx = clientX - centerX;
            const dy = clientY - centerY;
            const angle = Math.atan2(dy, dx);
            // Shorter, slower eye travel looks more natural than chasing the pointer
            // outside the drawn eye socket. These are SVG viewBox units.
            const distance = Math.min(1, Math.hypot(dx / 155, dy / 130));
            targetX = clamp(Math.cos(angle) * distance * 8.5, -8.5, 8.5);
            targetY = clamp(Math.sin(angle) * distance * 5.5, -5.5, 5.5);
        }
        function pointerMoved(event) {
            if (!enabled || prefersReducedMotion?.matches)
                return;
            // Do not follow finger movement elsewhere on the page; touch users can
            // interact by dragging directly on the avatar stage.
            if (event.pointerType === 'touch' && !stage.closest?.('.avatar-stage')?.contains?.(event.target))
                return;
            aimAt(event.clientX, event.clientY);
        }
        function resetTarget() { targetX = 0; targetY = 0; }
        function pointerLeave(event) {
            if (!event.relatedTarget)
                resetTarget(); // Cursor left browser viewport.
        }
        function touchReleased(event) {
            if (event.pointerType === 'touch')
                resetTarget();
        }
        function blink(now) {
            if (!leftLid || !rightLid)
                return;
            if (prefersReducedMotion?.matches)
                return;
            if (!blinkStarted && now >= blinkAt)
                blinkStarted = now;
            if (!blinkStarted)
                return;
            const phase = Math.min(1, (now - blinkStarted) / 170);
            const amount = phase < 0.5 ? phase * 2 : (1 - phase) * 2;
            leftLid.setAttribute('opacity', amount.toFixed(2));
            rightLid.setAttribute('opacity', amount.toFixed(2));
            if (phase >= 1) {
                blinkStarted = 0;
                blinkAt = now + 2400 + Math.random() * 2300;
                leftLid.setAttribute('opacity', '0');
                rightLid.setAttribute('opacity', '0');
            }
        }
        function tick(now) {
            if (!enabled)
                return;
            const dt = previous ? clamp(now - previous, 4, 50) : 16;
            previous = now;
            const alpha = prefersReducedMotion?.matches ? 1 : 1 - Math.exp(-dt / 90);
            currentX += (targetX - currentX) * alpha;
            currentY += (targetY - currentY) * alpha;
            eyes.setAttribute('transform', `translate(${currentX.toFixed(2)} ${currentY.toFixed(2)})`);
            blink(now);
            frameId = requestAnimationFrame(tick);
        }
        return {
            start() {
                if (enabled)
                    return;
                enabled = true;
                previous = 0;
                blinkAt = clock() + 1400;
                window.addEventListener('pointermove', pointerMoved, { passive: true });
                window.addEventListener('pointerout', pointerLeave);
                window.addEventListener('blur', resetTarget);
                window.addEventListener('pointerup', touchReleased);
                frameId = requestAnimationFrame(tick);
            },
            stop() {
                if (enabled) {
                    enabled = false;
                    window.removeEventListener('pointermove', pointerMoved);
                    window.removeEventListener('pointerout', pointerLeave);
                    window.removeEventListener('blur', resetTarget);
                    window.removeEventListener('pointerup', touchReleased);
                }
                if (frameId)
                    cancelAnimationFrame(frameId);
                frameId = 0;
                previous = 0;
                currentX = currentY = targetX = targetY = 0;
                eyes.setAttribute('transform', 'translate(0 0)');
                leftLid?.setAttribute('opacity', '0');
                rightLid?.setAttribute('opacity', '0');
            }
        };
    }
    const gaze = createGazeController();
    const status = (text, badge = '● Ready to present') => {
        get('avatarState').textContent = text;
        get('avatarLive').textContent = badge;
    };
    function deactivateMouth() {
        stage.classList.remove('is-speaking');
        stage.classList.remove('neural-talking');
        stage.style?.setProperty?.('--mouth-scale', '1');
        if (raf) {
            cancelAnimationFrame(raf);
            raf = 0;
        }
    }
    function stop(resetPlayer = true) {
        if (speech)
            speech.cancel();
        utterance = null;
        if (player) {
            player.pause();
            if (resetPlayer) {
                try {
                    player.currentTime = 0;
                }
                catch (_) { }
            }
        }
        deactivateMouth();
        get('avatarPause').textContent = '⏸ Pause';
        get('avatarPause').disabled = true;
        get('avatarStop').disabled = true;
    }
    function unloadAudio() {
        ++voiceGeneration; // Invalidate old audio downloads after voice or story changes.
        stop();
        if (audioPending) {
            audioPending.abort();
            audioPending = null;
        }
        if (player) {
            player.removeAttribute('src');
            player.load?.();
            player = null;
        }
        if (playerUrl && typeof URL !== 'undefined') {
            URL.revokeObjectURL(playerUrl);
            playerUrl = null;
        }
        playerKey = null;
        pendingSample = false;
        if (context) {
            context.close().catch(() => { });
            context = null;
        }
        analyser = null;
        mediaSource = null;
    }
    function close() {
        ++generation;
        if (pending) {
            pending.abort();
            pending = null;
        }
        unloadAudio();
        gaze.stop();
        panel.hidden = true;
        panel.setAttribute('aria-hidden', 'true');
        document.body.style.overflow = '';
        active = null;
        lastFocus?.focus?.();
    }
    const actualLanguage = () => {
        const code = narrationLang.toLowerCase().split('-')[0];
        return ['en', 'hi', 'mr'].includes(code) ? code : 'en';
    };
    const selectedLanguage = () => ['en', 'hi', 'mr'].includes(languageSelect?.value) ? languageSelect.value : 'en';
    const languageName = code => ({ en: 'English', hi: 'Hindi', mr: 'Marathi' }[code] || 'English');
    const isHindi = () => actualLanguage() === 'hi';
    const isMarathi = () => actualLanguage() === 'mr';
    const currentProvider = () => voiceSelect?.value || 'edge-swara';
    function browserVoice() {
        const all = speech?.getVoices?.() || [];
        const lang = narrationLang.toLowerCase();
        const relevant = all.filter(v => v.lang && v.lang.toLowerCase().startsWith(lang.split('-')[0]));
        if (isHindi() || isMarathi()) {
            // Web Speech has no standardized gender field. These named-voice hints
            // are a best effort; never silently select an unidentified male voice.
            const femaleHint = relevant.find(v => /priyamvada|swara|female|kalpana|lekha|heera|neerja|geeta|veena|kavya|rani|divya|aarohi/i.test(v.name || ''));
            return femaleHint || (isMarathi() ? relevant[0] || null : null);
        }
        return relevant.find(v => v.lang.toLowerCase() === lang) || relevant[0] || null;
    }
    function playBrowser() {
        if (!speech || typeof SpeechSynthesisUtterance === 'undefined') {
            status('This browser cannot synthesize speech. Try an online narrator if available.', '● Voice unavailable');
            return;
        }
        const selectedVoice = browserVoice();
        if ((isHindi() || isMarathi()) && !selectedVoice) {
            status(`No suitable ${languageName(actualLanguage())} system voice found. Select an online narrator.`, '● Voice unavailable');
            return;
        }
        stop();
        utterance = new SpeechSynthesisUtterance(transcript);
        utterance.lang = narrationLang;
        utterance.rate = Number(get('avatarRate').value);
        if (selectedVoice)
            utterance.voice = selectedVoice;
        const current = utterance;
        utterance.onstart = () => {
            if (utterance !== current)
                return;
            stage.classList.add('is-speaking');
            status(`Speaking in ${languageName(actualLanguage())} using your system voice.`, '● Speaking');
            get('avatarPause').disabled = false;
            get('avatarStop').disabled = false;
        };
        utterance.onend = () => {
            if (utterance !== current)
                return;
            deactivateMouth();
            status('Finished. Press Play to listen again.');
            get('avatarPause').disabled = true;
            get('avatarStop').disabled = true;
        };
        utterance.onerror = () => {
            if (utterance !== current)
                return;
            deactivateMouth();
            status('System voice playback failed. Try another narrator.', '● Playback error');
        };
        speech.speak(utterance);
    }
    function animateVolume() {
        raf = 0;
        if (!player || player.paused || !analyser)
            return;
        const buffer = new Uint8Array(analyser.fftSize);
        analyser.getByteTimeDomainData(buffer);
        let sum = 0;
        for (let i = 0; i < buffer.length; i++) {
            const v = (buffer[i] - 128) / 128;
            sum += v * v;
        }
        const level = Math.min(1, Math.sqrt(sum / buffer.length) * 6);
        stage.style?.setProperty?.('--mouth-scale', String((0.75 + level * 0.95).toFixed(2)));
        raf = requestAnimationFrame(animateVolume);
    }
    function connectVolume() {
        const AudioContextType = window.AudioContext || window.webkitAudioContext;
        if (!AudioContextType || !player)
            return;
        try {
            context = new AudioContextType();
            analyser = context.createAnalyser();
            analyser.fftSize = 512;
            mediaSource = context.createMediaElementSource(player);
            mediaSource.connect(analyser);
            analyser.connect(context.destination);
        }
        catch (err) {
            analyser = null;
            console.warn('Avatar audio visualization unavailable:', err);
        }
    }
    function playLoaded() {
        if (!player)
            return;
        player.playbackRate = Number(get('avatarRate').value);
        const promise = player.play();
        if (promise && promise.catch)
            promise.catch(() => status('Browser blocked audio playback. Click Play again.', '● Audio blocked'));
    }
    // The selected provider and ACTUAL narration language always determine the audio.
    // During a translation outage the actual language is English, not the requested locale.
    async function playNeural(sample = false) {
        if (!active || (!sample && !transcript))
            return;
        const provider = currentProvider();
        const language = actualLanguage();
        if (!voicesAvailable[provider]) {
            status('Online narrator is unavailable. Use the browser voice or retry later.', '● Narrator unavailable');
            return;
        }
        const key = sample ? `sample:${language}:${provider}` : `${active.id}:${language}:${provider}:${transcript}`;
        if (player && playerKey === key) {
            stop();
            playLoaded();
            return;
        }
        unloadAudio(); // Aborts previous request, stops the old voice and clears old audio.
        const voiceTicket = voiceGeneration;
        const articleTicket = generation;
        const controller = new AbortController();
        audioPending = controller;
        pendingSample = sample;
        get('avatarPlay').disabled = true;
        status(sample ? `Generating ${languageName(language)} voice preview…`
            : `Generating ${languageName(language)} news narration…`, '● Generating');
        try {
            const voicePath = sample ? '/api/avatar/voice/sample' : '/api/avatar/voice/' + encodeURIComponent(active.id);
            const verifiedVoicePath = !sample && window.tbaStoryUrl ? window.tbaStoryUrl(voicePath, active) : voicePath;
            const response = await fetch(verifiedVoicePath, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                cache: 'no-store', body: JSON.stringify({ language, provider }), signal: controller.signal
            });
            if (!response.ok) {
                const info = await response.json().catch(() => ({}));
                throw Error(info.error || `Voice generator returned HTTP ${response.status}`);
            }
            const deliveredVoice = response.headers?.get?.('X-TBA-Voice');
            const deliveredLanguage = response.headers?.get?.('X-TBA-Language');
            if (deliveredVoice && deliveredVoice !== provider)
                throw Error('Voice provider mismatch; please retry.');
            if (deliveredLanguage && deliveredLanguage !== language)
                throw Error('Voice language mismatch; please retry.');
            const blob = await response.blob();
            if (articleTicket !== generation || voiceTicket !== voiceGeneration ||
                provider !== currentProvider() || language !== actualLanguage())
                return;
            playerUrl = URL.createObjectURL(blob);
            player = new Audio(playerUrl);
            playerKey = key;
            player.preload = 'auto';
            connectVolume();
            const shortened = response.headers?.get?.('X-TBA-Script-Truncated') === 'true';
            if (shortened && !sample)
                get('avatarSourceKind').textContent += ' The audio reads only the opening section of the available text.';
            const voiceLabel = provider === 'edge-swara'
                ? ({ hi: 'Swara (female, Hindi)', mr: 'Aarohi (female, Marathi)', en: 'Neerja (female, English)' }[language])
                : provider === 'edge-madhur'
                    ? ({ hi: 'Madhur (male, Hindi)', mr: 'Manohar (male, Marathi)', en: 'Prabhat (male, English)' }[language])
                    : (voiceSelect?.selectedOptions?.[0]?.textContent?.split(' · ')[0] || provider);
            player.onplay = () => {
                stage.classList.add('is-speaking', 'neural-talking');
                status(`Playing ${languageName(language)} narration with ${voiceLabel}.`, '● Speaking');
                get('avatarPause').disabled = false;
                get('avatarStop').disabled = false;
                if (context?.state === 'suspended')
                    context.resume().catch(() => { });
                if (!raf && analyser)
                    raf = requestAnimationFrame(animateVolume);
            };
            player.onpause = () => { deactivateMouth(); };
            player.onended = () => {
                deactivateMouth();
                status('Finished. Press Play to listen again.');
                get('avatarPause').disabled = true;
                get('avatarStop').disabled = true;
            };
            player.onerror = () => status('Audio could not play. Please retry.', '● Playback error');
            playLoaded();
        }
        catch (err) {
            if (err.name !== 'AbortError' && articleTicket === generation && voiceTicket === voiceGeneration)
                status(err.message || 'Voice generation failed.', '● Voice error');
        }
        finally {
            if (audioPending === controller) {
                audioPending = null;
                pendingSample = false;
            }
            if (articleTicket === generation && voiceTicket === voiceGeneration)
                get('avatarPlay').disabled = !transcript;
        }
    }
    function play() {
        if (!transcript)
            return;
        if (currentProvider() !== 'browser')
            playNeural();
        else
            playBrowser();
    }
    function updateVoiceUI() {
        const enabled = true; // Preserve narrator choice if Hindi/Marathi translation falls back to English.
        const row = get('avatarVoiceRow');
        if (row)
            row.hidden = false;
        if (enabled) {
            const help = get('avatarVoiceHelp');
            const selected = currentProvider();
            if (selected === 'browser')
                help.textContent = 'Uses an English, Hindi, or Marathi system voice available in your browser.';
            else if (voicesAvailable[selected])
                help.textContent = selectedLanguage() === 'en'
                    ? 'Online English narrator available. No translation is needed.'
                    : `Online ${languageName(selectedLanguage())} narrator. Translation may use a third-party provider; the text is sent to Microsoft for speech.`;
            else
                help.textContent = 'Online narrator is currently unavailable; browser speech remains available.';
        }
    }
    async function checkProviders() {
        try {
            const response = await fetch('/api/avatar/voice/status');
            if (!response.ok)
                return;
            const data = await response.json();
            for (const name of Object.keys(voicesAvailable)) {
                voicesAvailable[name] = !!data?.providers?.[name];
            }
            updateVoiceUI();
        }
        catch (_) { /* The basic browser-only mode still works. */ }
    }
    async function prepare() {
        if (!active)
            return;
        const ticket = ++generation;
        if (pending)
            pending.abort();
        pending = new AbortController();
        unloadAudio();
        transcript = '';
        get('avatarPlay').disabled = true;
        const desired = languageSelect.value;
        updateVoiceUI();
        get('avatarTranscript').lang = desired;
        get('avatarTranscript').textContent = desired === 'hi'
            ? 'हिंदी में समाचार तैयार हो रहा है…'
            : desired === 'mr' ? 'मराठीत बातम्या तयार होत आहेत…' : 'Preparing your English news briefing…';
        get('avatarSourceKind').hidden = true;
        status(desired === 'en'
            ? 'Retrieving available news information…'
            : `Preparing news and ${languageName(desired)} translation…`, '● Preparing');
        try {
            const narrationPath = '/api/avatar/narration/' + encodeURIComponent(active.id);
            const res = await fetch(window.tbaStoryUrl ? window.tbaStoryUrl(narrationPath, active) : narrationPath, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ language: desired }), signal: pending.signal
            });
            const data = await res.json();
            if (ticket !== generation)
                return;
            if (!res.ok)
                throw Error(data.error || 'Could not prepare briefing');
            transcript = data.text || '';
            narrationLang = data.language || 'en-IN';
            get('avatarTranscript').lang = actualLanguage();
            get('avatarTranscript').textContent = transcript;
            get('avatarPlay').disabled = !transcript;
            const notice = get('avatarSourceKind');
            notice.hidden = false;
            notice.textContent = data.notice || 'Based on available publisher text.';
            const fallback = desired !== 'en' && actualLanguage() !== desired;
            status(fallback
                ? `${languageName(desired)} translation unavailable. English briefing ready; the selected narrator will speak English.`
                : `${languageName(desired)} briefing ready. Select a narrator and press Play.`, '● Ready');
            updateVoiceUI();
            // If translation failed the backend gave an English script, never request
            // Hindi or Marathi speech for it.
        }
        catch (err) {
            if (ticket !== generation && err.name === 'AbortError')
                return;
            if (ticket !== generation)
                return;
            get('avatarTranscript').textContent = 'Could not prepare a briefing. Try another story or refresh the feed.';
            status(err.message || 'Please try again.', '● Unavailable');
        }
        finally {
            if (ticket === generation)
                pending = null;
        }
    }
    function open(item) {
        if (!item?.id)
            return;
        lastFocus = document.activeElement;
        active = item;
        panel.hidden = false;
        gaze.start();
        panel.setAttribute('aria-hidden', 'false');
        document.body.style.overflow = 'hidden';
        get('avatarHeadline').textContent = item.title || 'News briefing';
        get('avatarClose').focus();
        checkProviders();
        prepare();
    }
    get('avatarPlay').addEventListener('click', play);
    get('avatarVoiceSample')?.addEventListener('click', () => {
        if (currentProvider() === 'browser') {
            status('Choose an online narrator in the menu to preview it.', '● Select online narrator');
            return;
        }
        playNeural(true);
    });
    get('avatarStop').addEventListener('click', () => { if (audioPending)
        unloadAudio();
    else
        stop(); get('avatarPlay').disabled = !transcript; status('Playback stopped.'); });
    get('avatarPause').addEventListener('click', () => {
        if (player && !player.ended) {
            if (player.paused) {
                playLoaded();
                get('avatarPause').textContent = '⏸ Pause';
            }
            else {
                player.pause();
                get('avatarPause').textContent = '▶ Resume';
            }
            return;
        }
        if (!speech)
            return;
        if (speech.paused) {
            speech.resume();
            get('avatarPause').textContent = '⏸ Pause';
            stage.classList.add('is-speaking');
        }
        else if (speech.speaking) {
            speech.pause();
            get('avatarPause').textContent = '▶ Resume';
            deactivateMouth();
        }
    });
    languageSelect.addEventListener('change', prepare);
    voiceSelect?.addEventListener('change', () => {
        // Abort the previous request, discard its result, and immediately start
        // the newly selected voice if there is a prepared article or sample.
        const wasPlaying = !!(player && !player.paused) || !!(utterance && speech?.speaking);
        const wasGenerating = !!audioPending;
        const wasSample = !!playerKey?.startsWith('sample:') || !!pendingSample;
        unloadAudio();
        updateVoiceUI();
        if (transcript && (wasPlaying || wasGenerating)) {
            if (currentProvider() === 'browser')
                playBrowser();
            else
                playNeural(wasSample);
        }
        else {
            status('Narrator changed. Press Play to hear the selected voice.', '● Ready');
        }
    });
    get('avatarRate').addEventListener('input', e => {
        const rate = Number(e.target.value);
        get('avatarRateLabel').textContent = rate.toFixed(1) + '×';
        if (player)
            player.playbackRate = rate;
    });
    get('avatarClose').addEventListener('click', close);
    panel.addEventListener('click', e => { if (e.target.dataset?.avatarClose)
        close(); });
    document.addEventListener('keydown', e => {
        if (e.key === 'Escape' && !panel.hidden) {
            e.stopImmediatePropagation();
            close();
        }
    }, true);
    window.addEventListener('pagehide', () => { unloadAudio(); gaze.stop(); });
    window.TBAAvatar = { open, close };
})();
