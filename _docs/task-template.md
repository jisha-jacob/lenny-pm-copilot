# Task template

Used by the PM ([_docs/team/pm.md](team/pm.md)) to groom an issue before
implementation. Every groomed issue should have these four sections.

## Goal

One or two sentences: what this task achieves and why it matters, in terms
someone unfamiliar with the rest of the backlog could understand.

## Acceptance criteria

A checklist of specific, checkable conditions. Each one should be
verifiable by running code or reading its output — not a subjective
judgment call. This is what QA checks off, one by one, to reach a
PASS/FAIL verdict.

## Out of scope

Anything explicitly not covered by this task, especially things that might
seem related. If work is being deferred rather than dropped, link the
follow-up issue that tracks it.

## Constraints

Any technical, architectural, or process constraints that bound how this
task can be implemented (e.g. "must not add a new dependency," "must reuse
the existing X function," relevant decisions from `_docs/plan.md`).
