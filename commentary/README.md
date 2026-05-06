# Commentary Interest Data

This directory holds compact, derived source data for commentary-interest counts.

Current source: [HistoricalChristianFaith Commentaries Database](https://github.com/HistoricalChristianFaith/Commentaries-Database).

Regenerate from its latest release:

```sh
curl -L -o /tmp/hcf-commentaries.sqlite \
  https://github.com/HistoricalChristianFaith/Commentaries-Database/releases/download/latest/commentaries.sqlite
python3 scripts/build_commentary_interest.py /tmp/hcf-commentaries.sqlite
python3 build.py
```

The app stores only aggregate counts per canonical OSIS verse and per source commentator. It does not vendor the full commentary text database.
