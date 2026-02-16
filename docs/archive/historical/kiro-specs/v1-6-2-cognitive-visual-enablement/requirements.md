# v1.6.2 Cognitive Visual Enablement

## Context

v1.6.1 (Cognitive Field Standardization) ensured that `concepts`, `surfaces_when`, and `authority_score` are:
- Consistently stored in ChromaDB as JSON strings
- Correctly reconstructed in V4 Cognitive Retrieval scoring
- Migrated for all existing memories

However, users cannot SEE these fields in the dashboard. v1.6.2 completes the work by making cognitive fields visible.

## User Stories

**US-1**: As a user viewing a memory in the dashboard sidebar, I want to see the extracted concepts so I understand how the system categorizes this memory.

**US-2**: As a user viewing a memory in the dashboard sidebar, I want to see `surfaces_when` triggers so I understand when this memory will be recalled.

**US-3**: As a user viewing a memory in the dashboard sidebar, I want to see the `authority_score` so I understand how authoritative this memory is considered.

## Acceptance Criteria

### AC-1: Concepts Display
- WHEN a user clicks a memory node in the dashboard graph
- THE SYSTEM SHALL display the `concepts` field as a list of tags/chips
- WITH location in the sidebar inspector below the existing Tags section

### AC-2: Surfaces When Display
- WHEN a user clicks a memory node with `surfaces_when` data
- THE SYSTEM SHALL display the triggers as a list of phrases
- WITH a section header "Surfaces When" and clear visual distinction

### AC-3: Authority Score Display
- WHEN a user clicks a memory node with `authority_score` data
- THE SYSTEM SHALL display the score as a visual indicator
- WITH format "Authority: X.XX" or a progress bar representation

### AC-4: Graceful Handling
- WHEN a memory lacks cognitive fields (legacy data)
- THE SYSTEM SHALL NOT display empty sections
- THE SYSTEM SHALL NOT throw errors or break the sidebar

## Technical Scope

**In Scope:**
- Dashboard UI (GraphCanvas.tsx) sidebar inspector modifications
- Display of cognitive fields from existing snapshot data

**Out of Scope:**
- Backend changes (v1.6.1 already provides the data)
- New API endpoints
- Editing cognitive fields from the UI

## Dependencies

- v1.6.1 Cognitive Field Standardization (COMPLETE)
- Dashboard snapshot includes cognitive fields (COMPLETE - scripts/update_dashboard_data.py)

## Approval

- [ ] Requirements approved by user
