# TELEGRAM F4

> A dark, operator-style Telegram channel console for publishing, scheduling, forwarding, reactions, and message button management.

F4 Manager is a Telegram bot built with `python-telegram-bot`, APScheduler, SQLite, and a compact inline control room. It is designed for fast actions, clear status symbols, direct shortcuts, and owner-level control.

## UI preview

```text
┈┈┈┈┈ ✦ ┈┈┈┈┈
𖦹 F4 // CONSOLE
┈┈┈┈┈ ✦ ┈┈┈┈┈

Welcome back, Farid.
✔ OWNER · unlimited access
✔ CHANNELS · 4/∞
✔ QUEUE · 2/∞
✘ RULES · 0/∞

[ Channels ] [ Compose ]
[ Queue    ] [ Forward ]
[ Reactions] [ Analytics]
```

The interface uses `✔` for selected/active and `✘` for unselected/inactive states. It keeps the visual language light: no full-side borders and no heavy square panels.

## What it can do

| Area | Capabilities |
| --- | --- |
| Publish | Text, photo, video, captions, URL buttons |
| Schedule | Queue posts in your configured timezone |
| Destinations | Channels, groups, and supergroups |
| Automation | Forwarding rules with include/exclude keywords |
| Reactions | Owner-managed packs with visible emoji contents |
| Premium | ₹39 plan, proof review, grant/revoke controls |
| Owner Panel | Users, IDs, usernames, roles, premium state, logs |
| Safety | Permission checks, migrations, timeout handling, owner alerts |

## Highlights

- Modern inline console with dashboard, queue, analytics, settings, and staff views
- Text, photo, and video publishing with optional URL buttons
- Scheduled delivery in the configured IANA timezone
- Channel forwarding rules with include/exclude keywords
- Owner-managed automatic reaction packs with visible emoji contents
- Existing-message button editing, text editing, and deletion
- SQLite persistence with automatic schema migration
- Premium limits and manual payment-proof review flow
- Owner user directory with premium grant/revoke controls

## Quick start

### 1. Create a Telegram bot

Create a bot with [@BotFather](https://t.me/BotFather), copy its token, and identify your Telegram numeric user ID.

### 2. Create a virtual environment

PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, run the commands from an activated terminal or use:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 3. Configure the bot

```powershell
Copy-Item .env.example .env
```

Edit `.env` and set at least:

```dotenv
BOT_TOKEN=your-token-from-botfather
OWNER_ID=your-telegram-user-id
```

Do not commit `.env`; it contains a private bot token.

### 4. Check and run

```powershell
.\.venv\Scripts\python.exe bot.py --check-config
.\.venv\Scripts\python.exe bot.py
```

The first run creates `f4manager.db` and applies any missing database columns automatically.

## Telegram permissions

For publishing, editing, reactions, and forwarding, add the bot as an administrator in each channel and grant the permissions it needs. Telegram may also require privacy/settings changes for the updates you want the bot to receive.

Channels, groups, and supergroups are supported as destinations. For a group, add the bot with permission to send messages and, when required, permission to read group messages. For a channel, give it the administrator permissions needed for posting, editing, reactions, and forwarding.

Payment screenshots are sent privately to the configured `OWNER_ID` for approval. The premium price is ₹39 for `PREMIUM_DAYS` days. The owner receives structured alerts for payment failures, promotion/demotion events, and unexpected runtime errors.

The owner’s Panel includes a paginated user directory with each member’s name, username, numeric Telegram ID, role, verification state, and premium status. The owner can grant or revoke premium directly, with or without a payment record. Username lookup accepts both `username` and `@username`, searches the local user directory first, and then tries Telegram’s lookup.

`PAYMENT_INSTRUCTIONS` uses the literal `\n` sequence in `.env`; the bot converts it to real Telegram line breaks automatically. Do not use `<br>` tags.

## Configuration

`TIMEZONE` accepts an IANA timezone such as `Asia/Kolkata`, `Asia/Dhaka`, or `UTC`. Scheduled times are entered as `YYYY-MM-DD HH:MM` in that timezone. Premium is configured at `₹39` for the configured number of days. `LOG_LEVEL` may be set to `DEBUG`, `INFO`, `WARNING`, or `ERROR`.

## Command shortcuts

All users can jump directly to the main console areas with `/channels`, `/compose`, `/queue`, `/buttons`, `/forward`, `/react`, `/stats`, `/settings`, `/upgrade`, `/packs`, and `/help`. Use `/cancel` to clear an active flow. `/panel` still works for the owner/operators but is intentionally hidden from Telegram’s public command menu.

The owner can manage shared reaction packs:

```text
/pack_add name 😀 🔥 ❤️
/pack_update name 😀 🔥 ❤️
/pack_remove name
```

Members can use `/packs` or the Reactions screen to see every active pack and its emoji contents. The UI uses `✔` for the selected pack, channel, or group and `✘` for an unselected one, so selection state is clear without relying on emoji glyphs.

## Owner controls

The `OWNER_ID` account has unlimited limits and legend-level control.

```text
/panel
/pack_add name 😀 🔥 ❤️
/pack_update name 😀 🔥 ❤️
/pack_remove name
```

Inside the owner Panel:

- Browse every known user with name, username, and numeric ID
- Grant or revoke premium without requiring a payment
- Review payment proofs and approve/reject requests
- Promote or demote operators
- Inspect activity logs and operational counters

Username lookup accepts `username`, `@username`, or a numeric ID. Telegram only exposes reliable username lookup for users who have opened or interacted with the bot, so the user directory is the source of truth for known members.

## Project layout

```text
bot.py             # application, Telegram handlers, scheduler, and SQLite layer
requirements.txt   # pinned runtime dependencies
.env.example       # safe configuration template
f4manager.db       # local runtime database, created automatically
LICENSE             # MIT License
```

## License and credits

Released under the [MIT License](LICENSE).

Made by **Farid**. Credits to **[@f4did](https://t.me/f4did)**. Keep the attribution, respect Telegram’s Terms of Service, and use the automation responsibly with permission for the channels and content you manage.
