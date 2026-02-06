# Engineering Memory: Lessons Learned

> A document for future builders - human and AI alike.

This captures what we learned while building the memory system for an AI companion. The goal is not just to document what we built, but *how we thought about it* - so you can build on this thinking.

---

## The Goal

We're building an AI companion that makes people feel **known**.

Not stored. Not analyzed. Known.

The way a good friend knows you after years of conversations.

---

## The Original System

We started with a simple approach:

```
User says something
    → Observation agent extracts facts
    → Store as ProfileFact(category, key, value)
    → Append to profile
```

**Example output:**
```
emotions | a1b2c3d4 | Simon is feeling overwhelmed by the job hunting process
emotions | e5f6g7h8 | Simon is feeling frustrated and overwhelmed
emotions | i9j0k1l2 | Simon is feeling overwhelmed and frustrated
```

### What Was Good

- Simple architecture
- Captured organic conversation (users talk about anything)
- Low engineering overhead
- The observation agent noticed real things

### What Was Broken

1. **No sense of time** - "Simon is overwhelmed" without knowing *when* or *for how long* is meaningless

2. **Unbounded growth** - Every observation got a unique hash key, so nothing was ever updated, only appended. The profile grew forever with redundant entries.

3. **Clinical language** - Observations read like a psychologist's assessment, not a friend's understanding
   - Bad: "Simon is experiencing feelings of overwhelm indicating emotional distress"
   - Better: "He's been grinding through rejections for weeks. Today felt heavier."

4. **No consolidation** - 50 entries about being overwhelmed, but no synthesis into meaning

---

## The Temptation (And Why We Avoided It)

The first instinct was to over-engineer:

```python
# We almost built this:
class UserStory:
    identity = {
        "core_fears": [...],
        "core_desires": [...],
        "wounds": [...],
    }
    current_chapter = {
        "title": "...",
        "phase": "beginning/middle/turning",
        "active_threads": [...]
    }
    arc = {
        "phases": [...],
        "turning_points": [...]
    }
    patterns = [...]
```

This is seductive because it feels complete. But it's wrong because:

1. **Too rigid** - Forces conversations into predefined boxes
2. **Assumes we know what matters** - But users talk about *anything*
3. **Loses the organic nature** - Friendship isn't structured data
4. **Complex to maintain** - Every edge case needs handling

**The insight:** The original system was 80% right. It just needed timestamps, better language, and periodic consolidation. Not a new architecture.

---

## The Simpler Solution

### Change 1: Add Timestamps

```python
# Before
ProfileFact(category, key, value)

# After
ProfileFact(category, key, value, observed_at)
```

Now you know *when* something was true. "Overwhelmed in January" vs "Still overwhelmed in March" tells a different story.

### Change 2: Fix the Observation Prompt

The prompt shapes everything. Current prompt produces clinical notes. We need journal entries.

**Before:**
```
OBSERVATION: [category] | [what you learned]
```

Produces: "Simon is experiencing feelings of overwhelm indicating emotional distress"

**After:**
```
Write like you're keeping a journal about a friend - not clinical notes.

Include a sense of time:
- "Still struggling with..." (ongoing)
- "First time he mentioned..." (new)
- "Again today..." (pattern)
- "Less than before..." (changing)

OBSERVATION: [category] | [what you noticed, naturally, with temporal sense]
```

Produces: "Still grinding through rejections. Eight weeks now. But he joked about it today - first time he's been light about it."

### Change 3: Periodic Consolidation (The Diary)

Don't change storage. Add a process.

Weekly, run a consolidation:
```
Read all recent observations
    → LLM writes a diary entry
    → Store in DiaryEntry table
    → Optionally prune old raw observations
```

The diary becomes the memory. Raw observations are working notes that fade.

**Diary prompt:**
```
Here are observations about {name} from the past week:
{observations_with_timestamps}

Write a short reflection (2-3 paragraphs) about how they're doing.
Not a summary of facts. A reflection from someone paying attention.
What's the thread? What's changing? What are you holding for them?
```

---

## The Philosophy Behind The Engineering

### Storage vs Memory

A database stores facts. A companion holds stories.

"Simon is overwhelmed" stored 50 times = noise.
"He's been drowning in rejections for two months, but last week something cracked - he laughed for the first time" = understanding.

The system should produce the second, not the first.

### Time Is Meaning

The same fact means different things at different times:

| Observation | Day 1 | Day 90 |
|-------------|-------|--------|
| "Simon is tired" | Jet lag | Maybe depression |
| "Simon is overwhelmed" | Normal for new situation | Chronic struggle |
| "Simon laughed" | Ordinary | Breakthrough |

Without timestamps, you can't know which interpretation is true.

### Consolidation Is Compression

Humans don't remember every conversation. They remember the *shape* of a relationship:

- "We started rocky but became close"
- "She always deflects when things get real"
- "That trip changed everything"

The diary practice mimics this. Raw observations are the daily experience. Diary entries are the compressed meaning. Over time, diary entries become the memory.

### Simplicity Wins

Every complex system we considered had the same flaw: it assumed we knew what structure mattered.

But users are unpredictable. They talk about their ex, then their job, then a random memory from childhood, then what they ate for lunch.

A simple system that captures everything loosely beats a complex system that forces things into boxes.

The magic isn't in the data model. It's in:
1. What you notice (observation prompt)
2. When you noticed it (timestamps)
3. How you make meaning (consolidation/diary)

---

## Technical Summary

### Data Model

```python
# Keep this simple
class ProfileFact:
    user_id: int
    category: str      # "emotions", "circumstances", "patterns", etc.
    key: str           # hash of content (for dedup) or semantic key
    value: str         # the actual observation
    observed_at: datetime  # ADD THIS
    confidence: float

class DiaryEntry:
    user_id: int
    entry_date: date
    content: str       # AI-written reflection
```

### Observation Prompt Principles

1. Write like a friend's journal, not clinical notes
2. Include temporal language (still, first time, again, less than before)
3. Notice patterns, not just facts
4. Let mundane things pass - not everything is significant

### Consolidation Process

1. Run weekly (or after N conversations)
2. Gather recent observations with timestamps
3. Generate diary entry via LLM
4. Store diary entry
5. Optionally prune observations older than X days (diary holds the meaning now)

### Context Building

When generating responses, build context from:
1. Recent diary entries (the consolidated understanding)
2. Recent observations (the fresh details)
3. Any relevant older observations retrieved by semantic search

The "5 minute story" test: If you had to describe this user in 5 minutes, what would you say? That's your context.

---

## What We Didn't Build (Yet)

Some ideas we explored but deferred:

1. **Semantic deduplication** - Check if new observation is similar to existing before storing. Could reduce redundancy but adds complexity.

2. **Pattern detection** - Automatically identify recurring themes. Currently handled by prompting the observation agent to notice patterns.

3. **Multi-timezone support** - Currently assumes single timezone. Would need user timezone storage and UTC conversion.

4. **Structured identity layer** - A fixed set of "core facts" (name, origin, fears, desires). Deferred because it's rigid. Better to let this emerge from observations.

5. **Arc tracking** - Explicit "phases" and "turning points" structure. Deferred because diary entries naturally capture this.

---

## For Future AI Assistants

If you're an AI working on this codebase:

1. **Read the soul documents first** - `soul_for_Dev.md` and `soul_memory.md` contain the philosophy. The code serves the philosophy, not the other way around.

2. **Resist complexity** - The temptation is always to add structure. Usually the answer is a better prompt.

3. **Test with real conversations** - Synthetic tests miss the organic weirdness of real human conversation.

4. **The goal is "known", not "stored"** - Every decision should serve the question: "Does this help the user feel understood?"

5. **Time matters everywhere** - If you're storing something without temporal context, you're probably missing meaning.

---

## For Human Developers

1. **The diary is the product** - Raw observations are working memory. The diary entries are what matter long-term. Invest in the consolidation prompt.

2. **Prompt engineering > data modeling** - We got more improvement from rewriting observation prompts than from any schema change.

3. **Watch real usage** - The `/debug` and `/scheduled` commands exist for a reason. Watch what the system actually produces. Adjust prompts based on real output.

4. **The soul documents are requirements** - They're not just philosophy. They define what "correct" means for this system.

---

*Written after a conversation about rebuilding the memory system. The best solution was the simplest one: add timestamps, improve the prompts, and periodically consolidate into diary entries. The architecture didn't need to change. The thinking did.*
