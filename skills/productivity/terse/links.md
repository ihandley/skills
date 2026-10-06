# Links and references

Use the syntax defined by the loaded mode.

| Source contains | Output |
| --- | --- |
| A name already written in the source, plus a known URL | Link that name with the mode's syntax |
| A URL whose only candidate label is a path segment | Keep the raw URL |
| Identifier without a URL | Keep the exact identifier |
| Platform mention token or ID | Preserve the native mention |
| Person or channel name without a mention token or ID | Keep the name as text |

A name is words already written in the source. A URL path segment is not a name.
Never invent a URL, label, identifier, mention token, or platform syntax. When
the mode defines an auto-linked ticket or PR form, use it instead of wrapping
the identifier in a link.
