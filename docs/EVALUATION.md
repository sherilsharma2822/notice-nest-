# Measuring accuracy

Accuracy numbers are what turn "it seems to work" into evidence. This is the most valuable thing you can show in an interview.

## What is in the box

`eval/gold/labels.json` plus `eval/gold/notices/*.txt` are **10 synthetic notices** I wrote so you can see the evaluation run. They are clean and easy, so the regex baseline scores very high on them. **Do not quote those numbers as real accuracy.**

## Build your own answer key (do this in Week 2)

1. Save 40 to 60 real notices from your university: copy the text of each PDF into a `.txt` file. Use this layout:

   ```
   Title: Examination Form for BCA III Semester
   Date: 20.10.2026
   ---
   (the full text of the notice)
   ```

2. Put the files in `eval/gold/notices/`.
3. For each one, add an entry to `eval/gold/labels.json` with the **correct answers written by you**, reading the original notice:

   ```json
   {
     "file": "my_notice_01.txt",
     "title": "Examination Form for BCA III Semester",
     "published": "2026-10-20",
     "expected": {
       "notice_type": "exam_form",
       "all": false,
       "courses": ["BCA"],
       "semesters": [3],
       "deadlines": ["2026-11-05", "2026-11-12"],
       "fees": [500, 1250]
     }
   }
   ```

   Allowed types: `exam_form`, `fee`, `result`, `scholarship`, `timetable`, `admission`, `holiday`, `other`.
   `deadlines` lists every real deadline date as `YYYY-MM-DD`. `fees` lists amounts in rupees.

4. Remove the 10 synthetic ones (or keep them separately) so your numbers describe real notices only.

**Keep about one third untouched.** Write your regex rules and prompts while looking at two thirds of the notices, then measure on the third you never looked at. That is the honest number.

## Run it

```bash
python -m eval.run_eval           # basic mode (offline)
python -m eval.run_eval --llm     # also the AI, needs a key in .env
```

It prints a table and saves `eval/results/latest.json`, which the **Accuracy** page shows.

## What the columns mean

| Column | Meaning |
|---|---|
| type acc | Share of notices given the right type |
| who acc | Share where "everyone / courses / semesters" is exactly right |
| date P (precision) | Of the dates reported, the share that are real deadlines |
| date R (recall) | Of the real deadlines, the share that were found |
| date F1 | One number balancing precision and recall |
| fee R | Share of real fee amounts found |
| invented | Dates reported that are written nowhere in the notice |

The three setups:

| Setup | Meaning |
|---|---|
| `regex` | Patterns only, after validation. The baseline |
| `llm_raw` | The AI's answer exactly as given |
| `llm_validated` | The AI's answer after `validator.py` |

## How to read the result

- If **llm_raw** has invented dates and **llm_validated** has fewer, the validator is doing its job. Quote the exact numbers.
- If the AI does **not** beat regex on your notices, say so. "I measured it, and for this university patterns were enough" is a strong, honest finding.
- Look at the errors, not just the score. Print which notices failed and why; most failures teach you what to improve.

## Also worth measuring (for the pilot)

- Share of notices marked *Needs review*.
- Replay old notices and check each reminder would have fired on the right day.
- How many students used it, and how many reminders were sent (the **Accuracy** page shows counts).
- Number of AI calls saved by the cache.

## Sample table to put in your README

| Setup | Type acc | Date precision | Date recall | Invented dates |
|---|---|---|---|---|
| Patterns only | | | | |
| AI, unchecked | | | | |
| AI + validator | | | | |
