# GitHub, demo and resume

## 1. Before you upload anything

- Open `.gitignore` and check it lists `.env`, `.venv/`, `data/noticenest.db`. These must **never** reach GitHub.
- Search the project for your API keys (VS Code: `Ctrl+Shift+F`, search part of the key). Keys belong only in `.env`.
- Open `LICENSE` and replace "NoticeNest contributors" with your name.
- Replace the demo University text in `README.md` with a sentence about the university you built it for.

If you ever push a secret by mistake, treat the key as stolen: delete it in the provider's console and create a new one. Removing it from GitHub later is not enough.

## 2. Create the repository

1. On github.com click **New repository**. Name it `noticenest`. Leave "Add a README" **unticked** (you already have one). Choose Public so recruiters can see it.
2. In the VS Code terminal, inside the project folder:

```bash
git init
git add .
git status                       # check .env and .venv are NOT in the list
git commit -m "Initial commit: NoticeNest pipeline, web app, tests and docs"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/noticenest.git
git push -u origin main
```

If Git asks who you are, run once:
`git config --global user.name "Your Name"` and `git config --global user.email "you@example.com"`.
When pushing, GitHub asks you to sign in through the browser (or use a personal access token).

## 3. Commit like a developer

Small commits with clear messages show how you work. After each piece of work:

```bash
git add .
git commit -m "Add selectors for <your university> notices"
git push
```

Good messages: `Fix semester parsing for "1st & 3rd semester"`, `Add 15 real notices to the gold set`, `Flag dates without a year as needs review`.
Suggested history for your own work: setup, first real source, gold set, regex tuning, AI extraction, matching, reminders, pilot, docs.

## 4. Make the repo look finished

- [ ] README has a one-line description at the top and a screenshot (add images to `docs/` and link them)
- [ ] The green tick from the *tests* workflow (it appears after your first push)
- [ ] Your **measured** accuracy table from real notices (see `docs/EVALUATION.md`)
- [ ] A short "Limitations" section (already included, keep it honest)
- [ ] Repository **Topics**: `python`, `flask`, `nlp`, `llm`, `web-scraping`, `sqlite`, `students`
- [ ] A 1-2 minute screen recording linked from the README

## 5. The 5-minute demo

1. **Problem (30 s).** Show a real notice PDF: long, dates buried in text.
2. **Config (30 s).** Show `sources.yaml`: adding a university is a config edit.
3. **Run it (60 s).** `python -m app.jobs.run_once`. Open the dashboard and show a card next to the original PDF, with the snippet under each date.
4. **Personalisation (45 s).** Two profiles (different course or semester) see different notices. Show a *May apply to you* notice and explain why *maybe* beats *no*.
5. **Reminder (30 s).** A Telegram message arriving.
6. **Revision (45 s).** `python tools/simulate_revision.py`, run the job, open **What changed**.
7. **Trust (60 s).** The **Accuracy** page and your table. Show one *Needs review* notice and explain the validator.
8. **Resilience (30 s).** Set `LLM_PROVIDER=none`, run again: still works.

## 6. Resume bullets (fill in the blanks with your real numbers)

> **NoticeNest** - automated university-notice tracker (Python, Flask, SQLite, LLM API)
> - Built a pipeline that scrapes official notice pages, extracts deadlines, fees and eligibility from PDFs with an LLM, and sends personalised Telegram/email reminders.
> - Added a validation layer that checks every AI-extracted date and fee against the source text, catching **__** invented dates on **__** hand-labelled notices; reached **__%** deadline precision and **__%** recall.
> - Designed graceful fallback (regex mode, retries, answer caching) so the system keeps working when free-tier AI quotas run out.
> - Piloted with **__** students; wrote **34** automated tests and CI on GitHub Actions.

Only write numbers you have measured. If a number is small, say it honestly.

## 7. Questions to prepare for

1. *Why a validator after the AI?* (Models can invent dates; a missed exam form is costly.)
2. *Why does an unknown audience become "maybe"?* (False negatives cost more than false positives.)
3. *How do you know it works?* (Gold set, precision/recall, held-out third, pilot.)
4. *What happens when the AI is down or the site changes?* (Fallback; the "0 notices" warning.)
5. *Is scraping allowed?* (robots.txt check, delay, identification, links to originals, no republishing.)
6. *What would you do next?* (OCR for Hindi, more universities, a Telegram sign-up flow, hosting.)
7. *What are the privacy risks?* (Emails stored; only public text goes to the AI; delete button; no passwords is a known limit.)

## 8. After submission

Ideas that each make good follow-up commits: Hindi OCR, a Telegram `/start` sign-up, a second university, a "deadline week" email digest, and measuring pilot feedback.
