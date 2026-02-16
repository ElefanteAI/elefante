# v1.6.2 Design - Cognitive Visual Enablement

## Architecture

```
dashboard_snapshot.json
   └── nodes[].properties
          ├── concepts: "[\"concept1\", \"concept2\"]"  (JSON string)
          ├── surfaces_when: "[\"trigger1\", \"trigger2\"]"  (JSON string)
          └── authority_score: "0.85"  (string or number)
                    │
                    ▼
           GraphCanvas.tsx
               │
               └── getProp() helper extracts and parses values
                          │
                          ▼
               Sidebar Inspector renders:
               ┌────────────────────────────┐
               │ 🧠 Second Brain Metrics    │
               │ [existing grid...]         │
               ├────────────────────────────┤
               │ 🎯 Concepts                │ ← NEW (AC-1)
               │ [chip] [chip] [chip]       │
               ├────────────────────────────┤
               │ ⚡ Surfaces When           │ ← NEW (AC-2)
               │ • "when user asks about X" │
               │ • "on project review"      │
               ├────────────────────────────┤
               │ 📊 Authority Score         │ ← NEW (AC-3)
               │ [progress bar] 0.85        │
               └────────────────────────────┘
```

## Component Changes

### File: `src/dashboard/ui/src/components/GraphCanvas.tsx`

**Location**: After the TAGS section (approximately line 2380-2400) in the selectedNode inspector sidebar.

**New Sections to Add:**

1. **Concepts Section**
   - Parse JSON string to array
   - Render as chips similar to Tags
   - Use cyan color for visual distinction from tags

2. **Surfaces When Section**
   - Parse JSON string to array
   - Render as bullet list of trigger phrases
   - Use purple accent for "cognitive" theme

3. **Authority Score Section**
   - Parse string/number to float
   - Render as progress bar (0.0 to 1.0 scale)
   - Color gradient: low=slate, mid=blue, high=emerald

## Data Path

```
getProp('concepts') → JSON.parse() → string[] → map to <span> chips
getProp('surfaces_when') → JSON.parse() → string[] → map to <div> bullets
getProp('authority_score') → parseFloat() → number → progress bar width %
```

## Error Handling

- If field is null/undefined → Don't render section
- If JSON.parse fails → Log warning, don't render
- If array is empty → Don't render section

## Maps to Requirements

| Design Element | Requirement |
|----------------|-------------|
| Concepts chips | AC-1 |
| Surfaces When bullets | AC-2 |
| Authority progress bar | AC-3 |
| Null checks | AC-4 |
