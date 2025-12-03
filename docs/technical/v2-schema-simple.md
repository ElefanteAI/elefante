# Memory Schema V2 - Simple Explanation

## What Changed and Why

### The Problem with V1 (Old Schema)
**V1 was a "junk drawer"** - everything went into a generic `custom` dictionary:

```python
# V1 - Everything dumped in "custom"
metadata = {
    "memory_type": "decision",
    "importance": 8,
    "tags": ["workflow"],
    "custom": {
        "category": "workflow-enforcement",  # What category?
        "enforcement_level": "mandatory",     # What does this mean?
        "applies_to": "all_tasks",           # How to search this?
        "user_preference": True,             # Mixed with other stuff
        "random_field": "whatever"           # No structure!
    }
}
```

**Problems:**
- ❌ Can't search by category (it's buried in `custom`)
- ❌ Can't filter by domain (no domain field exists)
- ❌ Can't track confidence (no confidence field)
- ❌ Can't measure relevance over time (no decay tracking)
- ❌ Mixed user preferences with technical metadata

---

## V2 Solution: Organized Layers

**V2 is like a filing cabinet** with 9 organized drawers:

### **Layer 1: Classification (What is it?)**
```python
domain: "user_profile"           # Top-level category
category: "preferences"          # Sub-category
memory_type: "decision"          # Specific type
```

**Think of it as:** `Filing Cabinet > Drawer > Folder > Document`

### **Layer 2: Quality Metrics (How good is it?)**
```python
importance: 8                    # How important? (1-10)
confidence: 0.95                 # How sure are we? (0-1)
```

### **Layer 3: Temporal Intelligence (How old is it?)**
```python
timestamp: "2025-12-03T16:00:00Z"
last_accessed: "2025-12-03T16:05:00Z"
access_count: 3
decay_rate: 0.1                  # How fast it becomes less relevant
```

### **Layer 4: Relationships (What's it connected to?)**
```python
related_memories: ["uuid1", "uuid2"]
contradicts: ["uuid3"]
supersedes: ["uuid4"]
```

### **Layer 5: Context (Where did it come from?)**
```python
source: "user_input"             # How was it created?
session_id: "uuid5"              # Which conversation?
intent: "store_preference"       # Why was it stored?
```

### **Layer 6: User Preferences (What does the user want?)**
```python
user_preferences: {
    "communication_style": "direct",
    "detail_level": "technical",
    "workflow_enforcement": True
}
```

### **Layer 7: Technical Metadata (System info)**
```python
embedding_model: "all-MiniLM-L6-v2"
embedding_dimension: 384
version: "2.0"
```

### **Layer 8: Status & Lifecycle**
```python
status: "active"                 # Is it still valid?
validation_status: "verified"   # Has it been checked?
```

### **Layer 9: Search & Discovery**
```python
tags: ["workflow", "quality-assurance"]
keywords: ["approval", "testing", "verification"]
```

---

## Real Example: Your Operational Rule

### V1 Way (Broken):
```python
{
    "content": "Never claim finished without user approval",
    "memory_type": "decision",
    "importance": 10,
    "tags": ["operational-rule"],
    "metadata": {
        "category": "workflow-enforcement",  # Lost in custom dict
        "enforcement_level": "mandatory"     # Can't search this
    }
}
```

### V2 Way (Structured):
```python
{
    "content": "Never claim finished without user approval",
    
    # Layer 1: Classification
    "domain": "workflow",
    "category": "quality_assurance",
    "memory_type": "decision",
    
    # Layer 2: Quality
    "importance": 10,
    "confidence": 1.0,
    
    # Layer 3: Temporal
    "timestamp": "2025-12-03T16:00:00Z",
    "decay_rate": 0.0,  # Never decays - always important
    
    # Layer 5: Context
    "source": "user_instruction",
    "intent": "enforce_workflow",
    
    # Layer 6: User Preferences
    "user_preferences": {
        "workflow_enforcement": True,
        "requires_approval": True
    },
    
    # Layer 9: Discovery
    "tags": ["operational-rule", "workflow", "quality-assurance"],
    "keywords": ["approval", "testing", "verification", "complete"]
}
```

---

## Why This Matters

### Searchability
**V1:** "Find all workflow rules" → Can't do it (buried in `custom`)  
**V2:** "Find all workflow rules" → `domain="workflow" AND category="quality_assurance"`

### Filtering
**V1:** "Show high-confidence decisions" → Can't do it (no confidence field)  
**V2:** "Show high-confidence decisions" → `memory_type="decision" AND confidence > 0.9`

### Temporal Intelligence
**V1:** "What's still relevant?" → Can't tell (no decay tracking)  
**V2:** "What's still relevant?" → Calculate: `importance * (1 - decay_rate * age)`

### User Preferences
**V1:** "What are my communication preferences?" → Search all memories, hope for the best  
**V2:** "What are my communication preferences?" → `domain="user_profile" AND category="preferences"`

---

## Current Status

### ✅ Completed:
1. V2 schema designed and documented
2. [`memory.py`](Elefante/src/models/memory.py) updated with V2 models
3. [`vector_store.py`](Elefante/src/core/vector_store.py) updated to store V2 metadata
4. 21/21 validation tests passed

### ⚠️ In Progress:
1. Update [`orchestrator.py`](Elefante/src/core/orchestrator.py) - remove `custom` dict usage (line 164)
2. Update [`graph_store.py`](Elefante/src/core/graph_store.py) - add V2 node types
3. Migrate 43 existing V1 memories to V2 format

### 🎯 Goal:
Store your operational rule with full V2 structure so it's:
- Easily searchable
- Never forgotten (decay_rate=0)
- Properly categorized
- Linked to quality assurance concepts

---

## Bottom Line

**V1 = Messy junk drawer**  
**V2 = Organized filing system with smart search**

The lock issue is fixed. Now we're upgrading the filing system so memories are properly organized and searchable.