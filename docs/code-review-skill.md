# Code Review Skill

## Why a dedicated review skill?

When Claude is executing a task it aims to complete it as quickly as possible, often missing required functionality or introducing bugs. Switching it to "reviewing code" changes its behaviour. A few lines of simple, terse text perform better than lists of things to check — Claude tends to skip long checklists.

I run `/simple-code-reviewer` before every commit. It catches things the automated tools (linter, type checker, tests) don't: incomplete implementations, logic bugs, missing edge cases, scope creep.

## The skill

```
Can you review the code changes here <PR_URL> OR <BRANCH_NAME>

Look for code smells, bugs, etc. Be rigorous, examine every line of code
that has changed or been created. Think deeply about whether the change is
well engineered and complete, does it do what the description in the PR says
it needs to, does it have good test coverage? Don't make suggestions that are
out of scope of the required change. Out of scope means that there would be
changes to files that weren't part of the original PR or changeset and
deferring these to a future PR wouldn't adversely affect the current
PR/branch.

Present your findings back to me.
```
