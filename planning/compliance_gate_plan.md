# Elefante Memory Compliance Gate (VS Code / Copilot Edition)

**Generated on:** 2025-12-28
**Target Environment:** VS Code + GitHub Copilot (No native "stop-hooks")

## 🌍 Project One-Liner
Build a **"Token-Based Compliance Gate"** inside the MCP Server that forces the agent to "earn" the right to complete a task by performing a memory search, mechanically enforcing the "Ralph-style" loop via tool dependencies.

---

## 🧠 The Core Problem & Solution
**Problem:** In VS Code, we cannot intercept the agent's final text output to block it (no "stop-hook"). We cannot force a loop *after* generation.
**Solution:** We move the enforcement **upstream** into the tool chain. We make the "Compliance Stamp" (which the user requires) impossible to forge. The agent *must* call a specific tool to generate the stamp, and that tool *will fail* if a search hasn't happened.

### The "Ralph Loop" Adaptation
Instead of a wrapper script looping the agent, the **Agent loops itself** against the MCP server:
1. Agent wants to finish.
2. Agent calls `elefanteAssertCompliance` to get the required stamp.
3. **GATE:** Tool returns `FAIL: No search detected. Search required.`
4. Agent is forced to call `elefanteMemorySearch`.
5. Agent calls `elefanteAssertCompliance` again.
6. **GATE:** Tool returns `PASS` + The Official Stamp.
7. Agent outputs response.

---

## ⚙️ Technical Architecture

### 1. Server-Side State Tracking (`src/mcp/server.py`)
The MCP Server will maintain a lightweight, transient state for the active session:
```python
self.compliance_state = {
    "last_search_timestamp": None,
    "last_search_count": 0,
    "search_token_valid": False  # The "Key"
}
```

### 2. The "Key" Generator: `elefanteMemorySearch`
We modify the existing search tool. When called, it not only returns results but **issues a compliance token**:
- Updates `last_search_timestamp = now()`
- Updates `last_search_count = len(results)`
- Sets `search_token_valid = True`

### 3. The "Gate" Tool: `elefanteAssertCompliance`
A new MCP tool that the agent is instructed to call at the end of every coding task.

**Logic:**
- **IF** `search_token_valid == False`:
    - **RETURN:** `{"status": "FAIL", "message": "⛔ GATE CLOSED. You have not searched Elefante in this turn. You MUST call 'elefanteMemorySearch' before I can issue the Compliance Stamp."}`
- **IF** `search_token_valid == True`:
    - **CONSUME TOKEN:** Set `search_token_valid = False` (One-time use per search).
    - **GENERATE STAMP:**
        - If `last_search_count > 0`: `"[COMPLIANCE] YES I HAVE SEARCHED, FOUND {n} RELEVANT MEMORIES, BROUGHT THEM TO AGENT."`
        - If `last_search_count == 0`: `"[COMPLIANCE] YES I HAVE SEARCHED, I HAVE FOUND ZERO RELEVANT MEMORIES, NOTHING WAS BROUGHT TO AGENT."`
    - **RETURN:** `{"status": "PASS", "stamp": "..."}`

---

## 📝 Implementation Steps

### Phase 1: Server State & Tool Logic
1.  **Modify `ElefanteMCPServer` class:** Add `_reset_compliance_state()` and the state dictionary.
2.  **Update `_handle_search_memories`:** Set the state flags upon successful search.
3.  **Implement `_handle_assert_compliance`:** The gate logic described above.
4.  **Register Tool:** Add `elefanteAssertCompliance` to the tool list description.

### Phase 2: Agent Instructions (The "Soft" Link)
1.  **Update `elefante-grounding` Prompt:** Explicitly tell the agent:
    > "You are REQUIRED to include the official Compliance Stamp at the end of your response. You cannot write this stamp yourself; you must obtain it by calling `elefanteAssertCompliance`. If the tool rejects you, you must perform the search it demands."

### Phase 3: Verification
1.  **Test Case A (The Lazy Agent):** Call `Assert` without searching -> Expect FAIL.
2.  **Test Case B (The Good Agent):** Call `Search` -> Call `Assert` -> Expect PASS + Stamp.
3.  **Test Case C (The Double Dip):** Call `Assert` twice -> Expect FAIL on second call (Token consumed).

---

## 🚦 Feasibility
- **VS Code Compatible:** Yes. Relies only on standard MCP tool calls.
- **Enforcement Level:** **High**. The agent cannot "guess" the stamp if we make the stamp format strict or include a dynamic hash (optional, but "YES/ZERO" is the user requirement).
- **Friction:** Adds 1 extra tool call step to the agent's workflow. Acceptable for the safety guarantee.

## ⏭️ Next Action
Wait for user approval to proceed with **Phase 1 (Server Implementation)**.
