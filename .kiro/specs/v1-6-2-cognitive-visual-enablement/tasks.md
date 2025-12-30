# v1.6.2 Tasks - Cognitive Visual Enablement

## Task List

### Task 1: Add Concepts Section to Sidebar
**Maps to**: Design - Concepts Section, AC-1
**File**: `src/dashboard/ui/src/components/GraphCanvas.tsx`
**Location**: After Tags section in selectedNode inspector
**Implementation**:
- Add helper to parse concepts JSON string safely
- Add section with header "🎯 Concepts"
- Render concepts as cyan chips
- Only render if concepts array is non-empty

### Task 2: Add Surfaces When Section to Sidebar
**Maps to**: Design - Surfaces When Section, AC-2
**File**: `src/dashboard/ui/src/components/GraphCanvas.tsx`
**Location**: After Concepts section
**Implementation**:
- Add helper to parse surfaces_when JSON string safely
- Add section with header "⚡ Surfaces When"
- Render as purple-accented bullet list
- Only render if surfaces_when array is non-empty

### Task 3: Add Authority Score Display to Sidebar
**Maps to**: Design - Authority Score Section, AC-3
**File**: `src/dashboard/ui/src/components/GraphCanvas.tsx`
**Location**: After Surfaces When section (or in metrics grid)
**Implementation**:
- Parse authority_score to float
- Render as progress bar with percentage
- Color: gradient based on value
- Only render if authority_score exists and > 0

### Task 4: Rebuild Dashboard UI
**Maps to**: Deployment requirement
**Command**: `cd src/dashboard/ui && npm run build`
**Verification**: dist/ folder updated with new bundle

### Task 5: Version Bump (LAW 13)
**Maps to**: Release protocol
**Files to update (per LAW 13 checklist)**:
- src/__init__.py
- setup.py
- config.yaml (3 locations)
- README.md
- CHANGELOG.md
- docs/README.md
- docs/technical/README.md
- docs/planning/roadmap.md
- docs/technical/architecture.md
- docs/technical/installation.md
- docs/technical/safe-restart.md
- docs/technical/temporal-memory-decay.md
- docs/debug/README.md
- examples/AGENT_TUTORIAL.md
- tests/README.md

### Task 6: Update CHANGELOG
**Maps to**: Documentation requirement
**Content**: Document v1.6.1 and v1.6.2 changes

### Task 7: Verify Visual Output
**Maps to**: AC-1, AC-2, AC-3, AC-4
**Steps**:
1. Run elefanteDashboardOpen with refresh=true
2. Click a memory node
3. Confirm concepts display as chips
4. Confirm surfaces_when displays as list
5. Confirm authority_score displays as bar
