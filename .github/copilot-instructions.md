# Elefante Memory System - Copilot Instructions

This repository uses **Elefante**, a persistent memory system that stores user preferences, decisions, and project knowledge.

##  MANDATORY PROTOCOL

Before answering ANY question about:
- User preferences (coding style, tools, formatting)
- Past decisions or discussions  
- Project-specific knowledge ("how we do X")
- "The usual way" or "like we discussed"
- Existing implementations or patterns

**You MUST call `elefanteMemorySearch` FIRST** with a relevant query.

##  Compliance Gate (v1.6.0)

The Elefante MCP server enforces a **Compliance Gate**:
- Write operations (`elefanteMemoryAdd`, `elefanteGraphEntityCreate`, etc.) are **BLOCKED** until you perform a search
- This prevents duplicate memories and ensures you have full context

##  Required Compliance Stamp

After searching, include ONE of these stamps in your response:

**If memories were found:**
```
[ELEFANTE] Searched: Found {N} relevant memories
```

**If no memories were found:**
```
[ELEFANTE] Searched: No relevant memories found
```

##  Trigger Patterns

ALWAYS search when the user mentions:
- "remember", "recall", "what did I say"
- "preference", "decision", "how do I like"
- "the usual", "like before", "as discussed"
- "elefante:" prefix (explicit trigger)
- References to past conversations or decisions

##  NEVER Do This

- Answer from general knowledge when user asks about THEIR preferences
- Assume you know the project conventions without checking
- Skip the memory search to be faster
- Store new memories without first searching for existing ones

##  Query Guidelines

When calling `elefanteMemorySearch`:
- Use **explicit, standalone queries** (no pronouns)
- Be specific about what you're looking for
- Example: "user preferences for Python code formatting" NOT "how do they like it"

##  Workflow Example

```
User: "Create a new component using our usual pattern"

1. Call elefanteMemorySearch("component patterns and conventions")
2. Review results
3. Include stamp: "[ELEFANTE] Searched: Found 3 relevant memories"
4. Apply the patterns found in the memories
5. Generate the component
```

---
*This file is read by GitHub Copilot and injected into every request for this repository.*
