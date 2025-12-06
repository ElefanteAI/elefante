# 🧠 DASHBOARD NEURAL REGISTER
## System Immunity: Dashboard Failure Laws

**Purpose**: Permanent record of dashboard architecture failures and visual design principles  
**Status**: Active Neural Register  
**Last Updated**: 2025-12-05

---

## 📜 THE LAWS (Immutable Truths)

### LAW #1: Data Path Separation
**Statement**: Dashboard MUST read from static snapshot files, NEVER directly from Kuzu database.

**Architecture Mandate**:
```
MCP Server (Write) → kuzu_db/ → Export Script → snapshot.json → Dashboard (Read)
```

**Rationale**:
1. **Lock Conflict**: Kuzu single-writer lock prevents concurrent access
2. **Performance**: Graph queries too slow for real-time UI
3. **Stability**: Dashboard crashes don't corrupt database
4. **Deployment**: Static files enable serverless hosting

**Anti-Pattern**: Dashboard connecting directly to `kuzu_db/`  
**Correct Pattern**: Dashboard reads `dashboard_data/snapshot.json`

**Implementation**:
- Export script: `scripts/update_dashboard_data.py`
- Data location: `Elefante/dashboard_data/snapshot.json`
- Update trigger: Manual or scheduled (not real-time)

---

### LAW #2: Semantic Zoom (Level of Detail)
**Statement**: Graph visualization MUST implement progressive disclosure based on zoom level.

**Visual Physics Principle**: Human cognition cannot process 1000+ nodes simultaneously.

**LOD Strategy**:
```
Zoom Level 1 (Far):   Show only Space nodes (5-10 nodes)
Zoom Level 2 (Mid):   Show Spaces + high-importance entities (50-100 nodes)
Zoom Level 3 (Near):  Show full subgraph with relationships (500+ nodes)
```

**Implementation Requirements**:
- Node filtering by importance score (1-10)
- Edge filtering by relationship strength
- Dynamic label rendering (hide at distance)
- Cluster aggregation for dense regions

**Anti-Pattern**: Rendering all nodes at once → browser freeze  
**Correct Pattern**: Progressive rendering based on viewport

---

### LAW #3: Force-Directed Layout Constraints
**Statement**: Physics simulation MUST have bounded parameters to prevent chaos.

**Critical Parameters**:
```javascript
{
  charge: -300,           // Repulsion (too high = explosion)
  linkDistance: 100,      // Edge length (too low = overlap)
  collisionRadius: 30,    // Node spacing (prevent overlap)
  alphaDecay: 0.02,       // Simulation cooling (too fast = jitter)
  velocityDecay: 0.4      // Friction (too low = perpetual motion)
}
```

**Failure Modes**:
1. **Explosion**: Charge too high → nodes fly off screen
2. **Collapse**: Charge too low → all nodes cluster at center
3. **Jitter**: Alpha decay too fast → simulation never stabilizes
4. **Perpetual Motion**: Velocity decay too low → nodes never stop

**Tuning Protocol**: Adjust one parameter at a time, test with real data (100+ nodes)

---

### LAW #4: Space-Based Organization
**Statement**: Knowledge graph MUST be organized into semantic "Spaces" for navigation.

**Space Definition**: Top-level category representing a domain of knowledge.

**Core Spaces**:
- 🏗️ **Architecture**: System design, technical decisions
- 🐛 **Debug**: Failure patterns, troubleshooting
- 📦 **Installation**: Setup, configuration, deployment
- 🧠 **Memory**: Cognitive model, retrieval strategies
- 🎨 **Dashboard**: Visualization, UI/UX

**Navigation Pattern**:
1. User selects Space → Filter graph to Space entities
2. User clicks entity → Show relationships within Space
3. User explores → Cross-Space links shown as bridges

**Implementation**: Entity metadata includes `space` property

---

### LAW #5: Build Toolchain Stability
**Statement**: Dashboard build MUST use locked dependency versions to prevent breakage.

**The npm Chaos**: Unlocked versions (`^1.2.3`) introduce breaking changes unpredictably.

**Lock Strategy**:
```json
{
  "dependencies": {
    "react": "18.2.0",           // Exact version, no ^
    "d3-force": "3.0.0",         // Exact version, no ^
    "vite": "5.0.0"              // Exact version, no ^
  }
}
```

**Verification**: `package-lock.json` MUST be committed to version control

**Failure Case** (2025-11-28):
- Vite updated from 5.0.0 → 5.1.0
- Breaking change in dev server API
- Dashboard build failed
- Resolution: Pin to 5.0.0, commit lock file

---

## 🔬 FAILURE PATTERNS (Documented Cases)

### Pattern #1: Direct Database Access Deadlock (2025-11-28)
**Trigger**: Dashboard attempting to read from `kuzu_db/` while MCP server running  
**Symptom**: "Cannot acquire lock" error, dashboard hangs  
**Root Cause**: Kuzu single-writer architecture  
**Impact**: Dashboard unusable when MCP active  
**Resolution**: Implement snapshot export pattern  
**Prevention**: Architecture documentation, code review

### Pattern #2: Node Explosion (2025-11-28)
**Trigger**: Rendering 500+ nodes without LOD filtering  
**Symptom**: Browser freeze, tab crash  
**Root Cause**: Force simulation with unbounded charge  
**Impact**: Dashboard unusable for real data  
**Resolution**: Implement semantic zoom, filter by importance  
**Prevention**: Performance testing with production data

### Pattern #3: Build Toolchain Breakage (2025-11-28)
**Trigger**: `npm install` with unlocked dependency versions  
**Symptom**: Vite dev server fails to start  
**Root Cause**: Breaking change in minor version update  
**Impact**: Development blocked  
**Resolution**: Pin exact versions, commit lock file  
**Prevention**: Dependency audit, lock file validation

---

## 🛡️ SAFEGUARDS (Active Protections)

### Safeguard #1: Snapshot Export Script
**Location**: `scripts/update_dashboard_data.py`  
**Action**: Export Kuzu graph to static JSON  
**Response**: Dashboard reads from snapshot, not live database

### Safeguard #2: Performance Budget
**Location**: Dashboard code comments  
**Action**: Max 100 nodes rendered at zoom level 1  
**Response**: Browser remains responsive

### Safeguard #3: Dependency Lock File
**Location**: `src/dashboard/ui/package-lock.json`  
**Action**: Exact version pinning  
**Response**: Reproducible builds

---

## 📊 METRICS

### Dashboard Load Time
- **Before Optimization**: 15+ seconds (500 nodes)
- **After LOD**: <2 seconds (filtered to 50 nodes)

### Browser Stability
- **Before**: Frequent tab crashes with real data
- **After**: Stable with 1000+ node graphs

### Build Reproducibility
- **Before**: 30% failure rate on fresh install
- **After**: 100% success with locked dependencies

---

## 🎯 IMPROVEMENT ROADMAP

### Phase 1: Core Stability (COMPLETE)
- ✅ Snapshot export pattern
- ✅ Semantic zoom implementation
- ✅ Dependency locking

### Phase 2: Enhanced Visualization (PLANNED)
- [ ] Cluster detection (DBSCAN algorithm)
- [ ] Temporal timeline view (memory evolution)
- [ ] Search and highlight (find entities)
- [ ] Export to image (PNG/SVG)

### Phase 3: Interactive Features (FUTURE)
- [ ] Node editing (update metadata)
- [ ] Relationship creation (drag-and-drop)
- [ ] Space management (create/delete)
- [ ] Memory consolidation trigger (UI button)

---

## 🔗 RELATED REGISTERS

- **DATABASE_NEURAL_REGISTER.md**: Kuzu lock architecture, connection lifecycle
- **INSTALLATION_NEURAL_REGISTER.md**: Pre-flight checks, configuration hierarchy

---

## 📚 SOURCE DOCUMENTS

- `docs/debug/dashboard/dashboard-postmortem.md` (detailed failure analysis)
- `docs/debug/dashboard/dashboard-build-failure-2025-11-28.md` (build issues)
- `docs/technical/dashboard-improvement-roadmap.md` (future enhancements)
- `docs/technical/dashboard.md` (architecture documentation)

---

**Neural Register Status**: ✅ ACTIVE  
**Enforcement**: Architecture review, performance testing  
**Last Validation**: 2025-12-05