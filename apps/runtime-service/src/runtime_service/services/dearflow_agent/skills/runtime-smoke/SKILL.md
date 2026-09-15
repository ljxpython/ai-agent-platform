---
name: runtime-smoke
description: Validate the Dear Agent TXT input, approval and artifact delivery loop.
---
Read the user input from /workspace/uploads/. Ask about missing requirements first.
Write the requested result under /workspace/work/, using approved tools.
When execution is required, run python /skills/runtime-smoke/check_text.py /workspace/work/result.txt.
Publish the verified text with present_artifacts. This is a platform smoke skill, not a migrated public skill.
