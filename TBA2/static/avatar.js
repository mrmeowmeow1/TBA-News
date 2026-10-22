"use strict";
(() => {
    const get = id => document.getElementById(id);
    const panel = get('newsAvatar');
    const stage = get('avatarFigure');
    const speech = window.speechSynthesis;
    const languageSelect = get('avatarLanguage');
    const narratorPreset = get('avatarNarratorPreset');
    let active = null, transcript = '', narrationLang = 'en-IN', utterance = null;
    let generation = 0, voiceGeneration = 0, lastFocus = null, pending = null, audioPending = null;
    let player = null, playerUrl = null, playerKey = null, pendingSample = false;
    let context = null, analyser = null, mediaSource = null, raf = 0;
    const voicesAvailable = { piper: false, 'piper-rohan': false, parler: false, 'edge-swara': false, 'edge-madhur': false };
    const isHindi = () => narrationLang.toLowerCase().startsWith('hi');
    const isMarathi = () => narrationLang.toLowerCase().startsWith('mr');
    const isBhojpuri = () => narrationLang.toLowerCase().startsWith('bho');
    const isMalayalam = () => narrationLang.toLowerCase().startsWith('ml');
    const isTatyaMode = () => (languageSelect?.value === 'mr') || isMarathi();
    // One authoritative user choice: there is no competing advanced engine selector.
    const currentProvider = () => (narratorPreset?.value || 'en:edge-swara').split(':')[1] === 'edge-madhur' ? 'edge-madhur' : 'edge-swara';
    const isFemaleNarrator = () => {
        const provider = currentProvider();
        return provider === 'edge-swara';
    };
    let tatyaCurlsInitialized = false;
    function initTatyaCurls() {
        if (tatyaCurlsInitialized)
            return;
        const curls = get('tatyaCurls');
        if (!curls || typeof document.createElementNS !== 'function')
            return;
        tatyaCurlsInitialized = true;
        let seed = 41;
        const rand = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; };
        const palette = ['#271820', '#33202a', '#3b2630', '#20141c', '#49303a'];
        for (let i = 0; i < 210; i++) {
            const a = rand() * Math.PI * 2;
            const x = 320 + Math.cos(a) * (145 + rand() * 50);
            const y = 186 + Math.sin(a) * (119 + rand() * 48);
            if (y > 320 || x < 122 || x > 515)
                continue;
            const r = 7 + rand() * 16;
            const c = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
            c.setAttribute('cx', x.toFixed(1));
            c.setAttribute('cy', y.toFixed(1));
            c.setAttribute('r', r.toFixed(1));
            c.setAttribute('fill', palette[Math.floor(rand() * 5)]);
            c.setAttribute('opacity', (0.65 + rand() * 0.33).toFixed(2));
            curls.appendChild(c);
        }
    }
    function setTatyaMouth(level) {
        const shape = get('tatyaMouthShape');
        if (!shape)
            return;
        const upper = get('tatyaUpperLip');
        const teeth = get('tatyaUpperTeeth');
        const tongue = get('tatyaTongueShape');
        const open = Math.max(0, Math.min(1, (level - 0.045) / 0.62));
        const depth = 4 + open * 29;
        const halfWidth = 42 + open * 4;
        const left = 323 - halfWidth, right = 323 + halfWidth;
        const top = 389;
        shape.setAttribute('d', `M${left} ${top} Q323 ${top + 12 + open * 2} ${right} ${top} Q323 ${top + depth * 2 + 10} ${left} ${top}Z`);
        if (upper)
            upper.setAttribute('d', `M${left} ${top} Q323 ${top + 11 + open * 2} ${right} ${top}`);
        if (teeth) {
            teeth.setAttribute('d', `M${left + 9} ${top + 5} Q323 ${top + 14 + open * 2} ${right - 9} ${top + 5} Q323 ${top + 15 + open * 3} ${left + 9} ${top + 5}Z`);
            teeth.setAttribute('opacity', Math.min(1, open * 3).toFixed(2));
        }
        if (tongue) {
            tongue.setAttribute('d', `M305 ${top + depth + 4} Q323 ${top + depth - 3} 341 ${top + depth + 4} Q323 ${top + depth + 11} 305 ${top + depth + 4}Z`);
            tongue.setAttribute('opacity', Math.max(0, Math.min(1, (open - 0.22) * 2)).toFixed(2));
        }
    }
    function setFemaleMouth(level) {
        const shape = get('femaleMouthShape');
        if (!shape)
            return;
        const clip = get('femaleMouthClipShape');
        const smile = get('femaleSmileLine');
        const teeth = get('femaleTeeth');
        const open = Math.max(0, Math.min(1, (level - 0.04) / 0.58));
        const left = 270 - 26, right = 270 + 26;
        const topY = 359 - open * 2.5;
        const bottomY = 360 + open * 26;
        const mouthPath = `M${left.toFixed(2)} 354 Q270 ${topY.toFixed(2)} ${right.toFixed(2)} 354 Q270 ${bottomY.toFixed(2)} ${left.toFixed(2)} 354Z`;
        shape.setAttribute?.('d', mouthPath);
        if (clip)
            clip.setAttribute?.('d', mouthPath);
        if (smile) {
            smile.setAttribute?.('d', `M${left.toFixed(2)} 354 Q270 360 ${right.toFixed(2)} 354`);
            smile.setAttribute?.('opacity', String(Math.max(0, 1 - open * 2.4)));
        }
        if (teeth) {
            teeth.setAttribute?.('opacity', String(Math.max(0, Math.min(0.65, (open - 0.3) * 2))));
        }
    }
    function updateAvatarCharacter() {
        const isTatya = isTatyaMode();
        const isFemale = !isTatya && isFemaleNarrator();
        const defaultWrap = get('defaultAvatarWrap');
        const tatyaWrap = get('tatyaAvatarWrap');
        const femaleWrap = get('femaleAvatarWrap');
        const stageEl = stage?.closest?.('.avatar-stage');
        const eyebrow = get('avatarEyebrow');
        if (isTatya) {
            if (defaultWrap)
                defaultWrap.hidden = true;
            if (femaleWrap)
                femaleWrap.hidden = true;
            if (tatyaWrap)
                tatyaWrap.hidden = false;
            stage?.classList?.add?.('is-tatya');
            stageEl?.classList?.add?.('is-tatya');
            stage?.classList?.remove?.('is-female');
            stageEl?.classList?.remove?.('is-female');
            if (eyebrow) {
                eyebrow.textContent = '🎭 TATYA VINCHU · MARATHI PRESENTER';
                eyebrow.classList?.add?.('is-tatya');
                eyebrow.classList?.remove?.('is-female');
            }
            initTatyaCurls();
            setFemaleMouth(0);
        }
        else if (isFemale) {
            if (defaultWrap)
                defaultWrap.hidden = true;
            if (tatyaWrap)
                tatyaWrap.hidden = true;
            if (femaleWrap)
                femaleWrap.hidden = false;
            stage?.classList?.remove?.('is-tatya');
            stageEl?.classList?.remove?.('is-tatya');
            stage?.classList?.add?.('is-female');
            stageEl?.classList?.add?.('is-female');
            if (eyebrow) {
                eyebrow.textContent = '👑 PRINCESS LUNA · AI NEWS PRESENTER';
                eyebrow.classList?.remove?.('is-tatya');
                eyebrow.classList?.add?.('is-female');
            }
            setTatyaMouth(0);
        }
        else {
            if (defaultWrap)
                defaultWrap.hidden = false;
            if (tatyaWrap)
                tatyaWrap.hidden = true;
            if (femaleWrap)
                femaleWrap.hidden = true;
            stage?.classList?.remove?.('is-tatya');
            stageEl?.classList?.remove?.('is-tatya');
            stage?.classList?.remove?.('is-female');
            stageEl?.classList?.remove?.('is-female');
            if (eyebrow) {
                eyebrow.textContent = 'TBA · AI NEWS PRESENTER';
                eyebrow.classList?.remove?.('is-tatya');
                eyebrow.classList?.remove?.('is-female');
            }
            setTatyaMouth(0);
            setFemaleMouth(0);
        }
        const pills = document.querySelectorAll?.('.avatar-lang-pill');
        if (pills) {
            const current = languageSelect?.value || 'en';
            for (let i = 0; i < pills.length; i++) {
                const pill = pills[i];
                if (pill?.dataset?.lang === current)
                    pill?.classList?.add?.('is-active');
                else
                    pill?.classList?.remove?.('is-active');
            }
        }
    }
    // Interactive gaze stays entirely in the browser. No camera, tracking API,
    // uploaded cursor data, extra package or server endpoint is necessary.
    function createGazeController() {
        const eyes = stage?.querySelector?.('#pupils');
        const whites = stage?.querySelector?.('#eyeWhites');
        const leftLid = stage?.querySelector?.('#blinkL');
        const rightLid = stage?.querySelector?.('#blinkR');
        const tatyaLeft = stage?.querySelector?.('#tatyaLeftPupil');
        const tatyaRight = stage?.querySelector?.('#tatyaRightPupil');
        const tatyaLidL = stage?.querySelector?.('#tatyaLidLeft');
        const tatyaLidR = stage?.querySelector?.('#tatyaLidRight');
        const tatyaWhites = stage?.querySelector?.('#tatyaEyeWhites');
        const femaleEyeL = stage?.querySelector?.('#femaleEyeL');
        const femaleEyeR = stage?.querySelector?.('#femaleEyeR');
        const femaleLids = stage?.querySelector?.('#femaleLids');
        const femaleWhites = stage?.querySelector?.('#femaleEyeWhites');
        const prefersReducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)');
        if ((!eyes && !tatyaLeft && !femaleEyeL) || typeof requestAnimationFrame !== 'function') {
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
            const activeWhites = isTatyaMode() ? (tatyaWhites || whites) : (isFemaleNarrator() ? (femaleWhites || whites) : (whites || tatyaWhites));
            if (!activeWhites?.getBoundingClientRect)
                return;
            const bounds = activeWhites.getBoundingClientRect();
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
            if (prefersReducedMotion?.matches)
                return;
            if (!blinkStarted && now >= blinkAt)
                blinkStarted = now;
            if (!blinkStarted)
                return;
            const phase = Math.min(1, (now - blinkStarted) / 170);
            const amount = phase < 0.5 ? phase * 2 : (1 - phase) * 2;
            leftLid?.setAttribute?.('opacity', amount.toFixed(2));
            rightLid?.setAttribute?.('opacity', amount.toFixed(2));
            if (tatyaLidL && tatyaLidR) {
                const s = `scaleY(${amount.toFixed(2)})`;
                tatyaLidL.style.transform = s;
                tatyaLidR.style.transform = s;
            }
            femaleLids?.setAttribute?.('opacity', amount > 0.35 ? '1' : '0');
            if (phase >= 1) {
                blinkStarted = 0;
                blinkAt = now + 2400 + Math.random() * 2300;
                leftLid?.setAttribute?.('opacity', '0');
                rightLid?.setAttribute?.('opacity', '0');
                if (tatyaLidL && tatyaLidR) {
                    tatyaLidL.style.transform = 'scaleY(0)';
                    tatyaLidR.style.transform = 'scaleY(0)';
                }
                femaleLids?.setAttribute?.('opacity', '0');
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
            const txStr = currentX.toFixed(2);
            const tyStr = currentY.toFixed(2);
            eyes?.setAttribute?.('transform', `translate(${txStr} ${tyStr})`);
            if (tatyaLeft && tatyaRight) {
                tatyaLeft.setAttribute('transform', `translate(${txStr} ${tyStr})`);
                tatyaRight.setAttribute('transform', `translate(${txStr} ${tyStr})`);
            }
            if (femaleEyeL && femaleEyeR) {
                femaleEyeL.setAttribute('transform', `translate(${txStr} ${tyStr})`);
                femaleEyeR.setAttribute('transform', `translate(${txStr} ${tyStr})`);
            }
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
                eyes?.setAttribute?.('transform', 'translate(0 0)');
                leftLid?.setAttribute?.('opacity', '0');
                rightLid?.setAttribute?.('opacity', '0');
                tatyaLeft?.setAttribute?.('transform', 'translate(0 0)');
                tatyaRight?.setAttribute?.('transform', 'translate(0 0)');
                if (tatyaLidL)
                    tatyaLidL.style.transform = 'scaleY(0)';
                if (tatyaLidR)
                    tatyaLidR.style.transform = 'scaleY(0)';
                femaleEyeL?.setAttribute?.('transform', 'translate(0 0)');
                femaleEyeR?.setAttribute?.('transform', 'translate(0 0)');
                femaleLids?.setAttribute?.('opacity', '0');
            }
        };
    }
    const gaze = createGazeController();
    const status = (text, badge = '● Ready to present') => {
        get('avatarState').textContent = text;
        get('avatarLive').textContent = badge;
    };
    function deactivateMouth() {
        stage?.classList?.remove?.('is-speaking');
        stage?.classList?.remove?.('neural-talking');
        stage?.style?.setProperty?.('--mouth-scale', '1');
        setTatyaMouth(0);
        setFemaleMouth(0);
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
    const currentLangCode = () => {
        if (isHindi()) return 'hi';
        if (isMarathi()) return 'mr';
        if (isBhojpuri()) return 'bho';
        if (isMalayalam()) return 'ml';
        return 'en';
    };
    const currentLangName = () => {
        if (isHindi()) return 'Hindi';
        if (isMarathi()) return 'Marathi';
        if (isBhojpuri()) return 'Bhojpuri';
        if (isMalayalam()) return 'Malayalam';
        return 'English';
    };
    function browserVoice() {
        const all = speech?.getVoices?.() || [];
        const lang = narrationLang.toLowerCase();
        const relevant = all.filter(v => v.lang && v.lang.toLowerCase().startsWith(lang.split('-')[0]));
        if (isHindi()) {
            // Web Speech has no standardized gender field. These named-voice hints
            // are a best effort; never silently select an unidentified male voice.
            return relevant.find(v => /priyamvada|swara|female|kalpana|lekha|heera|neerja|geeta|veena|kavya|rani|divya/i.test(v.name || '')) || null;
        }
        if (isMarathi()) {
            return relevant.find(v => /aarohi|manohar|marathi|female|swara/i.test(v.name || '')) || relevant[0] || null;
        }
        if (isBhojpuri()) {
            return relevant.find(v => /bhojpuri|swara|madhur|female|hindi/i.test(v.name || '')) || relevant[0] || null;
        }
        if (isMalayalam()) {
            return relevant.find(v => /sobhana|midhun|malayalam|female/i.test(v.name || '')) || relevant[0] || null;
        }
        return relevant.find(v => v.lang.toLowerCase() === lang) || relevant[0] || null;
    }
    function playBrowser() {
        if (!speech || typeof SpeechSynthesisUtterance === 'undefined') {
            status('This browser cannot synthesize speech. Install Piper for local Hindi narration.', '● Voice unavailable');
            return;
        }
        const selectedVoice = browserVoice();
        if (isHindi() && !selectedVoice) {
            status('No suitable Hindi system voice found. Select Swara or Madhur for neural narration.', '● Voice unavailable');
            return;
        }
        if (isMarathi() && !selectedVoice) {
            status('No suitable Marathi system voice found. Select Aarohi or Manohar for neural narration.', '● Voice unavailable');
            return;
        }
        if (isBhojpuri() && !selectedVoice) {
            status('No suitable Bhojpuri system voice found. Select Swara or Madhur for neural narration.', '● Voice unavailable');
            return;
        }
        if (isMalayalam() && !selectedVoice) {
            status('No suitable Malayalam system voice found. Select Sobhana or Midhun for neural narration.', '● Voice unavailable');
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
            status(`Speaking in ${currentLangName()} using your system voice.`, '● Speaking');
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
        stage?.style?.setProperty?.('--mouth-scale', String((0.75 + level * 0.95).toFixed(2)));
        if (isTatyaMode()) {
            setTatyaMouth(level);
        } else if (isFemaleNarrator()) {
            setFemaleMouth(level);
        }
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
    // During a translation outage the actual language is English, not Hindi.
    async function playNeural(sample = false) {
        if (!active || (!sample && !transcript))
            return;
        const provider = currentProvider();
        const language = sample ? (languageSelect?.value || currentLangCode()) : currentLangCode();
        const langName = sample ? ({ en:'English',hi:'Hindi',mr:'Marathi',bho:'Bhojpuri',ml:'Malayalam' }[language] || currentLangName()) : currentLangName();
        if (!voicesAvailable[provider]) {
            // A status check only detects package installation; trying the request also
            // gives the actual backend error (e.g. network/voice-service outage).
            status('Checking online narrator availability…', '● Connecting');
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
        status(sample ? `Generating ${langName} voice preview…`
            : `Generating ${langName} news narration…`, '● Generating');
        try {
            const response = await fetch(sample ? '/api/avatar/voice/sample' : '/api/avatar/voice/' + encodeURIComponent(active.id), {
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
                provider !== currentProvider() ||
                (sample ? language !== languageSelect?.value : language !== currentLangCode()))
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
                ? (language === 'hi' ? 'Swara (female, Hindi)'
                    : (language === 'mr' ? 'Aarohi (female, Marathi)'
                        : (language === 'bho' ? 'Swara (female Hindi voice reading Bhojpuri)'
                            : (language === 'ml' ? 'Sobhana (female, Malayalam)' : 'Neerja (female, English)'))))
                : provider === 'edge-madhur'
                    ? (language === 'hi' ? 'Madhur (male, Hindi)'
                        : (language === 'mr' ? 'Manohar (male, Marathi)'
                            : (language === 'bho' ? 'Madhur (male Hindi voice reading Bhojpuri)'
                                : (language === 'ml' ? 'Midhun (male, Malayalam)' : 'Prabhat (male, English)'))))
                    : provider;
            player.onplay = () => {
                stage.classList.add('is-speaking', 'neural-talking');
                status(`Playing ${langName} narration with ${voiceLabel}.`, '● Speaking');
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
        playNeural();
    }
    // The language buttons preserve female/male when changing languages.
    function syncNarratorPreset() {
        if (!narratorPreset || !languageSelect) return;
        narratorPreset.value = `${languageSelect.value}:${currentProvider()}`;
    }
    function updateVoiceUI() {
        syncNarratorPreset();
        const row = get('avatarVoiceRow');
        if (row) row.hidden = false;
        const help = get('avatarVoiceHelp');
        if (!help) return;
        const desired = languageSelect?.value || 'en';
        const selected = currentProvider();
        const female = selected === 'edge-swara';
        const voiceNames = {
            en: ['Neerja', 'Prabhat'], hi: ['Swara', 'Madhur'],
            mr: ['Aarohi', 'Manohar'], bho: ['Swara', 'Madhur'],
            ml: ['Sobhana', 'Midhun']
        };
        const name = (voiceNames[desired] || voiceNames.en)[female ? 0 : 1];
        const languageName = { en: 'English', hi: 'Hindi', mr: 'Marathi', bho: 'Bhojpuri', ml: 'Malayalam' }[desired];
        const approximation = desired === 'bho' ? ' This is a Hindi voice reading Bhojpuri text; the accent is approximate.' : '';
        const translationFallback = transcript && currentLangCode() !== desired;
        const providerStatus = voicesAvailable[selected] ? '' : ' The online voice service may be unavailable; use Preview to check.';
        help.textContent = translationFallback
            ? `${languageName} translation is unavailable. Article playback will use ${female ? 'Neerja' : 'Prabhat'} in English; voice preview still tests ${name} in ${languageName}.${approximation}${providerStatus}`
            : `${languageName}: ${name} (${female ? 'female' : 'male'}).${approximation} Narration requires internet; text is sent to Microsoft.${providerStatus}`;
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
        updateAvatarCharacter();
        updateVoiceUI();
        get('avatarTranscript').lang = desired;
        get('avatarTranscript').textContent = desired === 'hi'
            ? 'हिंदी में समाचार तैयार हो रहा है…'
            : (desired === 'mr' ? 'मराठीत बातमी तयार होत आहे…'
                : (desired === 'bho' ? 'भोजपुरी में खबर तैयार हो रहल बा…'
                    : (desired === 'ml' ? 'മലയാളത്തിൽ വാർത്ത തയ്യാറാക്കുന്നു…' : 'Preparing your English news briefing…')));
        get('avatarSourceKind').hidden = true;
        const prepNames = { hi: 'Hindi', mr: 'Marathi', bho: 'Bhojpuri', ml: 'Malayalam' };
        status(prepNames[desired]
            ? (desired === 'mr' ? 'Tatya Vinchu is preparing news and Marathi translation…' : `Preparing news and ${prepNames[desired]} translation…`)
            : 'Retrieving available news information…', '● Preparing');
        try {
            const res = await fetch('/api/avatar/narration/' + encodeURIComponent(active.id), {
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
            updateAvatarCharacter();
            get('avatarTranscript').lang = currentLangCode();
            get('avatarTranscript').textContent = transcript;
            get('avatarPlay').disabled = !transcript;
            const notice = get('avatarSourceKind');
            notice.hidden = false;
            notice.textContent = data.notice || 'Based on available publisher text.';
            const isNonEnglish = isHindi() || isMarathi() || isBhojpuri() || isMalayalam();
            const fallback = ['hi', 'mr', 'bho', 'ml'].includes(desired) && !isNonEnglish;
            const langLabel = currentLangName();
            status(fallback
                ? `${prepNames[desired] || desired} translation unavailable. English briefing ready; selected narrator will use English female/male voices.`
                : (desired === 'mr' ? 'Tatya Vinchu is ready with your Marathi briefing. Select a narrator and press Play.' : `${langLabel} briefing ready. Select a narrator and press Play.`), '● Ready');
            updateVoiceUI();
            // If translation failed the backend gave an English script, never try to
            // read that with Hindi neural voice.
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
        updateAvatarCharacter();
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
    // The prominent preset menu directly selects language AND female/male voice.
    let lastSelectedProvider = currentProvider();
    narratorPreset?.addEventListener?.('change', () => {
        const [lang, provider] = (narratorPreset.value || '').split(':');
        if (!['en','hi','mr','bho','ml'].includes(lang) ||
            !['edge-swara','edge-madhur'].includes(provider)) return;
        const languageChanged = languageSelect.value !== lang;
        // Read the previous gender before the preset value changed by the browser.
        // Language comes directly from the chosen preset, not a second dropdown.
        const voiceChanged = provider !== lastSelectedProvider;
        languageSelect.value = lang;
        lastSelectedProvider = provider;
        if (languageChanged) prepare();
        else if (voiceChanged) onVoiceChanged();
        else { updateVoiceUI(); updateAvatarCharacter(); }
    });
    languageSelect?.addEventListener?.('change', prepare);
    // For a <select>, change is sufficient. Avoid duplicate translation requests
    // (input + change) that can trigger provider rate limits.
    get('avatarLangPills')?.addEventListener?.('click', e => {
        const btn = e.target?.closest?.('.avatar-lang-pill');
        if (!btn || !btn.dataset?.lang)
            return;
        if (languageSelect && languageSelect.value !== btn.dataset.lang) {
            languageSelect.value = btn.dataset.lang;
            prepare();
        }
    });
    function onVoiceChanged() {
        // Never wait for Flask restart or keep playing an old generated MP3.
        // Abort the previous request, discard its result, and immediately start
        // the newly selected voice if there is a prepared article or sample.
        const wasPlaying = !!(player && !player.paused) || !!(utterance && speech?.speaking);
        const wasGenerating = !!audioPending;
        const wasSample = !!playerKey?.startsWith('sample:') || !!pendingSample;
        unloadAudio();
        updateAvatarCharacter();
        updateVoiceUI();
        if (transcript && (wasPlaying || wasGenerating)) {
            playNeural(wasSample);
        }
        else {
            status('Narrator changed. Press Play to hear the selected voice.', '● Ready');
        }
    }
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
    syncNarratorPreset();
    window.TBAAvatar = { open, close, setLanguage: (lang) => { if (languageSelect) { languageSelect.value = lang; prepare(); } } };
})();
