# ReadQueue (Local-First)

## 1. Runtime Requirement (Linux/WSL First)
ReadQueue is a Linux-based runtime application.
- Linux: run polling and ingestion directly.
- Windows: run the main runtime inside WSL.
- Windows `.bat` launcher is only a trigger into WSL runtime (not a standalone Windows runtime).

## 2. Project Overview
ReadQueue ingests links from multiple inputs, enriches them, and stores them in Notion.
Notion remains the primary UI for workflow management (Status, Read, Note, Tags).
This project does not provide a desktop GUI or web frontend.

## 3. Input Modes
- Telegram bot input (polling mode)
- One-click local clipboard input (Windows/macOS/Linux/WSL)

Both modes use the same shared ingestion pipeline:
- URL extraction and normalization
- Tracking parameter stripping
- Duplicate detection
- Metadata extraction
- OpenAI Korean cleanup title + one-line summary
- Non-link text extraction to Notion `Note`
- Notion storage

## 4. Latest Behavior Updates
- Robust multi-link processing:
  - One input with multiple links creates separate Notion items per link.
  - Processing order follows input order.
  - Duplicate links inside the same single input are suppressed after first processing.
- Shared note behavior:
  - Non-link text from the same input is copied to `Note` for all links in that input.
- Improved URL parsing:
  - URLs containing parentheses like `.../Function_(mathematics)` are handled correctly.
  - Wrapping punctuation (for example trailing `)` from surrounding text) is trimmed safely.
- Metadata failure fallback:
  - If page metadata extraction fails, ReadQueue can summarize the accompanying input text via OpenAI and still fill title/summary fields.
- Duplicate note append:
  - If a link already exists and new non-link text is sent with it, ReadQueue appends that text to existing `Note` on a new line.
  - Existing `Note` content is not overwritten.

## 5. Features
- Telegram polling capture with robust multi-link support
- Clipboard one-click send via generated launchers
- Shared ingestion architecture across input paths
- Notion duplicate prevention and status workflow
- Structured logging + retry/backoff for transient API failures

## 6. Prerequisites
- Python 3.11+
- OpenAI API key
- Notion integration token + Notion database
- Telegram bot token (for Telegram mode)
- WSL installed (if using Windows launcher)

## 7. Setup
1. Install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e .[dev]
   ```
2. Required config files:
   - Copy `config/config.example.yaml` to `config/config.yaml`
   - Copy `config/secrets.example.yaml` to `config/secrets.yaml`
3. Fill in real tokens/IDs.
4. Keep `config/secrets.yaml` out of git (already ignored by `.gitignore`).

## 8. Notion Setup
1. Create Notion internal integration and copy API key.
2. Create database and add required properties.
3. Share database with integration using **Add connections**.
4. Put database ID in `config/config.yaml`.

### Required Notion properties

| Property name | Type | Purpose |
|---|---|---|
| Title | title | Main display title |
| URL | url | Normalized original URL |
| Canonical URL | url | Canonical URL if available |
| Domain | rich_text | Host/domain |
| Original Title | rich_text | Raw source title |
| Cleaned Title KO | rich_text | OpenAI cleaned Korean title |
| Summary One Line KO | rich_text | One-line Korean summary |
| Status | select | Inbox/Queued/Reading/Done/Archived/Failed |
| Read | checkbox | Read state |
| Note | rich_text | User note (including appended duplicate notes) |
| Tags | multi_select | User tags |
| Source | select | telegram/local/manual |
| Saved At | date | Save timestamp |
| Telegram Message ID | rich_text | Telegram message id when source is telegram |
| Error Message | rich_text | Warning/failure details |

## 9. Telegram Setup
1. Create bot via `@BotFather`.
2. Put token in `config/secrets.yaml`.
3. Start chat with bot.
4. Optionally set `telegram.allowed_chat_ids`.

## 10. Local Clipboard Send
Use internal script:
```bash
python scripts/send_clipboard.py
```

Clipboard backend behavior:
- Windows native: `PowerShell Get-Clipboard`
- WSL: `powershell.exe -NoProfile -Command Get-Clipboard`
- macOS: `pbpaste`
- Linux: `wl-paste` -> `xclip` -> `xsel`

If clipboard is empty or backend is missing, script exits non-zero with a clear message.

Input parsing behavior (applies to Telegram and clipboard):
- If one input contains multiple links, each link is processed as a separate Notion item.
- If the same link appears multiple times in one input, only the first is processed and the rest are marked duplicate.
- Any non-link text in that same input is stored in the `Note` field for all links created from that input.
- If a link is duplicate and non-link text exists, that text is appended to the existing Notion `Note` with a newline.

## 11. Launcher Generation
Generate wrappers from config:
```bash
python scripts/generate_launchers.py
```

Configured in `config/config.yaml`:
- `launchers.windows_bat_output_path`
- `launchers.windows_pause_on_exit` (keep .bat console open so you can read output/errors)
- `launchers.macos_command_output_path`
- `linux_runtime.run_root`, `linux_runtime.python_bin`, `linux_runtime.use_venv`, `linux_runtime.venv_path`

Regenerate launchers whenever runtime path or venv/python path changes.

Windows path input guide (important when generating from WSL/Linux):
- Recommended: set `launchers.windows_bat_output_path` to WSL style, e.g. `/mnt/c/Users/YOUR_NAME/Desktop/ReadQueue_SendClipboard.bat`.
- You may also enter Windows style `C:/Users/...`; ReadQueue normalizes it to `/mnt/c/...` during generation.
- If you previously generated with a non-normalized setup, an accidental repo-local path like `./C:/Users/...` may appear. Regenerate after fixing config and delete the mistaken folder if needed.

## 12. Running
### Telegram polling runtime (Linux/WSL)
```bash
python scripts/run_polling.py
```

### Windows clipboard workflow example
1. Run runtime setup in WSL (venv + config).
2. Generate launcher: `python scripts/generate_launchers.py`.
3. Double-click generated `.bat`.
4. `.bat` calls `wsl.exe` and runs runtime-side `scripts/send_clipboard.py`.
5. If the console closes too quickly, set `launchers.windows_pause_on_exit: true` and regenerate launchers.

### macOS clipboard workflow example
1. Generate launcher.
2. Double-click generated `.command`.
3. It runs `scripts/send_clipboard.py` and exits after output.

## 13. Polling Runtime Availability
ReadQueue Telegram mode runs by polling.
That means ingestion only continues while the polling process is alive.

In practice, you must choose one of these:
- Keep your computer on and keep `scripts/run_polling.py` running.
- Deploy runtime to an always-on server/host (for example Linux VM/cloud instance) and keep the process running there.

If your machine sleeps/shuts down or process stops, Telegram ingestion stops until restarted.

## 14. Troubleshooting
- Windows launcher path misconfigured: fix `launchers.windows_bat_output_path` and regenerate.
- Mistaken local path created as `./C:/Users/...`: this means the launcher path was interpreted locally in WSL; use `/mnt/c/Users/...` (or keep `C:/...` with normalization), regenerate, then remove the accidental `./C:` folder.
- WSL unavailable: ensure `wsl.exe` works from Windows.
- Clipboard backend missing: install/use supported backend (Linux: wl-paste/xclip/xsel).
- Launcher points to wrong runtime: check `linux_runtime.run_root` and regenerate.
- Runtime not set up in Linux/WSL: verify venv, config files, and dependencies.
- Notion/OpenAI errors: verify keys, Notion DB sharing, property names.
- Metadata extraction failed often: check target site restrictions; ReadQueue will fallback to input-text summarization when possible.

## 15. Tests
Run:
```bash
pytest
```

Included coverage:
- config validation
- URL utilities (including parentheses/punctuation handling)
- dedup strategy
- shared ingestion source handling
- clipboard backend selection
- launcher rendering/generation
- metadata-failure fallback summarization
- duplicate-note append behavior

## 16. Future Improvements
- Telegram webhook mode
- richer article extraction
- batch import
- daily digest report
- optional local retry cache
