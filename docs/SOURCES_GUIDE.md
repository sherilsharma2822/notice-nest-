# Adding your real university

Do this in order. Each step is short.

## 1. Check you are allowed

1. Open `https://your-university.example.edu/robots.txt` in a browser. If it says `Disallow: /` for everything, do not scrape that site. Ask the university for an official feed or permission instead.
2. Read the site's terms. Notices are public, but be gentle: NoticeNest waits `REQUEST_DELAY_SECONDS` between requests and identifies itself in its User-Agent (set `USER_AGENT_CONTACT` in `.env`).

## 2. Find the notice list page

Find the page that lists notices (for example *Notices*, *Examination*, *Circulars*). Copy its address.

## 3. Let the helper inspect it

```bash
python tools/inspect_page.py https://your-university.example.edu/notices
```

It prints the links that look like notices and an HTML path for each, for example:

```
- text : Examination Form for BCA III Semester
  href : https://.../uploads/exam-form.pdf
  path : table > tbody > tr > td > a
```

If it warns about **very little text**, the page is built with JavaScript. See the section below.

## 4. Write the source block

Open `config/sources.yaml`, edit the second block and set `enabled: true`.

| Path ends with | Use |
|---|---|
| `tr > td > a` | `item_selector: "table tr"` |
| `li > a` | `item_selector: "ul li"` (or `ol li`) |
| `div.notice-item > a` | `item_selector: "div.notice-item"` |
| links not inside a repeating box | leave `item_selector` empty and set `link_must_contain: [".pdf"]` |

Other settings:

- `link_selector`: which link inside each item (default `a`).
- `title_from: item_text` uses the whole row's text when the link says only "Download".
- `date_selector`: where the date is inside each item (optional; otherwise NoticeNest looks for a date in the item text).
- `link_must_contain`: keep only links whose address contains one of these words.

## 5. Test it

```bash
python -m app.jobs.run_once --source "My University - Notices" --no-reminders
```

Look at the log. `found: N` should match what you see on the website. Then open the website and check a few notices against the originals.

## Common problems

| Symptom | Likely cause and fix |
|---|---|
| `returned 0 notices` | Selector does not match. Re-run `inspect_page.py` and compare |
| `robots.txt does not allow` | The site forbids bots on that path. Do not work around it |
| Page has almost no text | JavaScript-built page. Look in the browser's *Network* tab for a JSON request that returns the notice list and fetch that instead, or ask the university for a feed. Browser automation (such as Playwright) is a larger step and is not included |
| Titles say only "Download" | Use `title_from: item_text` |
| Dates are missing | Set `date_selector`, or accept that the notice date comes from the PDF text |
| Notice shows "Needs review" and no text | The PDF is a scan. Install the optional OCR (see the setup guide) |
| A notice is read twice | Its address changes each visit. Fingerprints use the address, so look for a stable link |

## Good habits

- Start with **one** source and make it work well before adding more.
- Run the job at most every few hours.
- If the site layout changes, the log will say `returned 0 notices`. Fix the selector then.
