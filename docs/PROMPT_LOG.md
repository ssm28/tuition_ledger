# Prompt log

This is every message I sent to the AI assistant (Claude, in the claude.ai chat) while building this project, in order
and **unedited**, including spelling mistakes and my casual style. The "Outcome" lines are short summaries of what the
assistant produced after each message. See [`../AI_USAGE.md`](../AI_USAGE.md) for how the assistant was used overall.

The first message came with two attachments: the text of the problem statement, and a screenshot of the
challenge e-mail (not reproduced here).

Days are approximate: the first seven prompts were on 6 November 2026, the rest on 7 November 2026.

---

## Prompt 1 (day 1)

```text
I am on the 3rd stage of the process, I need to submit it in the next 2.5 days, but i wanna complete it earlier so i have adequate time to understand it. How should we go about it in the most professional manner cause the company will have the git hub link.
```

Outcome: a time plan, the proposed stack (Python, pytest, few dependencies), the repository layout, the main design
ideas (valid baseline first, then labelled anomalies; validator scored against ground truth; fixed-seed reproducibility)
and professional-repo advice.

## Prompt 2 (day 1)

```text
Go ahead python is great, Lets start, in the mean time i will read all the things again and make a mind map.
```

Outcome: the project foundation: configuration, ID conventions, the schema as a single source of truth, the generated
data dictionary, `DESIGN.md` with draft rules, first tests and a Git commit.

## Prompt 3 (day 1)

```text
yes i did read all the rules, seems all good to me, just few things, I wanna understand it fully, so you explain me along what we are actually doing, in simple words. Then In the rule section what is the use of credit in fees? can't we keep it simple, just fees. And I didn't understand the today, date as of today part. what is it? Rest all seems good to me. 

I am explaining what i understood, correct me where needed. 
So we are basically simulating a database here. We are creating 10,000 students across 20 courses, generating 30,000 invoices (perfectly match if we have 3 terms), 50,000 payments(including all kinds of payments), 15,000 scholarships. But initially we are creating all master tables with the attributes. then they are connected to each other wherever needed, they use PK and FK. What are we doing next? we are just generating these data? what else, i know the anomaly injection part but what else?
```

Outcome: removed credit-hour fees (fees became one fixed amount per term); explained the fixed "as-of" date; corrected
and extended my understanding of the pipeline (generate, derive, inject, validate, score, export, reproduce); a list of
things for me to do.

## Prompt 4 (day 1)

```text
Okay yeah i understand now, In github it looks much clean and nice, easily undestandable. Okay so i didn't break any table like you said in the last point, i will do it, but lets move on to the next part?
```

Outcome: the master-data generators (terms, programs, students, fee schedules, scholarship schemes), CSV export,
tests, and explanations of the design choices.

## Prompt 5 (day 1)

```text
usage: tuition-synth [-h] {docs} ...
tuition-synth: error: argument command: invalid choice: 'master' (choose from docs)
```

Outcome: diagnosis (the installed command pointed at an older copy of the project) and the fix (reinstall from the
current folder).

## Prompt 6 (day 1)

```text
got it thank you, all the csv files also look nice, nothing odd in them. but i did change the summer from 0.6 to 0.7 but the test still got pass, why that could be happening? and yes lets move to the next step.
```

Outcome: the assistant found that the test compared the prices with the same constant the generator used, so it could not
fail; the test was rewritten against the documented factors and hand-checked prices. Then enrollments, invoices, invoice
lines, status history and the first version of the validator were built.

## Prompt 7 (day 1)

```text
Perfect, I did pick one random student and now i understand the whole entity relation. great, now just tell me how many more steps we have? Don't update anything for now, just give me quick recap of what we did today and the next steps for tomorrow. And anything you think worth knowing.
```

Outcome: a recap of the day, the remaining work in six blocks with difficulty estimates, a suggested schedule and
advice on the submission.

## Prompt 8 (day 2)

```text
Okay Good Morning, I am ready for the next steps, lets go ahead, I have read the late fees rules and refund rules, I was thinking of having a fixed late fees rather than a percentage, rest is all fine.
```

Outcome: fixed late fee of INR 500 instead of a percentage; scholarships and fee waivers; payments, allocations and
late fees; derived invoice statuses; extended validator and tests.

## Prompt 9 (day 2)

```text
Okay I did check few random payments and fees i picked, all connects nicely, all the calculation also as per out rules. Now lets move to the next step, quickly finish the work. Finish all the next steps at once.
```

Outcome: refunds, the student ledger, the five labelled anomalies with a separate ground-truth file, the CSV/JSON/SQL
exports, manifest, validation summary, the reproducibility command, final README and design documents, the committed
datasets and reports, and a list of what I needed to do.

## Prompt 10 (day 2)

```text
Okay Thank you, all looks fine to me, I wanna add few personal touches, Add all the prompts that i used in LLM to get the codes. Then i wanna add an ER diagram file, so that i understand it and the person who looks at that also gets it. Then i want you to create another document file with all the steps, dataflow, which files ([cofig.py](http://cofig.py/), [cil.py](http://cil.py/), etc) do what, for each file, every details like a developer need to know about his project. Do the final check and don't give any file if not needed, give just the new files i asked. You decide the best way to add the ER diagram, Mermaid?
```

Outcome: this prompt log and `AI_USAGE.md`, the Mermaid ER diagram document, the developer guide, a final review of the
repository (which fixed an incomplete check-family list, three unused imports and one unused function), and a
documentation-consistency test.
