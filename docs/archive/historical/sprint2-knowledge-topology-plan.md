# Sprint 2: Knowledge Topology Transformation

## Executive Summary

**Problem**: Current dashboard visualizes **Database Topology** (storage structure) instead of **Knowledge Topology** (idea connections). This creates artificial clusters around sessions and obscures semantic relationships between memories.

**Goal**: Transform visualization from "how data is stored" to "how ideas connect" - beating Supermemory.ai by emphasizing content clusters and semantic associations.

---

## Root Cause Analysis

### Issue 1: Raw Text Labels
**Current**: Node labels show raw content ("I am 99 years old...")
**Impact**: Visual noise, unreadable at scale
**Fix**: Generate 3-5 word semantic titles via LLM

### Issue 2: Session Node Clutter
**Current**: Memories cluster around Session nodes (temporal hierarchy)
**Impact**: Irrelevant for knowledge graph - users care about idea relationships, not timestamps
**Fix**: Hide sessions by default, let memories float freely connected to entities/concepts

### Issue 3: Missing Semantic Edges
**Current**: Only structural links (Session->Memory, Memory->Entity)
**Impact**: No visualization of "coherence" - which ideas relate to each other
**Fix**: Compute vector similarity, draw edges for cosine > 0.8

---

## Technical Architecture

### Backend Changes

#### 1. Memory Title Generation
**File**: `Elefante/src/core/orchestrator.py`
**Function**: `_generate_memory_title(content: str) -> str`

```python
async def _generate_memory_title(self, content: str) -> str:
    """Generate 3-5 word semantic title for memory"""
    prompt = f"Summarize this in 3-5 words: {content[:200]}"
    response = await self.llm.generate(prompt, max_tokens=20)
    return response.strip()
```

**Integration**: Call during `add_memory()`, store in `metadata.summary`

#### 2. Similarity Edge Computation
**File**: `Elefante/src/dashboard/graph_service.py`
**Function**: `_compute_similarity_edges(nodes, embeddings, threshold=0.8)`

```python
def _compute_similarity_edges(self, memories: List[Dict], threshold: float = 0.8) -> List[Dict]:
    """
    Compute semantic similarity edges between memories
    
    Args:
        memories: List of memory nodes with embeddings
        threshold: Cosine similarity threshold (default 0.8)
    
    Returns:
        List of edge dicts with {from, to, similarity, type: 'semantic'}
    """
    from sklearn.metrics.pairwise import cosine_similarity
    import numpy as np
    
    # Extract embeddings
    memory_ids = [m['id'] for m in memories if m['type'] == 'memory']
    embeddings = [m['embedding'] for m in memories if m['type'] == 'memory' and m.get('embedding')]
    
    if len(embeddings) < 2:
        return []
    
    # Compute pairwise similarities
    sim_matrix = cosine_similarity(np.array(embeddings))
    
    edges = []
    for i in range(len(memory_ids)):
        for j in range(i+1, len(memory_ids)):
            similarity = sim_matrix[i][j]
            if similarity >= threshold:
                edges.append({
                    'from': memory_ids[i],
                    'to': memory_ids[j],
                    'label': f'similar ({similarity:.2f})',
                    'similarity': float(similarity),
                    'type': 'semantic'
                })
    
    return edges
```

#### 3. Graph API Enhancement
**File**: `Elefante/src/dashboard/graph_service.py`
**Method**: `get_graph_data()`

**Changes**:
1. Fetch embeddings from ChromaDB alongside metadata
2. Call `_compute_similarity_edges()` after node processing
3. Append semantic edges to structural edges
4. Return edge type metadata for frontend rendering

---

### Frontend Changes

#### 4. Bounding Box Collision
**File**: `Elefante/src/dashboard/ui/src/components/GraphCanvas.tsx`
**Location**: Physics simulation loop (line ~96)

```typescript
// Replace point-based repulsion with box-based collision
const getLabelBounds = (node: Node) => {
  const ctx = canvasRef.current!.getContext('2d')!;
  ctx.font = '11px Inter, sans-serif';
  const metrics = ctx.measureText(node.label);
  return {
    x: node.x - metrics.width / 2 - 4,
    y: node.y + node.radius + 4,
    width: metrics.width + 8,
    height: 16
  };
};

// Box collision detection
for (let i = 0; i < nodes.length; i++) {
  for (let j = i + 1; j < nodes.length; j++) {
    const boundsA = getLabelBounds(nodes[i]);
    const boundsB = getLabelBounds(nodes[j]);
    
    // Check AABB collision
    if (boundsA.x < boundsB.x + boundsB.width &&
        boundsA.x + boundsA.width > boundsB.x &&
        boundsA.y < boundsB.y + boundsB.height &&
        boundsA.y + boundsA.height > boundsB.y) {
      
      // Apply separation force
      const dx = nodes[i].x - nodes[j].x;
      const dy = nodes[i].y - nodes[j].y;
      const dist = Math.sqrt(dx*dx + dy*dy) || 1;
      const force = 200 / dist; // Strong separation
      
      nodes[i].vx += (dx/dist) * force;
      nodes[i].vy += (dy/dist) * force;
      nodes[j].vx -= (dx/dist) * force;
      nodes[j].vy -= (dy/dist) * force;
    }
  }
}
```

#### 5. Shape Mapping
**File**: `GraphCanvas.tsx`
**Location**: Node rendering (line ~178)

```typescript
// Draw nodes with shape based on type
const drawNode = (ctx: CanvasRenderingContext2D, node: Node) => {
  ctx.save();
  ctx.translate(node.x, node.y);
  
  if (node.type === 'entity') {
    // Diamond
    ctx.beginPath();
    ctx.moveTo(0, -node.radius);
    ctx.lineTo(node.radius, 0);
    ctx.lineTo(0, node.radius);
    ctx.lineTo(-node.radius, 0);
    ctx.closePath();
  } else if (node.type === 'session') {
    // Square (small)
    const size = node.radius * 0.8;
    ctx.fillRect(-size, -size, size*2, size*2);
  } else {
    // Circle (memory)
    ctx.beginPath();
    ctx.arc(0, 0, node.radius, 0, Math.PI * 2);
  }
  
  ctx.fillStyle = getNodeColor(node);
  ctx.fill();
  ctx.restore();
};
```

#### 6. Semantic Edge Rendering
**File**: `GraphCanvas.tsx`
**Location**: Edge drawing (line ~163)

```typescript
// Render edges with type-based styling
edges.forEach(edge => {
  const source = nodes.find(n => n.id === edge.source);
  const target = nodes.find(n => n.id === edge.target);
  if (!source || !target) return;
  
  if (edge.type === 'semantic') {
    // Dashed cyan line for similarity
    ctx.strokeStyle = 'rgba(6, 182, 212, 0.4)'; // Cyan-500
    ctx.setLineDash([5, 5]);
    ctx.lineWidth = 1 + (edge.similarity - 0.8) * 5; // Thicker = more similar
  } else {
    // Solid grey for structural
    ctx.strokeStyle = 'rgba(148, 163, 184, 0.2)';
    ctx.setLineDash([]);
    ctx.lineWidth = 1;
  }
  
  ctx.beginPath();
  ctx.moveTo(source.x, source.y);
  ctx.lineTo(target.x, target.y);
  ctx.stroke();
  ctx.setLineDash([]); // Reset
});
```

#### 7. Sidebar Inspector
**File**: `GraphCanvas.tsx`
**New Component**: `<SidebarInspector>`

```typescript
const [selectedNode, setSelectedNode] = useState<Node | null>(null);

// In handleMouseDown: setSelectedNode(hitNode)

<div className={`fixed right-0 top-0 h-full w-96 bg-slate-900 border-l border-slate-700 
                 transform transition-transform ${selectedNode ? 'translate-x-0' : 'translate-x-full'}`}>
  {selectedNode && (
    <div className="p-6">
      <button onClick={() => setSelectedNode(null)} className="float-right"></button>
      <h2 className="text-xl font-bold mb-4">{selectedNode.label}</h2>
      <div className="space-y-2 text-sm">
        <div><strong>Type:</strong> {selectedNode.type}</div>
        <div><strong>ID:</strong> {selectedNode.id}</div>
        {selectedNode.properties?.description && (
          <div className="mt-4">
            <strong>Content:</strong>
            <p className="mt-2 text-slate-300">{selectedNode.properties.description}</p>
          </div>
        )}
        <pre className="mt-4 bg-slate-800 p-3 rounded text-xs overflow-auto max-h-96">
          {JSON.stringify(selectedNode, null, 2)}
        </pre>
      </div>
    </div>
  )}
</div>
```

#### 8. Node Type Toggles
**File**: `GraphCanvas.tsx`
**UI**: Top-left controls

```typescript
const [visibleTypes, setVisibleTypes] = useState({
  memory: true,
  entity: true,
  session: false // Hidden by default
});

// Filter nodes before rendering
const visibleNodes = nodes.filter(n => visibleTypes[n.type]);

// UI Controls
<div className="absolute top-16 left-4 bg-slate-800 p-3 rounded-lg">
  <div className="text-sm font-bold mb-2">Node Types</div>
  {Object.entries(visibleTypes).map(([type, visible]) => (
    <label key={type} className="flex items-center gap-2 cursor-pointer">
      <input
        type="checkbox"
        checked={visible}
        onChange={() => setVisibleTypes(prev => ({...prev, [type]: !prev[type]}))}
      />
      <span className="capitalize">{type}</span>
    </label>
  ))}
</div>
```

#### 9. Z-Index Fix
**File**: `GraphCanvas.tsx`

```typescript
// Container structure
<div className="relative w-full h-full">
  <canvas className="absolute inset-0 z-0" /> {/* Canvas at bottom */}
  <div className="absolute top-4 left-4 z-10 pointer-events-none"> {/* UI overlays */}
    <input className="pointer-events-auto" /> {/* Re-enable for inputs */}
  </div>
</div>
```

---

## Implementation Order

### Phase 1: Backend (Python)
1.  Add `summary` field to `MemoryMetadata` (already exists)
2. Add LLM title generation in `orchestrator.add_memory()`
3. Implement `_compute_similarity_edges()` in `graph_service.py`
4. Modify `get_graph_data()` to fetch embeddings and compute semantic edges
5. Update API response to include edge types

### Phase 2: Frontend (TypeScript/React)
6. Implement bounding box collision detection
7. Add shape mapping (diamond/circle/square)
8. Render semantic edges with dashed cyan styling
9. Build sidebar inspector component
10. Add node type toggle controls
11. Fix z-index layering

### Phase 3: Testing & Refinement
12. Test with 100+ memories
13. Tune similarity threshold (0.7-0.9 range)
14. Optimize collision detection performance
15. Add edge weight visualization (line thickness)

---

## Success Metrics

1. **Visual Clarity**: Labels readable at all zoom levels
2. **Semantic Coherence**: Related memories visually clustered via similarity edges
3. **Performance**: <16ms frame time with 500 nodes
4. **Usability**: Inspector panel provides full context without cluttering canvas

---

## Risk Mitigation

### Performance Risk
**Issue**: Similarity computation O(n²) for large graphs
**Mitigation**: 
- Compute offline, cache in snapshot
- Limit to top-k most similar per memory
- Use approximate nearest neighbors (FAISS) if >1000 memories

### UX Risk
**Issue**: Too many similarity edges = visual spaghetti
**Mitigation**:
- High threshold (0.8) filters weak connections
- Semantic zoom: hide similarity edges at far zoom
- Focus mode: show only edges for selected node

---

## Next Steps

**Immediate**: Switch to Code mode to implement Phase 1 (backend changes)

**Question for User**: Should we start with backend (Python) or frontend (TypeScript) changes first? Backend enables the data, frontend makes it visible.