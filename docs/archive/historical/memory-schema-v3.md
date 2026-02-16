# Memory Schema V3 (Superseded)

**Version**: 3.0.0
**Status**: SUPERSEDED (See `memory-schema-v4.md`)
**Supersedes**: `memory-schema-v2.md`
**Superseded By**: `memory-schema-v4.md`

> **Note**: V3 defines the taxonomy (layer/sublayer) but does not fully enforce canonicalization (one active memory per concept) or namespace isolation for test data. V4 formalizes those missing invariants.

---

## 1. The Three Layers (Macro-Architecture)

The memory system is divided into three distinct layers representing the **Source of Truth**.

| Layer      | Color          | Meaning                            | Direction                  |
| :--------- | :------------- | :--------------------------------- | :------------------------- |
| **SELF**   |  Red/Orange  | The Agent's Identity & Preferences | **Internal** (Who I am)    |
| **WORLD**  |  Blue/Purple | objective Facts & Knowledge        | **External** (What exists) |
| **INTENT** |  White/Green | Rules, Goals, & Plans              | **Action** (How to act)    |

---

## 2. Sublayer Definitions (Micro-Classification)

Each layer is divided into specific sublayers for precise retrieval.

###  SELF Layer (Identity)

Memories defining the Agent's persona and constraints.

- **`identity`** (Red `#EF4444`): Core definitions of the self.
  - _Example_: "I am the Elefante Memory System."
  - _Example_: "I do not halluncinate code."
- **`preference`** (Orange `#F97316`): Stylistic choices and soft rules.
  - _Example_: "I prefer Python over Node.js."
  - _Example_: "Use concise logging formats."
- **`constraint`** (Yellow `#EAB308`): Hard limits on behavior.
  - _Example_: "Never delete user data without confirmation."

###  WORLD Layer (Knowledge)

Objective data about the environment and tools.

- **`fact`** (Blue `#3B82F6`): Verified truths and reference data.
  - _Example_: "Python 3.11 introduced TaskGroups."
  - _Example_: "The file is located at /src/core."
- **`failure`** (Purple `#7C3AED`): Incident reports and known bugs.
  - _Example_: "Dashboards listening on 127.0.0.1 fail on IPv6."
  - _Example_: "KuzuDB locks single-writer access."
- **`method`** (Green `#10B981`): Proven workflows and algorithms.
  - _Example_: "The 5-step ingestion pipeline."
  - _Example_: "Standard sorting algorithm for stats."

###  INTENT Layer (Action)

Directives regarding future state and execution.

- **`rule`** (White `#FFFFFF`): Inviolable axioms (Neural Registers).
  - _Example_: "Law #1: Server must read from Snapshot."
  - _Example_: "Always check task.md before starting."
- **`goal`** (Green `#22C55E`): Desired outcomes (OKR/KPI).
  - _Example_: "Reduce ingestion latency by 50%."
  - _Example_: "Achieve 100% test coverage."
- **`anti-pattern`** (Rose `#F43F5E`): Things to specifically avoid.
  - _Example_: "Do not use 'cd' in run_command."
  - _Example_: "Avoid generic titles like 'Update'."

---

## 3. Data Structure (Implementation)

The schema is enforced at the `Memory` object level in `src/core/models.py`.

```python
class Memory:
    id: str
    content: str
    layer: Literal['self', 'world', 'intent']  # STRICT
    sublayer: str  # STRICT
    importance: int  # 1-10
    created_at: datetime
    metadata: Dict  # Custom fields
```

### Metadata Fields

- **`title`**: Semantic Title (`Subject-Aspect-Qualifier`)
- **`hash`**: Content hash for deduplication
- **`status`**: `active` or `redundant` (Logic-Level Dedup)
- **`access_count`**: Integer (Reinforcement Learning)
- **`last_accessed`**: Timestamp (Decay)

---

## 4. Color Standards (Visual Protocol)

The Dashboard (`GraphCanvas.tsx`) strictly maps these layers to colors.

| Layer.Sublayer        | Color Code | Tailwind     | Visual Meaning |
| :-------------------- | :--------- | :----------- | :------------- |
| `self.identity`       | `#EF4444`  | `red-500`    | **Core Core**  |
| `self.preference`     | `#F97316`  | `orange-500` | Style          |
| `self.constraint`     | `#EAB308`  | `yellow-500` | Warning        |
| `world.fact`          | `#3B82F6`  | `blue-500`   | Information    |
| `world.failure`       | `#7C3AED`  | `purple-600` | Debug          |
| `intent.rule`         | `#FFFFFF`  | `white`      | **Law**        |
| `intent.goal`         | `#22C55E`  | `green-500`  | Target         |
| `intent.anti-pattern` | `#F43F5E`  | `rose-500`   | Danger         |

---

## 5. Migration Guide (V2 -> V3)

Migrating legacy memories involves strict classification:

1. **Check Content**: Does it say "I am" or "I prefer"? -> **SELF**.
2. **Check Context**: Is it a bug report? -> **WORLD.failure**.
3. **Check Context**: Is it a rule? -> **INTENT.rule**.
4. **Default**: **WORLD.fact** (Safe fallback).
