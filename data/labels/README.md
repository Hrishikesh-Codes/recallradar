# Labelled evaluation data

Hand-labelled product/recall pairs for the matching evaluation (SPEC §6.9, Milestone 3).
No personal data: real-world items are stripped of names, addresses, and order numbers, and only
included with consent.

- `m1_smoke.jsonl`: 53 real inputs labelled by hand (expected verdict, the recalls that should be
  listed, and ones that must not be), used to catch regressions while building M1. The matcher's
  rules were tuned against it, so its score is not an accuracy estimate. Run it with `make eval`.
