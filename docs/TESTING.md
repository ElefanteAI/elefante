# Quick Testing Instructions for Hybrid Search

## Prerequisites
1. Elefante MCP server must be running
2. You need a session UUID (generate one or use existing)

## Test 1: Add Memory to LONG-TERM Storage
```
Use tool: addMemory
{
  "content": "Jaime prefers PostgreSQL for production databases",
  "memory_type": "fact",
  "importance": 8
}
```
**Expected**: Success message with memory_id

## Test 2: Search LONG-TERM Memory Only
```
Use tool: searchMemories
{
  "query": "What database does Jaime prefer?",
  "include_stored": true,
  "include_conversation": false
}
```
**Expected**: Should find the PostgreSQL memory you just added

## Test 3: Search with SHORT-TERM Context
First, have a conversation in this session, then:
```
Use tool: searchMemories
{
  "query": "What did we just discuss?",
  "session_id": "YOUR-SESSION-UUID-HERE",
  "include_conversation": true,
  "include_stored": false
}
```
**Expected**: Should find recent messages from THIS session only

## Test 4: Hybrid Search (SHORT + LONG)
```
Use tool: searchMemories
{
  "query": "database preferences",
  "session_id": "YOUR-SESSION-UUID-HERE",
  "include_conversation": true,
  "include_stored": true
}
```
**Expected**: Results from BOTH current session AND stored memories

## Test 5: Verify Deduplication
Add the same content twice, then search:
```
Use tool: addMemory
{"content": "Python is my favorite language", "importance": 7}

Use tool: addMemory  
{"content": "Python is my favorite language", "importance": 7}

Use tool: searchMemories
{"query": "favorite programming language"}
```
**Expected**: Should see merged/deduplicated results, not duplicates

## Quick Verification Checklist
- [ ] Can add memories (LONG-TERM storage works)
- [ ] Can search stored memories (LONG-TERM search works)
- [ ] Can search current session (SHORT-TERM search works)
- [ ] Can search both together (HYBRID works)
- [ ] Duplicates are removed (DEDUPLICATION works)

## Troubleshooting
- If no results: Check that memories were actually stored
- If duplicates appear: Check deduplication threshold (default 0.95)
- If session search fails: Verify session_id is correct UUID format

## Success Criteria
✅ All 5 tests pass
✅ No errors in responses
✅ Results are relevant to queries
✅ No duplicate results in hybrid search