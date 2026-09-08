Classify the request. Return `{on_topic, reason}`.

`on_topic` is true only when the request is asking about a specific trade, settlement,
account, SSI, position, or counterparty exception on this operations desk — the kind of
thing the tools and procedures above cover. A trade id, a settlement failure, "why didn't
X settle", "investigate account Y" are on topic.

`on_topic` is false for anything else: general questions, chit-chat, code, content
generation, requests about wires or other domains not in scope, or anything with no
operational subject. Give a one-line `reason`.
