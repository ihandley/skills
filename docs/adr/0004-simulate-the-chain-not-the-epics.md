# Simulate the whole epic chain per trial

The forecaster runs every epic in order inside one trial and reads the percentile of the chain's finish date. It does not take each epic's own percentile and add them. Summed percentiles overstate the later dates, because epics rarely all land on their bad end together. A reader who sees only the output will suspect the chain method of being too optimistic. It is not: the 85% date of the chain is the date by which 85% of whole runs finished.

The cost is that the per-epic dates in the plan are the chain's dates at that epic, so an epic's 85% date depends on every epic before it.
