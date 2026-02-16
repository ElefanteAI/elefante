# Dashboard Visualization Improvement Roadmap

**Date:** 2025-12-04  
**Status:** Planning Phase  
**Goal:** Transform debug tool into usable "Second Brain" interface

## Current Issues

**Problem:** "Label salad" - information density causes occlusion, unreadable without zoom  
**Root causes:**

- All labels rendered at all zoom levels
- Tight node clustering (insufficient repulsion)
- No visual hierarchy beyond size
- Static view with limited interaction

## Implementation Roadmap

### Phase 0: Ribbon (Top Toolbar) — Internal Iteration v32 (Next)

**Goal:** Make the dashboard controllable without editing config/files.

**Note:** “v32” here is an **internal iteration label**, not the repository’s semantic version.

**Priority:** HIGH  
**Complexity:** Medium  
**Files:**

- `src/dashboard/ui/src/App.tsx`
- `src/dashboard/ui/src/components/GraphCanvas.tsx`

**Ribbon controls (minimum):**

- Toggle: **Hide test artifacts** (default ON)
  - Matches server-side filtering for known test strings (e2e/persistence/entity-relationship).
  - Long-term: keep test nodes in snapshot with `is_test_artifact=true` and filter client-side.
- Toggle: **Show signal hubs** (topic/ring/knowledge_type) (default ON)
  - Useful when graph store has few/no edges.
- Button: **Refresh snapshot**
  - Calls MCP refresh endpoint or triggers backend refresh.
- Status: **Snapshot source + timestamp**
  - Display current snapshot path and `generated_at` so mismatches are obvious.

**Acceptance criteria:**

- A user can hide/show test artifacts and signal hubs without regenerating data.
- Dashboard clearly indicates whether it is reading from global data dir or repo-local `data/`.
- No “bag of dots”: with signal hubs on, most memory nodes have at least one edge.

### Phase 1: Visual Rendering & Occlusion Management

#### 1.1 Semantic Zoom (Level of Detail)
**Priority:** HIGH  
**Complexity:** Medium  
**File:** `src/dashboard/ui/src/components/GraphCanvas.tsx`

```typescript
// Add zoom-based LOD
const getVisibleLabels = (scale: number, nodes: Node[]) => {
  if (scale < 0.5) {
    // Z-Index 0: Only high-degree entity hubs
    return nodes.filter(n => n.type === 'entity' && n.degree > 5);
  } else if (scale < 1.0) {
    // Z-Index 1: Entities and Sessions
    return nodes.filter(n => n.type !== 'memory');
  } else {
    // Z-Index 2: All labels
    return nodes;
  }
};
```

**Changes:**
- Line 199-219: Wrap label rendering in LOD check
- Add `degree` property to nodes (calculated from edge count)
- Render labels conditionally based on `scale.current`

#### 1.2 Label Backgrounds & Truncation
**Priority:** HIGH  
**Complexity:** Low  
**File:** `src/dashboard/ui/src/components/GraphCanvas.tsx`

```typescript
// Add pill-shaped label backgrounds
const drawLabelWithBackground = (ctx: CanvasRenderingContext2D, text: string, x: number, y: number) => {
  const metrics = ctx.measureText(text);
  const padding = 4;
  const height = 16;
  
  // Background pill
  ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
  ctx.beginPath();
  ctx.roundRect(
    x - metrics.width / 2 - padding,
    y - height / 2,
    metrics.width + padding * 2,
    height,
    height / 2
  );
  ctx.fill();
  
  // Text
  ctx.fillStyle = '#fff';
  ctx.fillText(text, x, y);
};
```

**Changes:**
- Line 206-219: Replace direct `fillText` with `drawLabelWithBackground`
- Truncate to 15 characters: `text.length > 15 ? text.substring(0, 15) + '...' : text`

#### 1.3 Shape Mapping
**Priority:** MEDIUM  
**Complexity:** Medium  
**File:** `src/dashboard/ui/src/components/GraphCanvas.tsx`

```typescript
const drawNode = (ctx: CanvasRenderingContext2D, node: Node) => {
  ctx.save();
  ctx.translate(node.x, node.y);
  
  if (node.type === 'entity') {
    // Hexagon
    drawHexagon(ctx, node.radius);
  } else if (node.type === 'session') {
    // Square
    ctx.fillRect(-node.radius, -node.radius, node.radius * 2, node.radius * 2);
  } else {
    // Circle (memory)
    ctx.arc(0, 0, node.radius, 0, Math.PI * 2);
  }
  
  ctx.fill();
  ctx.restore();
};

const drawHexagon = (ctx: CanvasRenderingContext2D, radius: number) => {
  ctx.beginPath();
  for (let i = 0; i < 6; i++) {
    const angle = (Math.PI / 3) * i;
    const x = radius * Math.cos(angle);
    const y = radius * Math.sin(angle);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.closePath();
};
```

**Changes:**
- Line 178-197: Replace circle drawing with shape-based rendering

### Phase 2: Physics & Force-Directed Layout

#### 2.1 Increase Charge Repulsion
**Priority:** HIGH  
**Complexity:** Low  
**File:** `src/dashboard/ui/src/components/GraphCanvas.tsx`

**Current (Line 103-104):**
```typescript
if (dist < 200) {
  const force = 100 / (dist * dist);
```

**Improved:**
```typescript
if (dist < 300) {  // Increased range
  const force = 500 / (dist * dist);  // 5x stronger repulsion
```

#### 2.2 Collision Detection for Labels
**Priority:** MEDIUM  
**Complexity:** High  
**File:** `src/dashboard/ui/src/components/GraphCanvas.tsx`

```typescript
// Add label bounding box to node
interface Node {
  // ... existing properties
  labelWidth: number;
  labelHeight: number;
}

// In repulsion loop (after line 100)
const labelOverlap = (n1: Node, n2: Node) => {
  const dx = Math.abs(n1.x - n2.x);
  const dy = Math.abs(n1.y - n2.y);
  return dx < (n1.labelWidth + n2.labelWidth) / 2 &&
         dy < (n1.labelHeight + n2.labelHeight) / 2;
};

if (dist < 200 || labelOverlap(nodes[i], nodes[j])) {
  // Apply repulsion
}
```

#### 2.3 Variable Link Distances
**Priority:** MEDIUM  
**Complexity:** Low  
**File:** `src/dashboard/ui/src/components/GraphCanvas.tsx`

**Current (Line 126):**
```typescript
const force = (dist - 100) * 0.005;
```

**Improved:**
```typescript
// Determine ideal distance based on relationship
const getIdealDistance = (source: Node, target: Node, edgeType: string) => {
  if (source.type === 'session' && target.type === 'memory') return 80;  // Tight orbit
  if (source.type === 'entity' && target.type === 'memory') return 150;  // Loose connection
  return 100;  // Default
};

const idealDist = getIdealDistance(source, target, edge.type);
const force = (dist - idealDist) * 0.005;
```

#### 2.4 Cluster Force
**Priority:** LOW  
**Complexity:** High  
**File:** `src/dashboard/ui/src/components/GraphCanvas.tsx`

```typescript
// After line 145, add cluster gravity
const clusterCentroids = {
  'User': { x: width * 0.25, y: height * 0.25 },
  'Work': { x: width * 0.75, y: height * 0.25 },
  'Elefante': { x: width * 0.5, y: height * 0.75 }
};

nodes.forEach(node => {
  if (node.type === 'memory') {
    // Find primary entity connection
    const primaryEntity = findPrimaryEntity(node, edges);
    if (primaryEntity && clusterCentroids[primaryEntity]) {
      const centroid = clusterCentroids[primaryEntity];
      const dx = centroid.x - node.x;
      const dy = centroid.y - node.y;
      node.vx += dx * 0.0002;  // Weak clustering force
      node.vy += dy * 0.0002;
    }
  }
});
```

### Phase 3: Interaction Logic

#### 3.1 Focus Mode (Adjacency Highlighting)
**Priority:** HIGH  
**Complexity:** Medium  
**File:** `src/dashboard/ui/src/components/GraphCanvas.tsx`

```typescript
const [focusedNode, setFocusedNode] = useState<Node | null>(null);
const [adjacentNodes, setAdjacentNodes] = useState<Set<string>>(new Set());

const handleNodeClick = (node: Node) => {
  setFocusedNode(node);
  
  // Find all adjacent nodes
  const adjacent = new Set<string>([node.id]);
  edgesRef.current.forEach(edge => {
    if (edge.source === node.id) adjacent.add(edge.target);
    if (edge.target === node.id) adjacent.add(edge.source);
  });
  setAdjacentNodes(adjacent);
};

// In render loop (line 178)
nodes.forEach(node => {
  const isAdjacent = adjacentNodes.has(node.id);
  const opacity = focusedNode && !isAdjacent ? 0.1 : 1.0;
  
  ctx.globalAlpha = opacity;
  // ... draw node
  ctx.globalAlpha = 1.0;
});
```

#### 3.2 Sidebar Inspector Panel
**Priority:** MEDIUM  
**Complexity:** Medium  
**File:** `src/dashboard/ui/src/App.tsx` (new component)

```typescript
const InspectorPanel: React.FC<{ node: Node | null }> = ({ node }) => {
  if (!node) return null;
  
  return (
    <div className="fixed right-0 top-0 h-full w-96 bg-gray-900 p-6 overflow-y-auto">
      <h2 className="text-xl font-bold mb-4">{node.label}</h2>
      <div className="space-y-2">
        <div><strong>Type:</strong> {node.type}</div>
        <div><strong>ID:</strong> {node.id}</div>
        {node.properties?.description && (
          <div>
            <strong>Description:</strong>
            <p className="mt-2 text-sm text-gray-300">{node.properties.description}</p>
          </div>
        )}
        {node.properties?.created_at && (
          <div><strong>Created:</strong> {new Date(node.properties.created_at).toLocaleString()}</div>
        )}
      </div>
    </div>
  );
};
```

#### 3.3 Search/Filter
**Priority:** HIGH  
**Complexity:** Medium  
**File:** `src/dashboard/ui/src/App.tsx`

```typescript
const [searchQuery, setSearchQuery] = useState('');
const [filteredNodeIds, setFilteredNodeIds] = useState<Set<string>>(new Set());

useEffect(() => {
  if (!searchQuery) {
    setFilteredNodeIds(new Set());
    return;
  }
  
  const matches = new Set<string>();
  nodesRef.current.forEach(node => {
    const searchText = `${node.label} ${node.properties?.description || ''}`.toLowerCase();
    if (searchText.includes(searchQuery.toLowerCase())) {
      matches.add(node.id);
    }
  });
  setFilteredNodeIds(matches);
}, [searchQuery]);

// In render: highlight matches, fade non-matches
```

#### 3.4 Node Type Toggles
**Priority:** LOW  
**Complexity:** Low  
**File:** `src/dashboard/ui/src/App.tsx`

```typescript
const [visibleTypes, setVisibleTypes] = useState({
  memory: true,
  entity: true,
  session: true
});

// Filter nodes before rendering
const visibleNodes = nodesRef.current.filter(n => visibleTypes[n.type]);
```

### Phase 4: Architecture

#### 4.1 Web Workers for Physics
**Priority:** LOW (only if >500 nodes)  
**Complexity:** High  
**File:** `src/dashboard/ui/src/workers/physics.worker.ts` (new)

```typescript
// Offload physics simulation to worker thread
self.onmessage = (e) => {
  const { nodes, edges } = e.data;
  
  // Run physics step
  const updatedNodes = runPhysicsStep(nodes, edges);
  
  self.postMessage({ nodes: updatedNodes });
};
```

#### 4.2 Edge List Merging in Deduplication
**Priority:** MEDIUM  
**Complexity:** Low  
**File:** `src/dashboard/graph_service.py`

**Current (Line 67-78):** Edges reference canonical IDs but don't merge duplicates

**Improved:**
```python
# After deduplication, merge edge lists
edge_set = set()  # Use (src, dst, label) tuples to deduplicate
for e in data.get("edges", []):
    src = id_map.get(e["from"])
    dst = id_map.get(e["to"])
    if src and dst and src != dst:
        edge_set.add((src, dst, e["label"]))

processed_edges = [
    {"from": src, "to": dst, "label": label}
    for src, dst, label in edge_set
]
```

## Implementation Priority

**Sprint 1 (High Priority):**
1. Increase charge repulsion (2.1) - 1 hour
2. Label backgrounds & truncation (1.2) - 2 hours
3. Semantic zoom (1.1) - 4 hours
4. Focus mode (3.1) - 3 hours
5. Search/filter (3.3) - 3 hours

**Sprint 2 (Medium Priority):**
6. Variable link distances (2.3) - 2 hours
7. Shape mapping (1.3) - 4 hours
8. Sidebar inspector (3.2) - 3 hours
9. Collision detection (2.2) - 6 hours
10. Edge merging (4.2) - 2 hours

**Sprint 3 (Low Priority):**
11. Node type toggles (3.4) - 1 hour
12. Cluster force (2.4) - 4 hours
13. Web Workers (4.1) - 8 hours (only if needed)

## Success Metrics

- **Readability:** Can read all entity labels at default zoom
- **Navigation:** Can find specific memory in <10 seconds via search
- **Performance:** 60 FPS with 500+ nodes
- **Usability:** Can explore knowledge graph without documentation

---
*Roadmap created 2025-12-04 based on user feedback*