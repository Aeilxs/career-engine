# ADR-014 — Source Discovery Before LLM and Submission

**Date:** 2026-11-01  
**Status:** Accepted for the bootstrap roadmap.

## Context

Original v0.1 sequencing placed scheduled discovery after document generation and browser automation. This delays validation of the most important business uncertainty: how many relevant job postings can actually be reached via source-specific read paths.

## Decision

Use milestones J0–J7: J0 runtime; J1 manual ingest/tracker/XLSX; J2 source scan/digest; J3 explainable scoring; J4 CV package and approval; J5 simulated form inspection/fill; J6 simulated submission/recovery; J7 one explicitly approved real pilot. Run P1 (30 relevant postings with ATS/provider labels) in parallel with J0/J1 before choosing the first read connector.

## Consequences

The first useful business output appears at J1, and discovery coverage is measured at J2. Every milestone preserves earlier functionality. Failure to automate submission does not invalidate the discovery, qualification and preparation product. No generic ATS-agnostic auto-submit mechanism is promised.

## Change tracking

`REQ-022` moves from old milestone D to J2. The legacy task number is preserved only as provenance; active tickets are `tasks/TASK-J*.md`. Never execute a legacy task order as a substitute for this roadmap.
