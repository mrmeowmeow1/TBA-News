# TBA — Logo and branding

The TBA logo is based on the supplied original image and is included **inside this project**; there is no external logo CDN.

| Asset | Location | Use |
|---|---|---|
| Full logo | `static/assets/tba-logo.webp` | Sidebar, mobile header, share-card graphic |
| Editable-quality raster | `static/assets/tba-logo.png` | Printing and exports |
| Browser favicon | `static/assets/favicon-16.png`, `favicon-32.png` | Browser tab |
| Apple touch icon | `static/assets/apple-touch-icon.png` | Mobile home-screen icon |
| Larger app icon | `static/assets/tba-app-icon.png` | App/social integrations |
| Social preview image | `static/assets/tba-social.jpg` | Open Graph image |

The wordmark has a white background; the website intentionally displays it on a white badge for contrast with the navy sidebar. The small icons are crops of the original **T** design.

## Replacing the logo

When changing the artwork, preserve the above filenames or update their paths in `templates/index.html` and `static/share.js` together. Ensure the wordmark still reads **TBA** and stays legible on mobile. Shared story cards render the logo in an image only if the asset loads; otherwise they fall back to branded text.

Do not delete `innews-bookmarks-v1` or `innews-theme` compatibility keys in `static/app.js`: those keys are intentionally kept to import existing user preferences from earlier versions of the project.
