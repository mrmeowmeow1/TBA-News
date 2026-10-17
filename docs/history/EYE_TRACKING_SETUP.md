# Interactive eyes — TBA AI News Presenter

The existing news avatar now tracks the mouse cursor with its eyes. This is a **browser-only JavaScript interaction**: it does not need a camera, permission prompt, Python model, ML inference, or extra pip packages.

## Try it
1. Start TBA normally using `python app.py`.
2. Open `http://127.0.0.1:5000`.
3. Click **✦ Try me** on any story.
4. Move your cursor left, right, up and down, and watch the pupils follow. The avatar blinks occasionally.
5. Move the cursor outside the browser or close the presenter; eyes return to their neutral position.

Touch screens: drag a finger over the avatar panel to move the eyes; release to center them. Respect for `prefers-reduced-motion` disables motion effects.

## Modified files
- `static/avatar.js`: a `createGazeController()` with bounded targets, eased animation, blink timing, and event cleanup on dialog close. The speech and audio controls are preserved.
- `templates/avatar_character.html`: eyelid overlays for visible blinking.
- `templates/index.html`: subtle indicator on the avatar stage.
- `static/avatar.css`: indicator styles and reduced-motion preference.
- `tests/avatar_gaze_smoke.js`: browser-independent regression check for pointer tracking and cleanup.

## Important
Cursor tracking is an interactive animation feature, not eye tracking with a camera or a machine learning feature. The backend's article fetch, voice model, translation, and caching are unchanged.
