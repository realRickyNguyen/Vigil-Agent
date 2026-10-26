# Sample outputs

Three real live runs of Vigil, one per drug. Each was made on 26 Oct 2026 with Zetaris and Meterless Nightshift running locally (Nemotron 3 Ultra through Nightshift 1.2.7), with the code defaults: 4 model calls at a time, 1 revision round and a 600 s budget. The commands were `python -I run.py --drug <drug> --record` and the matching inputs in [input_examples/](../input_examples/). The files are copies of what the run wrote to `logs/`, **unedited**. The app never reads this folder.

| Drug | Input | Run | Time | Review next | Notes |
|---|---|---|---|---|---|
| montelukast | [example_1.json](../input_examples/example_1.json) | `20261026T014102Z-8640f9` | 396 s | 2 | Both review-next items are marked "check the reporting cluster first": 88% and 97% of their reports come from Canada, against 13% for the drug. The neuropsychiatric boxed-warning terms are found on the label. |
| isotretinoin | [example_2.json](../input_examples/example_2.json) | `20261026T014740Z-aa82a9` | 327 s | 2 | IRRITABLE BOWEL SYNDROME and INTESTINAL OBSTRUCTION are both marked as lawyer-reported clusters. |
| metformin | [example_3.json](../input_examples/example_3.json) | `20261026T015308Z-8cc80b` | 374 s | 6 | No reporting-cluster marks. METABOLIC ACIDOSIS is review next: the label covers lactic acidosis, a narrower term, and names metabolic acidosis only as a contraindication. |

Each folder has three files.
- **`dossier-<run>.json`:** the run's result. It has the ranked review queue, with each item's evidence, label search, objections, history, uncertainty, report sources, reporting-cluster mark and comparison with earlier runs (`since_last_run`). It also has the safety net, the World Model record, the time budget and the model calls.
- **`trace-<run>.jsonl`:** every step of the run, one JSON event per line. That covers every Zetaris query with its SQL, and every model call with its full prompt and reply, including Nemotron's reasoning and which model served it (`served_by`). It also covers the Reviewer's verdicts, retries, the Skeptic's checks and the World Model's audit entries.
- **`response.json`:** what `POST /run` returns for this run, built from the dossier.

## Replaying them without any service

The same runs were recorded for sample mode: [samples/](../samples/) holds every Zetaris result and model reply each run received. The replay gives the same review queue, rounds and counts as the dossiers here, and the offline test `tests/test_sample_mode.py` checks this for montelukast. It needs no Zetaris, no Nightshift and no network.

```bash
SAMPLE_MODE=true python -I run.py --drug montelukast
```

A replay is labelled: every trace event has `"sample_mode": true`, the console prefixes `[SAMPLE]`, and the dossier and the API response say which recorded run it replays. Its run ID, times and timings are its own.

The recordings were made from commit `b1edde4` plus the sample-mode recorder, which does not change what the agents do. If the agents change, record again with `python -I run.py --drug <drug> --record`.
