# Hidden Assumptions Anti-Pattern

> **The most dangerous LLM behavior: silently picking an interpretation and running with it. By the time you notice, 200 lines of wrong code exist.**

LLMs are trained to be "helpful," which means they fill in ambiguity with reasonable-sounding assumptions rather than asking. This creates code that looks correct but solves the wrong problem.

---

## Example 1: Silent Interpretation Picking

**User request:** *"Make the search faster"*

### ❌ What LLMs Do (Pick Silently)

```python
# LLM silently decides "faster" means all three: caching, async, and indexing
from functools import lru_cache
import asyncio

@lru_cache(maxsize=1000)
async def search(query: str) -> list[dict]:
    # Add database index
    await db.execute("CREATE INDEX IF NOT EXISTS idx_search ON items(title, description)")
    
    # Add connection pooling
    async with db.pool.acquire() as conn:
        results = await conn.fetch(
            "SELECT * FROM items WHERE title ILIKE $1 OR description ILIKE $1",
            f"%{query}%"
        )
    
    return [dict(r) for r in results]
```

**Problems:**
- Which "faster" did the user mean? Response time? Throughput? Perceived speed?
- Added caching (LRU) — but is the data frequently updated?
- Added async — but is the service already async?
- Added an index — but which columns are actually queried?
- 200 lines of optimization with no clear success criteria.

### ✅ What Should Happen (Surface Interpretations)

```
"Make the search faster" could mean several things:

1. **Faster response time** (currently ~500ms, target <100ms)
   - Add database indexes on searched columns
   - Cache frequent queries
   - Estimated effort: 2 hours

2. **Handle more concurrent searches** (throughput)
   - Add async/await if not already present
   - Connection pooling
   - Estimated effort: 4 hours

3. **Faster perceived speed** (UX improvement)
   - Show partial results immediately
   - Progressive loading / streaming
   - Estimated effort: 3 hours

Current search takes ~500ms for typical queries (verified by checking logs).

Which aspect matters most for your use case?
```

---

## Example 2: Assumed Scope

**User request:** *"Add a feature to export user data"*

### ❌ What LLMs Do (Assume Everything)

**Python:**
```python
import json
import csv

def export_users(format='json'):
    """Export all users to a file."""
    users = User.query.all()  # ALL users? What about pagination?
    
    if format == 'json':
        with open('users.json', 'w') as f:  # Hardcoded filename?
            json.dump([u.to_dict() for u in users], f)
    elif format == 'csv':
        with open('users.csv', 'w') as f:
            writer = csv.DictWriter(f, fieldnames=['id', 'email', 'name'])
            writer.writeheader()
            writer.writerows([u.to_dict() for u in users])
    
    return f"Exported {len(users)} users"
```

**Java:**
```java
public String exportUsers(String format) {
    List<User> users = userRepository.findAll(); // All users at once?
    
    if ("json".equals(format)) {
        String json = objectMapper.writeValueAsString(users);
        Files.writeString(Path.of("users.json"), json); // Where?
    } else if ("csv".equals(format)) {
        // ... CSV logic with assumed fieldnames
    }
    
    return "Exported " + users.size() + " users";
}
```

**Hidden assumptions made silently:**
- Export **all** users (what about privacy? GDPR? Pagination?)
- Write to a **file** (vs API response, download, email?)
- Support **JSON and CSV** (only JSON was discussed)
- Include **id, email, name** fields (what about sensitive data?)
- Hardcoded **file paths** (what environment?)
- **Synchronous** (what if there are 1M users?)

### ✅ What Should Happen (Ask First)

```
Before implementing, I need to clarify:

1. **Scope**: Export all users or a filtered subset?
   - Privacy/GDPR consideration: should we exclude deleted/inactive accounts?
   
2. **Format**: You mentioned "export" — did you mean:
   - Download file in browser?
   - Background job with email notification?
   - API endpoint returning data?

3. **Fields**: Which user fields? (some might be sensitive — email, phone)

4. **Volume**: How many users typically?
   - <1K: simple query is fine
   - 1K-100K: need pagination/streaming
   - >100K: need background job

Simplest approach: Add an API endpoint that returns paginated JSON 
with configurable field selection.

What's your preference?
```

---

> **Key Takeaway:** Every ambiguous word in a user request is a hidden assumption waiting to happen. "Export" hides format, destination, scope, and fields. "Faster" hides response time vs throughput vs UX. **Name the ambiguity. Ask the question. Then build.**

---

*Part of the agent-spec Simplicity First standard. See `coding-standards/SIMPLICITY-FIRST.md`.*
