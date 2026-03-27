# luther-contabulate

Search Luther's German Bible by token, phrase, and regex across testaments, books, chapters, verses, and verse text.

This repo contains:

- A Python build pipeline (`build.py`) that reads an OSIS XML source in `osis/`.
- A static web UI in `docs/` for GitHub Pages.
- Python and Playwright smoke tests for data and UI behavior.

## Corpus

- Source: `osis/deu-luther1912.osis.xml`
- Upstream family: [seven1m/open-bibles](https://github.com/seven1m/open-bibles)
- Edition: Luther 1912 OSIS text
- Scope: Old Testament + New Testament
- Default build excludes apocrypha/deuterocanon
- The build prefers `deu-luther1912.osis.xml` when present and falls back to other OSIS XML files only if needed.

## Build Data

Generate or regenerate the site data:

```bash
python3 build.py
```

Outputs:

- `docs/data/plays.json` for books
- `docs/data/chunks.json` for verses
- `docs/data/tokens.json`, `tokens2.json`, `tokens3.json`
- `docs/lines/all_lines.json` for verse-text search

## Run Locally

```bash
python3 -m http.server 8766 -d docs
```

Then open [http://localhost:8766](http://localhost:8766).

## Tests

Python:

```bash
python3 -m unittest tests.test_build_output test_parse_play -v
```

Playwright:

```bash
npm install
npx playwright install
npx playwright test
```

## Notes

- Generated JSON under `docs/data/` and `docs/lines/` is committed output for the static site.
- The frontend preserves the KJV Contabulate interaction model while remapping the hierarchy to testament/book/chapter/verse.
- Tokenization preserves German letters, including umlauts and `ß`, in both the build output and browser-side verse search.
