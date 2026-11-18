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

Run `python3 <this-skill>/forecaster.py <cmd>`. `queries pace --inputs <file>` and `queries scope --key <key>` print the Jira searches to run; `forecast --inputs <file>` does the arithmetic. It prints one JSON object. Exit 2 means a refusal; report the message and stop. Exit 3 means Python is too old.

## Inputs file (JSON)

- `epic`: the epic key.
- `remaining_points`: points left on the epic.
- `start_date`: ISO date the work starts.
- `capacity_share`: `[low, high]`, the fraction of Pace this work gets. Default `[1, 1]`. Assumed, not measured.
- `assignee`: whose Pace to read (needed by `queries`).
- `as_of`: ISO date, default today. The 12 whole weeks before its Monday are the window; holiday weeks stay in as zero.
- `points_field`: Jira field holding story points. Default `customfield_10016`. Warns when empty.
- `jira_results_file`: saved raw results of the `queries` search, relative to the inputs file. Builds Pace when `history` is absent.
- `history`: weekly Pace, a list of `{"week": "YYYY-MM-DD", "points": N}`. Or `history_file`: path to that list, relative to the inputs file.
- `scope_file`: saved Jira search results (`{"issues": [...]}`) from `queries scope`. Optional `initiative`. When set, `forecast` adds a `scope` block: epic order proposed from Blocks links (blocker first), `remaining_points` per epic (open leaf tickets), `not_in_the_dates` (points in Testing) and `warnings` (unpointed open tickets, Blocks cycles). `remaining_points` may then be omitted.
- `epic_order`: optional list of epic keys. Overrides the proposed order; show the proposal and ask the user to confirm or change it.
- `seed`: integer. The same seed and inputs give identical output.
- `trials`, `expiry_days`: optional. Defaults 10000 and 28.

Ask the user only for fields that are missing. Save answers to the inputs file so a rerun asks nothing.

## Scope from Jira

`python3 <this-skill>/forecaster.py queries scope --key <initiative-or-epic>` prints Jira search operations (points read from `customfield_10016`). Run them with the Atlassian tool, merge the issues into one JSON file and set `scope_file`. The script never calls Jira.

## Steps

1. Build or read the inputs file. If Pace is not saved yet, run `queries pace`, run each emitted operation through the Atlassian tool (all pages, with changelog), save the raw results, and set `jira_results_file`. The script never calls Jira.
2. Run `forecast`. Never invent history. Empty history is refused: tell the user, do not guess a date.
3. Report `likely_date` (date by which 50% of runs finish), `due_date` (date by which 85% of runs finish), `expiry` and `refresh_trigger`. A single date is not a forecast.

## Pace rules

A ticket counts in the week (Monday start) it first entered Testing or Done, from the status changelog. Canceled never counts. Parents of sub-tasks are skipped. Unpointed tickets are left out and listed in `warnings` and `unpointed`. Short or volatile history also adds a warning. Report every warning.
