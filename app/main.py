import argparse
import asyncio
from fastapi import FastAPI, Request, HTTPException
import uvicorn
from telegram import Update
from telegram.ext import Application

from .config import BOT_TOKEN, WEBHOOK_URL, SECRET_TOKEN
from .bot import build_app
from .storage import init_db

init_db()
app = FastAPI()
tg_app: Application = build_app(BOT_TOKEN)

@app.on_event("startup")
async def on_startup():
    await tg_app.initialize()
    if WEBHOOK_URL:
        await tg_app.bot.set_webhook(url=WEBHOOK_URL, secret_token=SECRET_TOKEN)
    await tg_app.start()

@app.on_event("shutdown")
async def on_shutdown():
    await tg_app.stop()
    await tg_app.shutdown()

@app.post("/webhook")
async def webhook(req: Request):
    if SECRET_TOKEN:
        st = req.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if st != SECRET_TOKEN:
            raise HTTPException(status_code=401, detail="bad secret token")

    data = await req.json()
    update = Update.de_json(data, tg_app.bot)
    await tg_app.process_update(update)
    return {"ok": True}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--polling", action="store_true", help="Run in polling mode for local dev")
    args = parser.parse_args()

    if args.polling or not WEBHOOK_URL:
        print("Running polling mode")
        tg_app.run_polling(close_loop=False)
    else:
        uvicorn.run("app.main:app", host="0.0.0.0", port=8000)

if __name__ == "__main__":
    main()
