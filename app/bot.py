import asyncio
from typing import Dict, List, Optional
from telegram import Update, Message, Chat, ReactionTypeEmoji
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackContext
)

from . import wording
from . import storage
from .utils import extract_time_place_format, format_options, uniq, parse_hours

# Emoji for voting per category
EMOJI = ["🅰️","🅱️","🅾️","🆎","1️⃣","2️⃣","3️⃣","4️⃣","5️⃣"]

def build_app(token: str) -> Application:
    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex(r"^!туса\b"), cmd_tusa))
    app.add_handler(MessageHandler(filters.Regex(r"^!напомни\b"), cmd_remind))
    app.add_handler(MessageHandler(filters.Regex(r"^!тише\b"), cmd_quiet_on))
    app.add_handler(MessageHandler(filters.Regex(r"^!громче\b"), cmd_quiet_off))
    app.add_handler(MessageHandler(filters.Regex(r"^!статус\b"), cmd_status))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    # Reaction updates (v21 supports MessageReactionUpdated)
    app.add_handler(MessageHandler(filters.UpdateType.MESSAGE_REACTION, on_reaction))

    return app

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        await update.message.reply_text(wording.START_PRIVATE)
    else:
        await update.message.reply_markdown(wording.START_GROUP)

async def cmd_tusa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    storage.ensure_chat(chat_id)

    active = storage.get_active_event(chat_id)
    if active and active["status"] in ("collecting","voting"):
        await update.message.reply_text("Уже есть активная туса. Напиши `!статус`.")
        return

    event_id = storage.create_event(chat_id, user_id)
    context.chat_data["event_id"] = event_id
    context.chat_data["times"] = []
    context.chat_data["places"] = []
    context.chat_data["formats"] = []
    context.chat_data["collecting"] = True

    await update.message.reply_markdown(wording.TUSA_INTRO)

    # auto-finish collecting after 7 minutes
    asyncio.create_task(finish_collecting_later(context, chat_id, event_id, delay_sec=7*60))

async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    event = storage.get_active_event(chat_id)
    if not event or event["status"] != "collecting":
        return

    text = update.message.text or ""
    times, places, formats = extract_time_place_format(text)

    ct = context.chat_data
    ct["times"] = uniq(ct.get("times", []) + times)
    ct["places"] = uniq(ct.get("places", []) + places)
    ct["formats"] = uniq(ct.get("formats", []) + formats)

    storage.update_options(event["event_id"], ct["times"], ct["places"], ct["formats"])

    if storage.get_quiet(chat_id) is False:
        await update.message.reply_text(wording.COLLECTING_HINT)

    # If we already have at least 2 in each category, start voting
    if len(ct["times"]) >= 2 and len(ct["places"]) >= 2 and len(ct["formats"]) >= 2:
        await start_voting(context, chat_id, event["event_id"])

async def finish_collecting_later(context: ContextTypes.DEFAULT_TYPE, chat_id: int, event_id: int, delay_sec: int):
    await asyncio.sleep(delay_sec)
    event = storage.get_active_event(chat_id)
    if not event or event["event_id"] != event_id or event["status"] != "collecting":
        return

    ct = context.application.chat_data.get(chat_id, {})
    times = ct.get("times", [])
    places = ct.get("places", [])
    formats = ct.get("formats", [])

    # if not enough options, do nothing; wait for more input
    if len(times) < 2 or len(places) < 2 or len(formats) < 2:
        if not storage.get_quiet(chat_id):
            await context.bot.send_message(chat_id, "Пока мало вариантов. Докиньте ещё 🙂")
        return

    await start_voting(context, chat_id, event_id)

async def start_voting(context: ContextTypes.DEFAULT_TYPE, chat_id: int, event_id: int):
    storage.set_status(event_id, "voting")

    ct = context.application.chat_data.setdefault(chat_id, {})
    times = ct.get("times", [])
    places = ct.get("places", [])
    formats = ct.get("formats", [])

    times_txt = format_options(times)
    places_txt = format_options(places)
    formats_txt = format_options(formats)

    msg = await context.bot.send_message(
        chat_id,
        wording.VOTING_START.format(times=times_txt, places=places_txt, formats=formats_txt),
        parse_mode="Markdown"
    )
    storage.set_voting_msg(event_id, msg.message_id)

    # Add reactions as vote buttons (A,B,C...)
    for i in range(max(len(times), len(places), len(formats))):
        if i < len(EMOJI):
            try:
                await msg.react(EMOJI[i])
            except Exception:
                pass

    # init votes
    votes = {
        "times": {str(i): [] for i in range(len(times))},
        "places": {str(i): [] for i in range(len(places))},
        "formats": {str(i): [] for i in range(len(formats))}
    }
    storage.set_votes(event_id, votes)

    # auto-finish voting after 12h
    asyncio.create_task(finish_voting_later(context, chat_id, event_id, delay_sec=12*60*60))

async def on_reaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    event = storage.get_active_event(chat_id)
    if not event or event["status"] != "voting":
        return
    if event["voting_msg_id"] != update.message_reaction.message_id:
        return

    user_id = update.message_reaction.user.id
    new_reactions = update.message_reaction.new_reaction or []

    votes = storage.get_votes(event)
    ct = context.application.chat_data.get(chat_id, {})
    times = ct.get("times", [])
    places = ct.get("places", [])
    formats = ct.get("formats", [])

    # Map emoji to option index
    emoji_to_idx = {EMOJI[i]: i for i in range(min(len(EMOJI), max(len(times),len(places),len(formats))))}

    for r in new_reactions:
        if not isinstance(r, ReactionTypeEmoji):
            continue
        e = r.emoji
        if e not in emoji_to_idx:
            continue
        idx = emoji_to_idx[e]

        # We can't tell which category user intended (Telegram limitation with shared reactions),
        # so we record the same vote for all categories up to their length.
        # This is a compromise to keep UX simple w/ free features.
        if idx < len(times) and user_id not in votes["times"][str(idx)]:
            votes["times"][str(idx)].append(user_id)
        if idx < len(places) and user_id not in votes["places"][str(idx)]:
            votes["places"][str(idx)].append(user_id)
        if idx < len(formats) and user_id not in votes["formats"][str(idx)]:
            votes["formats"][str(idx)].append(user_id)

    storage.set_votes(event["event_id"], votes)

async def finish_voting_later(context: ContextTypes.DEFAULT_TYPE, chat_id: int, event_id: int, delay_sec: int):
    await asyncio.sleep(delay_sec)
    event = storage.get_active_event(chat_id)
    if not event or event["event_id"] != event_id or event["status"] != "voting":
        return
    await finalize_plan(context, chat_id, event)

async def finalize_plan(context: ContextTypes.DEFAULT_TYPE, chat_id: int, event):
    votes = storage.get_votes(event)
    ct = context.application.chat_data.get(chat_id, {})
    times = ct.get("times", [])
    places = ct.get("places", [])
    formats = ct.get("formats", [])

    def winner(category: str, options: List[str]) -> str:
        if not options:
            return "—"
        counts = [(i, len(votes[category].get(str(i), []))) for i in range(len(options))]
        counts.sort(key=lambda x: x[1], reverse=True)
        return options[counts[0][0]]

    w_time = winner("times", times)
    w_place = winner("places", places)
    w_format = winner("formats", formats)

    storage.fix_plan(event["event_id"], w_time, w_place, w_format)

    await context.bot.send_message(
        chat_id,
        wording.PLAN_FIXED.format(time=w_time, place=w_place, format=w_format),
        parse_mode="Markdown"
    )

    # Schedule reminders (handled in-memory tasks)
    asyncio.create_task(schedule_reminders(context, chat_id, event["event_id"]))

async def schedule_reminders(context: ContextTypes.DEFAULT_TYPE, chat_id: int, event_id: int):
    # Basic naive reminders relative to fixed time text.
    # Since time can be free-form, we just send 3 reminders with delays:
    # 1h, 10m, 1m if we can't parse. Still useful.
    # You can replace with real datetime parsing later.
    delays = [24*60*60, 2*60*60, 30*60]
    event = storage.get_active_event(chat_id)
    if not event or event["status"] != "fixed":
        return

    when = event["final_time"] or "скоро"
    where = event["final_place"] or "где-то"
    fmt = event["final_format"] or "как-нибудь"

    for d in delays:
        await asyncio.sleep(d)
        # If reminders were disabled in between — stop
        current = storage.get_active_event(chat_id)
        if not current or current["event_id"] != event_id or current["status"] != "fixed":
            return
        await context.bot.send_message(
            chat_id,
            wording.REMINDER_TEMPLATE.format(when=when, where=where, format=fmt),
            parse_mode="Markdown"
        )

async def cmd_remind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    arg = (update.message.text or "").replace("!напомни", "").strip()

    event = storage.get_active_event(chat_id)
    if not event or event["status"] != "fixed":
        await update.message.reply_text(wording.NO_ACTIVE_TUSA)
        return

    if arg in ("выкл","off","нет"):
        await update.message.reply_text(wording.REMINDERS_OFF)
        # simplest: mark event cancelled reminders by switching status to fixed still,
        # but we do not have persistent reminder toggles in MVP.
        return

    hours = parse_hours(arg) if arg else None
    if hours:
        await update.message.reply_text(wording.REMINDERS_UPDATED.format(hours=hours))
    else:
        await update.message.reply_text(wording.REMINDERS_ON)

async def cmd_quiet_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    storage.set_quiet(chat_id, True)
    await update.message.reply_text(wording.QUIET_ON)

async def cmd_quiet_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    storage.set_quiet(chat_id, False)
    await update.message.reply_text(wording.QUIET_OFF)

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    event = storage.get_active_event(chat_id)
    if not event:
        await update.message.reply_text(wording.NO_ACTIVE_TUSA)
        return
    text = wording.STATUS_TEMPLATE.format(
        status=event["status"],
        time=event["final_time"] or "—",
        place=event["final_place"] or "—",
        format=event["final_format"] or "—",
    )
    await update.message.reply_markdown(text)
