"""SensAI domain agent for questions about how to use MuJoCo Mojo, answered from the docs that ship with the package."""

from __future__ import annotations

from pydantic_ai import Agent

from mujoco_mojo.utils.log import get_logger

from .deps import SensAIDeps
from .docs_catalog import read_docs as _read_docs
from .docs_catalog import search_docs as _search_docs
from .docs_catalog import table_of_contents

logger = get_logger(__name__)

_SYSTEM_PROMPT = f"""\
You are the docs agent inside the MuJoCo Mojo Dojo dashboard. You answer questions about \
how to use MuJoCo Mojo (installing it, starting a project, the generate and runtime \
scripts, running jobs and Monte Carlo, SLURM, the Dojo, Reloaded, requirements, \
optimization, the examples) and about what changed in a release, from the Mojo docs (the \
user guides, the command line reference and the changelog), and only from them.

Your tools, each with an example call:
- search_docs: find the parts of the docs about something. \
search_docs(query="submit a job to SLURM")
- read_docs: read a page of the docs, or one section of it. \
read_docs(path="user-guides/workflow/running-jobs/running-jobs.md", section="SLURM Mode")

Rules:
- Search first, or pick a page from the list below, and read the part you need before you \
answer. Do not answer from memory: every name, option and command you give must be one you \
read in the docs.
- changelog.md lists what changed in each release, newest first. For a question about a \
release or when something was added, read it (read_docs(path="changelog.md", \
section="Version 2.7.0") reads one release) or search it.
- If the docs do not cover the question, say so plainly and name the closest page. Never \
guess, and never describe something the docs do not mention.
- Answer in a few short steps or one short paragraph. Add a code block only when the \
question is how to write or run something, and copy it from the docs, shortened if need be.
- Finish with a link to the page you used, written as See [Title](link), using the link the \
tools gave you.
- Execute immediately; never ask the user to say more unless the question has no subject.

The pages, by path:
{table_of_contents()}
"""

docs_agent: Agent[SensAIDeps, str] = Agent(
    deps_type=SensAIDeps,
    output_type=str,
    system_prompt=_SYSTEM_PROMPT,
)


@docs_agent.tool_plain
def search_docs(query: str) -> str:
    """
    Finds the parts of the Mojo docs that best match some words, best first.

    Args:
        query: What to look for, in a few words such as "submit a job to SLURM" or "early termination of a requirement". Plain words are enough: how, the and similar words are ignored, and an ending such as -ing or -s does not matter.

    Returns:
        Up to five matches, each with the page's path, the section, the line that matched best and the docs site link. Nothing matched is said in words.

    """
    hits = _search_docs(query)
    logger.info("SensAI search_docs %r: %d hit(s)", query, len(hits))
    if not hits:
        return "Nothing in the docs matches those words. Try other words, or pick a page from your list."
    return "\n".join(
        f"{n}. {hit.section.path} | {hit.section.label}\n   {hit.snippet}\n   {hit.section.link}"
        for n, hit in enumerate(hits, start=1)
    )


@docs_agent.tool_plain
def read_docs(path: str, section: str = "") -> str:
    """
    Reads a page of the Mojo docs, or one section of it, with its title and docs site link on top.

    Args:
        path: The page's path, as the list in your instructions and the search results give it, such as "user-guides/workflow/running-jobs/running-jobs.md".
        section: Leave it out to read the whole page. To read one part of it, a heading of that page such as "SLURM Mode": the section and the ones under it are returned. A long page comes back cut, with a list of its sections to ask for.

    Returns:
        The text of the page or section. A path or section that is not there is answered with the ones that are.

    """
    logger.info("SensAI read_docs: %s %s", path, section)
    return _read_docs(path, section)
