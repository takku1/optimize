# External benchmark registry

External benchmark code and datasets are not silently treated as project
evidence. Each imported benchmark gets a versioned registry entry containing
its source URL, pinned revision, license, task scope, split policy, and known
execution risks.

The first registered reference is `mas-promptbench-v1.json`. It is a manifest-
only slice of MAS-PromptBench's frozen evaluation IDs. The upstream benchmark
requires model endpoints and framework dependencies; those are not vendored
into this package.
