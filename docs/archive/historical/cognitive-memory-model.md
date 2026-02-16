# Cognitive Memory Model: The "Soul" of Elefante

## The Problem

Current memory storage is "lame" because it treats memories as static text blobs with basic tags. It fails to capture the _impact_ of a memory—how it changes Elefante's understanding of the user, the world, and the relationship between them.

## The Solution: Graph-Native Cognitive Extraction

Instead of just storing a memory, we extract the **Cognitive Delta**: the structural change this memory imposes on the World Model.

### 1. The Cognitive Schema

Every memory is analyzed to extract four dimensions of metadata, which are stored not just as JSON properties, but as **Graph Nodes and Edges**.

#### A. The World Model (Entities & Relationships)

_What exists and how does it relate?_

- **Entities**: People, Tools, Concepts, Projects, Locations.
- **Relationships**: `(User)-[LOVES]->(Rust)`, `(Python)-[BLOCKS]->(Productivity)`, `(Project X)-[DEPENDS_ON]->(API Y)`.
- **Properties**: `strength` (0.0-1.0), `confidence` (0.0-1.0), `source` (memory_id).

#### B. The Emotional Context (The "Vibe")

_How does the user feel?_

- **Valence**: Positive (1.0) to Negative (-1.0).
- **Arousal**: Calm (0.0) to Intense (1.0).
- **Dominance**: In Control (1.0) to Overwhelmed (0.0).
- **Keywords**: "Frustrated", "Determined", "Curious", "Nostalgic".
- **Storage**: Stored as properties on the Memory node, but also used to weight the importance of the memory.

#### C. The Cognitive Intent (The "Why")

_Why is the user sharing this?_

- **Types**:
  - `TEACHING`: User is explaining a concept to Elefante.
  - `VENTING`: User is expressing emotion.
  - `PLANNING`: User is outlining future actions.
  - `REFLECTING`: User is analyzing past events.
  - `DECIDING`: User is making a choice.
- **Action**: This determines _how_ Elefante should use the memory later. (e.g., `TEACHING` memories are high-priority for RAG).

#### D. The Strategic Insight (The "So What?")

_What is the actionable takeaway?_

- A synthesized sentence that describes the _implication_ of the memory.
- Example: "User prioritizes memory safety over development speed."
- Storage: A `Concept` node or a `Rule` node linked to the User.

### 2. Implementation Strategy

#### Phase 1: The "Deep" Pipeline

Refactor `analyze_memory` to output this rich structure:

```json
{
  "title": "User's Disdain for Python GIL",
  "summary": "User expressed strong frustration with Python's GIL, contrasting it with Rust's safety.",
  "entities": [
    { "name": "User", "type": "Person" },
    { "name": "Python", "type": "Technology" },
    { "name": "Rust", "type": "Technology" },
    { "name": "GIL", "type": "Concept" }
  ],
  "relationships": [
    { "from": "User", "to": "Python", "type": "DISLIKES", "reason": "GIL" },
    {
      "from": "User",
      "to": "Rust",
      "type": "LOVES",
      "reason": "Memory Safety"
    },
    { "from": "Python", "to": "GIL", "type": "HAS_PART" }
  ],
  "emotional_context": {
    "valence": -0.6,
    "arousal": 0.8,
    "mood": "Frustrated"
  },
  "cognitive_intent": "VENTING",
  "strategic_insight": "Avoid suggesting Python for performance-critical tasks; prefer Rust."
}
```

#### Phase 2: Graph Execution

The Orchestrator will iterate through this JSON and execute the graph updates:

1.  **Merge Entities**: Ensure "Python" and "Rust" nodes exist.
2.  **Create Relationships**: Create the `DISLIKES` and `LOVES` edges.
3.  **Store Metadata**: Save the emotional/cognitive context in the Memory node's `properties`.

### 3. The "Impact"

When you ask "What do I think about backend languages?", Elefante won't just search for text matches. It will traverse:
`User -[LOVES]-> Rust`
`User -[DISLIKES]-> Python`
And answer: "You have a strong preference for Rust due to safety concerns, and you find Python's GIL frustrating."

**This is the difference between a text search engine and a digital extension of your mind.**
