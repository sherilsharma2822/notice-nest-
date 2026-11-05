# Architecture

## The pipeline

```
sources.yaml
   |
   v
fetcher.py ----> RawNotice(title, url, date [, text])        "what notices exist?"
   |
   v
pipeline.process_raw_notice
   |-- fingerprint = hash(source + url)       already stored?  -> skip, or compare text hash
   |-- get_notice_text                        PDF -> pdfplumber (OCR fallback), HTML -> BeautifulSoup
   |-- extract_and_validate
   |       AI on?  yes -> ai_extractor (JSON)   no / failed -> regex_extractor
   |       validator.validate                   checks every date and fee against the text
   |-- store notice + deadlines (SQLite)
   |-- new?     alerts.schedule_for_notice + alerts.send_notice_alerts("new")
   |-- changed? change_detector + changes row + alerts "revised"
   v
alerts.process_due_alerts   -> notifier (Telegram / email / console)
   v
Flask routes + templates    -> dashboard, notice page, changes, profile, calendar, accuracy
```

## Design decisions (and why)

| Decision | Reason |
|---|---|
| **Validator after the AI** | AI models sometimes invent dates. The validator accepts a date only if it is literally written in the notice, so a hallucination becomes a visible warning instead of a missed exam form. |
| **Regex fallback** | Free AI tiers have limits. The app must keep working, and the regex extractor is also the baseline for measuring the AI's value. |
| **One file talks to the AI** (`llm_client.py`) | Providers and model names change. Retry, timeout and caching live in one place. |
| **Answer cache** | The same notice text never costs a second API call (`llm_cache` table). |
| **`maybe` instead of `no`** | A missed deadline hurts more than an extra alert. |
| **Config-driven sources** | Adding a university means editing YAML, not Python. |
| **`local` source kind** | Lets you demo, test and evaluate with no internet and no scraping. |
| **SQLite** | One file, no server, built into Python. Perfect for a single-machine project. |
| **Deterministic change detection first** | Deadline differences are computed exactly by code. The AI (optional) only rephrases them in one sentence. |
| **Only public text leaves the machine** | Student data is never sent to an AI service. |
| **CSRF token, private link, delete button** | Basic privacy hygiene for a tool that stores emails. |

## Modules

| File | Responsibility |
|---|---|
| `config.py` | Reads `.env`; all settings |
| `db.py`, `schema.sql` | SQLite connection, tables |
| `services/fetcher.py` | robots.txt, polite downloads, list-page scraping, demo notices |
| `services/text_extractor.py` | PDF/HTML to plain text, scan detection, optional OCR |
| `services/regex_extractor.py` | Dates (3 formats), fees, notice type, courses, semesters |
| `services/llm_client.py` | Gemini/Groq calls, retry, cache, JSON parsing |
| `services/ai_extractor.py` | The prompt and normalisation of the AI's answer |
| `services/validator.py` | Checks extraction against the notice text |
| `services/matcher.py` | yes / maybe / no for a student |
| `services/change_detector.py` | Deadline diff and a one-sentence change summary |
| `services/notifier.py` | Telegram, email, console |
| `services/alerts.py` | Who gets what and when; sends due reminders |
| `services/pipeline.py` | Orchestrates everything (start reading here) |
| `jobs/run_once.py`, `jobs/scheduler.py` | Command-line entry points |
| `routes.py`, `templates/`, `static/` | The website |
| `eval/run_eval.py` | Accuracy measurement |

## Database

| Table | Holds |
|---|---|
| `sources` | Each website or folder watched |
| `notices` | One row per notice: text, type, summary, who it is for (JSON), fees (JSON), review status, issues, version |
| `notice_versions` | Every version of a notice's text |
| `deadlines` | Label, date, the exact snippet, and `verified` (1 = date found in the notice) |
| `changes` | Revisions: edited in place, or a separate "revised" notice |
| `users` | Name, email, private token, Telegram ID, course, semester, batch |
| `alerts` | One row per planned message. `deadline_id = 0` means a notice-level alert. `offset_days`: 3/1/0 = days before, -1 = new notice, -(100+version) = revised |
| `fetch_log` | Each fetch: how many found, any error |
| `llm_cache` | Saved AI answers |

## Concepts in plain language

| Term | Meaning |
|---|---|
| **Scraping** | A program reading a web page to collect data |
| **CSS selector** | A short pattern such as `table tr` that points at parts of a page |
| **robots.txt** | A file where a website says which pages bots may fetch |
| **Regex** | A pattern language for finding text, like dates |
| **Hash** | A short fingerprint of text. Same text, same hash. Used to spot duplicates and edits |
| **LLM** | A large language model, the kind of AI behind Gemini or ChatGPT |
| **API key** | A password that identifies you to an online service |
| **JSON** | A text format for structured data: `{"date": "2026-11-05"}` |
| **Prompt** | The instructions and text you give to an AI |
| **Hallucination** | When an AI states something that is not true or not in the source |
| **Validator** | Code that checks another step's output |
| **Cache** | A saved answer, reused instead of asking again |
| **SQLite** | A database stored in one file |
| **CSRF** | An attack where another website makes your browser submit a form. The hidden `csrf` field defends against it |
| **Precision / recall** | Of what the system reported, how much was right / of what was really there, how much was found |
| **Baseline** | A simple method you compare a fancier one against |
| **Ablation** | Turning one part off to measure what it contributes |

## Extending it

- **New source kind:** add a function in `fetcher.py` returning `RawNotice` items and register it in `fetch_source`.
- **New notice type:** add it to `NOTICE_TYPES` and keywords in `regex_extractor.py`, the prompt in `ai_extractor.py` and `TYPE_LABELS` in `app/__init__.py`.
- **New course:** add a pattern in `_COURSES` and the code to `COURSE_CHOICES` in `matcher.py`.
- **Different reminder days:** change `REMINDER_OFFSETS_DAYS` in `config.py`.
