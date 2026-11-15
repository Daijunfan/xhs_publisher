# LinkedIn public research sources

Reads public guest pages for person, organization, school and showcase accounts. JSON-LD `SocialMediaPosting` supplies the original text, canonical post URL, author and exact publication timestamp. Public page images and logos use the same bounded media path as other collectors. A page's canonical account alias is respected; another author's repost is excluded.

Default policy: poll every two hours; stagger cold starts; retain substantive original posts (at least 160 characters); exclude recruiting, giveaways and registration promotions; use only explicit platform publication times. Missing dates are not replaced with the time of discovery. At most ten public posts from the past 90 days and four images per post are read per collection, including low-frequency research accounts. Content fingerprints prevent repeated media downloads for unchanged complete posts; incomplete media is retried on the next poll while text remains readable. This is an information-density filter, not verification that every claim is correct.

No cookies, private member fields, contact extraction, login automation or account actions are used. HTTP 401/403/999 produces an access-required status; 429 backs off. No alternate IP or browser fingerprint is tried. Public guest visibility can change, so a healthy process does not establish that every target has data.

Core remains the subscription authority. The plugin returns ordinary `SourceRecord`/`CollectBatch` data and never writes the application database, sends messages or receives a Core control token.

The shared channel contract accepts images up to 8 MiB. Oversized or unsupported
original media retains its public source URL and a structured validation failure;
it is not repeatedly downloaded as a transient failure. Text collection continues.
