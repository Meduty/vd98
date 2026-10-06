> **Status: FROZEN** (written 2026-10-06). Append-only history.

# 2026-10-06 — Review loop closed, PRs #1–#6 merged, sandbox recipe handed over

## What happened

- PR #2 (T.14, effect-level secret protection) went through all three Codex review rounds,
  the stop rule's maximum. Each finding was checked against the code and answered on the PR
  ("fixed in <sha>" or "dismissed: <reason>"). Bug rows B.35–B.44 cover them.
- PR #3 (T.15–T.17: % and Size columns, smoothed ETA, resume after close) got its two review
  rounds answered and was rebased onto PR #2 twice.
- PRs #1 → #2 → #3 were merged in that order with merge commits (not squash: the PRs were
  stacked). The docs PRs #4 and #6 followed. CI passed on every step; `main` is the only branch left.
- The user's GUI click-through passed: drag, resize, columns, close → reopen → Resume.
  It also raised B.45 / issue #5: after closing the window, `uv run vd98` didn't seem to return.
- The tested sandbox recipe, its learnings and its limits went to the faq session. That
  session wrote them into faq PR #249 and planned the rollout as faq issue #250.

## Decisions

- D.12 (user): accept that the Codex login file `~/.codex/auth.json` stays readable by shell
  commands. The login is a subscription with no API key to mask; an API key would bill per
  use. File tools are blocked from that folder by the guard, not by a Read deny rule, because
  Read deny rules also land in the sandbox's read blocks and would lock Codex out of its own login.
- V.17 now states its limits plainly instead of overclaiming:
  - a branch can edit or delete its own CI workflow;
  - `main` is protected only by its required CI check;
  - the scan is pattern-based.

## Verified vs. not

- Verified:
  - the sandbox probe blocks 14 of 15 attempts; the one that gets through is the known
    same-command case;
  - `gh` works inside the sandbox through the masked `GH_TOKEN` (view, comment, edit,
    update-branch, checks, merge, branch delete), but only when Claude Code is started with
    `GH_TOKEN` exported. Otherwise it gets 401, as a later session showed.
- Not verified:
  - why `git push` / `fetch` over HTTPS still get 401 (the guess is the Base64-encoded
    placeholder in Basic auth);
  - whether a `keyring` login store is reachable from the sandbox.

## Agent errors (mine)

- I said `gh` couldn't work in the sandbox after testing only `git push`. One read-only
  `gh api user` call would have shown it worked.
- I first proposed a Read deny rule for `~/.codex/auth.json`. It would have broken Codex,
  for the reason under Decisions. I caught it before installing.
- A new test fixture first produced *errors* (the pre-change guard had no `PRIVATE_DIRS`)
  instead of *failures*. That proved nothing until `raising=False` made the old guard fail
  on behaviour.
- `git rev-parse --short A B` is invalid ("Needed a single revision"); it takes one ref at a time.
- I handed out long `!` commands. Two of them got split or cut off when pasted, and one arrived
  as chat text and never ran. Typing `!` by hand fixed that; so did a one-line wrapper script.

## Process notes

- The review rounds mixed false claims with real gaps. Round 2's "Bash can overwrite the hooks"
  was false (`os.access(W_OK)` is False for those paths inside the sandbox). But checking it
  turned up a real gap: a branch could weaken its own scanner. Verify every finding instead of
  accepting or rejecting it wholesale.
- The secret-name list must match in four places: guard, `check_secrets.py`, sandbox denyRead,
  `.gitignore`. SSH key names were missing from the last two until round 3.
