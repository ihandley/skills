# Order

A list is held and the user has not accepted an order.

Each item depends on the previous one. `capture` records that. An item that may proceed while an earlier item is on hold is free: pass it to `order` with `--free`, or `free` that id.

A Slack reply, a manual deploy, or another person is a `block` reason on the item that needs it. Put that item where the wait can start. The wait is a reason to hold.

Run `order` with every top-level id. The user accepts the sequence.

Done when the user has accepted the order and every top-level item depends on the previous id, or is marked free.
