# Contributing to IntentGraph

**Issues are welcome**: bug reports, questions, use cases, criticism of the formalism. They are
the best way to influence the project.

## Pull requests: a pull request is a gift of the code

IntentGraph has a single owner, Rémi Cura, who keeps the freedom to change the license of future
versions (see [LICENSE.md](LICENSE.md)). That freedom only holds if every line of the code
belongs to the owner. So the rule is simple:

**By opening a pull request, you give its content entirely to Rémi Cura.** Concretely, you agree
that:

1. you wrote the contribution yourself, or otherwise have the right to give it;
2. you transfer all your rights in it to Rémi Cura, who may use, modify, publish and relicense
   it under any terms, open or closed, without asking you and without paying you;
3. where the law does not allow such a transfer, you grant Rémi Cura instead a free, perpetual,
   worldwide, irrevocable license to do all of the above, including the right to sublicense;
4. nothing obliges the owner to merge, review or credit a pull request.

This is a plain-language statement of intent, not a lawyer-drafted contributor agreement. If you
cannot agree to it, open an issue describing the change instead: an idea in an issue gives
nothing away.

## Before you open one

- Read [CLAUDE.md](CLAUDE.md) and [agents/README.md](agents/README.md): intent is the source of
  truth, diffs stay small, node UIDs stay stable.
- Run the test suite from the repository root: `uv run --extra dev pytest` (1134 tests, about 15 s).
