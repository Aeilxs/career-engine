# Functional Feasibility and Discovery POCs

**This is a proposed evaluation plan, not a report of measurements.** Feasibility is high for local imports, tracking, documents and human review; variable for read connectors and site-specific ATS forms; unsupported as a universal auto-submission guarantee.

## Product value and boundaries

**A: Discovery/preparation:** ingest configured sources, normalize and deduplicate offers, rank against an approved profile, produce editable documents and track human decisions. This value must survive even if automated submission cannot be implemented across relevant sites.

**B: Controlled submission:** only on a capability-verified ATS, after human approval, with immutable evidence, uncertainty handling and no automatic repeat after a lost confirmation. Generic consumer-side APIs are not interchangeable with employer-admin submission APIs.

| Capability | Estimated feasibility | Actual proof required |
|---|---|---|
| Import text / HTML / URL | High, URL security matters | Source bytes + graceful retrieval errors |
| Read ATS from known board/company | High on qualifying sources | 30-offer sample coverage + one real read connector |
| Universal Internet job search | Not a justified MVP promise | Do not implement without sourcing study |
| Normalize / exact dedupe / revisions | High | Ten identical imports, changed revision, distinct similar offer |
| Human-reviewed scoring | High with uncertain fields | Annotated profile/offer corpus; error metrics |
| Generate tailored editable PDF package | High after renderer POC | Approved facts, text/visual inspection and hash check |
| Form inspect/fill via Playwright | Medium, ATS-specific | Local simulator + real no-submit inspections |
| Site-specific real submission | Medium, context dependent | One approved J7 pilot, proof or UNKNOWN |
| Universal ATS submission | Low | Out of initial scope |
| SQLite jobs / XLSX / history | High | Fault injection and SQL-backed reproducible export |

## POC program

| POC | Question | Procedure | Decision gate |
|---|---|---|---|
| P0 | Is Python 3.14/uv/container usable on Mac ARM64? | Lock, install, test, build, restart SQLite, inspect image architecture | Honest pass/fail report; no fabricated lockfile |
| P1 | Which ATS providers actually host relevant jobs? | Hand-sample 30 real targeted postings; record company, source, ATS, discoverability and limitations | Select first connector from measured coverage, not convenience |
| P2 | What extraction quality and cost? | 20 development + 10 held-out annotated offers, 2 provider candidates, 3 runs each | Proposed ≥95% accuracy on present critical fields; 0 invented salaries; publish sample size/errors |
| P3 | Can the existing LaTeX CV generator be integrated? | Five synthetic cases: long CV, accented chars, English, URLs, multiple jobs | Five readable/openable PDFs, extractable text, no layout truncation |
| P4 | Browser capability reliability | Mock ATS with conditional fields, uploads, validation/session expiry; qualify local browser | All supported scenarios verified; unsupported capabilities reported |
| P5 | Crash safety and transaction boundaries | Kill at DB/file/submit boundaries; restart; simulated ATS counts effects | No DB corruption; zero automatic resubmissions after UNKNOWN |
| P6 | What works on the chosen live ATS? | Five no-submit inspection/fill attempts then one explicit approved application | Record coverage, time, corrections and proof/uncertainty, do not extrapolate |

## Sampling protocol for P1

Use 30 genuinely relevant target roles, grouped by employer and ATS. Prefer distinct employers over 30 URLs on one board. Suggested target categories: business manager, engineering sales/account manager, industrial/energy business development and technical sales in the relevant French geography. Record each job's accessible posting URL, provider, whether a public read route exists, freshness and whether the submit route requires an account or employer credentials. **Do not include any personal identifiers or credentials in fixtures.**

A convenient provider API without meaningful sample coverage is a *failed* business fit, not a technical success. Start with configured boards, not a universal job-search crawler.

## Evaluation corpus

Include French and English offers; unknown salaries; fixed vs variable; multiple locations; ambiguous remote arrangements; closed offers; exact and near duplicates; malicious HTML/prompt injection; long descriptions; conditional questions; malformed JSON; browser timeouts. Keep synthetic tests in CI; live captures, when legally/operationally appropriate, must be redacted and processed only in explicitly enabled POC runs.

## Measurement definitions

Measure schema validity, presence-aware field accuracy, invented values, abstentions, human corrections, document acceptance, browser fill success, submission proof rate, p50/p95 latency and actual LLM tokens/cost. A model returning `null` for every field is not accurate. A matching score is not a calibrated probability of being hired. LLM outputs recorded in fixtures allow deterministic replay; identical prompts alone do not guarantee identical responses.

Source documentation (availability and terms require rechecking before building each connector):

- Greenhouse Job Board API: https://developers.greenhouse.io/job-board.html
- Lever Postings API: https://github.com/lever/postings-api
- Ashby public postings: https://developers.ashbyhq.com/docs/public-job-posting-api
- SmartRecruiters public postings: https://developers.smartrecruiters.com/reference/v1listpostings

Do not assume employer/admin API credentials permit candidate-side access. Current provider pricing and availability must be reverified during P1/P2; this document does **not** encode an unverified monthly cost forecast.
