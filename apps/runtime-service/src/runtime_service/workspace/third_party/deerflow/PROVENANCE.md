# DeerFlow source provenance

Upstream: https://github.com/bytedance/deer-flow
Commit: cc664451f03140b376611f329ae400c313530bdb
License: MIT (complete notice in LICENSE).

| Source | Destination | SHA256 |
| --- | --- | --- |
| backend/packages/harness/deerflow/sandbox/acquire_serialization.py | workspace/acquire_serialization.py | 8cfed7b1aa098be5bb376f459247f1d92636606ba45a9902d9d186570147f9d2 |
| backend/packages/harness/deerflow/sandbox/path_patterns.py | workspace/path_patterns.py | 09925243e0ef0ccf6380840f4ef55aa6b3f201ccf0989f818e2da6c0b16ec3fa |
| LICENSE | workspace/third_party/deerflow/LICENSE | b23dff4d4bac8d17b6efaaa7e88c2b730149c4dda45699ce676b719cfdffe7e1 |

Modules are copied unchanged; no deerflow runtime dependency. Node lifecycle and file transitions use AcquireSerializer; model-facing output uses replace_output_path_matches. Tests adapt imports to runtime_service and use a local ContextVar instead of DeerFlow trace infrastructure.
