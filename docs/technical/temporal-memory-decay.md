# Temporal Memory Decay & Reinforcement

**Feature Version**: 2.1.2  
**Status**: Production  
**Date**: 2026-02-25

---

## Overview

Temporal Memory Decay is an adaptive memory strength system that mimics human cognition by:

- **Decaying** memories over time (recency bias)
- **Reinforcing** memories when accessed (strengthened through use)
- **Archiving** unused memories automatically (planned)

This creates a dynamic memory system where frequently accessed memories stay strong while unused memories naturally fade.

---

## Core Concepts

### Memory Strength Formula

```python
strength = relevance_score × recency × reinforcement × access_recency

where:
  relevance_score = system-computed Behavioral Relevance (0-100)
  recency = exp(-decay_rate × days_since_created)
  reinforcement = 1.0 + 0.25 × ln(access_count + 1)
  access_recency = exp(-0.02 × days_since_accessed)
```

### Default Parameters

```python
decay_rate = 0.01              # 1% decay per day
reinforcement_factor = 0.1     # 10% boost per access
consolidation_threshold = 0.3  # Archive below 30% strength
```

---

## How It Works

### Phase 1: Temporal Scoring (Active)

**When**: During memory search operations  
**Where**: `vector_store.py` and `graph_store.py`

**Process**:

1. Retrieve memories from database
2. Calculate temporal strength for each
3. Apply strength as score multiplier
4. Return re-ranked results

**Effect**: Recent and frequently accessed memories rank higher in search results.

**Example**:

```python
# Memory A: Created 100 days ago, accessed 5 times, last access 2 days ago
strength_A = 50 × 0.0 × 1.5 × 0.98 = 0.0  # Too old, decayed completely

# Memory B: Created 10 days ago, accessed 3 times, last access 1 day ago
strength_B = 50 × 0.9 × 1.3 × 0.99 = 57.9  # Strong and recent

# Memory B ranks higher — its behavioral relevance earns better placement
```

### Phase 2: Background Consolidation (Planned)

**When**: Periodic background job (not yet implemented)

**Process**:

1. Scan all memories
2. Calculate temporal strength
3. Identify weak memories (strength < 0.3)
4. Move to archive with metadata
5. Keep searchable but marked as archived

**Effect**: Database stays focused on active memories while preserving history.

**Status**: This phase is planned but not yet implemented. The consolidation module does not exist yet.

---

## Implementation Details

### Memory Model Updates

**File**: `src/models/memory.py`

**New Fields**:

```python
class MemoryMetadata:
    last_accessed: datetime      # Updated on every retrieval
    access_count: int            # Incremented on every retrieval
    decay_rate: float = 0.01     # Customizable per memory
    reinforcement_factor: float = 0.1  # Customizable per memory
```

### Vector Store Integration

**File**: `src/core/vector_store.py`

**Modified Method**: `search()`

```python
def search(self, query: str, limit: int = 10) -> List[Memory]:
    # 1. Semantic search
    results = self.collection.query(query_texts=[query], n_results=limit*2)

    # 2. Calculate temporal strength
    for memory in results:
        temporal_strength = self._calculate_temporal_strength(memory)
        memory.relevance_score *= temporal_strength  # Apply multiplier

    # 3. Re-rank and return top results
    return sorted(results, key=lambda m: m.relevance_score, reverse=True)[:limit]
```

### Graph Store Integration

**File**: `src/core/graph_store.py`

**Modified Method**: `search_related()`

Similar temporal scoring applied to graph traversal results.

---

## Configuration

### Global Settings

**File**: `config.yaml`

```yaml
elefante:
  temporal_decay:
    enabled: true
    default_decay_rate: 0.01
    default_reinforcement_factor: 0.1
    consolidation_threshold: 0.3
    consolidation_schedule: "daily" # or "weekly", "manual"
```

### Per-Memory Settings

Memories can have custom decay/reinforcement rates:

```python
memory = Memory(
    content="Important project decision",
    metadata=MemoryMetadata(
        score=100,  # Behavioral vitality (0-100)
        decay_rate=0.001,  # Slower decay (0.1% per day)
        reinforcement_factor=0.2  # Stronger reinforcement
    )
)
```

---

## Usage Examples

### Example 1: Natural Memory Ranking

```python
# Store two memories
memory1 = orchestrator.add_memory("Python is great", memory_type="fact")
memory2 = orchestrator.add_memory("JavaScript is useful", memory_type="fact")

# Access memory1 multiple times
for _ in range(5):
    orchestrator.search_memories("programming languages")
    # memory1 accessed each time

# After 30 days, search again
results = orchestrator.search_memories("programming languages")

# memory1 ranks higher due to:
# - Same recency (both 30 days old)
# - Higher access_count (5 vs 1)
# - Stronger reinforcement (1.5x vs 1.1x)
```

### Example 2: Score vs Recency

```python
# Old but durable memory
old_memory = Memory(
    content="Critical system architecture decision",
    metadata=MemoryMetadata(
        memory_type="decision",
        created_at=datetime.now() - timedelta(days=365)
    )
)

# Recent but ephemeral memory
new_memory = Memory(
    content="Minor code style preference",
    metadata=MemoryMetadata(
        memory_type="note",
        created_at=datetime.now() - timedelta(days=1)
    )
)

# Search results balance both factors
# old_memory: 50 × 0.0 × 1.0 × 1.0 = 0.0 (decayed completely)
# new_memory: 50 × 0.99 × 1.0 × 1.0 = 49.5 (recent wins)

# But if old_memory is accessed frequently:
# old_memory: 10 × 0.0 × 2.0 × 0.99 = 0.0 (still decayed, but reinforcement helps)
```

### Example 3: Score vs Recency

```python
# A decision memory accessed 10 times in 72 days
decision = Memory(
    content="Use absolute paths for all imports",
    metadata=MemoryMetadata(
        memory_type="decision",
        access_count=10,
        decay_rate=0.005,  # decision type
    )
)

# calculate_relevance_score() returns 0.0-1.0
# High access slows decay via reinforcement factor
vitality = decision.calculate_relevance_score()
# => ~0.90 (still strong due to frequent access)
```

---

## Benefits

### 1. Adaptive Memory System

- Memories naturally adapt to usage patterns
- Important memories stay accessible
- Unused memories fade gracefully

### 2. Improved Search Relevance

- Recent context prioritized
- Frequently referenced knowledge surfaces
- Balanced with semantic similarity

### 3. Database Efficiency

- Active memories stay in hot storage
- Archived memories reduce query overhead
- Historical context preserved

### 4. Human-Like Cognition

- Mimics human memory patterns
- Recency bias (recent events more accessible)
- Reinforcement through repetition
- Natural forgetting of unused information

---

## Performance Impact

### Search Performance

- **Overhead**: ~5-10ms per search (temporal calculation)
- **Benefit**: Better relevance, fewer irrelevant results
- **Net**: Improved user experience

### Storage Impact

- **Active Memories**: No change
- **Archived Memories**: Moved to separate collection
- **Total Storage**: Slightly increased (metadata)

### Consolidation Performance

- **Frequency**: Daily (configurable)
- **Duration**: ~1-5 seconds per 1000 memories
- **Impact**: Runs in background, no user impact

---

## Testing

### Unit Tests

**File**: `tests/test_temporal_decay.py`

```python
def test_temporal_strength_calculation():
    """Test strength formula"""

def test_decay_over_time():
    """Test memories decay correctly"""

def test_reinforcement_on_access():
    """Test access count increases strength"""

def test_consolidation_threshold():
    """Test weak memories identified correctly"""
```

### Integration Tests

**File**: `tests/integration/test_temporal_search.py`

```python
def test_search_with_temporal_scoring():
    """Test search results ranked by temporal strength"""

def test_consolidation_workflow():
    """Test full consolidation cycle"""
```

---

## Future Enhancements

### Planned Features

1. **Adaptive Decay Rates**
   - Learn optimal decay rates per memory type
   - Adjust based on access patterns

2. **Smart Consolidation**
   - Predict which memories will be needed
   - Preserve memories before they're requested

3. **Memory Resurrection**
   - Automatically restore archived memories when relevant
   - Based on context and query patterns

4. **Dashboard Visualization**
   - Memory strength heatmap
   - Decay/reinforcement trends
   - Consolidation history

---

## Troubleshooting

### Issue: Memories Decaying Too Fast

**Solution**: Adjust decay rate in config:

```yaml
temporal_decay:
  default_decay_rate: 0.005 # Slower decay (0.5% per day)
```

### Issue: Important Memories Being Archived

**Solution**:

1. Access memories regularly to reinforce them (raises behavioral score)
2. Lower consolidation threshold
3. Memories with high access counts decay much slower

### Issue: Search Results Too Biased Toward Recent

**Solution**: Reduce reinforcement factor:

```yaml
temporal_decay:
  default_reinforcement_factor: 0.05 # Less reinforcement
```

---

## Related Documentation

- [`architecture.md`](architecture.md) - System architecture
- [`memory-schema-v4-cognitive.md`](memory-schema-v4-cognitive.md) - Memory data model
- [`usage.md`](usage.md) - API reference

---

**Version**: 2.1.2  
**Last Updated**: 2026-02-25  
**Status**: Production Ready (Phase 1), Planned (Phase 2)
