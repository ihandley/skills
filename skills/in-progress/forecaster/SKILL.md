---
name: forecaster
description: Forecast a likely date (50%) and a due date (85%) for one epic from your saved weekly Pace.
disable-model-invocation: true
compatibility: Requires Python 3.11+
metadata:
  author: ian.handley
---

# Forecaster

`forecaster.py` does all the arithmetic. It never touches the network or a credential. You gather inputs and report what it prints.

Run `python3 <this-skill>/forecaster.py forecast --inputs <file>`. It prints one JSON object. Exit 2 means a refusal; report the message and stop. Exit 3 means Python is too old.

## Inputs file (JSON)

- `epic`: the epic key.
- `remaining_points`: points left on the epic.
- `start_date`: ISO date the work starts.
- `capacity_share`: `[low, high]`, the fraction of Pace this work gets. Default `[1, 1]`. Assumed, not measured.
- `history`: weekly Pace, a list of `{"week": "YYYY-MM-DD", "points": N}`. Or `history_file`: path to that list, relative to the inputs file.
- `scope_file`: saved Jira search results (`{"issues": [...]}`) from `queries scope`. Optional `initiative`. When set, `forecast` adds a `scope` block: epic order proposed from Blocks links (blocker first), `remaining_points` per epic (open leaf tickets), `not_in_the_dates` (points in Testing) and `warnings` (unpointed open tickets, Blocks cycles). `remaining_points` may then be omitted.
- `epic_order`: optional list of epic keys. Overrides the proposed order; show the proposal and ask the user to confirm or change it.
- `seed`: integer. The same seed and inputs give identical output.
- `trials`, `expiry_days`: optional. Defaults 10000 and 28.

Ask the user only for fields that are missing. Save answers to the inputs file so a rerun asks nothing.

## Scope from Jira

`python3 <this-skill>/forecaster.py queries scope --key <initiative-or-epic>` prints Jira search operations (points read from `customfield_10016`). Run them with the Atlassian tool, merge the issues into one JSON file and set `scope_file`. The script never calls Jira.

## Steps

1. Build or read the inputs file.
2. Run `forecast`. Never invent history. Empty history is refused: tell the user, do not guess a date.
3. Report `likely_date` (date by which 50% of runs finish), `due_date` (date by which 85% of runs finish), `expiry` and `refresh_trigger`. A single date is not a forecast.
