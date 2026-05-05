# Snapshot QA Refactor

This refactor implements the snapshot-QA core reform plan.

The main product is now single-snapshot fMRI time-series QA with optional
comparison between two already-assessed snapshots. The refactor intentionally
removes or de-scopes experimental behavior that did not belong in the core
snapshot workflow, including GLMsingle beta-map QA, event-file validation, SDC
quality assessment, physiological peak flags, non-HTML report claims, and
authoritative automatic exclusion language.
