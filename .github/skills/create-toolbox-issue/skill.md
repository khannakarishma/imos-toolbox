---
name: create-toolbox-issue
description: >
  Use when creating, filing, or logging a GitHub issue for the IMOS Toolbox
  Python port. Handles porting tasks, parity tests, user stories, feature
  requests, enhancements, tasks, bugs, epics, and technical debt. Formats the
  title with the correct prefix, type tag, and phase tag, populates every
  section of the AODN body template, applies appropriate labels, assigns the
  issue to khannakarishma, and adds it to the AODN Pipeline Uplift Team
  project board (#72).
---

# Create Toolbox Issue

Create a GitHub issue for the IMOS Toolbox Python port following the appropriate template.

## Instructions

When the user describes an issue, determine the type, format the title correctly, fill in the template, create the issue, and add it to the project board.

### Workflow
1. Determine the issue type (see **Issue Types** below)
2. Format the title following the **Title Conventions**
3. Review relevant repo context to ground the details: the README, files under `docs/`, related existing issues, and the code area the issue touches. Use only what the prompt and the repo support — do not fabricate specifics.
4. Read `.github/ISSUE_TEMPLATE/pipeline-general-template.md` for structure and fill the sections that apply
5. Write the content to `NewIssue.md`
6. Create the issue and add it to the project board (see **Using GitHub CLI**)

## Issue Types
| Type | Title prefix | When to use |
|---|---|---|
| User Story | `AS A … I WANT … SO THAT …` | A new capability from a user's perspective |
| Porting task | `🔁(PORT)` | Translating a MATLAB function/module to Python |
| Parity test | `✅(PARITY)` | Verifying Python output matches the MATLAB reference |
| Feature / Enhancement | `✨` | A concrete deliverable beyond the original behaviour |
| Task | `📋(TASK)` | An operational or process task |
| Epic | plain title + `[epic]` tag | A whole phase; too large for one iteration |
| Bug | plain title + `[bug]` tag | Something broken |
| Technical Debt | plain title + `[technical debt]` tag | Clean-up or refactoring |

## Title Conventions
Titles follow this structure:
```
<prefix> <Short description> [phase-N] <[type tag]>
```
- **Phase tag**: always include `[phase-1]` … `[phase-7]` (e.g. NetCDF re-import parser = `[phase-2]`)
- **Type tags**: `[epic]`, `[bug]`, `[technical debt]`
- Story points are set via **labels only** (not in the title)

### Examples
```
🔁(PORT) NetCDF re-import parser [phase-2]
✅(PARITY) GSLA particle PNG output matches MATLAB baseline [phase-2]
✨ Dash callback for variable subsetting [phase-7]
AS A toolbox user I WANT QC flags preserved on re-import SO THAT my QC is not lost [phase-2]
Re-import parser drops global attributes [phase-2] [bug]
```

## Body Template
Use `.github/ISSUE_TEMPLATE/pipeline-general-template.md` as the body. Fill the sections that apply — do not invent content for a section just to fill it; leave a section empty if there is nothing real to put there.
- **User Story** — AS A / I WANT / SO THAT (even for non-story issues, state the goal)
- **Acceptance Criteria** — optional; numbered, verifiable outcomes only when they are known. For familiarisation, discovery, or spike stories, leave this section empty rather than inventing criteria. For ports, include "Python output matches the MATLAB reference within agreed tolerance" when applicable.
- **MATLAB reference** — link or path to the original function(s) being ported
- **Notes** — assumptions, constraints, edge cases, background links
- **Tasks** — checkbox list of sub-tasks; always include the DOD checklist link
- **PRs** — leave as template placeholder; include PR review guidelines link
- **Dependencies** — upstream issues or external blockers

## Using GitHub CLI (gh)

### Step 1 — Create the issue
```bash
# Default repo is aodn/datauplift; specify explicitly if needed
gh issue create -R aodn/datauplift \
  --title "<formatted title>" \
  --body-file NewIssue.md \
  --assignee khannakarishma \
  --label "type - development" \
  --label "2 story points"
```
The command returns the new issue URL — copy it for Step 2.

### Step 2 — Add to the AODN Pipeline Uplift Team project (#72)
```bash
gh project item-add 72 --owner aodn --url <issue-url>
```

### Common Labels
- `type - development` — New feature or system
- `type - operational` — Maintenance or operational work
- `type - testing & release` — Manual testing and deployment
- `Epic` — Too large for an iteration, needs breakdown
- `Blocked` — Cannot be worked on; has blocking dependencies
- `1 story points`, `2 story points`, `3 story points`, `5 story points`, `8 story points` — Complexity estimate

### Other Useful Commands
```bash
# List open issues
gh issue list -R aodn/datauplift

# View an issue
gh issue view <issue-number> -R aodn/datauplift

# Add a comment
gh issue comment <issue-number> -R aodn/datauplift --body "Comment text"

# List items currently in project #72
gh project item-list 72 --owner aodn
```