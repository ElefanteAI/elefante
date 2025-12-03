# Elefante Memory Schema V2.0 - Comprehensive Second Brain Design

**Status**: DRAFT - Awaiting User Approval  
**Date**: 2025-12-02  
**Author**: IBM Bob (Architect Mode)  
**Approved By**: [PENDING]

---

## Executive Summary

This document specifies the enhanced memory schema for Elefante, designed to support a comprehensive "second brain" system with:
- **3-level taxonomy** (domain → category → type)
- **Automatic relationship detection** (LLM-powered)
- **Confidence tracking** (verification & reliability)
- **Temporal intelligence** (access patterns, decay, reinforcement)

---

## Design Philosophy

### Core Principles

1. **Semantic Richness**: Capture not just WHAT, but WHY, HOW, and WHEN
2. **Graph-Native**: Every memory is a node; relationships are first-class citizens
3. **Self-Organizing**: System learns patterns and suggests connections
4. **Trust-Aware**: Track confidence, verification, and source reliability
5. **Temporal Intelligence**: Memories strengthen with use, fade with neglect
6. **Extensible**: Custom metadata for future needs

---

## Schema Architecture

### Layer 1: Core Identity (Immutable)

```python
id: UUID                          # Unique identifier (never changes)
content: str                      # The actual memory text (1-10000 chars)
embedding: List[float]            # 384-dim vector (sentence-transformers)
created_at: datetime              # Creation timestamp (UTC)
created_by: str                   # "user" | "agent" | "system"
```

**Storage**: 
- `content` + `embedding` → ChromaDB (vector search)
- `id` → Kuzu (graph node)

---

### Layer 2: Classification Hierarchy (3-Level Taxonomy)

```python
domain: DomainType                # High-level context
category: str                     # Mid-level grouping
memory_type: MemoryType           # Low-level type
subcategory: Optional[str]        # Ultra-specific (optional)
```

#### Domain Taxonomy (Enum)

```python
class DomainType(str, Enum):
    WORK = "work"                 # Professional context
    PERSONAL = "personal"         # Personal life
    LEARNING = "learning"         # Educational content
    PROJECT = "project"           # Specific project work
    REFERENCE = "reference"       # General knowledge base
    SYSTEM = "system"             # System-generated metadata
```

#### Category (Freeform String)

Examples by domain:
- **work**: "ai-ml", "architecture", "meetings", "decisions"
- **personal**: "health", "finance", "relationships", "hobbies"
- **learning**: "courses", "books", "tutorials", "research"
- **project**: "elefante", "client-x", "side-project-y"
- **reference**: "documentation", "apis", "best-practices"

**Design Decision**: Freeform string (not enum) for flexibility. System will suggest common categories based on usage patterns.

#### Memory Type (Enum - Refined)

```python
class MemoryType(str, Enum):
    CONVERSATION = "conversation"  # Dialogue exchange
    FACT = "fact"                  # Verifiable information
    INSIGHT = "insight"            # Derived understanding
    CODE = "code"                  # Code snippet/implementation
    DECISION = "decision"          # Choice made + rationale
    TASK = "task"                  # Action item
    NOTE = "note"                  # General note
    PREFERENCE = "preference"      # User preference/setting
    QUESTION = "question"          # Unanswered question
    ANSWER = "answer"              # Response to question
    HYPOTHESIS = "hypothesis"      # Unverified theory
    OBSERVATION = "observation"    # Empirical data point
```

**Example Hierarchy**:
```
domain: "work"
  category: "ai-projects"
    memory_type: "decision"
      subcategory: "chromadb-schema-design"
```

---

### Layer 3: Semantic Metadata

```python
intent: IntentType                # Why was this stored?
importance: int                   # 1-10 (user-defined priority)
urgency: int                      # 1-10 (time-sensitivity)
confidence: float                 # 0.0-1.0 (certainty level)
tags: List[str]                   # Freeform labels
keywords: List[str]               # Auto-extracted key terms
entities: List[str]               # Named entities (people, places, tech)
```

#### Intent Taxonomy (Enum)

```python
class IntentType(str, Enum):
    REFERENCE = "reference"        # For future lookup
    REMINDER = "reminder"          # To revisit later
    LEARNING = "learning"          # Educational purpose
    DECISION_LOG = "decision_log"  # Record of choice made
    CONTEXT = "context"            # Background information
    ACTION = "action"              # Requires follow-up
    ARCHIVE = "archive"            # Historical record
    TEMPLATE = "template"          # Reusable pattern
```

**Design Note**: `memory_type` describes WHAT it is; `intent` describes WHY you stored it.

---

### Layer 4: Relationship Tracking (Graph Intelligence)

```python
status: MemoryStatus              # Relationship to existing knowledge
relationship_type: RelationshipType  # How it connects
related_memory_ids: List[UUID]    # Direct links
parent_id: Optional[UUID]         # For threading
children_ids: List[UUID]          # For hierarchy
conflict_ids: List[UUID]          # Contradictory memories
supersedes_id: Optional[UUID]     # Replaces older memory
superseded_by_id: Optional[UUID]  # Replaced by newer memory
```

#### Memory Status (Enum - Enhanced)

```python
class MemoryStatus(str, Enum):
    NEW = "new"                    # First time seeing this
    REDUNDANT = "redundant"        # Duplicate of existing
    CONTRADICTORY = "contradictory"  # Conflicts with existing
    RELATED = "related"            # Connected to existing
    CONSOLIDATED = "consolidated"  # Merged from multiple sources
    REFINED = "refined"            # Improved version
    VERIFIED = "verified"          # Confirmed accurate
    DEPRECATED = "deprecated"      # Outdated/superseded
    ARCHIVED = "archived"          # Historical, not active
```

#### Relationship Type (Enum - Expanded)

```python
class RelationshipType(str, Enum):
    # Additive
    EXTENDS = "extends"            # Adds detail to existing
    SUPPORTS = "supports"          # Provides evidence for
    IMPLEMENTS = "implements"      # Realizes concept
    EXEMPLIFIES = "exemplifies"    # Example of pattern
    
    # Transformative
    REFINES = "refines"            # Improves existing
    SUPERSEDES = "supersedes"      # Replaces existing
    CONSOLIDATES = "consolidates"  # Merges multiple
    
    # Conflictual
    CONTRADICTS = "contradicts"    # Disagrees with existing
    CHALLENGES = "challenges"      # Questions existing
    
    # Structural
    DEPENDS_ON = "depends_on"      # Requires existing
    PART_OF = "part_of"            # Component of larger
    REFERENCES = "references"      # Cites existing
    RELATES_TO = "relates_to"      # General connection
    
    # Temporal
    FOLLOWS = "follows"            # Chronological sequence
    PRECEDES = "precedes"          # Comes before
    UPDATES = "updates"            # New version of
```

---

### Layer 5: Source Attribution & Trust

```python
source: SourceType                # Origin of memory
source_detail: str                # Specific attribution
source_reliability: float         # 0.0-1.0 (trust score)
verified: bool                    # Has been validated?
verified_by: Optional[str]        # Who/what verified
verified_at: Optional[datetime]   # When verified
session_id: Optional[UUID]        # Conversation context
author: str                       # Creator (for multi-user)
```

#### Source Type (Enum)

```python
class SourceType(str, Enum):
    USER_INPUT = "user_input"      # Direct user entry
    AGENT_GENERATED = "agent_generated"  # AI-created
    SYSTEM_INFERRED = "system_inferred"  # Auto-detected
    EXTERNAL_API = "external_api"  # From web service
    DOCUMENT = "document"          # From file/PDF
    WEB_SCRAPE = "web_scrape"      # From website
    CODE_ANALYSIS = "code_analysis"  # From codebase
    CONVERSATION = "conversation"  # From dialogue
```

#### Source Reliability Scoring

```python
RELIABILITY_SCORES = {
    SourceType.USER_INPUT: 0.9,        # High trust
    SourceType.DOCUMENT: 0.8,          # Medium-high
    SourceType.CODE_ANALYSIS: 0.8,     # Medium-high
    SourceType.AGENT_GENERATED: 0.7,   # Medium
    SourceType.CONVERSATION: 0.7,      # Medium
    SourceType.EXTERNAL_API: 0.6,      # Medium-low
    SourceType.WEB_SCRAPE: 0.5,        # Low
    SourceType.SYSTEM_INFERRED: 0.4,   # Very low
}
```

**Confidence Calculation**:
```python
final_confidence = base_confidence * source_reliability * verification_boost
```

---

### Layer 6: Context Anchoring

```python
project: Optional[str]            # Project name
workspace: Optional[str]          # Workspace path
file_path: Optional[str]          # File reference
line_number: Optional[int]        # Code line
url: Optional[str]                # External link
location: Optional[str]           # Physical/virtual location
```

---

### Layer 7: Temporal Intelligence

```python
last_accessed: datetime           # Most recent retrieval
last_modified: datetime           # Most recent update
access_count: int                 # Frequency of use
access_pattern: List[datetime]    # Last N accesses (for decay analysis)
decay_rate: float                 # How fast importance fades
reinforcement_factor: float       # Boost from repeated access
```

#### Temporal Scoring Algorithm

```python
def calculate_relevance_score(memory: Memory, current_time: datetime) -> float:
    """
    Combines base importance with temporal factors
    """
    # Base score
    base = memory.importance / 10.0
    
    # Recency factor (exponential decay)
    days_since_created = (current_time - memory.created_at).days
    recency = math.exp(-memory.decay_rate * days_since_created)
    
    # Access reinforcement (logarithmic growth)
    if memory.access_count > 0:
        reinforcement = 1 + (memory.reinforcement_factor * math.log(memory.access_count + 1))
    else:
        reinforcement = 1.0
    
    # Last access boost (recent use = higher relevance)
    days_since_access = (current_time - memory.last_accessed).days
    access_boost = math.exp(-0.1 * days_since_access)
    
    # Combined score
    return base * recency * reinforcement * access_boost
```

---

### Layer 8: Quality & Lifecycle

```python
version: int                      # Version number (starts at 1)
deprecated: bool                  # Is outdated?
archived: bool                    # Moved to archive?
summary: Optional[str]            # Short summary (auto-generated)
sentiment: Optional[float]        # -1.0 to 1.0 (for preferences)
quality_score: Optional[float]    # 0.0-1.0 (content quality)
```

---

### Layer 9: Extensibility

```python
custom_metadata: Dict[str, Any]   # User-defined fields
system_metadata: Dict[str, Any]   # System-internal data
```

---

## Storage Strategy

### ChromaDB (Vector Store)

**What Gets Stored**:
```python
{
    "ids": [str(memory.id)],
    "embeddings": [memory.embedding],
    "documents": [memory.content],
    "metadatas": [{
        # Layer 1: Core
        "created_at": memory.created_at.isoformat(),
        "created_by": memory.created_by,
        
        # Layer 2: Classification
        "domain": memory.domain.value,
        "category": memory.category,
        "memory_type": memory.memory_type.value,
        "subcategory": memory.subcategory or "",
        
        # Layer 3: Semantic
        "intent": memory.intent.value,
        "importance": memory.importance,
        "urgency": memory.urgency,
        "confidence": memory.confidence,
        "tags": ",".join(memory.tags),
        "keywords": ",".join(memory.keywords),
        
        # Layer 4: Relationships (IDs only)
        "status": memory.status.value,
        "parent_id": str(memory.parent_id) if memory.parent_id else "",
        
        # Layer 5: Source
        "source": memory.source.value,
        "source_reliability": memory.source_reliability,
        "verified": memory.verified,
        
        # Layer 6: Context
        "project": memory.project or "",
        "file_path": memory.file_path or "",
        
        # Layer 7: Temporal
        "last_accessed": memory.last_accessed.isoformat(),
        "access_count": memory.access_count,
        
        # Layer 8: Quality
        "version": memory.version,
        "deprecated": memory.deprecated,
    }]
}
```

**Limitations**: ChromaDB metadata is flat (no nested objects). Complex relationships stored in Kuzu.

### Kuzu (Graph Store)

**Node Types**:
```cypher
// Memory node
CREATE NODE TABLE Memory (
    id STRING PRIMARY KEY,
    content STRING,
    domain STRING,
    category STRING,
    memory_type STRING,
    importance INT64,
    confidence DOUBLE,
    created_at TIMESTAMP,
    last_accessed TIMESTAMP,
    access_count INT64
)

// Entity nodes (existing)
CREATE NODE TABLE Entity (
    id STRING PRIMARY KEY,
    name STRING,
    type STRING,
    properties MAP(STRING, STRING)
)
```

**Relationship Types**:
```cypher
// Memory-to-Memory relationships
CREATE REL TABLE EXTENDS (FROM Memory TO Memory, strength DOUBLE)
CREATE REL TABLE CONTRADICTS (FROM Memory TO Memory, severity DOUBLE)
CREATE REL TABLE SUPERSEDES (FROM Memory TO Memory, timestamp TIMESTAMP)
CREATE REL TABLE RELATES_TO (FROM Memory TO Memory, weight DOUBLE)

// Memory-to-Entity relationships
CREATE REL TABLE MENTIONS (FROM Memory TO Entity, relevance DOUBLE)
CREATE REL TABLE ABOUT (FROM Memory TO Entity, centrality DOUBLE)
```

---

## Automatic Relationship Detection

### LLM-Powered Analysis

When a new memory is added, the system:

1. **Semantic Search**: Find top-K similar memories (ChromaDB)
2. **LLM Analysis**: Send to LLM with prompt:
   ```
   New Memory: "{new_content}"
   
   Existing Memories:
   1. "{existing_1}"
   2. "{existing_2}"
   ...
   
   For each existing memory, determine:
   - Relationship type: [EXTENDS, CONTRADICTS, REFINES, etc.]
   - Confidence: [0.0-1.0]
   - Explanation: [brief reason]
   
   Output JSON:
   {
     "relationships": [
       {"memory_id": "uuid", "type": "EXTENDS", "confidence": 0.9, "reason": "..."},
       ...
     ],
     "status": "NEW" | "REDUNDANT" | "CONTRADICTORY" | "RELATED"
   }
   ```

3. **Graph Update**: Create relationship edges in Kuzu
4. **Status Update**: Set memory status based on LLM analysis

### Fallback (No LLM)

If LLM unavailable:
- Use cosine similarity threshold (>0.9 = REDUNDANT, >0.7 = RELATED)
- Set `status = NEW` by default
- User can manually tag relationships

---

## Migration Strategy (V1 → V2)

### Existing 43 Memories

**Current Schema** (V1):
```python
{
    "timestamp": datetime,
    "memory_type": str,
    "importance": int,
    "tags": List[str],
    "source": str,
    "session_id": UUID,
    "project": str,
    "file_path": str
}
```

**Migration Mapping**:

| V1 Field | V2 Field | Transformation |
|----------|----------|----------------|
| `timestamp` | `created_at` | Direct copy |
| `memory_type` | `memory_type` | Direct copy (if valid enum) |
| `importance` | `importance` | Direct copy |
| `tags` | `tags` | Direct copy |
| `source` | `source` | Map to SourceType enum |
| `session_id` | `session_id` | Direct copy |
| `project` | `project` | Direct copy |
| `file_path` | `file_path` | Direct copy |
| N/A | `domain` | **Infer from project/tags** |
| N/A | `category` | **Infer from tags** |
| N/A | `intent` | **Default: REFERENCE** |
| N/A | `confidence` | **Default: 0.7** |
| N/A | `status` | **Default: NEW** |
| N/A | `created_by` | **Default: "user"** |
| N/A | `last_accessed` | **Set to created_at** |
| N/A | `access_count` | **Default: 0** |
| N/A | `version` | **Default: 1** |

### Migration Script Pseudocode

```python
async def migrate_v1_to_v2():
    # 1. Backup existing database
    backup_database()
    
    # 2. Add 'topic' column (fix corruption)
    repair_chromadb_schema()
    
    # 3. Load all V1 memories
    v1_memories = load_all_memories_v1()
    
    # 4. Transform each memory
    for v1_mem in v1_memories:
        v2_mem = Memory(
            id=v1_mem.id,
            content=v1_mem.content,
            embedding=v1_mem.embedding,
            created_at=v1_mem.timestamp,
            created_by="user",
            
            # Infer domain from project/tags
            domain=infer_domain(v1_mem.project, v1_mem.tags),
            category=infer_category(v1_mem.tags),
            memory_type=v1_mem.memory_type,
            
            # Defaults for new fields
            intent=IntentType.REFERENCE,
            importance=v1_mem.importance,
            urgency=5,
            confidence=0.7,
            tags=v1_mem.tags,
            
            # Relationships (analyze later)
            status=MemoryStatus.NEW,
            
            # Source
            source=map_source(v1_mem.source),
            source_reliability=0.8,
            verified=False,
            
            # Context
            project=v1_mem.project,
            file_path=v1_mem.file_path,
            session_id=v1_mem.session_id,
            
            # Temporal
            last_accessed=v1_mem.timestamp,
            access_count=0,
            
            # Quality
            version=1,
            deprecated=False,
        )
        
        # 5. Update ChromaDB with new metadata
        update_chromadb(v2_mem)
        
        # 6. Create Kuzu node
        create_kuzu_node(v2_mem)
    
    # 7. Run relationship detection on all memories
    await detect_all_relationships()
    
    # 8. Verify migration
    verify_migration()
```

---

## Implementation Checklist

### Phase 1: Schema Definition
- [ ] Update `src/models/memory.py` with new fields
- [ ] Create enum classes (DomainType, IntentType, etc.)
- [ ] Update Pydantic models with validation

### Phase 2: Storage Layer
- [ ] Update `src/core/vector_store.py` for new metadata
- [ ] Update `src/core/graph_store.py` for new node/edge types
- [ ] Add ChromaDB schema repair (topic column)

### Phase 3: Relationship Detection
- [ ] Implement LLM-powered analysis
- [ ] Create fallback similarity-based detection
- [ ] Add relationship edge creation in Kuzu

### Phase 4: Migration
- [ ] Create migration script
- [ ] Test on backup copy first
- [ ] Implement rollback mechanism

### Phase 5: API Updates
- [ ] Update `add_memory()` to accept new fields
- [ ] Update `search_memories()` to filter by new fields
- [ ] Update MCP tools with new parameters

### Phase 6: Testing
- [ ] Unit tests for new models
- [ ] Integration tests for migration
- [ ] End-to-end test of memory lifecycle

---

## Open Questions for User Approval

1. **Domain Inference**: How should we infer `domain` from existing memories? Use project name? Tags? LLM analysis?

2. **Confidence Defaults**: Is 0.7 a reasonable default confidence for migrated memories?

3. **Relationship Detection**: Should we run LLM analysis on all 43 existing memories to detect relationships? (May incur API costs)

4. **Temporal Decay**: What decay rate should we use? Fast (0.1 = noticeable after 10 days) or slow (0.01 = noticeable after 100 days)?

5. **Custom Metadata**: Any specific custom fields you want to add now?

---

## Approval Required

**This schema represents a significant architectural change.** Before implementation:

- [ ] User reviews and approves taxonomy (domains, types, intents)
- [ ] User approves migration strategy for 43 existing memories
- [ ] User approves LLM usage for relationship detection
- [ ] User approves temporal decay parameters
- [ ] User confirms no additional custom fields needed

**Status**: AWAITING USER APPROVAL

---

## Next Steps (Post-Approval)

1. Implement schema changes in code
2. Create migration script
3. Test migration on backup
4. Execute migration
5. Repair ChromaDB corruption
6. Test memory operations
7. Restart MCP server
8. Verify all systems operational

---

**Document Version**: 1.0  
**Last Updated**: 2025-12-02  
**Approved By**: [PENDING]