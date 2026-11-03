# Write the files only when the candidate is defended

A candidate stays off disk until `compressor` accepts it. The script checks that candidate against the pre-image and is the only writer. It writes every file in the set, or it writes none. The agent may accept only by naming the padding removed, the signal that survived, and that the candidate added nothing. If it cannot name a script failure or a signal loss to answer, the run stops and the files stay as they were.

The old behavior was to always write a shorter file and put back anything an inventory said was lost. That was rejected because a shorter file can still be worse. Letting the agent edit the files directly was rejected because the script's checks would no longer be the gate.
