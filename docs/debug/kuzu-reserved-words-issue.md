# Kuzu Reserved Words Issue (`properties`)

**Status**: Documented (canonical analysis lives in the Database Compendium)

## Summary
Kuzu uses SQL for schema (DDL) and Cypher for operations (DML). A column/property name can be valid in SQL schema creation but fail at runtime in Cypher operations.

The most common foot-gun observed in Elefante is using **`properties`** as a column name.

## Canonical Reference
- Full write-up and resolution details: [`docs/debug/database-compendium.md` (Issue #1)](database-compendium.md#issue-1-reserved-word-collision)

## Actionable Rule
- Never use Cypher-reserved words as property names. Prefer `props`, `metadata`, `attributes`, or `data`.
