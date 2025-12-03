# Developer Journal & Retrospective

## Philosophy

"I have to answer a question or problem. First, I search in documentation, understand, fix, learn from mistakes, document them, then iterate."

## Session: Debugging Dashboard "No Nodes Found" (2025-11-30)

### The Problem

The dashboard displayed "No nodes found" (0 nodes) despite the `dashboard_snapshot.json` containing 24 valid nodes.

### The Journey (and The Failures)

1.  **Mistake: Scope Error (`UnboundLocalError`)**

    - **Action**: Added debug print statements to `app.py` to check `nodes` count.
    - **Error**: Placed the print statement _before_ the `nodes` variable was defined.
    - **Root Cause**: Rushing to see output without checking the execution flow.
    - **Lesson**: Always verify variable scope and definition order before inserting debug code.

2.  **Mistake: Function Signature Mismatch (`ValueError`)**

    - **Action**: Modified `GraphService.get_graph_data` to return `debug_log`.
    - **Error**: Updated the main return path but missed the "Snapshot not found" return path, causing a tuple unpacking error (expected 3 values, got 2).
    - **Root Cause**: Incomplete refactoring.
    - **Lesson**: When changing a function signature, check _all_ return statements and exit points.

3.  **Mistake: Scope Error (`NameError: debug_log`)**

    - **Action**: Added exception handling to log errors to `debug_log`.
    - **Error**: Initialized `debug_log` _inside_ the `try` block. When an error occurred before initialization, the `except` block failed trying to append to it.
    - **Root Cause**: Incorrect assumption about variable availability in exception blocks.
    - **Lesson**: Initialize accumulator variables _before_ entering `try/except` blocks.

4.  **Mistake: Accidental Code Deletion (`NameError: visible_ids`)**

    - **Action**: Added logging to the loop.
    - **Error**: Accidentally deleted the lines defining `visible_ids` and `edges` while using `replace_file_content`.
    - **Root Cause**: Careless use of the tool. Not verifying the context of the replacement.
    - **Lesson**: Use `view_file` to confirm the exact lines to be replaced. Ensure the `ReplacementContent` includes all necessary context if replacing a block.

5.  **Mistake: Logic Regression (Indentation Error)**

    - **Action**: Restored the loop body.
    - **Error**: Indented the `nodes.append` block _outside_ the `for` loop.
    - **Result**: Only the last node (or no nodes) would be processed/added.
    - **Root Cause**: Python indentation sensitivity + lack of visual verification of the structure.
    - **Lesson**: Double-check indentation after every block edit in Python.

6.  **Mistake: Syntax Error (Markdown in Code)**

    - **Action**: Added logging.
    - **Error**: Left a markdown code block fence (```) inside the Python file.
    - **Root Cause**: Copy-paste error from the thought process/response.
    - **Lesson**: Sanitize code before writing.

7.  **Mistake: Data Type Assumption (`AttributeError`)**
    - **Action**: Added trace logs.
    - **Error**: `AttributeError: 'str' object has no attribute 'get'`.
    - **Root Cause**: Assumed `properties` in the JSON snapshot was a dictionary. It was actually a JSON string.
    - **Lesson**: Never assume data types from external sources (files/APIs). Inspect the raw data (`view_file` on the JSON) _before_ writing code that depends on its structure.

### Corrective Actions for Future

1.  **Pre-Edit Inspection**: Always `view_file` the target area before applying `replace_file_content`.
2.  **Atomic Edits**: Make smaller, focused edits rather than large block replacements to minimize collateral damage (like deleting `visible_ids`).
3.  **Data Verification**: Inspect input data files (JSON/CSV) to confirm schema before writing parsing logic.
4.  **Self-Correction**: If a tool call fails, pause. Do not just retry. Analyze _why_ it failed (e.g., "Did I get the line numbers wrong?").

## Session: Browser Automation (General)

_Reflecting on past interactions_

- **Issue**: Opening the wrong browser or URL.
- **Lesson**: Explicitly check the `Url` argument in `open_browser_url`. Verify the port number (e.g., 8501 vs 3000).

---

_This journal will be updated after every significant debugging session._
