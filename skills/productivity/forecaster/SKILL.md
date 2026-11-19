---
name: forecaster
description: Forecast a likely date (50%) and a due date (85%) per epic, simulating the whole epic chain from your saved weekly Pace.
disable-model-invocation: true
compatibility: Requires Python 3.11+
metadata:
  author: ian.handley
---

# Forecaster

`forecaster.py` does all the arithmetic. It never touches the network or a credential. You gather inputs and report what it prints.

Run `python3 <this-skill>/forecaster.py <cmd>`. `queries pace --inputs <file>` and `queries scope --key <key> [--inputs <file>]` print the Jira searches to run; `forecast --inputs <file> [--percentiles 50,70,95] [--unit items|points]` does the arithmetic (default levels 50,85). It prints one JSON object. Exit 2 means a refusal; report the message and stop. Exit 3 means Python is too old.

## Inputs file (JSON)

- `epic`: the epic key.
- `remaining_points`: points left on the epic.
- `start_date`: ISO date the work starts.
- `capacity_share`: `[low, high]`, the fraction of Pace this work gets. Default `[1, 1]`. Assumed, not measured.
- `assignee`: whose Pace to read (needed by `queries`).
- `as_of`: ISO date, the Forecast date. The 12 whole weeks before its Monday are the window; holiday weeks stay in as zero. Required with `jira_results_file` (`forecast` refuses without it, and `inputs check` asks for it), so a rerun reads the same weeks. Expiry counts from it; without `as_of` (saved `history`) it is today.
- `points_field`: Jira field holding story points. Default `customfield_10024`; override it when your tenant uses another field (for example `inputs set --inputs <file> points_field=customfield_10016`). Pace queries, scope queries, Pace and scope all read this one field, and `forecast` states it in `inputs.points_field` and `scope.points_field`. Warns when the field is empty on a ticket, and once more when it is empty on every open ticket in scope. Pass the inputs file to `queries scope --inputs` so the search asks for the same field.
- `jira_results_file`: saved raw results of the `queries` search, relative to the inputs file. Builds Pace when `history` is absent.
- `history`: weekly Pace, a list of `{"week": "YYYY-MM-DD", "points": N}`. Or `history_file`: path to that list, relative to the inputs file.
- `scope_file`: saved Jira search results (`{"issues": [...]}`) from `queries scope`. Optional `initiative`. When set, `forecast` adds a `scope` block: epic order proposed from Blocks links (blocker first), `remaining_points` per epic (open leaf tickets), `not_in_the_dates` (a total, and per epic row; points in Testing) and `warnings` (unpointed open tickets, Blocks cycles). `remaining_points` may then be omitted.
- `epic_order`: optional list of epic keys. Overrides the proposed order; show the proposal and ask the user to confirm or change it.
- `december_factor`: number above 0. Multiplies Pace for weeks that start in December only. Assumed, not measured.
- `freezes`: list of `{"start", "end", "name"?}` ISO dates, inclusive. They constrain the production cutover only, never epic dates. Assumed, not measured.
- `soak_weeks`: whole weeks between an epic finishing and production cutover. When unset, `production` has no date and its `note` says so; report that.
- `seed`: integer. The same seed and inputs give identical output.
- `trials`, `expiry_days`: optional. Defaults 10000 and 28. Expiry is the Forecast date plus `expiry_days`.

Dates are stored: `start_date`, `as_of`, every `history` week, and `saved_on` (stamped by `inputs set`), all ISO. Keep them so a backtest can be added later.

## Flow

The skill is user-invoked. The argument is an optional initiative or epic key. Never ask a question `inputs check` did not report.

1. Pick the inputs file (default `forecaster-inputs.json` in the workspace; reuse the one the user names).
2. With a key argument, run `python3 <this-skill>/forecaster.py inputs set --inputs <file> epic=<key>` (use `initiative=<key>` when it is an initiative; run `queries scope --key <key>` and set `scope_file`). The scope is now known; do not ask for it. When `inputs set` changes `epic` or `initiative` from a different saved key, it drops the scope-dependent inputs tied to the old key (`remaining_points`, `remaining_items`, `scope_file`, `epic_order`, and the other scope key) and keeps Pace history, `jira_results_file`, `as_of`, `assignee` and the rest. Rerun `queries scope --key <key>` and set `scope_file` again. Setting the same key again changes nothing. With no argument and no saved scope, ask which initiative or epics to plan, then `inputs set` the answer.
3. Run `inputs check --inputs <file>`. It prints `{"complete", "missing": [{"key", "question"}]}`. Ask the user exactly the `question` of each missing item, nothing else, then save each answer with `inputs set --inputs <file> key=value ...` (value is JSON when it parses, else text; dates are `YYYY-MM-DD`). `set` keeps every other key, including hand edits, and prints the remaining gaps. Repeat until `complete` is true. `inputs check` reports `scope`, `remaining` and `pace`; `inputs set` takes the stored names, so save the answers as follows: `scope` as `epic=<key>` or `initiative=<key>`; `remaining` as `remaining_points=<n>` (or `remaining_items=<n>` with the items unit); `pace` as `jira_results_file=<path>` (then `as_of`, `assignee` as asked). `start_date` and `assignee` are stored under their own names. Answers to optional factors (capacity share, December speed, freezes, soak, seed) are saved the same way when the user volunteers them; do not interview for them.
4. The user may edit the file by hand at any time. Tell them its path. A rerun with a complete file asks nothing: go straight to the Steps below.

## Unit

`--unit points` (default) or `--unit items`, or `unit` in the inputs file (the flag wins). With `items`, Pace is the count of finished leaf tickets per week under the same rules (unpointed tickets count and are not warned about), and remaining work is the count of open leaf tickets: give `remaining_items` instead of `remaining_points`, and scope rows carry `remaining_items` and `not_in_the_dates_items`. Output states the unit in `unit`. History values stay under the `points` key, in the chosen unit. Say which unit the dates use when you report them.

## Scope from Jira

`python3 <this-skill>/forecaster.py queries scope --key <initiative-or-epic>` prints Jira search operations (points read from `points_field`, default `customfield_10024`; `queries pace` and `queries scope` emit the same `{operation: jira.search_issues, payload}` shape). Run them with the Atlassian tool, merge the issues into one JSON file and set `scope_file`. The script never calls Jira.

## Steps

1. Build or read the inputs file. If Pace is not saved yet, run `queries pace`, run each emitted operation through the Atlassian tool (all pages, with changelog), save the raw results, and set `jira_results_file`. The script never calls Jira. Jira truncates the changelog it expands on a search: for any issue whose `changelog.total` exceeds the histories returned, fetch its remaining changelog pages and merge them into `changelog.histories` before saving. `forecast` refuses an incomplete changelog and names the ticket.
2. Run `forecast`. Never invent history. Empty history is refused: tell the user, do not guess a date.
3. Report `likely_date` (date by which 50% of runs finish), `due_date` (date by which 85% of runs finish), `expiry` and `refresh_trigger`. A single date is not a forecast.

## Epic chain

With `scope_file` and no `epic` or `remaining_points`, `forecast` runs every epic in order inside each trial (ADR 0004). `chain` has one row per epic, in order: `likely_date` (50%), `due_date` (85%) and `dates` (every level asked for). Each is a percentile of that epic's cumulative finish date across whole runs, never a sum of per-epic percentiles, and a later epic is never earlier than the one before. The top-level dates are the last epic's. Report each epic's pair. With `epic` set or no `scope_file`, you get the single-epic forecast. An `epic` that is not in the saved scope is refused (exit 2); rerun `queries scope` for it or clear `epic` to forecast the chain. `epic_order` may not repeat a key.

## Calendar and assumptions

`capacity_share` accepts a range `[low, high]` or one number (0 < low <= high <= 1). `forecast` prints `assumptions`: one entry per factor in use, each labelled "assumed, not measured". Repeat that label wherever you report the factor. `production` (top level and per chain row) holds `likely_date`, `due_date`, `dates` and `note`: epic finish plus `soak_weeks`, moved to the first day after any freeze it falls in.

## Pace rules

A ticket counts in the week (Monday start) it first entered Testing or Done, from the status changelog. Canceled never counts. Epics never count (the Pace query asks for `issuetype`). Parents of sub-tasks are skipped. Unpointed tickets are left out and listed in `warnings` and `unpointed`. Short or volatile history also adds a warning. Report every warning. A warning that trials hit the 520 week cap means Pace is too low for the remaining work: say the dates are not a forecast.

## Render the plan

`python3 <this-skill>/forecaster.py render --forecast <forecast.json> --prose <prose.json>` prints Confluence-ready markdown: a dates table (Likely date, Due date per epic), a Production cutover section (per epic production dates when `soak_weeks` is set, else the no-soak note; kept apart from epic finish dates), the four prose sections, how the dates were built, assumptions (each "assumed, not measured"), data-quality warnings and the expiry with its refresh trigger. Due date is stated as the date by which 85% of runs finish.

`prose.json` holds `deferred_scope`, `waits_outside_the_plan`, `risks` and `asks_of_manager` (each a string or list of strings) and an optional `title`. Write them from the interview, never invent them. A missing or empty section is refused (exit 2) and named; ask the user for it and rerun. Save the output to a local file for review.

## Write the Due date back to Jira

Only after the planner confirms. The script never calls Jira (ADR 0005); it prints edit descriptors and you run them. The edit sets each epic's Jira `duedate` to its Due date (85%), never the Likely date.

1. Save the `forecast` output to a file. Run `python3 <this-skill>/forecaster.py writeback --forecast <file> prepare` before asking anything. It prints the `edits` (epic, duedate) and the `code` that covers exactly those edits. Keep that `code`.
2. Show the user the edits and ask: write these due dates to Jira? Run nothing else yet.
3. Only on an explicit yes, run `writeback --forecast <file> emit --confirm <code>` with the same `code` from step 1. Never run `prepare` again after the approval. `emit` refuses (exit 2) when the code does not match the current file. If it refuses, or the forecast file changed, redo `prepare`, show the new edits and ask again.
4. Run each descriptor with `editJiraIssue` (`jira.edit_issue` in the ticketer `references/tool-map.md`; fill `<cloud_id>`). On no or silence, stop. Never invent a code.
