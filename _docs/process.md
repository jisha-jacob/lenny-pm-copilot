# Process

## Tasks

Tasks are GitHub issues, worked one at a time. Don't start a second issue
while one is in progress.

Before starting an issue, and again before closing it, read its acceptance
criteria. Work isn't done because code was written — it's done because every
acceptance criterion is met.

Commit regularly, with clear messages. Don't batch a whole issue into one
commit at the end.

## Roles

- **PM** ([_docs/team/pm.md](team/pm.md)) grooms a task before anyone
  implements it — turning a backlog entry into a fully-specified issue.
- **Engineer** ([_docs/team/software-engineer.md](team/software-engineer.md))
  implements one groomed task.
- **QA** ([_docs/team/qa-engineer.md](team/qa-engineer.md)) checks the result
  against the issue's acceptance criteria.

## Orchestrator lifecycle

1. Pick the next open issue.
2. PM grooms it.
3. Engineer implements it.
4. QA verifies it.
   - **FAIL** → back to Engineer, with QA's comment as input. Return to
     step 3.
   - **PASS** → close the issue.
5. Repeat from step 1.
