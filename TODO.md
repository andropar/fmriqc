# Open Tasks

## High Priority

(none currently)

## Medium Priority

### CLI Argument Cleanup
- **Status**: Needs discussion
- **Issue**: CLI has 25 arguments across 8 groups - may be overwhelming
- **Considerations**:
  - Which arguments are commonly used vs. rarely needed?
  - Could some be config-file-only?
  - Are there sensible defaults that reduce need for explicit args?
  - Group structure: Input, Data Source, Output, Processing, Thresholds, Exclusion, Reuse, Utility

## Low Priority / Future

### Report Improvements
- Consider lazy-loading for large studies
- Mobile responsiveness could be improved

## Completed (Recent)

- [x] Fix spatial maps not displaying in flipbook (refactored serialize_to_disk to be asset-agnostic - iterates through all asset_paths entries instead of hardcoding specific keys)
- [x] Fix SVG viewBox for distribution plots
- [x] Fix distribution plot sizing in CSS grid
- [x] Add run modal navigation (prev/next buttons, keyboard shortcuts)
- [x] Fix subject report summary strip spacing
- [x] Update localStorage key to fmriqc_thresholds
