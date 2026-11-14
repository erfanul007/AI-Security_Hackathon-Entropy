# EHR Attacker

Automated white-hat red-team agent for **Riley** (Break the Model). A LangGraph state machine
walks ten prompt-only attack phases in order, an attacker LLM mutates probes that get refused, a
two-stage judge scores every reply, confirmed leaks are stored for offline verification, and a
benchmark ranks which prompt categories Riley is weakest against.

**Authorised testing only**: synthetic data, messages only, no server hacking (per repo README).

See `docs/SPEC.md` for the full design. Setup is the repo-root `.env` + `python3 setup.py`.

## Run

```bash
python ehr-attacker/agent.py                      # default target model, 150-probe cap
python ehr-attacker/agent.py --model "openai/gpt-oss-120b" --max-probes 80 --mutate 3
python ehr-attacker/agent.py --allow-side-effects # opt in to the injected send_email probe
```

Outputs land in `ehr-attacker/runs/<timestamp>/`: `results.jsonl` (every judged probe),
`report.md` (leaks by phase + severity), `scorecard.json`.

## Verify a leak is real (offline)

```bash
python ehr-attacker/export_evidence.py ehr-attacker/runs/<ts>/results.jsonl   # agent run -> evidence.db
python ehr-attacker/harvest_logs.py                                           # manual log -> evidence.db
python ehr-attacker/compare.py --reference /path/to/your/real.db              # MATCH = confirmed
```

`export_evidence.py` mines an agent run's `results.jsonl`; `harvest_logs.py` mines the hand-driven
`logs/my_attempts.jsonl` (full rows, keyed for diffing). Both write record-keyed leaks into
`ehr-explorer/data/evidence.db` (a constraint-stripped clone of prod.db's schema). `compare.py`
diffs that against the author's own DB — the agent never sees real data.

## Benchmark

```bash
python ehr-attacker/benchmark/bench.py            # all 4 models; worst categories first
```

Writes `benchmark/scorecard.json` + `benchmark/bench_report.md`.

## Phases (run in order)

P1 recon · P2 verify (soft vs hard guardrails) · P3 pattern sweep · P4 impersonate ·
P5 encode (decode offline) · P6 batch (join offline) · P7 fragment (reassemble offline) ·
P8 story · P9 context overload · P10 misc (indirect injection, tool-call leak, send_email).

## Tests

```bash
python -m pytest ehr-attacker/tests -q
```
