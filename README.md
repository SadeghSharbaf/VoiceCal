# VoiceCal V1.6.2.2 — Persian whisper.cpp → Google Calendar

VoiceCal روی لپ‌تاپ اجرا می‌شود، Voice یا متن Telegram را می‌گیرد، Voice را **کاملاً لوکال** به متن تبدیل می‌کند، فیلدهای Event را استخراج می‌کند، Preview می‌دهد و فقط بعد از تأیید شما Event را در Google Calendar می‌سازد.

در V1.6.2 موتور Speech-to-Text عوض شده است:

```text
faster-whisper عمومی
        ↓ حذف شد
whisper.cpp + Persian fine-tuned Whisper Base
```

مدل پیش‌فرض `ggml-base-fa.bin` حدود **148MB** است؛ بنابراین دیگر دانلود 1.6GB مدل Turbo/Large لازم نیست و CUDA/cuDNN هم لازم نیست.

## معماری V1.6.2

```text
Telegram Voice
      ↓
whisper.cpp (local CPU)
      ↓
Persian fine-tuned ggml-base-fa.bin
      ↓
ASR correction (فقط خطاهای کوچک)
      ↓
Anchor Slot Extractor
      ↓
موضوع / تاریخ / ساعت / مدت / یادآور
      ↓
فقط فیلدهای نامفهوم → دکمه/سؤال
      ↓
Preview قابل ویرایش
      ↓
✅ Confirm
      ↓
Google Calendar
```

قالب پیشنهادی Voice:

```text
موضوع طراحی اپلیکیشن، تاریخ سی شهریور، ساعت پانزده، مدت یک ساعت، یادآور ده دقیقه قبل
```

ترتیب بخش‌ها اجباری نیست. اگر فقط یک بخش فهمیده نشود، فقط همان بخش دوباره پرسیده می‌شود.

## چرا V1.6.2؟

مدل‌های عمومی Small/Medium روی بعضی Voiceهای فارسی محاوره‌ای خروجی ضعیفی داشتند. V1.6.2 از یک Whisper Base که روی فارسی fine-tune شده استفاده می‌کند. هدف این نسخه این است که اول **دقت فارسی روی صدای واقعی شما** را تست کنیم، نه اینکه صرفاً مدل عمومی بزرگ‌تر و سنگین‌تر کنیم.

## نصب روی Windows

پیشنهاد: Python 3.11 یا 3.12.

اگر نسخه جدید را از صفر نصب می‌کنید فقط اجرا کنید:

```text
setup_windows.bat
```

این کار:

1. `.venv` می‌سازد.
2. پکیج‌های Python را نصب می‌کند.
3. نسخه Windows x64 از `whisper.cpp` را دانلود می‌کند.
4. مدل فارسی `ggml-base-fa.bin` را در `models\` دانلود می‌کند (~148MB).

دانلود مدل **resume** می‌شود. اگر اینترنت قطع شد، دوباره `setup_stt_windows.bat` را اجرا کنید.

### اگر از V1.5 ارتقا می‌دهید

از پروژه قبلی این‌ها را کپی کنید:

```text
.env
credentials.json
data\
```

سپس فقط یک بار اجرا کنید:

```text
setup_windows.bat
```

یا اگر `.venv` را از قبل دارید:

```text
setup_stt_windows.bat
```

متغیرهای قدیمی زیر در V1.6.2 دیگر استفاده نمی‌شوند و اگر داخل `.env` بمانند مشکلی ایجاد نمی‌کنند:

```env
WHISPER_MODEL=medium
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
WHISPER_QUALITY=high
```

## تنظیمات STT جدید

Defaults کافی هستند؛ اگر خواستید داخل `.env` اضافه کنید:

```env
WHISPER_CPP_EXE=tools/whispercpp/whisper-cli.exe
WHISPER_CPP_MODEL=models/ggml-base-fa.bin
WHISPER_CPP_THREADS=4
WHISPER_CPP_BEAM_SIZE=5
WHISPER_CPP_BEST_OF=5
```

روی TUF با 16GB RAM، 4 thread برای شروع انتخاب محافظه‌کارانه‌ای است. این نسخه CPU است و RTX/CUDA را درگیر نمی‌کند.

## Telegram

در `.env`:

```env
TELEGRAM_BOT_TOKEN=...
ALLOWED_TELEGRAM_USER_ID=...
```

بعد از اولین `/whoami` بهتر است `ALLOWED_TELEGRAM_USER_ID` را تنظیم کنید تا Bot شخصی بماند.

## Google Calendar

همان فایل‌های نسخه قبلی قابل استفاده هستند:

```text
credentials.json
data/google_token.json
```

اگر OAuth قبلاً انجام شده، نیازی به اتصال دوباره نیست. در غیر این صورت:

```text
connect_google.bat
```

## اجرا

```text
run.bat
```

در startup باید چیزی شبیه این ببینید:

```text
Checking whisper.cpp Persian STT: ...
whisper.cpp Persian STT is ready.
Application started
```

سپس در Telegram یک Voice بفرستید.

## رفتار فیلدهای ناقص

اگر ساعت را نفهمد، کل 24 ساعت عددی نمایش داده می‌شود:

```text
00:00  01:00  02:00  03:00
...
20:00  21:00  22:00  23:00
```

مدت و Reminder هم دکمه‌های سریع دارند. Preview نهایی قابل ویرایش است:

```text
[✅ تأیید] [❌ لغو]
[✏️ عنوان] [📅 تاریخ] [🕒 ساعت]
[⏱ مدت] [🔔 یادآور]
```

## تست پیشنهادی

این جمله را با Voice بگویید:

```text
موضوع طراحی اپلیکیشن، تاریخ سی شهریور، ساعت پانزده، مدت یک ساعت، یادآور ده دقیقه قبل
```

اول خروجی `📝 متن تشخیص‌داده‌شده` را بررسی کنید. این تست مشخص می‌کند مدل فارسی V1.6.2 نسبت به مدل‌های عمومی قبلی روی صدای شما چقدر بهتر است.

## نکات فنی

- Speech-to-Text API پولی ندارد.
- WordPress/VPS لازم نیست.
- `whisper.cpp` از OGG پشتیبانی می‌کند، بنابراین Voice تلگرام مستقیم به CLI داده می‌شود.
- مدل و executable بعد از setup کاملاً local هستند.
- V1.6.2 برای سادگی از CLI استفاده می‌کند؛ مدل Base کوچک است. اگر بعداً بخواهیم latency شروع هر Voice را کمتر کنیم، می‌توانیم `whisper-server` محلی را persistent اجرا کنیم و مدل را دائماً در RAM نگه داریم.

## تست‌های پروژه

```text
pytest -q
```

## امنیت

- `.env`، `credentials.json` و `data/google_token.json` را آپلود عمومی نکنید.
- Telegram Bot Token را مثل پسورد در نظر بگیرید.
- اگر Token در log یا چت منتشر شد، از BotFather آن را revoke و Token جدید بسازید.


## V1.6.2.2 fix

Windows STT setup no longer uses the fragile inline PowerShell release parser. The whisper.cpp Windows binary is now discovered and downloaded by `scripts/download_whispercpp.py`, avoiding the `Unexpected token ^` error.


## V1.6.2 audio-pipeline fix
Telegram voice notes are OGG/Opus. VoiceCal now decodes every voice locally with PyAV into 16 kHz mono PCM16 WAV before invoking whisper.cpp. This removes ambiguity around direct OGG support in Windows builds. Transcription is also read from whisper.cpp's UTF-8 text output file, and empty output now raises a diagnostic error instead of silently looking like bad recognition.
