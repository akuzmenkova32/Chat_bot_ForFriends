# Tusa Planner Telegram Bot 🎉

A lightweight Telegram group-bot that helps friends quickly plan meetups:
- `!туса` — start planning a meetup
- Collects options for **when / where / format**
- Creates **reaction-based votes**
- Fixes the plan when voting ends or majority is reached
- Sends friendly reminders (24h / 2h / 30m before)
- `!напомни` — adjust reminders
- `!тише` / `!громче` — quiet mode

Built for **free deployment on Render.com (Blueprint)** using **webhooks**.

## Tech
- Python 3.11+
- FastAPI webhook server
- python-telegram-bot v21 (async)
- SQLite storage (free / embedded)

## Local run (polling)
1. Create `.env` from `.env.example`
2. Install deps:
   ```bash
   pip install -r requirements.txt
   ```
3. Run:
   ```bash
   python -m app.main --polling
   ```

## Render deploy (webhook)
1. Fork / upload this repo to GitHub
2. In Render: **New > Blueprint** and select your repo.
3. Fill environment variables:
   - `TELEGRAM_BOT_TOKEN`
   - `WEBHOOK_URL` (Render will show your service URL; set to `https://<your-service>.onrender.com/webhook`)
   - `SECRET_TOKEN` (any random string)
4. Deploy. The webhook will be set automatically on startup.

## Commands
See `app/wording.py` for all bot messages.

---

### Notes
- Uses only free features/APIs.
- Works in group chats; in private chat it warns user to add bot to a group.
