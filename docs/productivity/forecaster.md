## What it does

Forecaster gives you a Likely date and a Due date for each epic in a chain, simulated from your own saved weekly Pace. The agent gathers the inputs and talks to you. A script does all the arithmetic, never touches the network, and never holds a credential.

The constraint is that every date is a Forecast, not an estimate. The Likely date is the date by which half of the simulated runs finish. The Due date is the date by which 85% of them finish, and it is the only date written to Jira. A Forecast carries an expiry and a refresh trigger, and a single date is never reported alone. Empty history is refused, so the agent never guesses a date. Any factor you assume, such as a Capacity share, a December factor or a freeze, is labelled assumed, not measured wherever it appears.

## When to reach for it

Type `/forecaster`, and the agent will not reach for it. You can pass an initiative or epic key as the argument.

Reach for it when you need dates for an epic or a chain of epics, backed by your own throughput rather than a gut estimate, or when you need a plan to hand to a manager. It asks only the questions your saved inputs file still leaves open, and a rerun with a complete file asks nothing. It is the wrong tool for sizing a single ticket or for reporting what already shipped.

## Common questions

**Where do my answers live?**
In an inputs file, `forecaster-inputs.json` in the workspace by default. You can edit it by hand at any time, and the agent tells you its path.

**Where does Pace come from?**
From the weekly points you finished over the 12 whole weeks before the as-of date, read from the Jira status changelog. Holiday weeks stay in as zero. Unpointed tickets are left out and listed as warnings.

**Can I forecast by ticket count instead of points?**
Yes. Use the items unit. Pace is then finished leaf tickets per week, and the agent says which unit the dates use.

**What is Capacity share?**
The fraction of your Pace one body of work gets, given as a range or one number. It is assumed, not measured.

**How is a chain of epics handled?**
Every epic runs in order inside each simulated run, so a later epic is never earlier than the one before. Each date is a percentile across whole runs, never a sum of per-epic percentiles. Epic order is proposed from Blocks links, and you confirm or change it.

**Can the plan show sprints?**
Yes. Save a sprint length in weeks and a date a sprint starts on. Each epic's Likely and Due dates are then also reported as the sprint they fall in, and the plan gains a Sprints section. The calendar dates do not move, and with no sprint inputs the output is the same as before. The agent only asks for the cadence when you say you want sprints.

**Does it write to Jira?**
Only the Due date, and only after you confirm. The agent shows the list of edits first. A confirmation code ties the write to the exact dates you saw, so a stale code is refused.

**Does it need credentials?**
No. It prints the Jira searches and edits, and the agent runs them with its own Atlassian tool.

**What Python does it need?**
3.11 or newer. On an older interpreter it exits and names the problem.

**Can I get a plan document?**
Yes. It renders Confluence-ready markdown with a dates table, deferred scope, waits outside the plan, risks, asks of your manager, assumptions, warnings and the expiry. It refuses a missing section, and the agent asks you for it instead of inventing one.

## It's working if

- The agent asks only for inputs your file lacks, and nothing on a complete rerun.
- Each epic gets a Likely date and a Due date, plus the expiry and refresh trigger.
- With a sprint cadence saved, each epic also shows the sprint of each date.
- Every assumed factor is labelled assumed, not measured.
- Warnings about unpointed tickets or short history are reported, not dropped.
- With no history, the agent tells you so and gives no date.
- Nothing is written to Jira until you say yes to the listed Due dates.
