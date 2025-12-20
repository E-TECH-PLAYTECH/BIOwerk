# UI/UX Validation Checklist (Desktop Launcher & Dashboards)

Use this manual checklist to validate the cross-platform Electron launcher, onboarding, updates, and dashboard affordances before a release.

## Cross-Platform Launcher (Electron)
- **Startup**: macOS, Windows, and Linux launch without unsigned/permission prompts; tray icons render with correct theme variants.
- **Onboarding**: First-run wizard detects Docker, shows progress, and surfaces remediation links for missing prerequisites.
- **Updates**: In-app updater performs checksum verification, shows release notes, and rolls back cleanly on failure.
- **Settings persistence**: User preferences (theme, telemetry opt-in, mesh URL) survive restarts and OS reboots.
- **Safe defaults**: Pre-enable security headers and rate-limit awareness in any embedded webviews.

## Dashboards & Contextual Help
- **Tooltips** on critical metrics (rate-limit remaining, circuit breaker state, queue depth) show thresholds and remediation.
- **Inline help**: “Learn more” links point to `docs/OPENAPI_AND_TRY_IT.md`, `docs/API_RATE_LIMIT_TESTING.md`, and `docs/LOAD_AND_CHAOS_TESTING.md`.
- **Empty states**: Provide guided actions for no-data scenarios (e.g., “Run demo requests” button invoking `examples/run_demo_requests.py` or a mesh call).
- **Error surfacing**: Map mesh 429/503 responses to human-readable guidance and retry hints.

## Accessibility (A11y)
- Keyboard navigation for all dialogs and primary flows; ensure focus rings are visible and logical.
- Provide aria-labels for buttons, links, and tray items; avoid tooltip-only labels.
- Maintain 4.5:1 contrast ratio for text and 3:1 for UI controls; verify in both light/dark themes.
- Support screen readers by exposing semantic roles for tabs, toasts, and modals.

## Internationalization (i18n/l10n)
- Externalize strings into locale bundles; avoid hard-coded copy in components or preload scripts.
- Use date/number formatting with user locale and time zone awareness for schedules and metrics.
- Keep message templates placeholder-based to prevent string concatenation issues in translations.
- Validate bi-directional text handling and truncation/ellipsis in narrow layouts.

## Release Gate
- Complete this checklist for macOS, Windows, and Linux builds.
- Capture screenshots or short clips for onboarding, update, and dashboard flows.
- File issues for gaps; releases must block on unresolved P0/P1 accessibility or update flows.
