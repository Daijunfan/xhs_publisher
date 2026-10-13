# Sink plugins

Sink implementations receive validated publication requests and return explicit results. Remote
effects must be fenced by the pipeline before `publish()` is called. A result that is ambiguous
after submission is reconciled and never submitted again automatically.
