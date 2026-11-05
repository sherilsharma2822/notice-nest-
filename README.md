# NoticeNest

**Never miss a university deadline again.**
NoticeNest watches your university's official notice pages, reads every new notice (PDF or web page), finds the dates, fees and who it applies to, and sends each student reminders for *their* course and semester. If a notice is edited or a revision is published, it shows exactly what changed.

> Student project. NoticeNest reads public notices with software and can make mistakes. Every card links to the original notice, and anything it is unsure about is clearly marked **Needs review**.

---

## The problem

Exam-form dates, fee deadlines, revaluation windows and scholarship notices are published as long PDFs on university websites. Students find out late, through forwarded WhatsApp messages, or miss them completely. Nothing reads the official notice for you and tells you *what applies to you and by when*.

## What it does

| Feature | How it works |
|---|---|
| Watches notice pages | Config-driven scraper (CSS selectors in `config/sources.yaml`), obeys `robots.txt`, rate-limited |
| Reads PDFs and web pages | `pdfplumber` for PDFs, BeautifulSoup for HTML, optional OCR for scans |
| Extracts structured data | Notice type, summary, deadlines, fees, courses and semesters, with the **exact snippet** each date came from |
| Verifies the AI | Every date and fee must literally appear in the notice text, otherwise it is flagged **Needs review** |
| Works without AI | Regex "basic mode" is used when there is no API key or the free quota runs out |
| Personal matching | `yes` / `maybe` / `no` per student. Unknown audience means *maybe*, never *no* |
| Reminders | 3 days before, 1 day before and on the day, through Telegram or email |
| Revision detection | Same notice edited in place, or a "Revised/Extended" notice, with a plain-English summary of the change |
| Calendar export | Download your deadlines as an `.ics` file for Google or Apple Calendar |
| Measured accuracy | `python -m eval.run_eval` compares regex, raw AI and AI + validator on hand-labelled notices |

## Try it in 5 minutes (no API key, no internet scraping)

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate        macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                      # Windows: copy .env.example .env
python -m app.jobs.run_once               # loads 10 demo notices
python run.py                             # open http://127.0.0.1:5000
```

Then: open **Set up profile**, choose a course and semester, and watch the dashboard sort the notices. Run `python tools/simulate_revision.py` followed by `python -m app.jobs.run_once` to see a revised notice get detected.

Full step-by-step instructions (Windows, VS Code, AI keys, Telegram): **[docs/SETUP_GUIDE.md](docs/SETUP_GUIDE.md)**.

## How it works

```
Scheduler -> Fetch notice list -> Download + read text -> AI extractor (or regex)
          -> Validator (checks against the real text) -> SQLite
          -> Matcher + reminders (Telegram / email)      -> Web dashboard
```

Design rules that shape the code:

1. **The AI never gets the last word.** `validator.py` checks every extracted date and fee against the source text.
2. **Missing a deadline is worse than an extra alert.** Uncertain matches become *maybe*.
3. **Only public notice text goes to the AI.** Student profiles never leave your computer.
4. **Everything degrades gracefully.** No key, a rate limit or a bad answer means basic mode, not a crash.

Details: **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.

## Project layout

```
config/sources.yaml        which sites to watch
app/services/              fetcher, text_extractor, regex_extractor, llm_client, ai_extractor,
                           validator, matcher, change_detector, notifier, alerts, pipeline
app/jobs/                  run_once.py, scheduler.py
app/routes.py, templates/  the web app
eval/                      hand-labelled notices + run_eval.py
tools/                     inspect_page.py, get_telegram_chat_id.py, simulate_revision.py
tests/                     34 automated tests (pytest)
docs/                      guides
```

## Commands

| Command | What it does |
|---|---|
| `python run.py` | Start the website |
| `python -m app.jobs.run_once` | Fetch, read, extract, store and send due reminders once |
| `python -m app.jobs.run_once --no-llm` | Same, forcing basic (regex) mode |
| `python -m app.jobs.scheduler --every-minutes 180` | Repeat forever |
| `python -m eval.run_eval` / `--llm` | Measure accuracy |
| `pytest` | Run the tests |
| `python tools/inspect_page.py <url>` | Help writing selectors for a real site |

## Configuration

Copy `.env.example` to `.env`. Everything is optional. With no changes the app runs in basic mode with console alerts.

| Setting | Purpose |
|---|---|
| `LLM_PROVIDER` | `none`, `gemini` or `groq` |
| `GEMINI_API_KEY`, `GEMINI_MODEL` / `GROQ_API_KEY`, `GROQ_MODEL` | AI access. Free-tier limits and model names change, so check the provider's page |
| `TELEGRAM_BOT_TOKEN` | Telegram reminders |
| `SMTP_*` | Email reminders |
| `USER_AGENT_CONTACT`, `REQUEST_DELAY_SECONDS` | Scraping politeness |

## Evaluation

`eval/gold/` ships with 10 **synthetic** notices so you can see the evaluation work. They were written to be clear, so the scores on them are high and **should not be quoted as real-world accuracy**. To get honest numbers, label 40-60 real notices from your university: see **[docs/EVALUATION.md](docs/EVALUATION.md)**.

## What has and has not been tested

- Tested automatically (34 tests): extraction patterns, validator, matching, change detection, the whole pipeline on demo notices, reminders, web pages, forms and CSRF protection, and the AI code path using a *faked* AI.
- **Not** tested against a real university website, a live AI API, live Telegram or live email. These need your own keys and your own site. Expect to adjust selectors for your university (see [docs/SOURCES_GUIDE.md](docs/SOURCES_GUIDE.md)).

## Limitations

- Pages that build their content with JavaScript cannot be read by `requests` (see the sources guide for options).
- Scanned PDFs need the optional OCR setup; Hindi text needs extra OCR language data.
- Dates without a year are flagged, not guessed, in basic mode.
- Profiles have no passwords. A private link identifies you, which is fine for a class pilot but not for a public service.

## Ideas for next steps

Multiple universities with per-source defaults, a Telegram bot with `/start` registration, OCR for Hindi, a browser calendar view, and deployment with a scheduled job.

## Responsible use

Respect each website's `robots.txt` and terms, keep the request delay, do not republish notices, and always send students to the official notice.

## License

MIT, see [LICENSE](LICENSE).
