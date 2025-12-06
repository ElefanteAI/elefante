# Archived Documentation

**Status:** Cleaned 2025-12-05  
**Policy:** Keep only raw forensic evidence not captured elsewhere

---

## Contents

### raw_logs/
| File | Purpose | Why Kept |
|------|---------|----------|
| `install.log` | Original installation output (2025-11-27) | Raw pip versions, timestamps - forensic evidence if install breaks |

---

## What Was Removed

All markdown files were deleted because their information was **extracted and consolidated** into:

- **Neural Registers** - `docs/debug/*_NEURAL_REGISTER.md`
- **Domain Compendiums** - `docs/debug/*/compendium.md`
- **Technical Docs** - `docs/technical/`
- **Main README** - `README.md`

---

## Policy

> **If information is documented elsewhere, the source file has no purpose.**

Only keep:
- Raw logs (forensic evidence)
- Files with unique information not captured in consolidated docs
