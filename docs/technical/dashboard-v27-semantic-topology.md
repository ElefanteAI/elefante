# Dashboard v27.0 - Semantic Topology

**Status**: Implemented  
**Date**: 2025-12-05  
**Upgrade From**: v26.0 (Topology Prime)

---

## Overview

Version 27.0 solves the "Bag of Dots" problem by implementing **Semantic Topology** - a visual hierarchy system that transforms disconnected memory nodes into a coherent knowledge graph with orbital structure.

## The Problem: "Bag of Dots"

**Before v27.0:**
- All nodes rendered as uniform circles
- No visual distinction between critical laws and trivial facts
- Relationships existed in data but not visually apparent
- User couldn't identify important concepts at a glance

## The Solution: Orbital Hierarchy

**v27.0 Implements:**

### 1. Node Size = Importance (Gravity)
```typescript
if (importance >= 10) radius = 20;  // SUN (Critical Laws)
else if (importance >= 8) radius = 12; // PLANET (Insights)
else radius = 6;                       // SATELLITE (Facts)
```

### 2. Node Color = Memory Type (Spectrum)
```typescript
switch(memory_type) {
  case 'decision': return '#ef4444';  // Red (Laws)
  case 'insight': return '#a855f7';   // Purple (Wisdom)
  case 'preference': return '#eab308'; // Gold (User Style)
  case 'episodic': return '#10B981';  // Green (Personal)
  case 'procedural': return '#8B5CF6'; // Purple (How-To)
  default: return '#3b82f6';          // Blue (Facts)
}
```

### 3. Semantic Threads (Relationship Injection)

The topology repair script (`scripts/utils/repair_graph_topology.py`) creates edges based on:

| Rule | Criteria | Edge Type |
|------|----------|-----------|
| Identity Cluster | Shared `CORE_PERSONA` tag | `IDENTITY_BOND` |
| Project Context | Same project (elefante) | `PROJECT_LINK` |
| Domain Clustering | Shared critical tags | `DOMAIN_CLUSTER` |
| Importance Hierarchy | High-importance hub + shared tags | `IMPORTANCE_HIERARCHY` |

---

## Visual Language

### Node Hierarchy
- 🌟 **SUN** (Importance 10): Critical Laws, Core Identity
  - Size: 20px radius
  - Examples: "NEVER use 'properties' as column name", "User Persona"
  
- 🪐 **PLANET** (Importance 8-9): Insights, Preferences
  - Size: 12px radius
  - Examples: "Documentation Architecture", "Workflow Patterns"
  
- 🛰️ **SATELLITE** (Importance <8): Facts, Logs
  - Size: 6px radius
  - Examples: "Python syntax", "File paths"

### Color Spectrum
- 🔴 **Red**: Laws, Decisions (must follow)
- 🟣 **Purple**: Insights, Wisdom (learned patterns)
- 🟡 **Gold**: Preferences, User Style (personal choices)
- 🟢 **Green**: Episodic, Personal (life events)
- 🔵 **Blue**: Facts, Reference (neutral information)

---

## Implementation Files

### Backend
- **`scripts/utils/repair_graph_topology.py`** - Injects semantic relationships
- **`scripts/upgrade_to_v27.bat`** - Automated upgrade script

### Frontend
- **`src/dashboard/ui/src/components/GraphCanvas.tsx`** - Visual hierarchy rendering
- **`src/dashboard/ui/src/App.tsx`** - Debug overlay with topology stats

---

## Upgrade Instructions

### Automated Upgrade
```bash
cd Elefante
scripts\upgrade_to_v27.bat
```

### Manual Steps
1. **Run Topology Repair:**
   ```bash
   python scripts/utils/repair_graph_topology.py
   ```

2. **Update Dashboard Data:**
   ```bash
   python scripts/update_dashboard_data.py
   ```

3. **Restart Dashboard:**
   ```bash
   cd src/dashboard/ui
   npm run dev
   ```

4. **Hard Refresh Browser:**
   - Press `Ctrl+Shift+R` (Windows/Linux)
   - Press `Cmd+Shift+R` (Mac)

---

## Verification

### Visual Indicators

**1. Header Banner:**
- Should show: `🚨 DEBUG: VERSION 27.0 - SEMANTIC TOPOLOGY (HIERARCHY ENFORCED) 🚨`
- Color: Purple background (not red)

**2. Debug Overlay (Top-Right):**
```
SEMANTIC TOPOLOGY v27
NODES: 91 / 91
HUBS (Imp 10): X
ENTITIES: 17
HIERARCHY:
  🌟 SUN (10): Critical Laws
  🪐 PLANET (8-9): Insights
  🛰️ SAT (<8): Facts
```

**3. Visual Graph:**
- **Identity Cluster**: Large RED/GOLD nodes tightly linked in center
- **Critical Laws**: Large RED nodes standing out as anchors
- **Facts**: Small BLUE nodes orbiting larger concepts
- **Relationships**: Visible edges connecting related memories

### Expected Topology Stats

After running `repair_graph_topology.py`:
```
Total Memories Analyzed: 91
Edges Created:
  IDENTITY_BOND: ~10-15
  PROJECT_LINK: ~50-70
  DOMAIN_CLUSTER: ~30-50
  IMPORTANCE_HIERARCHY: ~20-40
Total Semantic Threads: ~110-175
```

---

## Troubleshooting

### Issue: "Still seeing v26.0 header"
**Solution:** Hard refresh browser (Ctrl+Shift+R)

### Issue: "All nodes same size"
**Solution:** 
1. Check if importance metadata exists in memories
2. Verify GraphCanvas.tsx changes applied
3. Clear browser cache

### Issue: "No semantic threads in debug overlay"
**Solution:**
1. Run `repair_graph_topology.py` again
2. Check ChromaDB for `related_memory_ids` field
3. Verify script completed without errors

### Issue: "Dashboard won't start"
**Solution:**
1. Check for TypeScript errors: `npm run build`
2. Verify all imports resolved
3. Check console for error messages

---

## Architecture Notes

### Why Separate Repair Script?

The topology repair is a **one-time migration** that modifies the database. It's separated from the dashboard code to:
1. Allow re-running if relationships need updating
2. Keep dashboard code focused on visualization
3. Enable batch processing of large memory sets
4. Provide clear audit trail of relationship creation

### Why Not Real-Time Relationship Detection?

Real-time semantic analysis would:
- Slow down memory ingestion
- Require LLM calls for every memory
- Create inconsistent relationships over time

Instead, v27.0 uses:
- **Metadata-based rules** (fast, deterministic)
- **Batch processing** (run once, use forever)
- **Explicit relationship storage** (queryable, debuggable)

---

## Future Enhancements (v28.0+)

### Planned Features
- [ ] **Cluster Detection**: DBSCAN algorithm for automatic grouping
- [ ] **Temporal Timeline**: Memory evolution over time
- [ ] **Interactive Editing**: Drag to create relationships
- [ ] **Relationship Strength**: Edge thickness based on semantic similarity
- [ ] **Space Filtering**: Show only memories in selected domain

### Research Directions
- [ ] **LLM-Enhanced Relationships**: Use GPT-4 to detect subtle connections
- [ ] **Temporal Decay Visualization**: Fade old memories unless reinforced
- [ ] **Conflict Detection**: Highlight contradictory memories
- [ ] **Knowledge Gaps**: Identify missing connections

---

## References

- **Neural Register Architecture**: `docs/debug/README.md`
- **Dashboard Architecture**: `docs/technical/dashboard.md`
- **Memory Schema**: `docs/technical/memory-schema-v2.md`
- **Critical Laws**: Stored in Elefante memory (importance: 10)

---

**Last Updated**: 2025-12-05  
**Version**: 27.0  
**Status**: ✅ Production Ready