# F1 source-value audit — 29 October 2026

The official [F1DB v2026.18.0 release](https://github.com/f1db/f1db/releases/tag/v2026.18.0) supplied the bundled F1 records. Its split JSON archive was downloaded again and verified against the SHA-256 digest published with the release:

`fba7a98c9b0ee946525e6ef497a86eb933f45fbf40398dd568e60196724e0840`

The input `f1db-races-race-results.json` contains 27,687 rows: 8,592 have non-null `points`, 19,095 contain null points, and none contains an explicit numeric zero. All 27,687 bundled records were matched against that source using race, driver, constructor and source display-order identifiers. There were **zero differences** in points values. The machine-readable counts are in [F1_SOURCE_AUDIT.json](F1_SOURCE_AUDIT.json).

There is no points-zero parsing bug and no seed rebuild is required. `F1DBProvider.normalize_zip` copies `result.get('points')` directly. The shared numeric parser preserves both `0` and the string `"0"`. The NBA CSV adapter also preserves explicit zero counts and percentages. Source-shaped controlled fixtures in `tests/test_provider_zero_preservation.py` verify zero, null and absent values separately; all 10 cases passed.

GameSense retains the F1DB nulls. The absence of a numeric zero in this source is not permission to replace its nulls with invented zero observations. A sum describes recorded points, while a mean or per-record rate excludes rows without a points value. Therefore a rate based on those 8,592 rows is **not points per all 27,687 race-result rows**. A complete-race points average cannot be claimed from that denominator under the application's missing-value policy.

Finishing-position averages similarly use recorded numeric classified finishes, with unavailable finishes reported separately. Experimental F1 ratings use recorded finish and numeric grid positions rather than missing points, and require both inputs. Grid zero is excluded because a pit-lane or unspecified start is not an ordered grid slot.

This audit verifies faithful copying of this pinned source; it does not establish that every sporting record or source field is complete or error-free. Downloaded official source archives stay in ignored QA storage and are not added to the submission ZIP by this audit.
