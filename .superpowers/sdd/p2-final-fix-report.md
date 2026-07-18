# Phase 2 whole-branch review final fixes

- `START_BATCH` now resets every selected task to `pending`, clears stale error expansion and progress data, and preserves the active batch IDs used by cancellation controls.
- Failed task rows now expand/collapse on click or keyboard activation and expose a button that copies the full sidecar error message.
- Removed browser file/folder inputs because browser `File` objects cannot reliably provide absolute local paths; absolute-path paste is now the only web UI entry point.
- Output directory state rolls back to the last saved config when `putConfig` fails.
- Added reducer and app-level regression coverage for batch reset, error expansion/copy, picker removal, and config rollback.

Verification:

- `npm test` in `ui/`: 2 files passed, 17 tests passed.
- `npm run build` in `ui/`: TypeScript and Vite production build passed.
