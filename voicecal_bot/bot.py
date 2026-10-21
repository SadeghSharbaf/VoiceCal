from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .asr_corrector import correct_calendar_asr
from .calendar_service import GoogleAuthRequired, GoogleCalendarService
from .config import Settings
from .formatting import format_preview
from .models import EventDraft
from .parser import EventParser
from .storage import Storage
from .stt import WhisperCppSTT
from .slot_extractor import AnchorSlotExtractor

logger = logging.getLogger(__name__)


class VoiceCalBot:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.storage = Storage(settings.database_file)
        self.parser = EventParser(
            timezone=settings.timezone,
            default_duration_minutes=settings.default_event_duration_minutes,
            default_reminder_minutes=settings.default_reminder_minutes,
        )
        self.command_parser = AnchorSlotExtractor(self.parser)
        self.stt = WhisperCppSTT(
            settings.whisper_cpp_exe,
            settings.whisper_cpp_model,
            settings.whisper_cpp_threads,
            settings.whisper_cpp_beam_size,
            settings.whisper_cpp_best_of,
        )
        self.calendar = GoogleCalendarService(
            settings.google_token_file, settings.google_calendar_id
        )

    def build_application(self) -> Application:
        app = (
            Application.builder()
            .token(self.settings.telegram_bot_token)
            .post_init(self.post_init)
            .build()
        )
        app.add_handler(CommandHandler("start", self.start))
        app.add_handler(CommandHandler("help", self.help_command))
        app.add_handler(CommandHandler("whoami", self.whoami))
        app.add_handler(CommandHandler("calendar", self.calendar_status))
        app.add_handler(CommandHandler("cancel", self.cancel_command))
        app.add_handler(CallbackQueryHandler(self.callback_query))
        app.add_handler(MessageHandler(filters.VOICE, self.voice_message))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.text_message))
        app.add_error_handler(self.error_handler)
        return app

    async def post_init(self, application: Application) -> None:
        await application.bot.set_my_commands(
            [
                BotCommand("start", "شروع"),
                BotCommand("calendar", "وضعیت اتصال Google Calendar"),
                BotCommand("cancel", "لغو رویداد در حال ساخت"),
                BotCommand("whoami", "نمایش Telegram User ID"),
                BotCommand("help", "راهنما"),
            ]
        )
        logger.info(
            "Checking whisper.cpp Persian STT: exe=%s model=%s threads=%s ...",
            self.settings.whisper_cpp_exe,
            self.settings.whisper_cpp_model,
            self.settings.whisper_cpp_threads,
        )
        await asyncio.to_thread(self.stt.load)
        logger.info("whisper.cpp Persian STT is ready.")

    def _authorized(self, update: Update) -> bool:
        user = update.effective_user
        if not user:
            return False
        allowed = self.settings.allowed_telegram_user_id
        return allowed is None or user.id == allowed

    async def _reject_if_unauthorized(self, update: Update) -> bool:
        if self._authorized(update):
            return False
        if update.effective_message:
            await update.effective_message.reply_text("⛔ این ربات شخصی است.")
        return True

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._reject_if_unauthorized(update):
            return
        await update.effective_message.reply_text(
            "سلام 👋\n"
            "V1.6 از مدل فارسی سبک whisper.cpp استفاده می‌کند. بهتره این قالب رو بگی:\n\n"
            "موضوع ... تاریخ ... ساعت ... مدت ... یادآور ...\n\n"
            "مثال:\n"
            "«موضوع رسیدگی به پروژه‌ها، تاریخ 28 شهریور، ساعت 6 عصر، مدت یک ساعت، یادآور 5 دقیقه قبل»\n\n"
            "ترتیب بخش‌ها اجباری نیست. هر بخشی را نفهمم فقط همان بخش را می‌پرسم؛ قبل از ثبت هم پیش‌نمایش می‌فرستم."
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._reject_if_unauthorized(update):
            return
        await update.effective_message.reply_text(
            "فرمت پیشنهادی V1.6:\n"
            "موضوع ... | تاریخ ... | ساعت ... | مدت ... | یادآور ...\n\n"
            "• تاریخ: فردا، پس‌فردا، شنبه، 28 شهریور، 19 سپتامبر\n"
            "• ساعت: 18، 6 عصر، شش و نیم\n"
            "• مدت: یک ساعت / 90 دقیقه\n"
            "• یادآور: 5 دقیقه قبل / یک ساعت قبل\n\n"
            "کلمات موضوع/تاریخ/ساعت/مدت/یادآور مرز هر بخش را مشخص می‌کنند. اگر یک بخش خراب شنیده شود، فقط همان بخش را با دکمه یا پیام بعدی تکمیل می‌کنیم."
        )

    async def whoami(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        if user:
            await update.effective_message.reply_text(f"Telegram User ID: {user.id}")

    async def calendar_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._reject_if_unauthorized(update):
            return
        connected = await asyncio.to_thread(self.calendar.is_connected)
        if connected:
            await update.effective_message.reply_text("✅ Google Calendar متصل است.")
        else:
            await update.effective_message.reply_text(
                "❌ Google Calendar هنوز متصل نیست.\n"
                "روی لپ‌تاپ اجرا کن:\n"
                "python -m voicecal_bot.google_auth"
            )

    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._reject_if_unauthorized(update):
            return
        user_id = update.effective_user.id
        if self.storage.cancel_active(user_id):
            await update.effective_message.reply_text("❌ رویداد در حال ساخت لغو شد.")
        else:
            await update.effective_message.reply_text("رویداد فعالی برای لغو وجود ندارد.")

    async def text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._reject_if_unauthorized(update):
            return
        await self._process_text(update, update.effective_message.text)

    async def voice_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._reject_if_unauthorized(update):
            return
        voice = update.effective_message.voice
        duration = voice.duration.total_seconds() if isinstance(voice.duration, timedelta) else voice.duration
        if duration > self.settings.max_voice_seconds:
            await update.effective_message.reply_text(
                f"ویس خیلی طولانی است. فعلاً حداکثر {self.settings.max_voice_seconds} ثانیه بفرست."
            )
            return

        status = await update.effective_message.reply_text("🎙 دارم ویس را روی لپ‌تاپ تبدیل به متن می‌کنم…")
        temp_path: Path | None = None
        try:
            tg_file = await voice.get_file()
            fd, raw_path = tempfile.mkstemp(suffix=".ogg")
            os.close(fd)
            temp_path = Path(raw_path)
            await tg_file.download_to_drive(custom_path=temp_path)
            raw_text = await asyncio.to_thread(self.stt.transcribe, temp_path)
            if not raw_text:
                await status.edit_text("متوجه ویس نشدم. یک بار کوتاه‌تر و واضح‌تر بفرست.")
                return
            text = correct_calendar_asr(raw_text)
            if text != raw_text.strip():
                await status.edit_text(
                    f"📝 متن خام:\n{raw_text.strip()}\n\n"
                    f"✨ اصلاح تقویمی:\n{text}"
                )
            else:
                await status.edit_text(f"📝 متن تشخیص‌داده‌شده:\n{text}")
            await self._process_text(update, text)
        except Exception:
            logger.exception("Voice processing failed")
            await status.edit_text("در پردازش ویس خطا پیش آمد. لاگ برنامه را روی لپ‌تاپ بررسی کن.")
        finally:
            if temp_path:
                temp_path.unlink(missing_ok=True)

    async def _process_text(self, update: Update, text: str) -> None:
        user_id = update.effective_user.id
        now = datetime.now(self.settings.tz)
        active = self.storage.get_active_draft(user_id)

        if active:
            if active["pending_field"]:
                draft: EventDraft = active["draft"]
                field = active["pending_field"]
                ok = self.parser.patch_missing(draft, field, text, now)
                if not ok:
                    await self._ask_missing(update, active["id"], draft, field, retry=True)
                    return
                draft.resolve_pending(field)
                next_field = draft.next_missing_field()
                self.storage.update_draft(active["id"], draft, next_field)
                if next_field:
                    await self._ask_missing(update, active["id"], draft, next_field)
                else:
                    await self._show_preview(update, active["id"], draft)
                return

            await update.effective_message.reply_text(
                "یک رویداد در انتظار تأیید داری. اول ✅ تأیید یا ❌ لغوش کن؛ یا /cancel بزن."
            )
            return

        result = self.command_parser.parse(text, now)
        draft = result.draft
        pending = draft.next_missing_field()
        if result.anchors:
            logger.info(
                "Voice protocol anchors=%s slots=%s pending=%s",
                result.anchors,
                result.slot_text,
                result.pending_fields,
            )
        draft_id = self.storage.save_new_draft(user_id, draft, pending)
        if pending:
            await self._ask_missing(update, draft_id, draft, pending)
        else:
            await self._show_preview(update, draft_id, draft)

    def _preview_markup(self, draft_id: int) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("✅ تأیید", callback_data=f"confirm:{draft_id}"),
                    InlineKeyboardButton("❌ لغو", callback_data=f"cancel:{draft_id}"),
                ],
                [
                    InlineKeyboardButton("✏️ عنوان", callback_data=f"edit:{draft_id}:title"),
                    InlineKeyboardButton("📅 تاریخ", callback_data=f"edit:{draft_id}:date"),
                    InlineKeyboardButton("🕒 ساعت", callback_data=f"edit:{draft_id}:start_time"),
                ],
                [
                    InlineKeyboardButton("⏱ مدت", callback_data=f"edit:{draft_id}:duration"),
                    InlineKeyboardButton("🔔 یادآور", callback_data=f"edit:{draft_id}:reminder"),
                ],
            ]
        )

    def _all_hours_markup(self, draft_id: int) -> InlineKeyboardMarkup:
        buttons = [
            InlineKeyboardButton(
                f"{hour:02d}:00", callback_data=f"time:{draft_id}:{hour:02d}00"
            )
            for hour in range(24)
        ]
        return InlineKeyboardMarkup([buttons[i : i + 4] for i in range(0, 24, 4)])

    def _duration_markup(self, draft_id: int) -> InlineKeyboardMarkup:
        values = [15, 30, 45, 60, 90, 120, 180, 240]
        labels = {60: "1 ساعت", 90: "1:30", 120: "2 ساعت", 180: "3 ساعت", 240: "4 ساعت"}
        buttons = [
            InlineKeyboardButton(
                labels.get(value, f"{value} دقیقه"),
                callback_data=f"duration:{draft_id}:{value}",
            )
            for value in values
        ]
        return InlineKeyboardMarkup([buttons[i : i + 3] for i in range(0, len(buttons), 3)])

    def _reminder_markup(self, draft_id: int) -> InlineKeyboardMarkup:
        values = [0, 5, 10, 15, 30, 60, 120]
        labels = {0: "بدون یادآور", 60: "1 ساعت قبل", 120: "2 ساعت قبل"}
        buttons = [
            InlineKeyboardButton(
                labels.get(value, f"{value} دقیقه قبل"),
                callback_data=f"reminder:{draft_id}:{value}",
            )
            for value in values
        ]
        return InlineKeyboardMarkup([buttons[i : i + 2] for i in range(0, len(buttons), 2)])

    async def _ask_missing(
        self,
        update: Update,
        draft_id: int,
        draft: EventDraft,
        field: str,
        retry: bool = False,
    ) -> None:
        prefix = "متوجه نشدم. " if retry else ""
        if field == "title":
            text = prefix + "موضوع رویداد چی باشد؟ عنوان را به صورت متن یا ویس بفرست."
            markup = None
        elif field == "date":
            text = prefix + "تاریخ رو انتخاب کن یا تاریخ دیگری را به صورت متن/ویس بفرست:"
            markup = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("امروز", callback_data=f"date:{draft_id}:today"),
                        InlineKeyboardButton("فردا", callback_data=f"date:{draft_id}:tomorrow"),
                        InlineKeyboardButton("پس‌فردا", callback_data=f"date:{draft_id}:dayafter"),
                    ]
                ]
            )
        elif field == "start_time":
            text = prefix + "ساعت شروع رو مستقیم از 00 تا 23 انتخاب کن. همه ساعت‌ها عددی‌اند:"
            markup = self._all_hours_markup(draft_id)
        elif field == "time_period":
            raw = draft.ambiguous_time or ""
            hour, minute = map(int, raw.split(":"))
            pm_hour = hour + 12 if 1 <= hour < 12 else hour
            am_hour = 0 if hour == 12 else hour
            text = prefix + "منظورت کدام ساعت است؟"
            markup = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            f"☀️ {am_hour:02d}:{minute:02d}",
                            callback_data=f"period:{draft_id}:am",
                        ),
                        InlineKeyboardButton(
                            f"🌙 {pm_hour:02d}:{minute:02d}",
                            callback_data=f"period:{draft_id}:pm",
                        ),
                    ]
                ]
            )
        elif field == "duration":
            text = prefix + "مدت رویداد رو انتخاب کن یا به صورت متن بفرست:"
            markup = self._duration_markup(draft_id)
        elif field == "reminder":
            text = prefix + "یادآور رو انتخاب کن یا به صورت متن بفرست:"
            markup = self._reminder_markup(draft_id)
        else:
            text, markup = prefix + "اطلاعات رویداد ناقص است.", None
        await update.effective_message.reply_text(text, reply_markup=markup)

    async def _show_preview(self, update: Update, draft_id: int, draft: EventDraft) -> None:
        await update.effective_message.reply_text(
            format_preview(draft), reply_markup=self._preview_markup(draft_id)
        )

    async def callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        if await self._reject_if_unauthorized(update):
            return

        parts = (query.data or "").split(":")
        if len(parts) < 2:
            return
        action = parts[0]
        try:
            draft_id = int(parts[1])
        except ValueError:
            return

        row = self.storage.get_draft(draft_id)
        if not row or row["user_id"] != update.effective_user.id:
            await query.edit_message_text("این درخواست دیگر معتبر نیست.")
            return
        if row["status"] != "active":
            await query.edit_message_text("این درخواست قبلاً پردازش شده است.")
            return

        draft: EventDraft = row["draft"]

        if action == "edit" and len(parts) == 3:
            field = parts[2]
            if field not in {"title", "date", "start_time", "duration", "reminder"}:
                return
            if field == "start_time":
                draft.ambiguous_time = None
            self.storage.update_draft(draft_id, draft, field)
            labels = {
                "title": "عنوان",
                "date": "تاریخ",
                "start_time": "ساعت شروع",
                "duration": "مدت",
                "reminder": "یادآور",
            }
            await query.edit_message_text(f"✏️ ویرایش {labels[field]}")
            await self._ask_missing(update, draft_id, draft, field)
            return

        if action == "date" and len(parts) == 3:
            if row["pending_field"] != "date":
                return
            now = datetime.now(self.settings.tz)
            offset = {"today": 0, "tomorrow": 1, "dayafter": 2}.get(parts[2])
            if offset is None:
                return
            draft.date_iso = (now.date() + timedelta(days=offset)).isoformat()
            draft.resolve_pending("date")
            next_field = draft.next_missing_field()
            self.storage.update_draft(draft_id, draft, next_field)
            if next_field:
                await query.edit_message_text("✅ تاریخ ثبت شد.")
                await self._ask_missing(update, draft_id, draft, next_field)
            else:
                await query.edit_message_text(
                    format_preview(draft), reply_markup=self._preview_markup(draft_id)
                )
            return

        if action == "time" and len(parts) == 3:
            if row["pending_field"] != "start_time":
                return
            hhmm = parts[2]
            if len(hhmm) != 4 or not hhmm.isdigit():
                return
            hour, minute = int(hhmm[:2]), int(hhmm[2:])
            if hour > 23 or minute > 59:
                return
            draft.start_time = f"{hour:02d}:{minute:02d}"
            draft.ambiguous_time = None
            draft.resolve_pending("start_time")
            next_field = draft.next_missing_field()
            self.storage.update_draft(draft_id, draft, next_field)
            if next_field:
                await query.edit_message_text("✅ ساعت ثبت شد.")
                await self._ask_missing(update, draft_id, draft, next_field)
            else:
                await query.edit_message_text(
                    format_preview(draft), reply_markup=self._preview_markup(draft_id)
                )
            return

        if action == "duration" and len(parts) == 3:
            if row["pending_field"] != "duration":
                return
            try:
                minutes = int(parts[2])
            except ValueError:
                return
            if minutes <= 0 or minutes > 24 * 60:
                return
            draft.duration_minutes = minutes
            draft.resolve_pending("duration")
            next_field = draft.next_missing_field()
            self.storage.update_draft(draft_id, draft, next_field)
            if next_field:
                await query.edit_message_text("✅ مدت ثبت شد.")
                await self._ask_missing(update, draft_id, draft, next_field)
            else:
                await query.edit_message_text(
                    format_preview(draft), reply_markup=self._preview_markup(draft_id)
                )
            return

        if action == "reminder" and len(parts) == 3:
            if row["pending_field"] != "reminder":
                return
            try:
                minutes = int(parts[2])
            except ValueError:
                return
            if minutes < 0 or minutes > 28 * 24 * 60:
                return
            draft.reminder_minutes = minutes
            draft.resolve_pending("reminder")
            next_field = draft.next_missing_field()
            self.storage.update_draft(draft_id, draft, next_field)
            if next_field:
                await query.edit_message_text("✅ یادآور ثبت شد.")
                await self._ask_missing(update, draft_id, draft, next_field)
            else:
                await query.edit_message_text(
                    format_preview(draft), reply_markup=self._preview_markup(draft_id)
                )
            return

        if action == "period" and len(parts) == 3:
            if row["pending_field"] != "time_period" or not draft.ambiguous_time:
                return
            hour, minute = map(int, draft.ambiguous_time.split(":"))
            if parts[2] == "pm" and 1 <= hour < 12:
                hour += 12
            elif parts[2] == "am" and hour == 12:
                hour = 0
            draft.start_time = f"{hour:02d}:{minute:02d}"
            draft.ambiguous_time = None
            draft.resolve_pending("time_period")
            next_field = draft.next_missing_field()
            self.storage.update_draft(draft_id, draft, next_field)
            if next_field:
                await query.edit_message_text("✅ زمان ثبت شد.")
                await self._ask_missing(update, draft_id, draft, next_field)
            else:
                await query.edit_message_text(
                    format_preview(draft), reply_markup=self._preview_markup(draft_id)
                )
            return

        if action == "cancel":
            self.storage.set_status(draft_id, "cancelled")
            await query.edit_message_text("❌ لغو شد؛ چیزی در Google Calendar ثبت نشد.")
            return

        if action == "confirm":
            if draft.next_missing_field():
                await query.edit_message_text("رویداد هنوز ناقص است. /cancel بزن و دوباره بفرست.")
                return
            try:
                event = await asyncio.to_thread(self.calendar.create_event, draft)
            except GoogleAuthRequired as exc:
                retry_markup = InlineKeyboardMarkup(
                    [[
                        InlineKeyboardButton("✅ تلاش دوباره", callback_data=f"confirm:{draft_id}"),
                        InlineKeyboardButton("❌ لغو", callback_data=f"cancel:{draft_id}"),
                    ]]
                )
                await query.edit_message_text(
                    "Google Calendar هنوز وصل نیست.\n\n"
                    "روی لپ‌تاپ اجرا کن:\n"
                    "python -m voicecal_bot.google_auth\n\n"
                    "بعد از اتصال، همین «تلاش دوباره» را بزن.",
                    reply_markup=retry_markup,
                )
                logger.warning(str(exc))
                return
            except Exception:
                logger.exception("Google Calendar event creation failed")
                retry_markup = InlineKeyboardMarkup(
                    [[
                        InlineKeyboardButton("🔄 تلاش دوباره", callback_data=f"confirm:{draft_id}"),
                        InlineKeyboardButton("❌ لغو", callback_data=f"cancel:{draft_id}"),
                    ]]
                )
                await query.edit_message_text(
                    "ثبت در Google Calendar خطا داد. درخواست را نگه داشتم؛ لاگ برنامه را بررسی کن و دوباره تلاش کن.",
                    reply_markup=retry_markup,
                )
                return

            self.storage.set_status(draft_id, "confirmed")
            self.storage.log_created_event(update.effective_user.id, event["id"], draft)
            link = event.get("htmlLink")
            text = "✅ در Google Calendar ثبت شد."
            if link:
                text += f"\n{link}"
            await query.edit_message_text(text)

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        logger.exception("Unhandled telegram error", exc_info=context.error)
