# Reddit public subscriptions

This adapter reads a community's `new/.rss` feed or a public user's `submitted/.rss` feed. It does not use private endpoints, replay browser sessions or bypass access challenges. Source identities normalize `/r/name`, `/u/name` and homepage aliases; multiple-community feeds, post URLs and non-Reddit hosts are rejected.

Atom entry IDs, authors, original publication times and permalinks survive mapping. HTML becomes readable text with source links; only Reddit image hosts are downloaded. Posts are deduplicated through the existing fingerprint checkpoint. The adapter does not invent votes, member counts or a complete comment tree.

Feed requests are serialized with a 15-second minimum interval. A 429 starts a shared 15-minute cooldown, in addition to scheduler backoff; waiting never bypasses a collection deadline. 403 is an explicit access failure. These public feeds may become unavailable as Reddit changes support. Configuration applied, publicly visible community identity, successful retrieval and successful Bot publication are different states.

Use the ordinary Core source add/update/remove operations. `agents-reddit` is created through the existing subscription projection; private YAML and other credentials are preserved. Run `tests/unit/plugins/sources/test_reddit.py` and the Aexus subscription tests with disposable state.
