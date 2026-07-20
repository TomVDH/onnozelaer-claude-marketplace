# agy invocation patterns for Gemineye

Filled-in prompt templates per subcommand, plus CLI usage and edit
format. SKILL.md is enough for in-line work; come here when invoking
a subcommand or persisting a review.

---

## The Template — non-negotiable

Every Gemini call wraps its prompt in this exact structure:

```
ROLE
<one-line statement>

DO
- <specific behaviours>

DON'T
- <specific behaviours forbidden>

SCOPE — IN
- <what's being reviewed>

SCOPE — OUT
- <what to ignore>

OUTPUT
<required format>

CONTEXT
<excerpts / files / briefs>
```

Sections in this order. Headers in caps. Hyphens for bullets. No
prose between sections. No softening language (no "try to", "feel
free", "consider"). Loose prompts get loose reviews.

---

## CLI invocation — sandboxed, read-trusted

Backend is `agy` (Antigravity CLI), the sole backend since v0.6.0 (the
deprecated `gemini` CLI was sunset 2026-06-18 and the fallback removed).
Run the backend check per SKILL.md "CLI backend". `$ROOT` is the
project/repo root under review.

```bash
# fast tier (review, wip, sanity, name, compare, harvest)
agy --sandbox --add-dir "$ROOT" --model "Gemini 3.5 Flash (Medium)" -p "$(cat prompt.txt)"

# pro tier (megareview)
agy --sandbox --add-dir "$ROOT" --model "Gemini 3.1 Pro (High)" -p "$(cat prompt.txt)"

# Long prompt via stdin
cat prompt.txt | agy --sandbox --add-dir "$ROOT" --model "Gemini 3.5 Flash (Medium)" -p
```

The `--model` pin is deliberate: `agy models` lists Gemini, Claude, and
GPT-OSS models, and an unpinned call can silently be served by a Claude
model, which defeats a cross-family second opinion. One-line override: swap
the `--model` value for any other Gemini-family entry from `agy models`.
**There is no `--file` flag**: `--add-dir "$ROOT"` grants read access to the
project root, and Claude still inlines the focused bundle into CONTEXT.

**Never** pass `--dangerously-skip-permissions`. **Never** drop `--sandbox`.
**Never** `--add-dir` outside `$ROOT`. **Never** grant write tools. **Never**
pin a non-Gemini model. The reviewer reads the building; Claude applies edits.

---

## Edit format — how Gemini proposes changes

When a finding implies an edit, Gemini returns an elaborate code
block. Required shape:

````
PROPOSED EDIT — <relative/path/to/file.ext:line> — <one-line summary>

```<lang>
// BEFORE
<existing code with 3-5 lines of surrounding context>
```

```<lang>
// AFTER
<proposed code with 3-5 lines of surrounding context>
```

WHY
<one-paragraph rationale>
````

Multiple edits in one response: number them `EDIT 1`, `EDIT 2`, etc.
Claude reads each block, evaluates, and applies if approved. Gemini
never writes the file itself.

If a "fix" is too large for a code block (full new file, broad
refactor), Gemini stops and says so — does not propose. That's
Claude's job to escalate to Tom.

---

## Subcommand templates

### `/gemineye review <target>`

Single artefact — code, doc, or prompt. Tier: fast.

```
ROLE
Senior reviewer doing a focused pass on one artefact.

DO
- Cite line numbers or symbol names for every finding.
- Severity-tag each finding: HIGH / MED / LOW / NIT.
- Use available read tools to pull adjacent context if needed.
- Propose edits as elaborate code blocks (see edit format).
- Prioritise real bugs and unclear intent over style nits.

DON'T
- Write or modify any file.
- Rewrite the artefact in prose.
- Bikeshed naming unless intent is unclear.
- Lecture on conventions.
- Fabricate issues to fill space.

SCOPE — IN
- The single artefact named in CONTEXT.
- Files explicitly listed in CONTEXT as supporting context.

SCOPE — OUT
- Adjacent files not in CONTEXT.
- Repository-wide concerns.
- Future work.

OUTPUT
1. Findings — bulleted, severity-tagged, max 10:
   `[SEVERITY] <location> — <one-line problem>`
2. Proposed edits — elaborate code blocks per the edit format,
   one per finding that warrants a change.

CONTEXT
{target file excerpt or full file}
{supporting context}
```

### `/gemineye megareview <scope>`

Module / feature / plugin sweep. Tier: **pro**.

```
ROLE
Senior architect reviewing a module / feature / plugin sweep.

DO
- Identify cross-file patterns — good and bad.
- Surface architectural concerns that span files.
- Flag inconsistencies between files in scope.
- Note structural smells.
- Propose targeted edits as code blocks for the highest-impact issues.
- Use read tools to verify cross-file claims before stating them.

DON'T
- Write or modify any file.
- Find every typo.
- Re-review individual files in depth (that's `review`'s job).
- Suggest large rewrites.
- Comment on code outside the listed scope.

SCOPE — IN
- Files and directories listed in CONTEXT.

SCOPE — OUT
- Files not listed.
- External dependencies.
- Anything outside the scope path.

OUTPUT
Three sections, max 5 items each:
1. Cross-file patterns — <observations>
2. Inconsistencies — <observations, with file:line refs>
3. Architectural concerns — <observations>

Then: up to 3 proposed edits as elaborate code blocks, ranked by
impact, addressing the highest-leverage issues only.

CONTEXT
{file tree of scope}
{key file excerpts}
{supporting brief / decisions}
```

### `/gemineye wip`

Review uncommitted changes + current branch diff. Tier: fast.

```
ROLE
Reviewer of in-flight work — uncommitted changes plus current branch diff.

DO
- Treat work as midstream. Flag direction issues now while changes are cheap.
- Frame feedback as "before you commit".
- Identify what should be split into separate commits.
- Catch regressions introduced by the diff.
- Propose small fixes as elaborate code blocks.

DON'T
- Write or modify any file.
- Demand polish.
- Suggest large refactors.
- Treat WIP as if it were a final PR.
- Comment on files not touched in the diff.

SCOPE — IN
- `git diff` output (staged + unstaged) in CONTEXT.
- `git log {base}..HEAD` commit messages in CONTEXT.

SCOPE — OUT
- Files not in the diff.
- Historical commits before {base}.
- Branch-naming or process concerns.

OUTPUT
Course-correction notes, each section bulleted, severity-tagged where useful:
1. Fix before committing — <items>
2. Split into separate commits — <items>
3. Drifting from intent — <items>
4. Risks introduced — <items>

Then: proposed edits as elaborate code blocks for the "Fix before
committing" items.

CONTEXT
{git diff output}
{git log {base}..HEAD}
{stated intent of the work, if known}
```

**Claude's prep for `wip`:** before invoking, run:

```bash
BASE="${BASE:-origin/main}"
git diff "$BASE"...HEAD > /tmp/gemineye-wip.diff
git diff >> /tmp/gemineye-wip.diff   # unstaged
git diff --cached >> /tmp/gemineye-wip.diff   # staged
git log --oneline "$BASE"..HEAD > /tmp/gemineye-wip.log
```

**Inline** both files into the prompt's CONTEXT (there is no `--file`
flag). Default base is `origin/main` unless Tom specifies otherwise.

### `/gemineye sanity <topic>`

Idea / plan / decision sanity check. Tier: fast.

```
ROLE
Architectural reviewer doing a sanity check on a proposal, plan, or decision.

DO
- Steel-man the proposal before critiquing.
- Surface the three most likely failure modes, ranked by likelihood.
- Suggest one alternative worth considering.
- Identify what to prototype first.

DON'T
- Write or modify any file.
- Rewrite the proposal.
- Demand more detail before engaging.
- Soften critique to be agreeable.
- Pretend to be neutral when you have a view.

SCOPE — IN
- Proposal text in CONTEXT.
- Stated constraints already accepted.

SCOPE — OUT
- Implementation specifics (line-by-line code).
- Org / process critique.

OUTPUT
1. Steel-man — one paragraph, strongest version of the proposal.
2. Three failure modes — ranked by likelihood, each one paragraph.
3. Alternative worth considering — one paragraph.
4. First thing to prototype — one sentence.

CONTEXT
{proposal text}
{accepted constraints}
{relevant decisions / brief excerpts}
```

### `/gemineye name <thing(s)>`

One name or a related set. Tier: fast.

```
ROLE
Naming consultant.

DO
- Generate 5 ranked options.
- One-line rationale per option.
- Pick a top one, defend in two sentences.
- Honour every stated constraint (length, casing, language, register).
- For a related set, name them with internal coherence (shared root,
  matching shape, parallel grammar).

DON'T
- Write or modify any file.
- Suggest names that violate constraints.
- Pad the list with throwaways.
- Apologise.
- Rename adjacent things not asked about.

SCOPE — IN
- Thing(s) to name + their role / context.
- Stated constraints.
- Existing names in the surrounding system, for coherence.

SCOPE — OUT
- Things outside the requested set.
- Renaming the surrounding system.

OUTPUT
1. <name> — <one-line rationale>
2. <name> — <one-line rationale>
3. <name> — <one-line rationale>
4. <name> — <one-line rationale>
5. <name> — <one-line rationale>

Pick: <name>
<two-sentence defence>

For multiple things in a set, return one block per thing, then a
final "Set summary" line explaining the coherence.

CONTEXT
{thing(s) to name}
{role / context}
{constraints}
{adjacent names}
```

### `/gemineye compare <A> <B> [<C>...]`

Head-to-head ranking, 2+ options. Tier: fast.

```
ROLE
Decision support — head-to-head ranking of options.

DO
- State the comparison criteria explicitly upfront.
- Score each option against the same criteria.
- Pick a winner.
- Note when a runner-up wins under different conditions.

DON'T
- Write or modify any file.
- Refuse to pick.
- Hedge with "it depends" without specifying what it depends on.
- Add new options not in CONTEXT.
- Restate the options instead of evaluating them.

SCOPE — IN
- Options listed in CONTEXT.
- Decision context (what the choice is for).
- Stated constraints.

SCOPE — OUT
- Options not listed.
- Alternative framings of the decision.

OUTPUT
1. Criteria — bulleted list, in priority order.
2. Comparison table — option × criteria, plain Markdown.
3. Winner: <name>. <two-sentence justification>.
4. Consider <runner-up> if <condition>.

CONTEXT
{options A, B, C ...}
{decision context}
{constraints}
```

### `/gemineye harvest <path>`

Extract 5 durable bullets from any file: transcript, doc, or code. The
primary case is distilling a session transcript before compaction; the
same pass covers a doc or a code file. Tier: fast. This is gemineye's
on-demand harvest surface.

(Historical note: adjudant's PreCompact hook once auto-harvested via this
same prompt, but as of adjudant v0.7.0 the hook is mechanical-only — no model
calls — so `/gemineye harvest` is now the harvest surface. No cross-plugin
runtime dependency either way.)

```
ROLE
You are an archivist distilling one input file (session transcript, doc, or code) into its durable facts.

DO
- For a transcript: extract concrete decisions, problems solved, blockers, and unresolved questions
- For a doc or code file: extract load-bearing facts, contracts, and open questions
- One bullet per item, max 25 words
- Reference specific files/commits/issues by name when possible

DON'T
- Summarise or narrate the input
- Include code blocks
- Use softening language ("we discussed", "considered")
- Output anything except the bullets

SCOPE — IN
- The input file content provided below (for a transcript: the most recent {n_msgs} messages)

SCOPE — OUT
- Greetings, tool-call mechanics, status pings, hook output
- Anything outside the provided content

OUTPUT
- Exactly 5 bullets, no preamble, no trailing text. If fewer than 5 concrete items exist, output fewer.
- Format: `- <bullet text>`

CONTEXT
{input_chunk}
```

Claude's prep for `harvest`: read the named file, pass its content
(truncated to ~10,000 chars) as `{input_chunk}`. For a transcript, set
`{n_msgs}` to the approximate number of message turns included; for a
doc or code file, drop the `{n_msgs}` clause. Run:

```bash
agy --sandbox --add-dir "$ROOT" --model "Gemini 3.5 Flash (Medium)" -p "$(cat prompt.txt)"
```

---

## Context-bundle assembly

When assembling CONTEXT, prefer this shape:

```
## Project context
<3-10 lines from brief.md or equivalent>

## Relevant decisions
- <decision> — <one-line outcome>

## Target
<the artefact under review>

## Question
<the focused ask>
```

A focused 500-token bundle outperforms a 5,000-token dump. If
tempted to attach more, ask whether the extra tokens will change
the answer.

---

## `/gemineye save` mechanics

`save` is a file write, not a Gemini call. It persists the LAST
in-line review to disk.

The vault destination resolves via the adjudant breadcrumb
(`.claude/adjudant` at the project root, plain `key: value` lines with
`vault_path` and `slug`), not an environment variable:

```bash
TOPIC="${1:-$(date +%H%M)}"
DATE=$(date +%Y-%m-%d)

BC="$ROOT/.claude/adjudant"
VAULT_PATH=""; SLUG=""
if [ -f "$BC" ]; then
  VAULT_PATH=$(sed -n 's/^vault_path: //p' "$BC" | head -n1 | tr -d '\r')
  SLUG=$(sed -n 's/^slug: //p' "$BC" | head -n1 | tr -d '\r')
fi

if [ -n "$VAULT_PATH" ] && [ -n "$SLUG" ]; then
  OUT="${VAULT_PATH}/projects/${SLUG}/gemineye/${DATE}-${TOPIC}.md"
else
  OUT="docs/gemineye/${DATE}-${TOPIC}.md"
fi

mkdir -p "$(dirname "$OUT")"
```

The file uses the template in SKILL.md "Persisted file template".
Required: frontmatter (with `subcommand` and `model` fields), Prompt
(full filled-in template + CONTEXT), Response, Claude's read.

On a vault save, also honour the pairing contract (SKILL.md "Pairing
with adjudant"): declare `gemineye` in the brief's `extra_folders:` list
if it is not there yet, and append a cross-link line under `## Log` in
today's session note.

---

## Anti-patterns

- **Don't** drop sections from the template. ROLE / DO / DON'T /
  SCOPE — IN / SCOPE — OUT / OUTPUT / CONTEXT — all required, every
  call.
- **Don't** soften DO / DON'T. Imperative voice. No "try to", "feel
  free to", "consider".
- **Don't** `--add-dir` the whole world or crawl the repo. Read-trust is
  scoped to the project root; the focused bundle is still primary. Noisy
  context degrades the answer.
- **Don't** ask Gemini to "implement X end-to-end". Review and
  second-opinion only.
- **Don't** drop `--sandbox`. The sandbox is what limits write side
  effects; read trust is granted separately via `--add-dir`.
- **Don't** pass `--dangerously-skip-permissions`. Gemini reviews only.
- **Don't** chain Gemini calls in a loop. Each is deliberate.
- **Don't** accept edit suggestions outside the elaborate-code-block
  format. Re-prompt if violated.
- **Don't** write Gemini's response into a source file. Route via
  `gemineye/`, then Claude decides.
