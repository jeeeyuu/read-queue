# Telegram -> Notion Reading Inbox (Local-First)

## 1. Project overview
This project is a local Telegram-to-Notion reading inbox tool written in Python.
It ingests links from Telegram messages, extracts metadata, generates a cleaned Korean title and a one-line Korean summary using OpenAI, and stores everything in a Notion database.

Notion is the primary UI for reading workflow management (status, read state, notes, tags).
This version does **not** include a desktop app or web frontend.

## 2. Features
- Telegram link capture (polling mode)
- Multiple links in one message
- Page metadata extraction (title, domain, canonical URL, excerpt)
- OpenAI title cleanup + one-line summary in Korean
- Notion storage with configurable property names
- Duplicate prevention via normalized URL/canonical URL checks
- Read-state and workflow management via Notion properties

## 3. Prerequisites
- Python 3.11+
- Telegram account
- Telegram bot token
- Notion integration token
- Notion database
- OpenAI API key

## 4. Setup
1. Install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows PowerShell: .venv\Scripts\Activate.ps1
   pip install -e .[dev]
   ```
2. Create config files from examples:
   - Copy `config/config.example.yaml` to `config/config.yaml`
   - Copy `config/secrets.example.yaml` to `config/secrets.yaml`
3. Fill in your real IDs and API keys in both files.

## 5. Required config files
- Copy `config/config.example.yaml` to `config/config.yaml`
- Copy `config/secrets.example.yaml` to `config/secrets.yaml`

## 6. Secret handling
`config/secrets.yaml` must never be committed.
This repository already excludes it in `.gitignore`.

## 7. Notion setup
1. Create a Notion internal integration in Notion settings.
2. Copy the integration secret (Notion API key).
3. Create a Notion database for your reading inbox.
4. Add the required properties (see table below) and confirm names match `config/config.yaml`.
5. Open the database menu and use **Add connections** to share it with your integration.
6. Copy the database ID into `config/config.yaml` under `notion.database_id`.

### Required Notion properties

| Property name | Type | Purpose |
|---|---|---|
| Title | title | Main display title for each saved item |
| URL | url | Normalized original URL |
| Canonical URL | url | Canonical URL when available |
| Domain | rich_text | Host/domain for quick filtering |
| Original Title | rich_text | Raw title extracted from source page |
| Cleaned Title KO | rich_text | OpenAI-cleaned Korean title |
| Summary One Line KO | rich_text | One-line Korean summary |
| Status | select | Workflow state (Inbox/Queued/Reading/Done/Archived/Failed) |
| Read | checkbox | Read/unread state |
| Note | rich_text | Personal memo |
| Tags | multi_select | Topic tags |
| Source | select | Ingestion source (telegram/manual) |
| Saved At | date | Timestamp when saved |
| Telegram Message ID | rich_text | Source Telegram message identifier |
| Error Message | rich_text | Metadata/summarization error details |

## 8. Telegram setup
1. Create a bot via `@BotFather`.
2. Get the bot token and set it in `config/secrets.yaml`.
3. Start a chat with your bot.
4. Optionally set `telegram.allowed_chat_ids` to restrict accepted chats.

## 9. Running the app
Run polling mode:
```bash
python scripts/run_polling.py
```

Expected behavior when sending a message with one or more links:
1. URLs are extracted and normalized.
2. Tracking query params are removed (if enabled).
3. Duplicate check is run against Notion.
4. Metadata and summary are generated for new items.
5. A Notion record is created.
6. Telegram reply is sent:
   - `Saved to Notion: [cleaned title]`
   - `Already exists in reading inbox.`
   - `Saved with warning: metadata or summary failed.`

## 10. Troubleshooting
- Notion 404/403: database is not shared with the integration (use **Add connections**).
- Telegram auth error: invalid `TELEGRAM_BOT_TOKEN`.
- OpenAI error: missing/invalid `OPENAI_API_KEY`.
- Notion property mismatch: property names in Notion do not match `config/config.yaml`.
- Duplicate issues: URL normalization or tracking strip settings may need adjustment.

Run quick checks:
```bash
python scripts/healthcheck.py
pytest
```

## 11. Future improvements
- Webhook mode for Telegram
- Richer article extraction (readability-like parsing)
- Batch import from text/CSV
- Daily digest summary to Telegram
- Optional local cache for offline retry queues
