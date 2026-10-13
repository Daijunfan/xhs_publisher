# Source plugins

Each source directory contains one manifest and one public `SourcePlugin` class.
Plugins perform bounded collection calls only; scheduling, persistence, retries,
queues, processing, and publishing belong to the application core.
