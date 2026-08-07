# Why it exists

Natural-language artifacts have become real software. A slash command routes work, an agent
description decides when that agent is invoked, a skill's frontmatter determines whether it loads at
all. These behave like code — but they are usually reviewed like prose, which is to say barely.

The consequences are ordinary software consequences. An agent whose description does not say when to
use it never triggers. A command that declares tools it never calls grants authority for no reason. A
skill that buries its trigger in paragraph six is invisible to the model that was supposed to load
it. None of these produce a stack trace.

vibe-suite treats those artifacts as the programs they are. It scores them against rules with stated
penalties, checks them for consistency across a repository, and runs specifications written in the
same natural language the artifacts use. Where a finding is concrete and reproducible, the pipeline
can carry the fix upstream as a pull request.

The project is deliberately opinionated about evidence. A score is only useful if the same input
produces the same number, so scoring is deterministic. A finding is only worth sending to a
maintainer if someone reproduced it, so unreproduced findings never become pull requests. And a gate
that cannot fail is not a gate, which is why the checks here are tested against inputs that are
supposed to break them.
