#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TELEGRAM F4 — v2 // GLYPH BUILD
Owner / Admin / Verified-Premium / Free role engine
Inline button forge, channel message editor, auto-reactor, verification desk.
"""

import os
import json
import random
import logging
import asyncio
import datetime
import html
import re
import sqlite3
import sys
from functools import wraps
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, ReactionTypeEmoji, BotCommand
)
from telegram.ext import (
    Application, CommandHandler, ContextTypes, CallbackQueryHandler,
    MessageHandler, filters
)
from telegram.constants import ParseMode

# -----------------------------------------------------------------------------
# 1. GLYPH PALETTE
# -----------------------------------------------------------------------------

G = {
    "skull": "◇", "spiral": "𖦹", "ghost": "○", "pen": "𖡎", "orbit": "𖣂",
    "heart": "𖧊", "gift": "𖧋", "gear": "𖣠", "fire": "𖤛", "paw": "𖦆",
    "crown": "𖤶", "mask": "𖣦", "chart": "𖥾", "clock": "𖡄", "mail": "𖠚",
    "star": "𖧞", "bolt": "𖣘", "moon": "𖥚", "flame": "𖤍", "eye": "𖤂",
    "key": "𖤇", "shield": "𖥁", "link": "𖦄", "check": "𖧡", "cross": "𖢞",
    "plus": "𖧷", "user": "𖡡", "sun": "𖤓", "wave": "𖨬", "bird": "𖨧",
    "cat": "𖨨", "gem": "𖤕", "box": "𖤖", "tag": "𖤗", "up": "𖦏",
    "down": "𖦕", "dot": "𖦖", "arrow": "𖧏", "misc": "𖧐",
}

CHECK_ICON = "✔"
CROSS_ICON = "✘"

def rule(side=G["spiral"]):
    return f"✦ {side} ┈┈┈┈┈ ⋆ ┈┈┈┈┈ {side} ✦"

def bar(n, total, width=8):
    if total <= 0:
        return "▱" * width
    filled = max(0, min(width, round(width * n / total)))
    return "▰" * filled + "▱" * (width - filled)

def card(title, lines, top=G["spiral"], tag=""):
    divider = "┈┈┈┈┈ ✦ ┈┈┈┈┈"
    t = f"<b>{title}</b>" + (f"  <i>{tag}</i>" if tag else "")
    top_line = divider
    bottom_line = divider
    return f"{top_line}\n{t}\n{bottom_line}\n" + "\n".join(lines)

def fmt_dt(dt):
    return dt.strftime("%d %b %Y · %H:%M")

# -----------------------------------------------------------------------------
# 2. CONFIG
# -----------------------------------------------------------------------------

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
try:
    OWNER_ID = int(os.getenv("OWNER_ID", "0"))
except ValueError:
    OWNER_ID = 0
DATABASE_PATH = os.getenv("DATABASE_PATH", "f4manager.db")
TIMEZONE_STR = os.getenv("TIMEZONE", "Asia/Kolkata")
try:
    APP_TIMEZONE = ZoneInfo(TIMEZONE_STR)
except ZoneInfoNotFoundError:
    raise SystemExit(f"Invalid TIMEZONE '{TIMEZONE_STR}'. Use an IANA timezone such as Asia/Kolkata.")

def local_now():
    """Return the configured local time as a naive datetime for SQLite storage."""
    return datetime.datetime.now(APP_TIMEZONE).replace(tzinfo=None)

MAX_CHANNELS_FREE = int(os.getenv("MAX_CHANNELS_FREE", 2))
MAX_SCHEDULES_FREE = int(os.getenv("MAX_SCHEDULES_FREE", 5))
MAX_RULES_FREE = int(os.getenv("MAX_RULES_FREE", 2))
MAX_BUTTONS_FREE = int(os.getenv("MAX_BUTTONS_FREE", 5))
MAX_CHANNELS_PAID = int(os.getenv("MAX_CHANNELS_PAID", 25))
MAX_SCHEDULES_PAID = int(os.getenv("MAX_SCHEDULES_PAID", 200))
MAX_RULES_PAID = int(os.getenv("MAX_RULES_PAID", 50))
MAX_BUTTONS_PAID = int(os.getenv("MAX_BUTTONS_PAID", 20))
UNLIMITED = 99999

CURRENCY_SYMBOL = os.getenv("CURRENCY_SYMBOL", "₹")
PREMIUM_PRICE = os.getenv("PREMIUM_PRICE", "39")
PREMIUM_DAYS = int(os.getenv("PREMIUM_DAYS", 30))
PAYMENT_UPI_ID = os.getenv("PAYMENT_UPI_ID", "")
PAYMENT_UPI_NAME = os.getenv("PAYMENT_UPI_NAME", "")
PAYMENT_INSTRUCTIONS = os.getenv("PAYMENT_INSTRUCTIONS", "")
# dotenv keeps \n as two literal characters. Telegram needs a real newline;
# normalize common line-break spellings before rendering the payment card.
PAYMENT_INSTRUCTIONS = PAYMENT_INSTRUCTIONS.replace("\\n", "\n")
PAYMENT_INSTRUCTIONS = PAYMENT_INSTRUCTIONS.replace("<br>", "\n").replace("<br/>", "\n")
PAYMENT_INSTRUCTIONS = PAYMENT_INSTRUCTIONS.format(
    upi_id=PAYMENT_UPI_ID, upi_name=PAYMENT_UPI_NAME
)

REACTION_PRESETS = {
    "a": ["👍", "🔥", "❤️", "🎉", "💯", "⚡", "🏆", "👏"],
    "b": ["🤯", "😱", "👀", "🤔", "😐", "🤡", "🗿", "👻"],
    "c": ["🌚", "🍌", "🦄", "🐳", "🌸", "☃", "🎃", "💊"],
}

logging.basicConfig(format="%(asctime)s · %(name)s · %(levelname)s · %(message)s",
                    level=os.getenv("LOG_LEVEL", "INFO").upper())
logger = logging.getLogger("f4")

async def notify_owner(context, text, **kwargs):
    """Best-effort owner alert; never let a notification failure crash the bot."""
    try:
        await context.bot.send_message(OWNER_ID, text, **kwargs)
    except Exception as exc:
        logger.error("owner notification failed: %s", exc)

async def report_error(update, context, error):
    user = getattr(update, "effective_user", None)
    chat = getattr(update, "effective_chat", None)
    callback = getattr(update.callback_query, "data", "") if update and update.callback_query else ""
    details = (
        f"{G['cross']} <b>F4 ERROR</b>\n"
        f"user=<code>{user.id if user else '?'}</code> "
        f"chat=<code>{chat.id if chat else '?'}</code>\n"
        f"callback=<code>{html.escape(callback[:80])}</code>\n"
        f"<code>{html.escape(str(error)[:900])}</code>"
    )
    await notify_owner(context, details, parse_mode=ParseMode.HTML)

async def safe_callback_answer(query, *args, **kwargs):
    """A slow Telegram callback acknowledgement must not stop the action itself."""
    try:
        await query.answer(*args, **kwargs)
        return True
    except Exception as exc:
        logger.warning("callback acknowledgement failed: %s", exc)
        return False

async def application_error_handler(update, context):
    error = context.error or RuntimeError("unknown Telegram update error")
    logger.error("Unhandled update error", exc_info=(type(error), error, error.__traceback__))
    await report_error(update, context, error)

# -----------------------------------------------------------------------------
# 3. DATABASE
# -----------------------------------------------------------------------------

class Database:
    def __init__(self, path):
        self.path = path
        self.init_db()

    def conn(self):
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys = ON")
        return c

    def init_db(self):
        c = self.conn()
        cur = c.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT, first_name TEXT,
            plan TEXT DEFAULT 'FREE',
            role TEXT DEFAULT 'user',
            is_verified INTEGER DEFAULT 0,
            paid_until TIMESTAMP,
            is_banned INTEGER DEFAULT 0,
            auto_react TEXT,
            react_preset TEXT DEFAULT 'a',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            channel_id INTEGER, channel_username TEXT, title TEXT, chat_type TEXT DEFAULT 'channel',
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS source_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            source_channel_id INTEGER, source_username TEXT,
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS forwarding_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, source_id INTEGER,
            dest_channel_ids TEXT, keyword_include TEXT, keyword_exclude TEXT,
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            content_text TEXT, media_file_id TEXT, media_type TEXT,
            channel_ids TEXT, buttons_json TEXT, scheduled_time TIMESTAMP,
            status TEXT DEFAULT 'pending', message_ids TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS post_buttons (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            channel_id INTEGER, message_id INTEGER, buttons_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount TEXT,
            utr_or_proof TEXT, status TEXT DEFAULT 'pending', proof_type TEXT,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reviewed_by INTEGER, reviewed_at TIMESTAMP)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            action TEXT, details TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS reaction_packs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            emojis_json TEXT NOT NULL,
            created_by INTEGER,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

        default_emojis = list(dict.fromkeys(
            emoji for preset in REACTION_PRESETS.values() for emoji in preset
        ))
        cur.execute(
            "INSERT OR IGNORE INTO reaction_packs (name, emojis_json, created_by) VALUES (?,?,?)",
            ("default", json.dumps(default_emojis, ensure_ascii=False), OWNER_ID),
        )

        self._migrate(cur)
        c.commit()
        c.close()

    def _migrate(self, cur):
        """Add any columns the old schema is missing."""
        wanted = {
            "users": {
                "username": "TEXT", "first_name": "TEXT",
                "plan": "TEXT DEFAULT 'FREE'", "role": "TEXT DEFAULT 'user'",
                "is_verified": "INTEGER DEFAULT 0", "paid_until": "TIMESTAMP",
                "is_banned": "INTEGER DEFAULT 0", "auto_react": "TEXT",
                "react_preset": "TEXT DEFAULT 'a'", "created_at": "TIMESTAMP",
            },
            "channels": {"channel_username": "TEXT", "title": "TEXT", "chat_type": "TEXT DEFAULT 'channel'"},
            "source_channels": {"source_username": "TEXT", "is_active": "INTEGER DEFAULT 1"},
            "forwarding_rules": {"keyword_include": "TEXT", "keyword_exclude": "TEXT",
                                 "is_active": "INTEGER DEFAULT 1"},
            "schedules": {"media_type": "TEXT", "buttons_json": "TEXT",
                          "message_ids": "TEXT", "status": "TEXT DEFAULT 'pending'"},
            "payments": {"proof_type": "TEXT", "status": "TEXT DEFAULT 'pending'",
                         "reviewed_by": "INTEGER", "reviewed_at": "TIMESTAMP"},
        }
        for table, cols in wanted.items():
            cur.execute(f"PRAGMA table_info({table})")
            existing = {row[1] for row in cur.fetchall()}
            for col, decl in cols.items():
                if col not in existing:
                    cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
                    logger.info("migrated %s.%s", table, col)

        # CURRENT_TIMESTAMP can't be an ALTER default, backfill it instead
        cur.execute("UPDATE users SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
        cur.execute("UPDATE users SET plan = 'FREE' WHERE plan IS NULL")
        cur.execute("UPDATE users SET role = 'user' WHERE role IS NULL")
        # Migrate legacy A/B/C selections to the shared default pack.
        cur.execute("UPDATE users SET react_preset = 'default' WHERE react_preset IS NULL OR react_preset IN ('a','b','c')")
        cur.execute("UPDATE channels SET chat_type = 'channel' WHERE chat_type IS NULL")
    # ---- users ----
    def ensure_user(self, uid, uname, fname):
        c = self.conn()
        c.execute("INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?,?,?)",
                  (uid, uname, fname))
        c.execute("UPDATE users SET username=?, first_name=? WHERE user_id=?", (uname, fname, uid))
        # Keep the configured owner synchronized even if the row already existed
        # before OWNER_ID was added or changed in .env.
        if uid == OWNER_ID:
            c.execute("UPDATE users SET role='owner', is_verified=1 WHERE user_id=?", (uid,))
        c.commit()
        c.close()

    def get_user(self, uid):
        c = self.conn()
        r = c.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
        c.close()
        return r

    def user_by_username(self, username):
        username = username.strip().lstrip("@").lower()
        c = self.conn()
        r = c.execute(
            "SELECT * FROM users WHERE LOWER(username)=? ORDER BY user_id LIMIT 1",
            (username,),
        ).fetchone()
        c.close()
        return r

    def update_plan(self, uid, plan, until=None):
        c = self.conn()
        c.execute("UPDATE users SET plan=?, paid_until=? WHERE user_id=?", (plan, until, uid))
        c.commit()
        c.close()

    def set_role(self, uid, role):
        c = self.conn()
        c.execute("UPDATE users SET role=? WHERE user_id=?", (role, uid))
        c.commit()
        c.close()

    def set_verified(self, uid, flag):
        c = self.conn()
        c.execute("UPDATE users SET is_verified=? WHERE user_id=?", (1 if flag else 0, uid))
        c.commit()
        c.close()

    def set_ban(self, uid, flag):
        c = self.conn()
        c.execute("UPDATE users SET is_banned=? WHERE user_id=?", (1 if flag else 0, uid))
        c.commit()
        c.close()

    def set_react(self, uid, enabled, preset=None):
        c = self.conn()
        c.execute("UPDATE users SET auto_react=?, react_preset=COALESCE(?, react_preset) WHERE user_id=?",
                  ("on" if enabled else None, preset, uid))
        c.commit()
        c.close()

    def reaction_packs(self):
        c = self.conn()
        rows = c.execute(
            "SELECT * FROM reaction_packs WHERE is_active=1 ORDER BY name"
        ).fetchall()
        c.close()
        return rows

    def reaction_pool(self, name):
        c = self.conn()
        row = c.execute(
            "SELECT emojis_json FROM reaction_packs WHERE name=? AND is_active=1",
            (name,),
        ).fetchone()
        c.close()
        if row:
            try:
                return json.loads(row["emojis_json"])
            except (TypeError, json.JSONDecodeError):
                pass
        return list(dict.fromkeys(
            emoji for preset in REACTION_PRESETS.values() for emoji in preset
        ))

    def add_reaction_pack(self, name, emojis, created_by):
        c = self.conn()
        try:
            existing = c.execute(
                "SELECT id, is_active FROM reaction_packs WHERE name=?", (name,)
            ).fetchone()
            if existing:
                if existing["is_active"]:
                    return False
                c.execute(
                    "UPDATE reaction_packs SET emojis_json=?, created_by=?, is_active=1 WHERE name=?",
                    (json.dumps(emojis, ensure_ascii=False), created_by, name),
                )
                c.commit()
                return True
            c.execute(
                "INSERT INTO reaction_packs (name, emojis_json, created_by) VALUES (?,?,?)",
                (name, json.dumps(emojis, ensure_ascii=False), created_by),
            )
            c.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            c.close()

    def update_reaction_pack(self, name, emojis, updated_by):
        if name == "default":
            return False
        c = self.conn()
        c.execute(
            "UPDATE reaction_packs SET emojis_json=?, created_by=?, is_active=1 WHERE name=?",
            (json.dumps(emojis, ensure_ascii=False), updated_by, name),
        )
        changed = c.rowcount > 0
        c.commit()
        c.close()
        return changed

    def remove_reaction_pack(self, name):
        if name == "default":
            return False
        c = self.conn()
        c.execute("UPDATE reaction_packs SET is_active=0 WHERE name=?", (name,))
        changed = c.rowcount > 0
        c.commit()
        c.close()
        return changed

    def all_users(self):
        c = self.conn()
        r = c.execute("SELECT * FROM users").fetchall()
        c.close()
        return r

    def staff(self):
        c = self.conn()
        r = c.execute("SELECT * FROM users WHERE role IN ('owner','admin')").fetchall()
        c.close()
        return r

    def unverified(self):
        c = self.conn()
        r = c.execute("SELECT * FROM users WHERE is_verified=0 AND plan='PAID'").fetchall()
        c.close()
        return r

    # ---- channels ----
    def add_channel(self, uid, cid, uname, title, chat_type="channel"):
        c = self.conn()
        try:
            existing = c.execute(
                "SELECT 1 FROM channels WHERE user_id=? AND channel_id=?",
                (uid, cid),
            ).fetchone()
            if existing:
                return False
            c.execute("INSERT INTO channels (user_id, channel_id, channel_username, title, chat_type) VALUES (?,?,?,?,?)",
                      (uid, cid, uname, title, chat_type))
            c.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            c.close()

    def remove_channel(self, uid, cid):
        c = self.conn()
        c.execute("DELETE FROM channels WHERE user_id=? AND channel_id=?", (uid, cid))
        c.commit()
        c.close()

    def user_channels(self, uid):
        c = self.conn()
        r = c.execute("SELECT * FROM channels WHERE user_id=? ORDER BY id", (uid,)).fetchall()
        c.close()
        return r

    def count_channels(self, uid):
        c = self.conn()
        n = c.execute("SELECT COUNT(*) FROM channels WHERE user_id=?", (uid,)).fetchone()[0]
        c.close()
        return n

    # ---- schedules ----
    def add_schedule(self, uid, content, fid, ftype, cids, buttons, when):
        c = self.conn()
        cur = c.execute(
            "INSERT INTO schedules (user_id, content_text, media_file_id, media_type, channel_ids, buttons_json, scheduled_time)"
            " VALUES (?,?,?,?,?,?,?)",
            (uid, content, fid, ftype, json.dumps(cids), json.dumps(buttons or []), when))
        sid = cur.lastrowid
        c.commit()
        c.close()
        return sid

    def due_schedules(self):
        c = self.conn()
        now = local_now().strftime("%Y-%m-%d %H:%M:%S")
        r = c.execute("SELECT * FROM schedules WHERE status='pending' AND scheduled_time<=?",
                      (now,)).fetchall()
        c.close()
        return r

    def set_schedule(self, sid, status, mids=None):
        c = self.conn()
        if mids:
            c.execute("UPDATE schedules SET status=?, message_ids=? WHERE id=?",
                      (status, json.dumps(mids), sid))
        else:
            c.execute("UPDATE schedules SET status=? WHERE id=?", (status, sid))
        c.commit()
        c.close()

    def cancel_schedule(self, uid, sid):
        c = self.conn()
        c.execute("UPDATE schedules SET status='cancelled' WHERE id=? AND user_id=?", (sid, uid))
        c.commit()
        c.close()

    def user_schedules(self, uid):
        c = self.conn()
        r = c.execute("SELECT * FROM schedules WHERE user_id=? AND status='pending' ORDER BY scheduled_time",
                      (uid,)).fetchall()
        c.close()
        return r

    # ---- forwarding ----
    def add_source(self, uid, sid, uname):
        c = self.conn()
        try:
            c.execute("INSERT INTO source_channels (user_id, source_channel_id, source_username) VALUES (?,?,?)",
                      (uid, sid, uname))
            c.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            c.close()

    def user_sources(self, uid):
        c = self.conn()
        r = c.execute("SELECT * FROM source_channels WHERE user_id=?", (uid,)).fetchall()
        c.close()
        return r

    def add_rule(self, uid, source_row_id, dests, inc, exc):
        c = self.conn()
        c.execute("INSERT INTO forwarding_rules (user_id, source_id, dest_channel_ids, keyword_include, keyword_exclude)"
                  " VALUES (?,?,?,?,?)",
                  (uid, source_row_id, json.dumps(dests), inc, exc))
        c.commit()
        c.close()

    def user_rules(self, uid):
        c = self.conn()
        r = c.execute("SELECT * FROM forwarding_rules WHERE user_id=?", (uid,)).fetchall()
        c.close()
        return r

    def rules_for_chat(self, chat_id):
        c = self.conn()
        r = c.execute(
            "SELECT fr.*, sc.source_channel_id FROM forwarding_rules fr"
            " JOIN source_channels sc ON sc.id = fr.source_id"
            " WHERE fr.is_active=1 AND sc.is_active=1 AND sc.source_channel_id=?",
            (chat_id,)).fetchall()
        c.close()
        return r

    def reactors_for_chat(self, chat_id):
        c = self.conn()
        r = c.execute(
            "SELECT DISTINCT u.* FROM users u WHERE u.auto_react='on' AND u.is_banned=0 AND ("
            " u.user_id IN (SELECT user_id FROM source_channels WHERE source_channel_id=?)"
            " OR u.user_id IN (SELECT user_id FROM channels WHERE channel_id=?))",
            (chat_id, chat_id)).fetchall()
        c.close()
        return r

    # ---- buttons ----
    def save_buttons(self, uid, cid, mid, buttons):
        c = self.conn()
        c.execute("DELETE FROM post_buttons WHERE channel_id=? AND message_id=?", (cid, mid))
        c.execute("INSERT INTO post_buttons (user_id, channel_id, message_id, buttons_json) VALUES (?,?,?,?)",
                  (uid, cid, mid, json.dumps(buttons)))
        c.commit()
        c.close()

    def get_buttons(self, cid, mid):
        c = self.conn()
        r = c.execute("SELECT * FROM post_buttons WHERE channel_id=? AND message_id=?",
                      (cid, mid)).fetchone()
        c.close()
        return r

    # ---- payments ----
    def submit_payment(self, uid, amount, proof, ptype):
        c = self.conn()
        c.execute("INSERT INTO payments (user_id, amount, utr_or_proof, proof_type) VALUES (?,?,?,?)",
                  (uid, amount, proof, ptype))
        c.commit()
        c.close()

    def pending_payments(self):
        c = self.conn()
        r = c.execute("SELECT * FROM payments WHERE status='pending' ORDER BY id").fetchall()
        c.close()
        return r

    def payment(self, pid):
        c = self.conn()
        r = c.execute("SELECT * FROM payments WHERE id=?", (pid,)).fetchone()
        c.close()
        return r

    def review_payment(self, pid, status, reviewer):
        c = self.conn()
        c.execute("UPDATE payments SET status=?, reviewed_by=?, reviewed_at=CURRENT_TIMESTAMP WHERE id=?",
                  (status, reviewer, pid))
        c.commit()
        c.close()

    # ---- logs / stats ----
    def log(self, uid, action, details=""):
        c = self.conn()
        c.execute("INSERT INTO activity_logs (user_id, action, details) VALUES (?,?,?)",
                  (uid, action, details))
        c.commit()
        c.close()

    def recent_logs(self, limit=12):
        c = self.conn()
        r = c.execute("SELECT * FROM activity_logs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        c.close()
        return r

    def stats(self):
        c = self.conn()
        total = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        paid = c.execute("SELECT COUNT(*) FROM users WHERE plan='PAID'").fetchone()[0]
        pend = c.execute("SELECT COUNT(*) FROM payments WHERE status='pending'").fetchone()[0]
        chans = c.execute("SELECT COUNT(*) FROM channels").fetchone()[0]
        c.close()
        return total, paid, pend, chans


db = Database(DATABASE_PATH)

# -----------------------------------------------------------------------------
# 4. ROLES, LIMITS, SECURITY
# -----------------------------------------------------------------------------

def is_owner(uid):
    return bool(OWNER_ID) and uid == OWNER_ID

def is_staff(u):
    return bool(u) and (is_owner(u["user_id"]) or u["role"] in ("owner", "admin"))

def limits(u):
    """(channels, schedules, rules, buttons)"""
    if not u:
        return MAX_CHANNELS_FREE, MAX_SCHEDULES_FREE, MAX_RULES_FREE, MAX_BUTTONS_FREE
    if is_owner(u["user_id"]) or u["role"] == "owner":
        return UNLIMITED, UNLIMITED, UNLIMITED, UNLIMITED
    if u["role"] == "admin" or u["plan"] == "PAID":
        return MAX_CHANNELS_PAID, MAX_SCHEDULES_PAID, MAX_RULES_PAID, MAX_BUTTONS_PAID
    return MAX_CHANNELS_FREE, MAX_SCHEDULES_FREE, MAX_RULES_FREE, MAX_BUTTONS_FREE

def badge(u):
    if not u:
        return G["user"]
    if is_owner(u["user_id"]) or u["role"] == "owner":
        return G["skull"]
    if u["role"] == "admin":
        return G["shield"]
    if u["is_verified"]:
        return G["check"]
    if u["plan"] == "PAID":
        return G["gem"]
    return G["dot"]

def rank_name(u):
    if not u:
        return "GUEST"
    if is_owner(u["user_id"]) or u["role"] == "owner":
        return "OWNER"
    return {"admin": "ADMIN"}.get(u["role"], "PREMIUM" if u["plan"] == "PAID" else "FREE")

def refresh(u):
    """Expire paid plans."""
    if u and u["plan"] == "PAID" and u["paid_until"]:
        try:
            if local_now() > datetime.datetime.strptime(u["paid_until"], "%Y-%m-%d %H:%M:%S"):
                db.update_plan(u["user_id"], "FREE")
                return db.get_user(u["user_id"])
        except Exception:
            pass
    return u

def check_auth(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *a, **kw):
        user = update.effective_user
        if not user:
            return
        db.ensure_user(user.id, user.username, user.first_name)
        u = db.get_user(user.id)
        if u["is_banned"]:
            await edit_or_reply(update, f"{G['cross']} <b>ACCESS REVOKED</b>\n\nYour account is suspended.")
            return
        if os.getenv("MAINTENANCE_MODE", "false").lower() == "true" and not is_staff(u):
            await edit_or_reply(update, f"{G['gear']} <b>MAINTENANCE</b>\n\nSystems are locked. Come back soon.")
            return
        return await func(update, context, *a, **kw)
    return wrapper

def staff_only(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *a, **kw):
        u = db.get_user(update.effective_user.id)
        if not is_staff(u):
            if update.callback_query:
                await safe_callback_answer(update.callback_query, "⛔ Staff only.", show_alert=True)
            else:
                await edit_or_reply(update, f"{G['cross']} Staff only.")
            return
        return await func(update, context, *a, **kw)
    return wrapper

def owner_only(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *a, **kw):
        if update.effective_user.id != OWNER_ID:
            if update.callback_query:
                await safe_callback_answer(update.callback_query, "⛔ Owner only.", show_alert=True)
            else:
                await edit_or_reply(update, f"{G['cross']} Owner only.")
            return
        return await func(update, context, *a, **kw)
    return wrapper

# -----------------------------------------------------------------------------
# 5. UI PLUMBING
# -----------------------------------------------------------------------------

async def edit_or_reply(update, text, markup=None, parse_mode=ParseMode.HTML):
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(text, reply_markup=markup, parse_mode=parse_mode)
            return
        except Exception as e:
            if "not modified" in str(e).lower():
                return
            await update.callback_query.message.reply_text(text, reply_markup=markup, parse_mode=parse_mode)
    elif update.message:
        await update.message.reply_text(text, reply_markup=markup, parse_mode=parse_mode)

def kb(rows):
    return InlineKeyboardMarkup([[InlineKeyboardButton(**b) for b in row] for row in rows])

def back(target="dashboard", label=None):
    return [{"text": f"{G['mail']} {label or 'Back'}".strip(), "callback_data": target}]

def url_markup(rows):
    """rows = list of list of dict(text,url) -> InlineKeyboardMarkup"""
    if not rows:
        return None
    return InlineKeyboardMarkup([[InlineKeyboardButton(**b) for b in row] for row in rows])

def parse_button_lines(raw, max_buttons):
    """Each line = one row. Buttons inside a line separated by ';;'. Button = 'Label | URL'."""
    rows, count, errors = [], 0, []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        row = []
        for chunk in line.split(";;"):
            chunk = chunk.strip()
            if not chunk:
                continue
            if "|" not in chunk:
                errors.append(chunk)
                continue
            label, target = [p.strip() for p in chunk.split("|", 1)]
            if not label or not target:
                errors.append(chunk)
                continue
            if target.startswith("@") or (not target.startswith("http") and "." not in target and "/" not in target):
                target = "https://t.me/" + target.lstrip("@")
            if count >= max_buttons:
                errors.append(f"{label} (over limit)")
                continue
            row.append({"text": label[:60], "url": target})
            count += 1
        if row:
            rows.append(row)
    return rows, errors, count

def parse_msg_ref(text):
    """Accepts 1234 or https://t.me/name/1234 -> int or None"""
    text = text.strip()
    if text.lstrip("-").isdigit():
        return int(text)
    m = re.search(r"/(\d+)(?:\?.*)?$", text)
    if m:
        return int(m.group(1))
    return None

# -----------------------------------------------------------------------------
# 6. DASHBOARD
# -----------------------------------------------------------------------------

async def show_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    u = refresh(db.get_user(user.id))
    lim_c, lim_s, lim_r, lim_b = limits(u)

    chans = db.count_channels(user.id)
    scheds = len(db.user_schedules(user.id))
    rules = len(db.user_rules(user.id))

    def q(n, limit):
        return "∞" if limit >= UNLIMITED else f"{n}/{limit}"

    lines = [
        f"{G['wave']} <i>Welcome back, {user.first_name}.</i>",
        "",
        f"{G['user']} <b>RANK</b> · {rank_name(u)} {badge(u)}",
        f"{G['orbit']} <b>CHANNELS</b> · {q(chans, lim_c)}  {bar(chans, min(lim_c, 8))}",
        f"{G['clock']} <b>QUEUE</b> · {q(scheds, lim_s)}  {bar(scheds, min(lim_s, 8))}",
        f"{G['paw']} <b>RULES</b> · {q(rules, lim_r)}",
    ]
    if u["plan"] == "PAID" and u["paid_until"]:
        lines.append(f"{G['gem']} <b>VALID TILL</b> · {u['paid_until'][:16]}")
    if u["role"] == "owner":
        lines.append(f"{G['flame']} <i>Unlimited everything. Absolute clearance.</i>")

    text = card(f"{G['spiral']} F4 // CONSOLE", lines, G["skull"])

    rows = [
        [{"text": f"{G['orbit']} Channels", "callback_data": "m_chan"},
         {"text": f"{G['pen']} Compose", "callback_data": "m_post"}],
        [{"text": f"{G['clock']} Queue", "callback_data": "m_sched"},
         {"text": f"{G['paw']} Forward", "callback_data": "m_fwd"}],
        [{"text": f"{G['link']} Button Forge", "callback_data": "m_btn"},
         {"text": f"{G['pen']} Edit / Buttons", "callback_data": "m_btn"}],
        [{"text": f"{G['heart']} Reactions", "callback_data": "m_react"},
         {"text": f"{G['chart']} Analytics", "callback_data": "m_stats"}],
        [{"text": f"{G['gear']} Settings", "callback_data": "m_set"},
         {"text": f"{G['gift']} Upgrade", "callback_data": "m_up"}],
    ]
    if is_staff(u):
        rows.append([{"text": f"{G['shield']} Staff Deck", "callback_data": "adm_home"}])
    rows.append([{"text": f"{G['star']} Help", "callback_data": "m_help"}])

    await edit_or_reply(update, text, kb(rows))

# -----------------------------------------------------------------------------
# 7. CHANNELS
# -----------------------------------------------------------------------------

async def m_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = db.get_user(uid)
    chans = db.user_channels(uid)
    lim = limits(u)[0]

    if not chans:
        text = card(f"{G['orbit']} CHANNEL VAULT", [
            f"{G['ghost']} <i>No channels wired in.</i>",
            "",
            f"Add the bot as <b>admin</b> with post + edit rights,",
            f"then register the channel here.",
        ])
        rows = [[{"text": f"{G['plus']} Wire a Channel", "callback_data": "ch_add"}], back()]
        return await edit_or_reply(update, text, kb(rows))

    lines = [f"{G['fire']} <b>{len(chans)}</b> of {'∞' if lim >= UNLIMITED else lim} slots used", ""]
    rows = []
    for ch in chans:
        title = ch["title"] or ch["channel_username"] or str(ch["channel_id"])
        kind = "GROUP" if ch["chat_type"] in ("group", "supergroup") else "CHANNEL"
        lines.append(f"{CHECK_ICON} <b>{kind}</b> · {title}")
        rows.append([{"text": f"{G['down']} Unwire {title}"[:60], "callback_data": f"ch_del_{ch['channel_id']}"}])

    if len(chans) < lim:
        rows.append([{"text": f"{G['plus']} Wire Another", "callback_data": "ch_add"}])
    rows.append(back())
    await edit_or_reply(update, card(f"{G['orbit']} CHANNEL VAULT", lines), kb(rows))

async def ch_add_prompt(update, context):
    context.user_data["flow"] = "ch_add"
    text = card(f"{G['plus']} WIRE A CHANNEL", [
        f"{G['shield']} Bot must be <b>administrator</b>.",
        f"{G['pen']} Needs post + edit message rights.",
        "",
        f"Send <code>@username</code> or numeric <code>-100…</code> id.",
    ])
    await edit_or_reply(update, text, kb([back("m_chan", "Cancel")]))

async def ch_add_process(update, context):
    text = update.message.text.strip()
    if not (text.startswith("@") or text.lstrip("-").isdigit()):
        return await update.message.reply_text(f"{G['cross']} Use @username or numeric id.")
    try:
        chat = await context.bot.get_chat(text)
        if chat.type not in ("channel", "group", "supergroup"):
            return await update.message.reply_text(f"{G['cross']} Use a channel or group.")
        bot_member = await context.bot.get_chat_member(chat.id, context.bot.id)
        if chat.type == "channel" and bot_member.status not in ("administrator", "creator"):
            return await update.message.reply_text(
                f"{G['cross']} The bot must be an administrator in a channel."
            )
        if chat.type in ("group", "supergroup") and bot_member.status in ("left", "kicked"):
            return await update.message.reply_text(f"{G['cross']} The bot is not a member of that group.")
        if db.add_channel(update.effective_user.id, chat.id, chat.username, chat.title, chat.type):
            db.log(update.effective_user.id, "channel_add", str(chat.id))
            context.user_data.pop("flow", None)
            await update.message.reply_text(f"{G['check']} <b>{chat.title}</b> wired.")
            await show_dashboard(update, context)
        else:
            await update.message.reply_text(f"{G['dot']} Already wired.")
    except Exception as e:
        logger.error(e)
        await update.message.reply_text(f"{G['cross']} Could not verify channel.")

# -----------------------------------------------------------------------------
# 8. COMPOSER
# -----------------------------------------------------------------------------

def new_draft(context):
    context.user_data["draft"] = {"buttons": [], "dests": []}
    context.user_data["flow"] = "post"

async def m_compose(update, context):
    new_draft(context)
    context.user_data["flow"] = "post_type"
    text = card(f"{G['pen']} COMPOSER", [
        f"{G['misc']} Choose the payload type.",
        "",
        f"{G['pen']} <b>Text</b> — plain message",
        f"{G['box']} <b>Media</b> — photo or video with caption",
    ])
    rows = [
        [{"text": f"{G['pen']} Text", "callback_data": "p_text"},
         {"text": f"{G['box']} Media", "callback_data": "p_media"}],
        back("dashboard", "Abort"),
    ]
    await edit_or_reply(update, text, kb(rows))

async def p_type(update, context):
    kind = update.callback_query.data.split("_")[-1]
    d = context.user_data.setdefault("draft", {"buttons": [], "dests": []})
    d["kind"] = kind
    if kind == "text":
        context.user_data["flow"] = "post_content"
        await update.callback_query.edit_message_text(
            card(f"{G['pen']} COMPOSE // TEXT", [f"{G['misc']} Send the message body.", "HTML allowed."]),
            reply_markup=kb([back("dashboard", "Abort")]), parse_mode=ParseMode.HTML)
    else:
        context.user_data["flow"] = "post_media"
        await update.callback_query.edit_message_text(
            card(f"{G['box']} COMPOSE // MEDIA", [f"{G['misc']} Send a photo or video now."]),
            reply_markup=kb([back("dashboard", "Abort")]), parse_mode=ParseMode.HTML)

async def post_content(update, context):
    d = context.user_data["draft"]
    d["content"] = update.message.text_html
    await ask_buttons(update, context)

async def post_media(update, context):
    d = context.user_data["draft"]
    if update.message.photo:
        d["file_id"], d["media_type"] = update.message.photo[-1].file_id, "photo"
    elif update.message.video:
        d["file_id"], d["media_type"] = update.message.video.file_id, "video"
    else:
        return await update.message.reply_text(f"{G['cross']} Unsupported media.")
    d["content"] = update.message.caption_html or ""
    await ask_buttons(update, context)

async def ask_buttons(update, context):
    d = context.user_data["draft"]
    u = db.get_user(update.effective_user.id)
    maxb = limits(u)[3]
    preview = ""
    if d.get("buttons"):
        preview = "\n".join(" · ".join(b["text"] for b in row) for row in d["buttons"])
    lines = [
        f"{G['link']} Inline buttons are optional.",
        "",
        f"Format: <code>Label | https://url</code>",
        f"One line = one row · <code>;;</code> splits a row",
        f"Limit: {'∞' if maxb >= UNLIMITED else maxb} buttons",
    ]
    if preview:
        lines += ["", f"<b>Current:</b>", f"<code>{preview}</code>"]
    rows = [
        [{"text": f"{G['link']} Add Buttons", "callback_data": "p_btn"}],
        [{"text": f"{G['check']} Continue", "callback_data": "p_dest"}],
        back("dashboard", "Abort"),
    ]
    await edit_or_reply(update, card(f"{G['link']} BUTTON FORGE", lines), kb(rows))

async def p_btn_prompt(update, context):
    context.user_data["flow"] = "post_btn"
    await edit_or_reply(update, card(f"{G['link']} BUTTON FORGE", [
        f"{G['pen']} Send your button block.",
        "",
        f"<code>Join | https://t.me/yourchannel</code>",
        f"<code>Site | site.com ;; Chat | @yourchat</code>",
    ]), kb([back("p_dest", "Skip")]))

async def p_btn_apply(update, context):
    d = context.user_data["draft"]
    u = db.get_user(update.effective_user.id)
    maxb = limits(u)[3]
    rows, errors, count = parse_button_lines(update.message.text, maxb)
    if not rows:
        return await update.message.reply_text(f"{G['cross']} No valid buttons. Use <code>Label | URL</code>.",
                                               parse_mode=ParseMode.HTML)
    d["buttons"] = rows
    context.user_data["flow"] = None
    msg = f"{G['check']} {count} button(s) forged."
    if errors:
        msg += f"\n{G['dot']} Skipped: {', '.join(errors[:5])}"
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
    await ask_buttons(update, context)

async def p_dest(update, context):
    uid = update.effective_user.id
    chans = db.user_channels(uid)
    d = context.user_data.setdefault("draft", {"buttons": [], "dests": []})
    if not chans:
        await edit_or_reply(update, f"{G['cross']} No channels wired.")
        return await show_dashboard(update, context)
    context.user_data["flow"] = None
    await render_dests(update, context, d)

async def render_dests(update, context, d):
    chans = db.user_channels(update.effective_user.id)
    lines = [f"{G['fire']} Tap to toggle targets.", ""]
    rows = []
    for ch in chans:
        raw_title = ch["title"] or ch["channel_username"] or str(ch["channel_id"])
        kind = "GROUP" if ch["chat_type"] in ("group", "supergroup") else "CHANNEL"
        title = f"{kind} · {raw_title}"
        on = ch["channel_id"] in d["dests"]
        lines.append(f"{CHECK_ICON if on else CROSS_ICON} {title}")
        rows.append([{"text": f"{CHECK_ICON if on else CROSS_ICON} {title}"[:60],
                      "callback_data": f"p_tog_{ch['channel_id']}"}])
    rows.append([{"text": f"{G['bolt']} Publish Now", "callback_data": "p_go"},
                 {"text": f"{G['clock']} Schedule", "callback_data": "p_sched"}])
    rows.append(back("dashboard", "Abort"))
    await edit_or_reply(update, card(f"{G['orbit']} TARGETS", lines), kb(rows))

async def p_toggle(update, context):
    cid = int(update.callback_query.data.split("_")[-1])
    d = context.user_data["draft"]
    d["dests"].remove(cid) if cid in d["dests"] else d["dests"].append(cid)
    await render_dests(update, context, d)

async def deliver(bot, chat_id, content, file_id, media_type, buttons):
    markup = url_markup(buttons) if buttons else None
    if file_id:
        if media_type == "photo":
            return await bot.send_photo(chat_id, file_id, caption=content or None,
                                        parse_mode=ParseMode.HTML, reply_markup=markup)
        return await bot.send_video(chat_id, file_id, caption=content or None,
                                    parse_mode=ParseMode.HTML, reply_markup=markup)
    return await bot.send_message(chat_id, content, parse_mode=ParseMode.HTML, reply_markup=markup)

async def p_go(update, context):
    d = context.user_data.get("draft", {})
    if not d.get("dests"):
        return await safe_callback_answer(update.callback_query, "Pick at least one channel.", show_alert=True)
    await safe_callback_answer(update.callback_query, "Deploying…")
    sent, failed = [], []
    for cid in d["dests"]:
        try:
            msg = await deliver(context.bot, cid, d.get("content"), d.get("file_id"),
                                d.get("media_type"), d.get("buttons"))
            sent.append(cid)
            if d.get("buttons"):
                db.save_buttons(update.effective_user.id, cid, msg.message_id, d["buttons"])
        except Exception as e:
            logger.error(f"publish: {e}")
            failed.append(cid)
    db.log(update.effective_user.id, "publish", f"{len(sent)} ok / {len(failed)} fail")
    out = card(f"{G['bolt']} DEPLOY REPORT", [
        f"{G['check']} Delivered · <b>{len(sent)}</b>",
        f"{G['cross']} Failed · <b>{len(failed)}</b>",
    ])
    await edit_or_reply(update, out, kb([back("dashboard", "Console")]))
    context.user_data.pop("draft", None)

async def p_sched_prompt(update, context):
    d = context.user_data.get("draft", {})
    if not d.get("dests"):
        return await safe_callback_answer(update.callback_query, "Pick at least one channel.", show_alert=True)
    context.user_data["flow"] = "post_time"
    await edit_or_reply(update, card(f"{G['clock']} SCHEDULE", [
        f"{G['pen']} Send the launch time.",
        "",
        f"<code>YYYY-MM-DD HH:MM</code>",
        f"<i>Server clock: {TIMEZONE_STR}</i>",
    ]), kb([back("p_dest", "Cancel")]))

async def post_time(update, context):
    try:
        when = datetime.datetime.strptime(update.message.text.strip(), "%Y-%m-%d %H:%M")
        if when <= local_now():
            return await update.message.reply_text(f"{G['cross']} Choose a future time in {TIMEZONE_STR}.")
    except ValueError:
        return await update.message.reply_text(f"{G['cross']} Bad format. YYYY-MM-DD HH:MM")
    d = context.user_data["draft"]
    u = db.get_user(update.effective_user.id)
    lim = limits(u)[1]
    if len(db.user_schedules(u["user_id"])) >= lim:
        return await update.message.reply_text(f"{G['cross']} Queue full.")
    sid = db.add_schedule(u["user_id"], d.get("content"), d.get("file_id"), d.get("media_type"),
                          d["dests"], d.get("buttons"), when.strftime("%Y-%m-%d %H:%M:%S"))
    db.log(u["user_id"], "schedule", f"id={sid}")
    await update.message.reply_text(f"{G['check']} Queued as <b>#{sid}</b> for {fmt_dt(when)}",
                                    parse_mode=ParseMode.HTML)
    context.user_data.pop("draft", None)
    context.user_data["flow"] = None
    await show_dashboard(update, context)

# -----------------------------------------------------------------------------
# 9. SCHEDULER
# -----------------------------------------------------------------------------

async def scheduler_tick(app):
    for s in db.due_schedules():
        try:
            dests = json.loads(s["channel_ids"] or "[]")
            buttons = json.loads(s["buttons_json"] or "[]")
            mids = {}
            for cid in dests:
                try:
                    msg = await deliver(app.bot, cid, s["content_text"], s["media_file_id"],
                                        s["media_type"], buttons)
                    mids[cid] = msg.message_id
                    if buttons:
                        db.save_buttons(s["user_id"], cid, msg.message_id, buttons)
                except Exception as e:
                    logger.error(f"sched send: {e}")
                    await report_error(None, app, e)
            db.set_schedule(s["id"], "sent" if mids else "failed", mids or None)
        except Exception as e:
            logger.error(f"sched tick: {e}")
            await report_error(None, app, e)
            db.set_schedule(s["id"], "failed")

async def m_queue(update, context):
    scheds = db.user_schedules(update.effective_user.id)
    if not scheds:
        return await edit_or_reply(update, card(f"{G['clock']} QUEUE", [f"{G['ghost']} Empty."]),
                                   kb([back()]))
    lines, rows = [], []
    for s in scheds:
        body = (s["content_text"] or "[media]")[:36]
        lines.append(f"{G['clock']} <b>#{s['id']}</b> · {s['scheduled_time'][:16]}\n   <i>{body}</i>")
        rows.append([{"text": f"{G['cross']} Kill #{s['id']}", "callback_data": f"q_del_{s['id']}"}])
    rows.append(back())
    await edit_or_reply(update, card(f"{G['clock']} QUEUE · {len(scheds)}", lines), kb(rows))

async def q_del(update, context):
    sid = int(update.callback_query.data.split("_")[-1])
    db.cancel_schedule(update.effective_user.id, sid)
    await safe_callback_answer(update.callback_query, "Killed.")
    await m_queue(update, context)

# -----------------------------------------------------------------------------
# 10. BUTTON FORGE ON EXISTING MESSAGES
# -----------------------------------------------------------------------------

async def m_btn(update, context):
    chans = db.user_channels(update.effective_user.id)
    if not chans:
        return await edit_or_reply(update, f"{G['cross']} Wire a channel first.", kb([back()]))
    rows = [[{"text": f"{G['orbit']} {c['title'] or c['channel_username']}"[:60],
              "callback_data": f"b_pick_{c['channel_id']}"}] for c in chans]
    rows.append(back())
    await edit_or_reply(update, card(f"{G['link']} BUTTON FORGE // TARGET", [
        f"{G['misc']} Pick the channel holding the message."]), kb(rows))

async def b_pick(update, context):
    cid = int(update.callback_query.data.split("_")[-1])
    context.user_data["btn_chat"] = cid
    context.user_data["flow"] = "btn_ref"
    await edit_or_reply(update, card(f"{G['link']} MESSAGE REFERENCE", [
        f"{G['pen']} Send the message id or its link.",
        "",
        f"<code>https://t.me/yourchannel/1234</code>",
        f"<code>1234</code>",
    ]), kb([back("m_btn", "Cancel")]))

async def b_ref(update, context):
    mid = parse_msg_ref(update.message.text)
    if not mid:
        return await update.message.reply_text(f"{G['cross']} Could not read a message id.")
    context.user_data["btn_msg"] = mid
    context.user_data["flow"] = "btn_action"
    rows = [
        [{"text": f"{G['link']} Set / Replace Buttons", "callback_data": "b_set"}],
        [{"text": f"{G['pen']} Edit Text", "callback_data": "b_text"}],
        [{"text": f"{G['down']} Delete Message", "callback_data": "b_kill"}],
        back("m_btn", "Cancel"),
    ]
    await update.message.reply_text(card(f"{G['misc']} MESSAGE {mid}", [
        f"{G['eye']} Choose an operation."]), reply_markup=kb(rows), parse_mode=ParseMode.HTML)

async def b_set_prompt(update, context):
    context.user_data["flow"] = "btn_lines"
    u = db.get_user(update.effective_user.id)
    maxb = limits(u)[3]
    await edit_or_reply(update, card(f"{G['link']} BUTTON BLOCK", [
        f"{G['pen']} Send the block. Limit {'∞' if maxb >= UNLIMITED else maxb}.",
        f"<code>Label | https://url</code> per line",
        f"<code>;;</code> splits a row",
        "",
        f"<i>Send</i> <code>-</code> <i>to strip all buttons.</i>",
    ]), kb([back("m_btn", "Cancel")]))

async def b_set_apply(update, context):
    cid = context.user_data["btn_chat"]
    mid = context.user_data["btn_msg"]
    raw = update.message.text.strip()
    if raw == "-":
        buttons = []
    else:
        u = db.get_user(update.effective_user.id)
        buttons, errors, _ = parse_button_lines(raw, limits(u)[3])
        if not buttons:
            return await update.message.reply_text(f"{G['cross']} No valid buttons.")
    try:
        await context.bot.edit_message_reply_markup(cid, mid, reply_markup=url_markup(buttons))
        db.save_buttons(update.effective_user.id, cid, mid, buttons)
        db.log(update.effective_user.id, "btn_set", f"{cid}/{mid}")
        await update.message.reply_text(
            f"{G['check']} Buttons {'cleared' if not buttons else 'applied'} on message {mid}.",
            parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(e)
        await update.message.reply_text(f"{G['cross']} Failed: {e}")
    context.user_data["flow"] = None

async def b_text_prompt(update, context):
    context.user_data["flow"] = "btn_newtext"
    await edit_or_reply(update, card(f"{G['pen']} EDIT TEXT", [
        f"{G['misc']} Send the replacement text.",
        f"HTML allowed. Existing buttons are preserved.",
    ]), kb([back("m_btn", "Cancel")]))

async def b_text_apply(update, context):
    cid = context.user_data["btn_chat"]
    mid = context.user_data["btn_msg"]
    stored = db.get_buttons(cid, mid)
    markup = url_markup(json.loads(stored["buttons_json"])) if stored else None
    try:
        await context.bot.edit_message_text(update.message.text_html, chat_id=cid, message_id=mid,
                                            parse_mode=ParseMode.HTML, reply_markup=markup)
        db.log(update.effective_user.id, "msg_edit", f"{cid}/{mid}")
        await update.message.reply_text(f"{G['check']} Text replaced on message {mid}.",
                                        parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(e)
        await update.message.reply_text(f"{G['cross']} Failed: {e}")
    context.user_data["flow"] = None

async def b_kill(update, context):
    cid = context.user_data["btn_chat"]
    mid = context.user_data["btn_msg"]
    try:
        await context.bot.delete_message(cid, mid)
        await safe_callback_answer(update.callback_query, "Deleted.")
        db.log(update.effective_user.id, "msg_delete", f"{cid}/{mid}")
        await show_dashboard(update, context)
    except Exception as e:
        await safe_callback_answer(update.callback_query, f"Failed: {e}", show_alert=True)

# -----------------------------------------------------------------------------
# 11. AUTO-FORWARDING
# -----------------------------------------------------------------------------

async def m_fwd(update, context):
    uid = update.effective_user.id
    u = db.get_user(uid)
    srcs = db.user_sources(uid)
    rules = db.user_rules(uid)
    lim = limits(u)[2]
    lines = [f"{G['paw']} Rules: {len(rules)}/{'∞' if lim >= UNLIMITED else lim}", ""]
    if srcs:
        for s in srcs:
            lines.append(f"{G['dot']} source <code>{s['source_channel_id']}</code>")
    else:
        lines.append(f"{G['ghost']} No sources.")
    rows = [
        [{"text": f"{G['plus']} Add Source", "callback_data": "f_add"}],
        [{"text": f"{G['paw']} New Rule", "callback_data": "f_rule"}],
        back(),
    ]
    await edit_or_reply(update, card(f"{G['paw']} AUTO-FORWARD", lines), kb(rows))

async def f_add_prompt(update, context):
    context.user_data["flow"] = "f_source"
    await edit_or_reply(update, card(f"{G['plus']} SOURCE", [
        f"{G['pen']} Send the source @username or id.",
        f"<i>Private sources require bot admin rights.</i>",
    ]), kb([back("m_fwd", "Cancel")]))

async def f_add_apply(update, context):
    try:
        chat = await context.bot.get_chat(update.message.text.strip())
        if db.add_source(update.effective_user.id, chat.id, chat.username):
            await update.message.reply_text(f"{G['check']} Source <b>{chat.title}</b> added.",
                                            parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text(f"{G['dot']} Already added.")
    except Exception:
        await update.message.reply_text(f"{G['cross']} Channel not found.")
    context.user_data["flow"] = None
    await m_fwd(update, context)

async def f_rule_prompt(update, context):
    srcs = db.user_sources(update.effective_user.id)
    if not srcs:
        return await edit_or_reply(update, f"{G['cross']} Add a source first.", kb([back("m_fwd")]))
    rows = [[{"text": f"{G['dot']} {s['source_username'] or s['source_channel_id']}"[:60],
              "callback_data": f"f_src_{s['id']}"}] for s in srcs]
    rows.append(back("m_fwd", "Cancel"))
    await edit_or_reply(update, card(f"{G['paw']} RULE // SOURCE", [f"{G['misc']} Pick a source."]), kb(rows))

async def f_rule_source(update, context):
    context.user_data["rule_src"] = int(update.callback_query.data.split("_")[-1])
    context.user_data["flow"] = "f_keywords"
    await edit_or_reply(update, card(f"{G['tag']} RULE // KEYWORDS", [
        f"{G['check']} <code>+word</code> must appear",
        f"{G['cross']} <code>-word</code> must not appear",
        f"{G['dot']} <code>-</code> alone for no filter",
        "",
        f"Send both on one line, space separated.",
    ]), kb([back("m_fwd", "Cancel")]))

async def f_rule_keywords(update, context):
    inc, exc = "", ""
    for token in update.message.text.split():
        if token.startswith("+") and len(token) > 1:
            inc = token[1:]
        elif token.startswith("-") and len(token) > 1:
            exc = token[1:]
    context.user_data["rule_inc"], context.user_data["rule_exc"] = inc, exc
    context.user_data["rule_dests"] = []
    context.user_data["flow"] = None
    await render_rule_dests(update, context)

async def render_rule_dests(update, context):
    chans = db.user_channels(update.effective_user.id)
    dests = context.user_data.get("rule_dests", [])
    rows = []
    for c in chans:
        raw_title = c["title"] or c["channel_username"] or str(c["channel_id"])
        kind = "GROUP" if c["chat_type"] in ("group", "supergroup") else "CHANNEL"
        title = f"{kind} · {raw_title}"
        on = c["channel_id"] in dests
        rows.append([{"text": f"{CHECK_ICON if on else CROSS_ICON} {title}"[:60],
                      "callback_data": f"f_dst_{c['channel_id']}"}])
    rows.append([{"text": f"{G['check']} Save Rule", "callback_data": "f_save"}])
    rows.append(back("m_fwd", "Cancel"))
    await edit_or_reply(update, card(f"{G['orbit']} RULE // TARGETS", [
        f"{G['fire']} Toggle destinations."]), kb(rows))

async def f_rule_dest(update, context):
    cid = int(update.callback_query.data.split("_")[-1])
    dests = context.user_data.setdefault("rule_dests", [])
    dests.remove(cid) if cid in dests else dests.append(cid)
    await render_rule_dests(update, context)

async def f_rule_save(update, context):
    dests = context.user_data.get("rule_dests", [])
    if not dests:
        return await safe_callback_answer(update.callback_query, "Pick a destination.", show_alert=True)
    uid = update.effective_user.id
    u = db.get_user(uid)
    if len(db.user_rules(uid)) >= limits(u)[2]:
        return await safe_callback_answer(update.callback_query, "Rule limit reached.", show_alert=True)
    db.add_rule(uid, context.user_data["rule_src"], dests,
                context.user_data.get("rule_inc", ""), context.user_data.get("rule_exc", ""))
    await safe_callback_answer(update.callback_query, "Rule saved.")
    await m_fwd(update, context)

async def process_source_message(msg, context):
    if not msg:
        return
    chat_id = msg.chat.id

    # auto reactions
    for u in db.reactors_for_chat(chat_id):
        pool = db.reaction_pool(u["react_preset"] or "default")
        if not pool:
            continue
        try:
            await context.bot.set_message_reaction(
                chat_id, msg.message_id, reaction=[ReactionTypeEmoji(random.choice(pool))],
                is_big=False)
        except Exception as e:
            logger.info(f"reaction skipped: {e}")
            await notify_owner(context, f"{G['cross']} Reaction skipped in chat <code>{chat_id}</code>\n<code>{html.escape(str(e)[:700])}</code>",
                               parse_mode=ParseMode.HTML)
        break  # one reactor per channel is enough

    # forwarding rules
    rules = db.rules_for_chat(chat_id)
    if not rules:
        return
    text = (msg.caption_html or msg.text_html or "").lower()
    for r in rules:
        inc, exc = (r["keyword_include"] or "").lower(), (r["keyword_exclude"] or "").lower()
        if inc and inc not in text:
            continue
        if exc and exc in text:
            continue
        for dest in json.loads(r["dest_channel_ids"] or "[]"):
            try:
                await context.bot.copy_message(dest, chat_id, msg.message_id)
            except Exception as e:
                logger.error(f"fwd: {e}")
                await notify_owner(context, f"{G['cross']} Forwarding failed to <code>{dest}</code>\n<code>{html.escape(str(e)[:700])}</code>",
                                   parse_mode=ParseMode.HTML)

async def on_channel_post(update, context):
    await process_source_message(update.channel_post, context)

async def on_group_message(update, context):
    """Apply forwarding and reaction rules to normal group/supergroup messages."""
    await process_source_message(update.message, context)

# -----------------------------------------------------------------------------
# 12. REACTIONS
# -----------------------------------------------------------------------------

async def m_react(update, context):
    u = db.get_user(update.effective_user.id)
    on = u["auto_react"] == "on"
    preset = u["react_preset"] or "default"
    packs = db.reaction_packs()
    lines = [
        f"{G['heart']} State · <b>{'ARMED' if on else 'OFF'}</b>",
        f"{G['misc']} Pack · <b>{preset}</b>",
        f"{G['box']} Library · <b>{len(packs)}</b> active pack(s)",
        "",
        f"{G['eye']} The bot reacts to every new post in your",
        f"source and destination channels and groups.",
        "",
        f"<b>Available reaction packs</b>",
    ]
    rows = []
    for pack in packs:
        try:
            emojis = json.loads(pack["emojis_json"])
        except (TypeError, json.JSONDecodeError):
            emojis = []
        lines.append(f"{CHECK_ICON if preset == pack['name'] else CROSS_ICON} <b>{pack['name']}</b> · {len(emojis)} emoji · {' '.join(emojis)}")
        rows.append([{"text": f"{CHECK_ICON if preset == pack['name'] else CROSS_ICON} {pack['name']}"[:60],
                      "callback_data": f"r_set_{pack['name']}"[:64]}])
    rows.insert(0, [{"text": f"{G['down']} Disarm" if on else f"{G['bolt']} Arm", "callback_data": "r_tog"}])
    if is_owner(update.effective_user.id):
        lines += ["", f"{CHECK_ICON} Owner pack tools: <code>/pack_add</code> · <code>/pack_update</code> · <code>/pack_remove</code>"]
    rows.append(back())
    await edit_or_reply(update, card(f"{G['heart']} REACTOR", lines), kb(rows))

async def r_toggle(update, context):
    u = db.get_user(update.effective_user.id)
    db.set_react(u["user_id"], u["auto_react"] != "on")
    await m_react(update, context)

async def r_set(update, context):
    preset = update.callback_query.data.removeprefix("r_set_")
    u = db.get_user(update.effective_user.id)
    if not any(pack["name"] == preset for pack in db.reaction_packs()):
        return await safe_callback_answer(update.callback_query, "That reaction pack is unavailable.", show_alert=True)
    db.set_react(u["user_id"], True, preset)
    await m_react(update, context)

# -----------------------------------------------------------------------------
# 13. ANALYTICS / SETTINGS / HELP
# -----------------------------------------------------------------------------

async def m_stats(update, context):
    uid = update.effective_user.id
    u = db.get_user(uid)
    chans = db.count_channels(uid)
    scheds = len(db.user_schedules(uid))
    rules = len(db.user_rules(uid))
    srcs = len(db.user_sources(uid))
    lines = [
        f"{G['orbit']} Channels · <b>{chans}</b>",
        f"{G['clock']} Queued · <b>{scheds}</b>",
        f"{G['paw']} Rules · <b>{rules}</b>",
        f"{G['eye']} Sources · <b>{srcs}</b>",
        "",
        f"{G['user']} Rank · <b>{rank_name(u)}</b>",
        f"{G['misc']} Since · {str(u['created_at'])[:10]}",
    ]
    await edit_or_reply(update, card(f"{G['chart']} ANALYTICS", lines), kb([back()]))

async def m_settings(update, context):
    u = db.get_user(update.effective_user.id)
    lines = [
        f"{G['user']} ID · <code>{u['user_id']}</code>",
        f"{G['tag']} Handle · @{u['username'] or '—'}",
        f"{G['shield']} Rank · <b>{rank_name(u)}</b> {badge(u)}",
        f"{G['misc']} Zone · {TIMEZONE_STR}",
    ]
    await edit_or_reply(update, card(f"{G['gear']} SETTINGS", lines),
                        kb([[{"text": f"{G['heart']} Reactor", "callback_data": "m_react"}], back()]))

async def m_help(update, context):
    text = card(f"{G['star']} FIELD MANUAL", [
        f"{G['orbit']} <b>Channels</b> — bot needs admin + edit rights",
        f"{G['pen']} <b>Compose</b> — text or media, optional buttons",
        f"{G['link']} <b>Forge</b> — buttons on old messages",
        f"{G['pen']} <b>Edit</b> — rewrite old channel posts",
        f"{G['heart']} <b>Reactor</b> — auto reactions on new posts",
        f"{G['clock']} <b>Queue</b> — scheduled deploys",
        "",
        f"{G['mail']} <b>Shortcuts</b>",
        f"/panel · /channels · /compose · /queue",
        f"/buttons · /forward · /react · /stats",
        f"/settings · /upgrade · /packs · /help · /cancel",
    ])
    await edit_or_reply(update, text, kb([back()]))

# -----------------------------------------------------------------------------
# 14. PREMIUM + PAYMENTS
# -----------------------------------------------------------------------------

async def m_up(update, context):
    u = db.get_user(update.effective_user.id)
    if u["plan"] == "PAID" and u["role"] == "user":
        return await edit_or_reply(update, card(f"{G['gem']} ALREADY PREMIUM", [
            f"{G['check']} Valid till {u['paid_until'] or '—'}",
            f"{G['misc']} Verification · {'yes' if u['is_verified'] else 'pending'}"]),
            kb([back()]))
    text = card(f"{G['gem']} F4 PREMIUM", [
        f"{G['tag']} Price · <b>{CURRENCY_SYMBOL}{PREMIUM_PRICE}</b> / {PREMIUM_DAYS} days",
        "",
        f"{G['orbit']} {MAX_CHANNELS_PAID} channels",
        f"{G['clock']} {MAX_SCHEDULES_PAID} queued posts",
        f"{G['paw']} {MAX_RULES_PAID} forwarding rules",
        f"{G['link']} {MAX_BUTTONS_PAID} buttons per post",
        f"{G['check']} Verified badge",
        "",
        PAYMENT_INSTRUCTIONS or "",
    ])
    await edit_or_reply(update, text,
                        kb([[{"text": f"{G['check']} Submit Proof", "callback_data": "pay_go"}], back()]))

async def pay_prompt(update, context):
    context.user_data["flow"] = "pay_proof"
    await edit_or_reply(update, card(f"{G['mail']} PROOF", [
        f"{G['pen']} Send the UTR number or a payment screenshot."]),
        kb([back("m_up", "Cancel")]))

async def pay_submit(update, context):
    msg = update.message
    if msg.photo:
        proof, ptype = f"photo:{msg.photo[-1].file_id}", "photo"
    elif msg.text:
        proof, ptype = msg.text[:120], "text"
    else:
        return await msg.reply_text(f"{G['cross']} Send text or a photo.")
    uid = update.effective_user.id
    db.submit_payment(uid, PREMIUM_PRICE, proof, ptype)
    db.log(uid, "payment_submit", proof[:40])
    context.user_data["flow"] = None
    await msg.reply_text(card(f"{G['clock']} UNDER REVIEW", [
        f"{G['shield']} A staff member will verify shortly."]), parse_mode=ParseMode.HTML)
    owner_caption = card(f"{G['gift']} PAYMENT INTAKE", [
        f"{G['user']} {html.escape(msg.from_user.first_name or 'Member')} · <code>{uid}</code>",
        f"{G['tag']} {CURRENCY_SYMBOL}{PREMIUM_PRICE} · {PREMIUM_DAYS} days",
        f"{G['misc']} Type · {ptype}",
        f"{G['shield']} Review this proof in the payment desk.",
    ])
    owner_markup = kb([[{"text": f"{G['eye']} Open Payment Desk", "callback_data": "adm_pay"}]])
    if ptype == "photo":
        try:
            await context.bot.send_photo(
                OWNER_ID,
                photo=msg.photo[-1].file_id,
                caption=owner_caption,
                parse_mode=ParseMode.HTML,
                reply_markup=owner_markup,
            )
        except Exception as exc:
            await report_error(update, context, exc)
    else:
        await notify_owner(context, owner_caption + f"\n<b>UTR</b> · <code>{html.escape(proof)}</code>",
                           reply_markup=owner_markup, parse_mode=ParseMode.HTML)

# -----------------------------------------------------------------------------
# 15. STAFF DECK
# -----------------------------------------------------------------------------

async def adm_home(update, context):
    total, paid, pend, chans = db.stats()
    u = db.get_user(update.effective_user.id)
    lines = [
        f"{G['user']} Users · <b>{total}</b>",
        f"{G['gem']} Premium · <b>{paid}</b>",
        f"{G['mail']} Pending · <b>{pend}</b>",
        f"{G['orbit']} Channels · <b>{chans}</b>",
        "",
        f"{G['shield']} Operator · <b>{rank_name(u)}</b>",
    ]
    rows = [
        [{"text": f"{G['mail']} Payment Desk", "callback_data": "adm_pay"},
         {"text": f"{G['check']} Verify", "callback_data": "adm_ver"}],
        [{"text": f"{G['bolt']} Broadcast", "callback_data": "adm_bc"},
         {"text": f"{G['eye']} Logs", "callback_data": "adm_logs"}],
    ]
    if is_owner(update.effective_user.id):
        rows.append([{"text": f"{G['user']} User Directory", "callback_data": "adm_users_0"}])
        rows.append([{"text": f"{G['crown']} Operators", "callback_data": "adm_ops"},
                     {"text": f"{G['gear']} Switches", "callback_data": "adm_sw"}])
    rows.append(back("dashboard", "Exit Deck"))
    await edit_or_reply(update, card(f"{G['shield']} STAFF DECK", lines, G["skull"]), kb(rows))

def user_status_line(user):
    if user["role"] == "owner" or is_owner(user["user_id"]):
        return f"{CHECK_ICON} OWNER"
    if user["plan"] == "PAID":
        return f"{CHECK_ICON} PREMIUM"
    return f"{CROSS_ICON} FREE"

def user_display_name(user):
    return html.escape(user["first_name"] or "Unnamed")

@owner_only
async def adm_users(update, context):
    data = update.callback_query.data if update.callback_query else ""
    try:
        page = max(0, int(data.rsplit("_", 1)[-1])) if data else 0
    except ValueError:
        page = 0
    users = db.all_users()
    users.sort(key=lambda row: (row["plan"] != "PAID", (row["first_name"] or "").lower(), row["user_id"]))
    page_size = 8
    total_pages = max(1, (len(users) + page_size - 1) // page_size)
    page = min(page, total_pages - 1)
    start = page * page_size
    current = users[start:start + page_size]
    premium = sum(1 for row in users if row["plan"] == "PAID")
    lines = [
        f"{G['user']} Total users · <b>{len(users)}</b>",
        f"{G['gem']} Premium · <b>{premium}</b>",
        f"{G['clock']} Page · <b>{page + 1}/{total_pages}</b>",
        "",
    ]
    rows = []
    for user in current:
        username = f"@{html.escape(user['username'])}" if user["username"] else "no username"
        lines.append(
            f"{user_status_line(user)} · <b>{user_display_name(user)}</b> · {username}\n"
            f"   <code>{user['user_id']}</code>"
        )
        rows.append([{
            "text": f"{user_status_line(user)} {user_display_name(user)[:38]}",
            "callback_data": f"adm_user_{user['user_id']}",
        }])
    nav = []
    if page > 0:
        nav.append({"text": "‹ Previous", "callback_data": f"adm_users_{page - 1}"})
    if page < total_pages - 1:
        nav.append({"text": "Next ›", "callback_data": f"adm_users_{page + 1}"})
    if nav:
        rows.append(nav)
    rows.append(back("adm_home"))
    await edit_or_reply(update, card(f"{G['user']} USER DIRECTORY", lines, G["skull"]), kb(rows))

@owner_only
async def adm_user_detail(update, context):
    uid = int(update.callback_query.data.rsplit("_", 1)[-1])
    user = db.get_user(uid)
    if not user:
        return await safe_callback_answer(update.callback_query, "User not found.", show_alert=True)
    username = f"@{html.escape(user['username'])}" if user["username"] else "—"
    lines = [
        f"{G['user']} Name · <b>{user_display_name(user)}</b>",
        f"{G['tag']} Username · {username}",
        f"{G['key']} User ID · <code>{user['user_id']}</code>",
        f"{G['gem']} Status · <b>{user_status_line(user)}</b>",
        f"{G['shield']} Role · <b>{html.escape(user['role'])}</b>",
        f"{G['check']} Verified · <b>{'yes' if user['is_verified'] else 'no'}</b>",
        f"{G['clock']} Valid till · <b>{user['paid_until'] or '—'}</b>",
    ]
    rows = []
    if not is_owner(uid):
        rows.append([{"text": f"{G['gem']} Grant / Renew Premium", "callback_data": f"adm_grant_{uid}"}])
        if user["plan"] == "PAID" or user["is_verified"]:
            rows.append([{"text": f"{CROSS_ICON} Revoke Premium", "callback_data": f"adm_revoke_{uid}"}])
    rows.append(back("adm_users_0", "User Directory"))
    await edit_or_reply(update, card(f"{G['user']} USER PROFILE", lines, G["skull"]), kb(rows))

@owner_only
async def adm_grant(update, context):
    uid = int(update.callback_query.data.rsplit("_", 1)[-1])
    user = db.get_user(uid)
    if not user or is_owner(uid):
        return await safe_callback_answer(update.callback_query, "Cannot change this user.", show_alert=True)
    until = (local_now() + datetime.timedelta(days=PREMIUM_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
    db.update_plan(uid, "PAID", until)
    db.set_verified(uid, True)
    db.log(update.effective_user.id, "premium_grant", f"user={uid}")
    try:
        await context.bot.send_message(uid, card(f"{G['gem']} PREMIUM // GRANTED", [
            f"{G['check']} Premium was activated by the owner.",
            f"{G['clock']} Valid till {until[:16]}.",
            f"{G['bolt']} Your premium limits are now unlocked.",
        ]), parse_mode=ParseMode.HTML)
    except Exception as exc:
        await report_error(update, context, exc)
    await safe_callback_answer(update.callback_query, "Premium granted.")
    await adm_user_detail(update, context)

@owner_only
async def adm_revoke(update, context):
    uid = int(update.callback_query.data.rsplit("_", 1)[-1])
    user = db.get_user(uid)
    if not user or is_owner(uid):
        return await safe_callback_answer(update.callback_query, "Cannot change this user.", show_alert=True)
    db.update_plan(uid, "FREE")
    db.set_verified(uid, False)
    db.log(update.effective_user.id, "premium_revoke", f"user={uid}")
    try:
        await context.bot.send_message(uid, card(f"{G['cross']} PREMIUM // REVOKED", [
            f"Your premium access was revoked by the owner.",
            f"{G['misc']} You can upgrade again from the Premium screen.",
        ]), parse_mode=ParseMode.HTML)
    except Exception as exc:
        await report_error(update, context, exc)
    await safe_callback_answer(update.callback_query, "Premium revoked.")
    await adm_user_detail(update, context)

async def adm_pay(update, context):
    pend = db.pending_payments()
    if not pend:
        return await edit_or_reply(update, card(f"{G['mail']} DESK", [f"{G['ghost']} Nothing pending."]),
                                   kb([back("adm_home")]))
    p = pend[0]
    target = db.get_user(p["user_id"])
    lines = [
        f"{G['user']} {target['first_name'] if target else '?'} · <code>{p['user_id']}</code>",
        f"{G['tag']} {CURRENCY_SYMBOL}{p['amount']}",
        f"{G['misc']} {p['utr_or_proof'][:80]}",
        f"{G['clock']} {str(p['submitted_at'])[:16]}",
        "",
        f"{G['dot']} {len(pend)} in queue",
    ]
    rows = [
        [{"text": f"{G['check']} Approve", "callback_data": f"adm_ok_{p['id']}"},
         {"text": f"{G['cross']} Reject", "callback_data": f"adm_no_{p['id']}"}],
        [{"text": f"{G['arrow']} Skip", "callback_data": "adm_pay"}],
        back("adm_home"),
    ]
    await edit_or_reply(update, card(f"{G['mail']} PAYMENT #{p['id']}", lines), kb(rows))

async def adm_ok(update, context):
    pid = int(update.callback_query.data.split("_")[-1])
    p = db.payment(pid)
    if not p:
        return await safe_callback_answer(update.callback_query, "Gone.")
    db.review_payment(pid, "approved", update.effective_user.id)
    until = (local_now() + datetime.timedelta(days=PREMIUM_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
    db.update_plan(p["user_id"], "PAID", until)
    db.set_verified(p["user_id"], True)
    db.log(update.effective_user.id, "pay_approve", f"user={p['user_id']}")
    try:
        await context.bot.send_message(p["user_id"], card(f"{G['gem']} PREMIUM // ACTIVATED", [
            f"{G['check']} Payment approved and account verified",
            f"{G['clock']} Valid till {until[:16]}",
            f"{G['bolt']} Your premium limits are now unlocked."]), parse_mode=ParseMode.HTML)
    except Exception as exc:
        await report_error(update, context, exc)
    await safe_callback_answer(update.callback_query, "Approved + verified.")
    await adm_pay(update, context)

async def adm_no(update, context):
    pid = int(update.callback_query.data.split("_")[-1])
    p = db.payment(pid)
    if p:
        db.review_payment(pid, "rejected", update.effective_user.id)
        db.log(update.effective_user.id, "pay_reject", f"user={p['user_id']}")
        try:
            await context.bot.send_message(p["user_id"], card(f"{G['cross']} PAYMENT UPDATE", [
                f"Your premium proof was not approved.",
                f"{G['pen']} Please send a clearer screenshot or valid UTR and try again.",
            ]), parse_mode=ParseMode.HTML)
        except Exception as exc:
            await report_error(update, context, exc)
    await safe_callback_answer(update.callback_query, "Rejected.")
    await adm_pay(update, context)

async def adm_ver(update, context):
    context.user_data["flow"] = "verify"
    await edit_or_reply(update, card(f"{G['check']} VERIFY", [
        f"{G['pen']} Send a user id or @username.",
        f"<i>Verifies and grants premium for {PREMIUM_DAYS} days.</i>",
    ]), kb([back("adm_home", "Cancel")]))

async def adm_ver_apply(update, context):
    target = await resolve_user(update, context, update.message.text)
    if not target:
        return
    until = (local_now() + datetime.timedelta(days=PREMIUM_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
    db.set_verified(target["user_id"], True)
    db.update_plan(target["user_id"], "PAID", until)
    db.log(update.effective_user.id, "verify", str(target["user_id"]))
    context.user_data["flow"] = None
    await update.message.reply_text(
        f"{G['check']} <b>{target['first_name']}</b> verified till {until[:16]}.",
        parse_mode=ParseMode.HTML)
    try:
        await context.bot.send_message(target["user_id"],
                                       f"{G['check']} <b>You are verified.</b>", parse_mode=ParseMode.HTML)
    except Exception:
        pass
    await adm_home(update, context)

async def resolve_user(update, context, raw):
    raw = raw.strip()
    if not raw:
        await update.message.reply_text(f"{G['cross']} Send a username or numeric user ID.")
        return None
    username = raw.lstrip("@").lower()
    target = None
    if username.isdigit():
        target = db.get_user(int(username))
    else:
        # Prefer users already known to the bot. This fixes lookups for users
        # whose username Telegram will not expose through get_chat.
        target = db.user_by_username(username)
        try:
            if not target:
                chat = await context.bot.get_chat("@" + username)
                if chat.type == "private":
                    db.ensure_user(chat.id, chat.username, chat.first_name)
                    target = db.get_user(chat.id)
        except Exception:
            pass
    if not target:
        await update.message.reply_text(
            f"{G['cross']} User not found. Try the exact @username or numeric user ID.\n"
            f"The user must have opened this bot once before username lookup can work."
        )
    return target

async def adm_bc(update, context):
    context.user_data["flow"] = "broadcast"
    await edit_or_reply(update, card(f"{G['bolt']} BROADCAST", [
        f"{G['pen']} Send the message to blast to every user.",
        f"<i>HTML allowed.</i>",
    ]), kb([back("adm_home", "Cancel")]))

async def adm_bc_send(update, context):
    context.user_data["flow"] = None
    ok = fail = 0
    for u in db.all_users():
        try:
            await context.bot.send_message(u["user_id"], update.message.text_html,
                                           parse_mode=ParseMode.HTML)
            ok += 1
        except Exception:
            fail += 1
        await asyncio.sleep(0.05)
    db.log(update.effective_user.id, "broadcast", f"{ok}/{fail}")
    await update.message.reply_text(card(f"{G['bolt']} BLAST DONE", [
        f"{G['check']} {ok} delivered", f"{G['cross']} {fail} blocked"]), parse_mode=ParseMode.HTML)
    await adm_home(update, context)

async def adm_logs(update, context):
    lines = []
    for row in db.recent_logs():
        lines.append(f"{G['dot']} <code>{row['user_id']}</code> · {row['action']} · {str(row['timestamp'])[11:16]}")
    await edit_or_reply(update, card(f"{G['eye']} ACTIVITY", lines or [f"{G['ghost']} Empty."]),
                        kb([back("adm_home")]))

async def adm_ops(update, context):
    ops = [u for u in db.staff() if u["user_id"] != OWNER_ID]
    lines = [f"{G['crown']} Owner · <code>{OWNER_ID}</code>", ""]
    for o in ops:
        lines.append(f"{G['shield']} {o['first_name']} · <code>{o['user_id']}</code>")
    rows = [[{"text": f"{G['plus']} Appoint", "callback_data": "adm_ops_add"}]]
    for o in ops:
        rows.append([{"text": f"{G['down']} Demote {o['first_name']}"[:60],
                      "callback_data": f"adm_ops_rm_{o['user_id']}"}])
    rows.append(back("adm_home"))
    await edit_or_reply(update, card(f"{G['crown']} OPERATORS", lines, G["skull"]), kb(rows))

async def adm_ops_add(update, context):
    context.user_data["flow"] = "add_op"
    await edit_or_reply(update, card(f"{G['plus']} APPOINT", [
        f"{G['pen']} Send a user id or @username.",
        f"<i>Admins get premium limits and the staff deck.</i>",
    ]), kb([back("adm_ops", "Cancel")]))

async def adm_ops_add_apply(update, context):
    target = await resolve_user(update, context, update.message.text)
    if not target:
        return
    db.set_role(target["user_id"], "admin")
    db.log(update.effective_user.id, "appoint", str(target["user_id"]))
    context.user_data["flow"] = None
    await update.message.reply_text(f"{G['shield']} <b>{target['first_name']}</b> appointed.",
                                    parse_mode=ParseMode.HTML)
    try:
        await context.bot.send_message(target["user_id"],
                                       card(f"{G['shield']} OPERATOR STATUS", [
                                           f"{G['check']} You have been promoted to operator.",
                                           f"{G['bolt']} Staff tools and premium limits are now active.",
                                       ]),
                                       parse_mode=ParseMode.HTML)
    except Exception as exc:
        await report_error(update, context, exc)
    await notify_owner(context, card(f"{G['shield']} OPERATOR PROMOTED", [
        f"{target['first_name'] or 'Member'} · <code>{target['user_id']}</code>",
        f"by <code>{update.effective_user.id}</code>",
    ]), parse_mode=ParseMode.HTML)
    await adm_ops(update, context)

async def adm_ops_rm(update, context):
    uid = int(update.callback_query.data.split("_")[-1])
    target = db.get_user(uid)
    db.set_role(uid, "user")
    db.log(update.effective_user.id, "demote", str(uid))
    await safe_callback_answer(update.callback_query, "Demoted.")
    if target:
        try:
            await context.bot.send_message(uid, card(f"{G['down']} OPERATOR STATUS", [
                f"Your operator access has been removed by the owner.",
                f"{G['misc']} Your regular member access remains available.",
            ]), parse_mode=ParseMode.HTML)
        except Exception as exc:
            await report_error(update, context, exc)
        await notify_owner(context, card(f"{G['down']} OPERATOR DEMOTED", [
            f"{target['first_name'] or 'Member'} · <code>{uid}</code>",
            f"by <code>{update.effective_user.id}</code>",
        ]), parse_mode=ParseMode.HTML)
    await adm_ops(update, context)

async def adm_sw(update, context):
    mode = os.getenv("MAINTENANCE_MODE", "false").lower() == "true"
    rows = [
        [{"text": f"{G['gear']} Toggle Maintenance", "callback_data": "adm_sw_maint"}],
        back("adm_home"),
    ]
    await edit_or_reply(update, card(f"{G['gear']} SWITCHES", [
        f"{G['misc']} Maintenance · <b>{'ON' if mode else 'OFF'}</b>",
        f"<i>Env flag driven; restart applies.</i>"]), kb(rows))

# -----------------------------------------------------------------------------
# 16. ROUTERS
# -----------------------------------------------------------------------------

@check_auth
async def start(update, context):
    await show_dashboard(update, context)

@check_auth
async def cmd_id(update, context):
    u = update.effective_user
    row = db.get_user(u.id)
    await update.message.reply_text(
        f"{G['tag']} <code>{u.id}</code>\n{G['shield']} {rank_name(row)} {badge(row)}",
        parse_mode=ParseMode.HTML)

@check_auth
async def cmd_packs(update, context):
    await m_react(update, context)

@check_auth
async def cmd_pack_add(update, context):
    if not is_owner(update.effective_user.id):
        return await update.message.reply_text(f"{G['cross']} Owner only.")
    if len(context.args) < 2:
        return await update.message.reply_text(
            f"{G['misc']} Usage: <code>/pack_add name 😀 🔥 ❤️</code>",
            parse_mode=ParseMode.HTML,
        )
    name = context.args[0].lower()
    emojis = list(dict.fromkeys(context.args[1:]))
    if name == "default" or not re.fullmatch(r"[a-z0-9_-]{1,20}", name):
        return await update.message.reply_text(
            f"{G['cross']} Pack names may contain only a-z, 0-9, _ and -, up to 20 characters."
        )
    if len(emojis) > 30:
        return await update.message.reply_text(f"{G['cross']} Use up to 30 emojis per pack.")
    if db.add_reaction_pack(name, emojis, update.effective_user.id):
        db.log(update.effective_user.id, "pack_add", name)
        await update.message.reply_text(
            f"{G['check']} <b>{name}</b> added · {' '.join(emojis)}",
            parse_mode=ParseMode.HTML,
        )
    else:
        await update.message.reply_text(f"{G['cross']} A pack named <b>{name}</b> already exists.",
                                        parse_mode=ParseMode.HTML)

@check_auth
async def cmd_pack_remove(update, context):
    if not is_owner(update.effective_user.id):
        return await update.message.reply_text(f"{G['cross']} Owner only.")
    if len(context.args) != 1:
        return await update.message.reply_text(f"{G['misc']} Usage: /pack_remove name")
    name = context.args[0].lower()
    if db.remove_reaction_pack(name):
        db.log(update.effective_user.id, "pack_remove", name)
        return await update.message.reply_text(f"{G['check']} Pack <b>{name}</b> removed.",
                                                parse_mode=ParseMode.HTML)
    await update.message.reply_text(f"{G['cross']} Pack not found or the default pack cannot be removed.")

@check_auth
async def cmd_pack_update(update, context):
    if not is_owner(update.effective_user.id):
        return await update.message.reply_text(f"{G['cross']} Owner only.")
    if len(context.args) < 2:
        return await update.message.reply_text(
            f"{G['misc']} Usage: <code>/pack_update name 😀 🔥 ❤️</code>",
            parse_mode=ParseMode.HTML,
        )
    name = context.args[0].lower()
    emojis = list(dict.fromkeys(context.args[1:]))
    if name == "default" or not re.fullmatch(r"[a-z0-9_-]{1,20}", name):
        return await update.message.reply_text(f"{G['cross']} Invalid pack name.")
    if len(emojis) > 30:
        return await update.message.reply_text(f"{G['cross']} Use up to 30 emojis per pack.")
    if db.update_reaction_pack(name, emojis, update.effective_user.id):
        db.log(update.effective_user.id, "pack_update", name)
        return await update.message.reply_text(
            f"{G['check']} <b>{name}</b> updated · {' '.join(emojis)}",
            parse_mode=ParseMode.HTML,
        )
    await update.message.reply_text(f"{G['cross']} Pack not found. Use /pack_add first.")

@check_auth
async def cmd_shortcut(update, context):
    """Open a console section directly from a compact Telegram command."""
    command = update.message.text.split()[0].split("@", 1)[0].lower()
    shortcuts = {
        "/channels": m_channels,
        "/compose": m_compose,
        "/queue": m_queue,
        "/buttons": m_btn,
        "/forward": m_fwd,
        "/react": m_react,
        "/stats": m_stats,
        "/settings": m_settings,
        "/upgrade": m_up,
        "/packs": cmd_packs,
        "/help": m_help,
    }
    if command == "/panel":
        if is_staff(db.get_user(update.effective_user.id)):
            return await adm_home(update, context)
        return await update.message.reply_text(
            f"{G['cross']} Staff panel access is restricted to the owner and operators."
        )
    handler = shortcuts.get(command)
    if handler:
        return await handler(update, context)

async def cmd_cancel(update, context):
    context.user_data.pop("flow", None)
    context.user_data.pop("draft", None)
    await update.message.reply_text(f"{G['cross']} Aborted.")
    await show_dashboard(update, context)

@check_auth
async def router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    d = q.data
    if d.startswith("adm_") and not is_staff(db.get_user(update.effective_user.id)):
        await safe_callback_answer(q, "⛔ Staff only.", show_alert=True)
        return
    try:
        await safe_callback_answer(q)
        if d == "dashboard": await show_dashboard(update, context)
        elif d == "m_chan": await m_channels(update, context)
        elif d == "ch_add": await ch_add_prompt(update, context)
        elif d.startswith("ch_del_"):
            db.remove_channel(update.effective_user.id, int(d.split("_")[-1])); await m_channels(update, context)
        elif d == "m_post": await m_compose(update, context)
        elif d.startswith("p_text") or d.startswith("p_media"): await p_type(update, context)
        elif d == "p_btn": await p_btn_prompt(update, context)
        elif d == "p_dest": await p_dest(update, context)
        elif d.startswith("p_tog_"): await p_toggle(update, context)
        elif d == "p_go": await p_go(update, context)
        elif d == "p_sched": await p_sched_prompt(update, context)
        elif d == "m_sched": await m_queue(update, context)
        elif d.startswith("q_del_"): await q_del(update, context)
        elif d == "m_btn": await m_btn(update, context)
        elif d.startswith("b_pick_"): await b_pick(update, context)
        elif d == "b_set": await b_set_prompt(update, context)
        elif d == "b_text": await b_text_prompt(update, context)
        elif d == "b_kill": await b_kill(update, context)
        elif d == "m_fwd": await m_fwd(update, context)
        elif d == "f_add": await f_add_prompt(update, context)
        elif d == "f_rule": await f_rule_prompt(update, context)
        elif d.startswith("f_src_"): await f_rule_source(update, context)
        elif d.startswith("f_dst_"): await f_rule_dest(update, context)
        elif d == "f_save": await f_rule_save(update, context)
        elif d == "m_react": await m_react(update, context)
        elif d == "r_tog": await r_toggle(update, context)
        elif d.startswith("r_set_"): await r_set(update, context)
        elif d == "m_stats": await m_stats(update, context)
        elif d == "m_set": await m_settings(update, context)
        elif d == "m_help": await m_help(update, context)
        elif d == "m_up": await m_up(update, context)
        elif d == "pay_go": await pay_prompt(update, context)
        elif d == "adm_home": await adm_home(update, context)
        elif d.startswith("adm_users_"): await adm_users(update, context)
        elif d.startswith("adm_user_"): await adm_user_detail(update, context)
        elif d.startswith("adm_grant_"): await adm_grant(update, context)
        elif d.startswith("adm_revoke_"): await adm_revoke(update, context)
        elif d == "adm_pay": await adm_pay(update, context)
        elif d.startswith("adm_ok_"): await adm_ok(update, context)
        elif d.startswith("adm_no_"): await adm_no(update, context)
        elif d == "adm_ver": await adm_ver(update, context)
        elif d == "adm_bc": await adm_bc(update, context)
        elif d == "adm_logs": await adm_logs(update, context)
        elif d == "adm_ops": await adm_ops(update, context)
        elif d == "adm_ops_add": await adm_ops_add(update, context)
        elif d.startswith("adm_ops_rm_"): await adm_ops_rm(update, context)
        elif d == "adm_sw": await adm_sw(update, context)
        elif d == "adm_sw_maint": await safe_callback_answer(
            q, "Set MAINTENANCE_MODE in .env and restart.", show_alert=True)
        else: await safe_callback_answer(q, "Unknown node.")
    except Exception as e:
        logger.error("callback handler failed", exc_info=(type(e), e, e.__traceback__))
        await report_error(update, context, e)
        try:
            await q.message.reply_text(
                f"{G['cross']} Something went wrong. The owner has been notified."
            )
        except Exception:
            pass

async def msg_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.channel_post:
        return
    flow = context.user_data.get("flow")
    msg = update.message
    if flow == "ch_add": return await ch_add_process(update, context)
    if flow == "post_content": return await post_content(update, context)
    if flow == "post_media": return await post_media(update, context)
    if flow == "post_btn": return await p_btn_apply(update, context)
    if flow == "post_time": return await post_time(update, context)
    if flow == "btn_ref": return await b_ref(update, context)
    if flow == "btn_lines": return await b_set_apply(update, context)
    if flow == "btn_newtext": return await b_text_apply(update, context)
    if flow == "f_source": return await f_add_apply(update, context)
    if flow == "f_keywords": return await f_rule_keywords(update, context)
    if flow == "pay_proof": return await pay_submit(update, context)
    if flow == "verify": return await adm_ver_apply(update, context)
    if flow == "add_op": return await adm_ops_add_apply(update, context)
    if flow == "broadcast": return await adm_bc_send(update, context)

async def cmd_skip(update, context):
    if context.user_data.get("flow") == "post_media":
        context.user_data["draft"]["content"] = ""
        return await ask_buttons(update, context)
    await msg_router(update, context)

# -----------------------------------------------------------------------------
# 17. ENTRY
# -----------------------------------------------------------------------------

async def set_bot_commands(app):
    """Populate Telegram's command menu so users can use the shortcuts easily."""
    try:
        await app.bot.set_my_commands([
            BotCommand("start", "Open the F4 console"),
            BotCommand("channels", "Manage connected channels"),
            BotCommand("compose", "Create a post"),
            BotCommand("queue", "View scheduled posts"),
            BotCommand("buttons", "Edit message buttons"),
            BotCommand("forward", "Manage forwarding rules"),
            BotCommand("react", "Configure auto-reactions"),
            BotCommand("stats", "View your usage"),
            BotCommand("settings", "View account settings"),
            BotCommand("upgrade", "View premium options"),
            BotCommand("packs", "View reaction packs"),
            BotCommand("help", "Show help and shortcuts"),
            BotCommand("id", "Show your Telegram ID"),
            BotCommand("cancel", "Cancel the active flow"),
        ])
    except Exception as exc:
        logger.warning("could not update Telegram command menu: %s", exc)

def validate_config():
    """Validate required settings before opening a Telegram polling session."""
    missing = []
    if not BOT_TOKEN:
        missing.append("BOT_TOKEN")
    if OWNER_ID <= 0:
        missing.append("OWNER_ID")
    if missing:
        raise SystemExit(
            "Missing or invalid configuration: " + ", ".join(missing) +
            ". Copy .env.example to .env and fill in the values."
        )

def main():
    if "--check-config" in sys.argv:
        validate_config()
        print(f"Configuration OK · database={DATABASE_PATH} · timezone={TIMEZONE_STR}")
        return

    validate_config()

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .connect_timeout(30)
        .read_timeout(45)
        .write_timeout(45)
        .pool_timeout(30)
        .post_init(set_bot_commands)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("dashboard", start))
    app.add_handler(CommandHandler("id", cmd_id))
    app.add_handler(CommandHandler(
        ["panel", "channels", "compose", "queue", "buttons", "forward", "react",
         "stats", "settings", "upgrade", "packs", "help"],
        cmd_shortcut,
    ))
    app.add_handler(CommandHandler("pack_add", cmd_pack_add))
    app.add_handler(CommandHandler("pack_remove", cmd_pack_remove))
    app.add_handler(CommandHandler("pack_update", cmd_pack_update))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CommandHandler("skip", cmd_skip))

    app.add_handler(MessageHandler(filters.ChatType.CHANNEL, on_channel_post))
    app.add_handler(MessageHandler(
        filters.ChatType.GROUPS & (filters.TEXT | filters.PHOTO | filters.VIDEO) & ~filters.COMMAND,
        on_group_message,
    ))
    app.add_handler(CallbackQueryHandler(router))
    app.add_handler(MessageHandler((filters.TEXT | filters.PHOTO | filters.VIDEO) & ~filters.COMMAND, msg_router))
    app.add_error_handler(application_error_handler)

    sched = AsyncIOScheduler(timezone=APP_TIMEZONE)
    sched.add_job(scheduler_tick, "interval", minutes=1, args=[app])
    sched.start()

    logger.info("F4 v2 online")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
