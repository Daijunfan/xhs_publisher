# Zhihu public editorial sources

The currently usable credential-free route is `https://daily.zhihu.com/`, using Zhihu's own public editorial JSON. It reads original selected answers/articles, images, author attribution, original Zhihu links and substantive public comments with their parent discussion. Editorial date is recorded as editorial selection date with day precision, never falsely presented as the original answer's creation time. Comments retain their own exact platform timestamp and reply context.

Default collection reads three days of editorial items every thirty minutes, with a bounded maximum of eight days. Comments shorter than eighty characters and simple promotions are excluded; longer explanations, references and substantive additions remain eligible even without high like counts. Identical records and media are deduplicated. Text and source links are preserved rather than summarized through an additional model call.

An author/organization homepage can be retained as a subscription identity, but the public route does **not** provide that author's complete activity or all Zhihu comments. Such collection fails explicitly with `AUTH_REQUIRED`, never silently falls back to editorial samples. Authorized main-site/API access requires separate verification before enabling complete author collection. No anti-bot signature, CAPTCHA, private data or login restriction is bypassed.

Candidate lists should distinguish demonstrated public authorship from verified profile identity and from a working full-author subscription. A public editorial sample is evidence for a candidate, not evidence that all of the author's content is available.
