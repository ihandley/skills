# Accept a candidate by a rule walk

A candidate stays off disk until `compressor` accepts it. The script inventories the pre-image, then walks a fixed list of rules against the candidate. Each rule returns pass or its defects. The walk stops at the first failing rule and returns every defect of that rule. Apply writes the set only when a full walk returns no defects, and it writes every file or none. The agent proposes which leftover sentences are padding. It does not decide that the candidate is acceptable.

This replaces the earlier decision that the agent accepts by naming the padding removed and the signal that survived. That judgment had no control behind it: the script checked structure, and a passing check said nothing about a deleted obligation. A quote proves the surviving sentence exists and does not prove the obligation moved, so a pass is not proof that signal survived.

The loop stays in the procedure. The script calls no model, stores no report, and counts no tries. An identical defect list, or a second answer to the same rule, ends the run with the files untouched.

Letting the agent edit the files directly was rejected because the script's walk would no longer be the gate.
