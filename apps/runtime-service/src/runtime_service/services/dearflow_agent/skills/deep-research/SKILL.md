---
name: deep-research
description: Use this skill instead of search_web for ANY question requiring web research. Trigger on queries like "what is X", "explain X", "compare X and Y", "research X", or before content generation tasks. Provides systematic multi-angle research methodology instead of single superficial searches. Use this proactively when the user's question needs online information.
---

# Deep Research Skill

## Overview

This skill provides a disciplined, bounded methodology for conducting high signal-to-noise web research. **Load this skill BEFORE starting any content generation task** to gather necessary evidence from multiple angles while strictly respecting the research budget and avoiding endless crawling.

## Research Budget & Hard Limits

**Research must strictly adhere to the following bounded budget to ensure timely delivery:**

| Task Type | Target `search_web` Queries | Target `fetch_page` Reads | Maximum Allowable Searches |
|---|---|---|---|
| **Quick Investigation / Fact-finding** | 2 – 3 queries | 1 – 2 full reads | 4 queries max |
| **Topic Deep Dive / Industry Report** | 3 – 5 queries | 2 – 4 full reads | 6 queries max |
| **Comprehensive Multidisciplinary Research** | 4 – 6 queries | 3 – 5 full reads | 8 queries max |

> ⚠️ **Hard Ceiling**: Under NO circumstances should any single task exceed **8 searches** or **5 page fetches**. Once the budget is reached, you **MUST immediately stop researching and begin synthesizing and producing output**.

## Core Principles

1. **Signal-to-Noise Over Raw Quantity**: The quality of your output depends on selecting authoritative, high-density sources, NOT the raw count of web requests.
2. **Law of Diminishing Returns**: The first 3 to 5 well-targeted searches yield 80% of critical insights. Subsequent queries have rapidly diminishing returns. Stop when the core landscape and key figures are confirmed.
3. **No Endless Rabbit Holes**: Do NOT follow every secondary reference or tangential company mentioned in articles. Focus strictly on the user's primary prompt.
4. **Snippet-First Evaluation**: Evaluate search snippets first. Most facts (dates, specs, funding amounts, market rankings) are already clear in snippets. Only use `fetch_page` for deep analysis or conflicting claims.

## When to Use This Skill

**Always load this skill when:**

### Research Questions
- User asks "what is X", "explain X", "research X", "investigate X"
- User wants to understand a concept, technology, or topic in depth
- The question requires current, comprehensive information from multiple sources
- A single web search would be insufficient to answer properly

### Content Generation (Pre-research)
- Creating presentations (PPT/slides)
- Creating frontend designs or UI mockups
- Writing articles, reports, or documentation
- Producing videos or multimedia content
- Any content that requires real-world information, examples, or current data

## Research Methodology

### Phase 1: Broad Exploration (1-2 Queries)

Start with 1-2 broad searches to map the landscape:
1. **Initial Survey**: Search for the main topic with temporal awareness (`<current_date>`)
2. **Identify Core Dimensions**: Identify 2-3 essential pillars (e.g., technical breakthrough, market status, commercial bottlenecks)

### Phase 2: Targeted Deep Dive (2-3 Queries)

For each essential dimension, run 1 focused query:
1. **Specific Queries**: Use precise terms (e.g., `"humanoid dexterous hand 2026 DOF tactile sensor"`)
2. **Selective Reading**: Use `fetch_page` ONLY on the 2-3 most authoritative or data-rich reports.

### Phase 3: Diversity & Validation (1 Query if needed)

Resolve conflicting figures or verify industry challenges:
- Check concrete metrics (costs, yield, production volume, MTBF)
- Identify industry consensus vs. marketing hype

### Phase 4: Synthesis Check

Before proceeding to content generation, verify:

- [ ] Have I answered the core user intent with concrete data and examples?
- [ ] Have I captured the main technical bottlenecks and commercial reality?
- [ ] Have I reached or approached my search budget (3-6 queries)?

**Stopping Rule**: If you have sufficient information to address the user's prompt, or if you have reached your search budget, **STOP searching immediately and start synthesizing**. Gaps in non-essential trivia should be acknowledged in the final report under "Recommended Next Inquiries" rather than delaying delivery with more searches.

## Search Strategy Tips

### Effective Query Patterns

```
# Be specific with context
❌ "AI trends"
✅ "enterprise AI adoption trends 2026"

# Include authoritative source hints
"[topic] research paper"
"[topic] industry analysis"
"[topic] market report"

# Use temporal qualifiers — always use the ACTUAL current year from <current_date>
"[topic] 2026"
"[topic] latest"
```

### Temporal Awareness

**Always check `<current_date>` in your context before forming ANY search query.**

| User intent | Temporal precision needed | Example query |
|---|---|---|
| "today / this morning / just released" | **Month + Day** | `"tech news February 28 2026"` |
| "this week" | **Week range** | `"technology releases week of Feb 24 2026"` |
| "recently / latest / new" | **Month** | `"AI breakthroughs February 2026"` |
| "this year / trends" | **Year** | `"software trends 2026"` |

### When to Use fetch_page

Use `fetch_page` sparingly and selectively:
- ✅ The source is an authoritative in-depth technical whitepaper or official OEM report
- ✅ The snippet indicates vital data tables, architectural breakdown, or benchmarks needed for the report
- ❌ Do NOT fetch generic news aggregators, social forums, or pages where the snippet already answered your question

## Quality Bar

Your research is sufficient when you can clearly answer:
1. What is the current status and latest breakthrough?
2. What are the key metrics and real-world deployment cases?
3. What are the core challenges or limitations preventing scale?
4. Who are the representative players and what is their approach?

## Common Mistakes to Avoid

- ❌ **Endless rabbit holes**: Searching every secondary company, component, or tangent mentioned
- ❌ **Over-fetching**: Calling `fetch_page` on every single search result (wasting time and tokens)
- ❌ **Perfectionist trap**: Trying to crawl the entire internet before typing a single sentence
- ❌ **Ignoring the budget**: Continuing past 6-8 searches when diminishing returns have set in
- ❌ **Superficial single search**: Relying on 1 generic search without cross-checking key numbers

## Output

After completing research (strictly within 3-6 queries):
1. **Deliver the synthesis immediately**: Produce the structured report, document, or answer.
2. **Structured Evidence**: Cite specific sources and data points gathered.
3. **Open Questions**: If certain niche details remain unverified due to budget limits, note them transparently in an "Open Questions / Next Steps" section.
