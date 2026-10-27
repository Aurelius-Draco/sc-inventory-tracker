# Design preview

`dashboard-preview.html` is the real dashboard with sample data built in, so
you can open it in a browser and work on the look without the game or the
tracker running. The sample data lives in one block marked `DEMO MOCK START`
... `DEMO MOCK END`. It fakes the server's `/api/*` replies and nothing else.

The page players actually get is `sctracker/static/index.html`. The two are
kept in step with `tools/make_preview.py`:

```
python tools/make_preview.py           # rebuild the preview from the real page
python tools/make_preview.py --apply   # copy design changes back into the real page
```

Rules for changes to the page:

- One self-contained HTML file: inline CSS and plain JavaScript, no frameworks, no build step.
- Nothing loaded from the internet (no CDN scripts, web fonts or external images). Fonts that ship with Windows only; icons as inline SVG or CSS.
- Keep the `__TOKEN__` and `__VERSION__` placeholders, the `api(path, body)` helper, every `/api/...` path and every request payload as they are.
- App code stays outside the sample data block.
- Plain, friendly Australian English in sentence case. No em dashes.

`tests/test_page.py` checks the first two rules on every push.
