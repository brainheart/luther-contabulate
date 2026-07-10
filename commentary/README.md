# Commentary Interest Data

This directory holds compact, derived source data for commentary-interest counts. The build also writes lazy-loaded individual comment records to `docs/commentary/`.

Current source: [HistoricalChristianFaith Commentaries Database](https://github.com/HistoricalChristianFaith/Commentaries-Database).

Regenerate from its latest release:

```sh
curl -L -o /tmp/hcf-commentaries.sqlite \
  https://github.com/HistoricalChristianFaith/Commentaries-Database/releases/download/latest/commentaries.sqlite
python3 scripts/build_commentary_interest.py /tmp/hcf-commentaries.sqlite
python3 build.py
```

Each generated detail record retains the commentator, approximate date, source work, source URL, HCF passage URL, and a deterministic Contabulate ID. Historical records include their full HCF excerpt. Records dated after 1930 are treated conservatively as potentially copyrighted: the generated site stores only a 24-word identifying preview and links to HCF and any supplied source URL for further reading.

The date cutoff is a display policy, not a legal determination. HistoricalChristianFaith's license notes that its compilation and public-domain excerpts are reusable, while some modern excerpts remain copyrighted and are included upstream on a fair-use basis.
