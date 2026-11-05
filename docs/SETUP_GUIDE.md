# Setup guide (Windows, macOS, Linux)

This guide assumes you have never set up a Python project before. Follow the steps in order.

## 1. Install the tools

1. **Python 3.10 or newer** from python.org. On Windows, tick *Add python.exe to PATH* in the installer.
   Check it worked: open a terminal and run `python --version` (on Windows you can also try `py --version`).
2. **Visual Studio Code** from code.visualstudio.com, then install the **Python** extension (Microsoft).
3. **Git** from git-scm.com (needed later for GitHub).

## 2. Open the project in VS Code

1. Unzip `noticenest.zip` somewhere easy, for example `Documents/noticenest`.
2. In VS Code: **File > Open Folder** and choose the `noticenest` folder (the one that contains `run.py`).
3. Open the built-in terminal: **Terminal > New Terminal**. All commands below are typed there.
   Always run commands from the project folder, the one that contains `run.py`.

## 3. Create a virtual environment

A virtual environment is a private box of Python libraries for this one project, so projects do not interfere with each other.

```bash
python -m venv .venv
```

Activate it:

| System | Command |
|---|---|
| Windows (PowerShell) | `.venv\Scripts\Activate.ps1` |
| Windows (Command Prompt) | `.venv\Scripts\activate.bat` |
| macOS / Linux | `source .venv/bin/activate` |

You should now see `(.venv)` at the start of the terminal line.
If PowerShell says scripts are disabled, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, then activate again.

Tell VS Code to use it: press `Ctrl+Shift+P`, type **Python: Select Interpreter**, and choose the one inside `.venv`.

## 4. Install the libraries

```bash
pip install -r requirements.txt
```

## 5. Create your settings file

```bash
# macOS / Linux
cp .env.example .env
# Windows
copy .env.example .env
```

You can leave everything as it is for now. `.env` holds secrets, so it is already listed in `.gitignore` and will **not** be uploaded to GitHub. Never remove it from that list.

## 6. Run the demo

```bash
python -m app.jobs.run_once
python run.py
```

The first command creates the database and loads 10 demo notices (it prints "console alerts" instead of sending real messages). The second starts the website. Open **http://127.0.0.1:5000** in your browser. Stop the server with `Ctrl+C`.

Things to try:

1. Click **Set up profile**, choose *BCA* and semester *3*. The dashboard now shows only notices that apply to you.
2. Open a notice and look at the **snippet** under each date, which is the exact sentence the date came from.
3. Look at **Circular regarding hostel allotment**. It says *May apply to you* because the notice does not say who it is for.
4. In a second terminal (activate the venv there too): `python tools/simulate_revision.py` then `python -m app.jobs.run_once`. Open **What changed**.
5. Put it back: `python tools/simulate_revision.py --undo`.
6. Click **Add my deadlines to my calendar** to download an `.ics` file.

To start over, stop the server and delete `data/noticenest.db` and `data/.demo_anchor`.

## 7. Run the tests and the evaluation

```bash
pytest
python -m eval.run_eval
```

## 8. Turn on the AI (optional)

Basic mode already works. The AI helps with messy notices.

1. Get a free API key: Google AI Studio (Gemini) or the Groq console. **Free limits and model names change often**, so read the provider's current page.
2. Edit `.env`:
   ```
   LLM_PROVIDER=gemini
   GEMINI_API_KEY=paste-your-key-here
   GEMINI_MODEL=gemini-flash-latest
   ```
   If you get a "model not found" error in the log, open the provider's model list and paste a current model name.
3. Run `python -m app.jobs.run_once --no-reminders`. Notices show *by AI* on the **Accuracy** page.
4. Compare: `python -m eval.run_eval --llm`.

Only the **public notice text** is sent to the AI. Do not paste personal data into notices or prompts.

## 9. Telegram reminders (optional)

1. In Telegram, chat with **@BotFather**, send `/newbot`, follow the steps, and copy the token into `.env` as `TELEGRAM_BOT_TOKEN=`.
2. Open your new bot in Telegram and press **Start** (or send "hi").
3. Run `python tools/get_telegram_chat_id.py`. It prints your chat ID.
4. Paste the chat ID into **My profile** on the website.

A bot can only message people who have started a chat with it first.

## 10. Email reminders (optional)

For Gmail: turn on 2-step verification, create an **App password** in your Google account security settings, and set in `.env`:

```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASSWORD=your-16-character-app-password
SMTP_FROM=you@gmail.com
```

Never use your normal password here.

## 11. Run it automatically (optional)

```bash
python -m app.jobs.scheduler --every-minutes 180
```

This runs the job every 3 hours while the terminal stays open. Alternatives: Windows Task Scheduler, cron on Linux/macOS, or a scheduled GitHub Actions workflow calling `python -m app.jobs.run_once`.

## 12. Optional OCR for scanned PDFs

Scanned notices are only pictures. To read them you need extra programs:

1. Install **Tesseract OCR** and **Poppler** (search for their install instructions for your system) and make sure both are on your PATH.
2. `pip install -r requirements-optional.txt`

NoticeNest uses OCR automatically when a PDF has no readable text. Without OCR, such notices are stored as **Needs review**.

## Troubleshooting

| Message or problem | Fix |
|---|---|
| `python` is not recognised | Reinstall Python and tick *Add to PATH*, or use `py` on Windows |
| `No module named 'flask'` (or similar) | The venv is not active, or you skipped `pip install -r requirements.txt` |
| `No module named 'app'` | You are not in the project folder. `cd` into the folder containing `run.py` |
| Port 5000 already in use | Edit `run.py` to `app.run(debug=True, port=5001)` |
| Every date shows "Needs review" | The notice text may be a scan, or dates have no year |
| `LLM error HTTP 401/403` | Wrong or missing API key in `.env` |
| `LLM error HTTP 404` | Wrong model name in `.env` |
| `LLM busy or rate limited (HTTP 429)` | Free quota used up. The app retries, then falls back to basic mode |
| Source returned 0 notices | Selectors are wrong or the page uses JavaScript. See `docs/SOURCES_GUIDE.md` |
| Weird characters on Windows | All files are UTF-8. Do not re-save them in another encoding |
| `PermissionError` when deleting the database | Stop the server first |
