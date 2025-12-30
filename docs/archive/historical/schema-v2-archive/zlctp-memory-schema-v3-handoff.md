# ZLCTP Handoff Package – Elefante Memory Schema V3: Three-Layer Architecture

**Generated**: 2025-12-06 (UTC)

---

## 1.  Project One-Liner

Designing a universal, measurable, three-layer memory classification system (SELF/WORLD/INTENT) for Elefante's "second brain" dashboard that enables clean graph visualization and context-aware agent responses for any user.

---

## 2.  Current Status Snapshot

**Timestamp**: 2025-12-06 ~20:00 UTC

**Last Completed Action**: Defined 9 measurable sublayers (3 per layer) using regex/keyword detection + established 4 connection types (structural, entity, temporal, causal) with scoring logic.

**VERY NEXT Action**: Implement schema changes in `src/models/memory.py` - add `layer` and `sublayer` fields, then create classification logic in `src/core/orchestrator.py` that auto-detects layer/sublayer from memory content using the regex/keyword rules we defined.

---

## 3.  Core Understanding & Mental Model

### The Fundamental Insight
Elefante is NOT a database - it's a **second brain** that helps AI agents understand users. The classification problem is NOT "how to organize files" - it's **"what makes a memory useful to inject into agent context?"**

### The Three Questions Every Agent Must Answer
1. **Who am I talking to?** -> SELF layer
2. **What do they know?** -> WORLD layer
3. **What should I do?** -> INTENT layer

### The Visual Problem We're Solving
Current dashboard shows 107 nodes in chaotic "soup" - tangled, unreadable. User demands "tight, neat, clean" with "electric effect" when connections illuminate. This requires hierarchical structure, not flat graph.

### The Connection Philosophy
All memories belong to ONE user (Jaime) -> everything is connected by default. The agent must INFER connections it doesn't see yet. Classification exists to:
- Create visual clusters in dashboard
- Enable layer-aware retrieval (get SELF+WORLD+INTENT for every query)
- Measure connection strength between memories

### Critical Design Principles
- **Agnostic**: Must work for ANY user, ANY situation, ANY intent
- **Measurable**: "Can I code this?" = yes -> proceed
- **No overfitting**: No hardcoded categories like "jaime-preferences" or "elefante-project"
- **Entity-centric**: Memories connect through shared entities (from Kuzu graph)
- **Agent-as-brain**: The LLM agent classifies memories, not redundant LLM API call

### What We Rejected
-  Domain/category/subcategory (89 of 91 memories had domain="reference" - useless)
-  "Illuminates" as freeform text (too vague, can't code it)
-  Hardcoded user-specific categories (overfitting)
-  `memory_type` with 8 values (redundant with `layer`)

---

## 4.  Full Decision & Learning Log

### Turn 1-3: Initial Overfitting Problem
**User**: "This is primitive! I need agnostic architecture. You're overfitting with hardcoded rules."

**I proposed**: domain (6 types), category (freeform), memory_type (8 types)

**User rejected**: Too many buckets, not thinking from first principles.

### Turn 4-6: The One Question
**I asked**: "If you have only one question to improve classification, what is it?"

**User**: "When you store a memory, what do you want to happen LATER because of it?"

**Answer**: Elefante automatically injects relevant memories to help agent make better decisions. This is MCP-driven, LLM-agnostic.

### Turn 7-9: The Intent Discovery
**I proposed**: 4 intents (guide, warn, inform, connect)

**User**: "All memories belong to same user. If you don't see connection, you're ignorant. Close the gap."

**Insight**: Classification isn't about buckets - it's about inferring connections.

### Turn 10-12: The Three Layers Emerge
**I proposed**: SELF (who), WORLD (what), INTENT (do)

**User**: "Good work! Carry on."

**Validation**: These three answer the questions every agent needs.

### Turn 13-15: Importance vs Layer
**User**: "Is this optimal? Does importance already solve this?"

**Discovery**: Importance prioritizes individual memories (9-10 always injected). Layer enables balanced retrieval across all three questions.

### Turn 16-18: The Protocol Understanding
**User**: "User calls 'Elefante remember this <raw memory>' - agent must POSITION it with context."

**Insight**: `layer` enables context-aware injection beyond semantic similarity. Agent classifies memory at storage time to position it in graph structure.

### Turn 19-21: Reading All 91 Memories
**User**: Attached `memories_complete_export_91.csv`

**I analyzed**: 
- 89 have domain="reference" (useless)
- 7 duplicates ("Python 3.12" repeated)
- Mix of Jaime identity, Elefante lessons, protocol rules, debugging methodologies

**User**: "These belong to same person. Everything connects. Build way to capture context augmentation."

### Turn 22-24: Visual Requirements
**User**: Shows dashboard screenshot - chaotic soup with 107 nodes

**User**: "I deeply care about visual and details. Tight, neat, clean. Electric effect is essential UI feature."

**Requirement**: Clean clusters that PULSE when related memories illuminate together. Hierarchical structure (big anchor nodes -> small memory nodes orbiting).

### Turn 25-27: The Universal Architecture
**I proposed**: Three layers with sublayers, visual color coding, hierarchical graph

**User**: "Good start but soulless. 'Values' seriously? Get real. Measurable, effective. Define them."

### Turn 28-30: The 9 Sublayers (Measurable)
**I defined**: 
- SELF: identity (regex: "is" + entity), preference (regex: prefer|like|hate), constraint (regex: must|never|always + SELF)
- WORLD: fact (declarative), failure (keywords: bug|error|fail), method (keywords: technique|protocol|method)
- INTENT: rule (uppercase NEVER|ALWAYS|MUST), goal (future tense), anti-pattern (don't|avoid)

**User**: "That is one layer. Now let's talk about connection - this can be tricky."

### Turn 31-33: Connection Logic
**I proposed**: 4 connection types with scoring:
1. Structural (layer/sublayer proximity): same sublayer=1.0, same layer=0.4-0.7, different=0.0
2. Entity (shared concepts in Kuzu): 0.2 per shared entity (max 1.0)
3. Temporal (time proximity): within 1hr=0.8, 1day=0.5, 1week=0.3
4. Causal (one references another): explicit=1.0, implicit=0.5

**Combined score**: `max()` not `sum()` (don't double-count same connection)

**Cross-layer rules**: SELF->INTENT=strong, WORLD->INTENT=strong, others=weak/medium

**Question raised**: How to measure causal connections programmatically?

**Status**: Parked for continuation.

---

## 5.  Hard Requirements & Non-Negotiables

1. **"CAN I CODE THIS?" test** - If answer is no, reject the approach
2. **Agnostic architecture** - Must work for any user, any situation, any intent
3. **No overfitting** - No hardcoded user-specific or project-specific categories
4. **Measurable everything** - Every classification rule must be regex/keyword/syntax testable
5. **Visual = tight, neat, clean** - No chaotic soup, hierarchical clusters required
6. **Electric effect** - When clicking node, related memories must "light up" with visual pulse
7. **Agent-as-brain** - LLM agent calling MCP addMemory classifies the memory, no redundant API call
8. **Entity extraction essential** - Kuzu graph stores entities, connections measured through shared entities
9. **All memories connect to user** - User entity is implicit root of entire graph
10. **Three layers non-negotiable** - SELF, WORLD, INTENT (answering who/what/do questions)

---

## 6.  Soft Preferences & Observed Style

### User (Jaime) Communication Style
- **Direct, brutal honesty**: "That's soulless", "Get real", "ARE YOU NUTS?"
- **Zero tolerance for fluff**: Hates explanations without substance
- **Demands conciseness**: "BE EXTREMELY CONCISE. BE SMART."
- **Loves structure**: Tables, bullets, clear headers
- **Challenges assumptions**: Constantly pushes back to force deeper thinking
- **Values visual detail**: Cares deeply about how things LOOK in UI

### Interaction Pattern
- Jaime asks one sharp question -> I answer -> Jaime validates or rejects -> Repeat
- When Jaime says "good work, carry on" = proceed with confidence
- When Jaime says "stop, let's refine" = we're off track, back to basics
- Uses ALL CAPS for emphasis on critical points

### Technical Sophistication
- Senior AI/data science leader (20 years experience)
- Strong in: AI concepts, product logic, LLMs, agents, RAG
- Self-identifies as "junior" in: infrastructure, server tooling, packaging
- Expects agent to act as senior DevOps engineer

---

## 7.  All External Materials

### File: `memories_complete_export_91.csv`
**Location**: `c:\Users\JaimeSubiabreCistern\Documents\Agentic\Elefante\data\memories_complete_export_91.csv`

**Structure**: 489 lines, 91 memories with fields:
- id, content, created_at, created_by
- domain, category, memory_type, subcategory (OLD schema - to be replaced)
- importance, urgency, confidence
- tags, keywords, entities, status
- Many other metadata fields

**Key Observations**:
- 89 of 91 have `domain: "reference"` (useless classification)
- 7 duplicates: "Python 3.12 introduced improved error messages" repeated
- 1 test memory: "This is a test memory for temporal decay validation"
- Content types: Jaime identity (name, style, values), Elefante project lessons, debugging protocols, Three Gaps framework, workspace hygiene rules

**Sample memories** (representative):
1. `"User is a senior applied AI/data science leader..."` (SELF.identity)
2. `"User communication style: Direct, technical, compact..."` (SELF.constraint)
3. `"NEVER delete files, move to ARCHIVE..."` (INTENT.rule)
4. `"THREE GAPS - Core AI Failure Pattern..."` (WORLD.method)
5. `"Kuzu 0.11.x Breaking Change..."` (WORLD.failure)

### Dashboard Screenshot
**Attached**: Image showing current dashboard state
- 107 nodes in chaotic "soup" layout
- Tangled edges everywhere
- Labels overlapping, hard to read
- No clear clusters or hierarchy
- User calls this "disgusting thing we are going to make beautiful"

---

## 8.  Work Already Delivered or Built

### Final Schema Design
```python
class Memory:
    content: str              # The raw memory text
    layer: str                # "self" | "world" | "intent"
    sublayer: str             # 9 possible values (3 per layer)
    importance: int           # 1-10 activation weight (unchanged)
    entities: List[Entity]    # Extracted from Kuzu graph (unchanged)
    created_at: datetime      # Timestamp (unchanged)
```

### The 9 Sublayers (Codeable Classification Rules)

**SELF Layer:**
- `identity`: Contains "is" + user entity (regex: `\bis\b.*\b(Jaime|user)\b`)
- `preference`: Contains preference verbs (regex: `prefer|like|hate|love|value`)
- `constraint`: Contains modal verbs about behavior (regex: `must|never|always` in context of SELF)

**WORLD Layer:**
- `fact`: Declarative statement, no modals, no "I"
- `failure`: Contains error keywords (keywords: `bug|error|fail|problem|issue|crash|break`)
- `method`: Contains process keywords (keywords: `technique|protocol|method|process|workflow|framework`)

**INTENT Layer:**
- `rule`: Uppercase absolute modals (regex: `\b(NEVER|ALWAYS|MUST)\b` uppercase)
- `goal`: Future-oriented language (regex: future tense or `want|need|goal|achieve`)
- `anti-pattern`: Negative imperatives (regex: `don't|do not|avoid|stop`)

### Connection Scoring System

**4 Connection Types:**

1. **Structural** (layer/sublayer proximity):
   - Same sublayer = 1.0
   - Same layer, adjacent sublayer = 0.7
   - Same layer, different sublayer = 0.4
   - Different layer = 0.0 (unless other connection exists)

2. **Entity** (shared concepts in Kuzu):
   - Score = shared_entity_count × 0.2 (max 1.0)

3. **Temporal** (time proximity):
   - Within 1 hour = 0.8
   - Within 1 day = 0.5
   - Within 1 week = 0.3
   - Beyond 1 week = 0.0

4. **Causal** (references):
   - Explicit reference = 1.0
   - Implicit reference = 0.5

**Combined Score**: `connection_strength = max(structural, entity, temporal, causal)`

**Cross-Layer Connection Boosts:**
- SELF -> INTENT: +0.3 (identity shapes rules)
- SELF -> WORLD: +0.2 (identity shapes knowledge)
- WORLD -> INTENT: +0.3 (knowledge informs action)
- Others: +0.0

### Visual Design Specification

**Graph Layout:**
```
        [USER: Jaime] (implicit root)
              │
    ┌─────────┼─────────┐
    │         │         │
 [SELF]   [WORLD]   [INTENT]
    │         │         │
Red-Yellow Blue-Purple Black-Green
 Cluster    Cluster    Cluster
```

**Color Coding:**
- SELF: Red-Orange-Yellow gradient
  - identity =  Red
  - preference =  Orange  
  - constraint =  Yellow
- WORLD: Blue-Purple-Green gradient
  - fact =  Blue
  - failure =  Purple
  - method =  Green
- INTENT: Black-Green-Blue gradient
  - rule =  Black
  - goal =  Green
  - anti-pattern =  Blue

**Connection Visualization:**
- Thick line (0.8-1.0) = Strong connection
- Normal line (0.5-0.7) = Medium connection
- Dashed line (0.2-0.4) = Weak connection
- No line (0.0) = No connection

**Electric Effect**: Click node -> all connected nodes pulse with glow animation

---

## 9.  Exact Next Steps

### Step 1: Update Memory Model Schema
**File**: `src/models/memory.py`
**Action**: Add `layer` and `sublayer` fields to Memory class
```python
layer: Literal["self", "world", "intent"]
sublayer: str  # Will be one of 9 values
```

### Step 2: Create Classification Logic
**File**: `src/core/classifier.py` (NEW FILE)
**Action**: Implement auto-classification function using regex/keyword rules defined above
```python
def classify_memory(content: str) -> Tuple[str, str]:
    """Returns (layer, sublayer) based on content analysis"""
    # SELF layer detection
    # WORLD layer detection  
    # INTENT layer detection
    # Return tuple
```

### Step 3: Update MCP addMemory Tool
**File**: `src/mcp/server.py`
**Action**: Update addMemory tool description to instruct agent:
- "YOU ARE THE BRAIN. Classify this memory into layer+sublayer."
- Provide examples of each sublayer
- Agent provides layer/sublayer, system validates

### Step 4: Create Migration Script
**File**: `scripts/migrate_to_v3_schema.py` (NEW FILE)
**Action**: Reclassify all 91 existing memories:
- Read from ChromaDB
- Apply classification logic
- Update with new layer/sublayer
- Delete 7 duplicates
- Store back to ChromaDB

### Step 5: Update Dashboard Data Pipeline
**File**: `scripts/dashboard/update_dashboard_data.py`
**Action**: Include layer/sublayer in snapshot.json structure

### Step 6: Implement Hierarchical Graph Layout
**File**: `src/dashboard/src/components/GraphCanvas.tsx`
**Action**: 
- Create 3 anchor nodes (SELF, WORLD, INTENT)
- Position sublayer nodes as inner orbits
- Position memory nodes orbiting their sublayer
- Apply color coding
- Implement connection strength visualization

### Step 7: Implement Electric Effect
**File**: `src/dashboard/src/components/GraphCanvas.tsx`
**Action**: On node click, calculate all connected nodes and add pulsing glow animation

### Step 8: Test Full Pipeline
- Store new memory via MCP
- Verify auto-classification works
- Check dashboard renders correctly
- Verify electric effect activates
- Test with Jaime reviewing actual results

---

## 10.  Definition of Done

### Visual Success Criteria
 Dashboard shows clean 3-cluster layout (not soup)
 Colors clearly distinguish layers/sublayers
 Clicking any node triggers electric pulse effect on connected nodes
 Connection lines vary thickness by strength
 All 91 memories properly classified (no "reference" domain)

### Functional Success Criteria
 Agent can store new memory with auto-classification
 searchMemories returns balanced SELF+WORLD+INTENT results
 Connection scores calculated correctly (structural + entity + temporal + causal)
 Dashboard loads without errors
 User (Jaime) says "this is beautiful" or equivalent approval

### Technical Success Criteria
 All regex/keyword rules codified and tested
 Migration script runs successfully on 91 memories
 Schema changes backward compatible (old memories still readable)
 Performance: Dashboard renders <2sec for 100 memories
 MCP tools work without breaking changes

---

## 11.  Known Traps & Pitfalls

### Classification Edge Cases
- **Problem**: Some memories fit multiple layers (e.g., "I must verify" - SELF.constraint or INTENT.rule?)
- **Solution**: Prioritize by keyword strength - uppercase MUST = INTENT.rule, lowercase must = SELF.constraint

- **Problem**: Causal connections hard to detect programmatically
- **Trap**: Don't over-engineer - start with explicit text matching ("Three Gaps" mentioned in content), add LLM inference later if needed

### Visual Rendering Issues
- **Problem**: 107 nodes might still be too dense even with hierarchy
- **Solution**: Implement zoom levels - show only anchor nodes by default, expand sublayers on click

- **Problem**: Electric effect could be laggy with many connections
- **Solution**: Limit animation to max 20 connected nodes, prioritize by connection strength

### Migration Risks
- **Problem**: 91 memories all get reclassified - if wrong, user loses context
- **Solution**: Keep old domain/category fields, add new layer/sublayer alongside, allow manual correction

### Dashboard State
- **Known Issue**: Kuzu single-writer architecture - dashboard and MCP can't run simultaneously
- **Workaround**: User must stop dashboard before using MCP tools (documented limitation)

---

## 12.  Remaining Open Questions for the User

### Classification Questions
1. **Causal connection measurement**: Should we use (a) agent inference at storage time, (b) keyword matching, or (c) user explicitly tags relationships? User asked this at end but we parked it.

2. **Sublayer ambiguity**: When memory could fit multiple sublayers (e.g., "I hate bugs" - SELF.preference or WORLD.failure?), should we:
   - Allow multiple sublayers per memory?
   - Force single sublayer with priority rules?
   - Let user manually adjust?

### Visual Questions
3. **Dashboard zoom behavior**: Should clicking anchor node (SELF) expand to show all sublayers, or show aggregated view?

4. **Connection strength threshold**: At what score do we NOT draw a line? (Currently thinking <0.2 = no line)

### Data Questions
5. **The 7 duplicates**: Delete immediately or show user first for confirmation?

6. **Test memory**: Delete "This is a test memory for temporal decay validation" or keep as example?

---

## 13.  Technical Metadata

### Output Format
- Schema changes: Python (Pydantic models)
- Classification logic: Python (regex + keywords)
- Migration script: Python
- Dashboard: TypeScript/React (existing stack)
- Documentation: Markdown

### Repository State
- **Location**: `c:\Users\JaimeSubiabreCistern\Documents\Agentic\Elefante`
- **Branch**: `main`
- **Last commits**:
  - `ef9e444`: "refactor: agent-as-brain classification (remove redundant LLM call)"
  - `f24dbcd`: "feat: implement Memory Schema V2 domain/category classification"

### Tools/Stack
- **Backend**: Python 3.8+
- **Vector DB**: ChromaDB (for memories)
- **Graph DB**: Kuzu (for entities/relationships)
- **MCP Server**: Python-based, 12 tools currently
- **Dashboard**: React + D3.js force-directed graph
- **Environment**: Windows PowerShell

### Model Preferences
- LLM-agnostic design (works with Claude, Gemini, Ollama via MCP)
- Agent classification at storage time (no real-time inference needed)

### Next Session Git Actions
1. Create feature branch: `git checkout -b feature/memory-schema-v3`
2. Implement changes (steps 1-7 above)
3. Test thoroughly
4. Commit with message: "feat: implement three-layer memory architecture (SELF/WORLD/INTENT) with measurable sublayers and connection scoring"
5. Push and wait for user approval before merging

---

## — ZLCTP PACKAGE COMPLETE — NEXT LLM CAN START INSTANTLY —

**Continuation trigger**: "Let's implement Memory Schema V3"

**First action**: Open `src/models/memory.py` and add `layer` + `sublayer` fields.
