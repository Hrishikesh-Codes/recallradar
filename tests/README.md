# Cross-package tests

- `fixtures/`: real sample responses from each recall source, saved before any parser is written
  (never invented; SPEC §0.3). Each fixture notes where and when it was fetched.
- `integration/`: end-to-end tests across packages (input -> identify -> match -> verdict -> alert).

Package-level unit tests live next to their package (`packages/*/tests`, `apps/api/tests`).
