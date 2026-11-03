# Compress existing files, and leave outward drafts to terse

`compressor` takes an existing Markdown or plain-text file by path. `terse` takes Slack, email, Jira, Confluence, and pull-request text being drafted or rewritten in the conversation. A document may get harder for a person to skim. An outward draft may not, because readability and tone are gates there. The path is the boundary so a pasted pull-request description cannot enter `compressor`.

One tool for every kind of text was rejected because it collides with `terse`. Letting `terse` own every human-facing file was rejected because a README or a design doc is a document.
