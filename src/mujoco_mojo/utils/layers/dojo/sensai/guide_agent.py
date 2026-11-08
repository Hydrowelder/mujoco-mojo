"""SensAI domain agent for questions about how to use MuJoCo Mojo, answered from the user guides that ship with the package."""

from __future__ import annotations

from pydantic_ai import Agent

from mujoco_mojo.utils.log import get_logger

from .deps import SensAIDeps
from .guide_catalog import read_guide as _read_guide
from .guide_catalog import search_guides as _search_guides
from .guide_catalog import table_of_contents

logger = get_logger(__name__)

_SYSTEM_PROMPT = f"""\
You are the guide agent inside the MuJoCo Mojo Dojo dashboard. You answer questions about \\
how to use MuJoCo Mojo (installing it, starting a project, the generate and runtime \\
scripts, running jobs and Monte Carlo, SLURM, the Dojo, Reloaded, requirements, \\
optimization, the examples) from the Mojo user guides, and only from them.

Your tools, each with an example call:
- search_guides: find the parts of the guides about something. \\
search_guides(query="submit a job to SLURM")
- read_guide: read a guide, or one section of it. \\
read_guide(path="workflow/running-jobs/running-jobs.md", section="SLURM Mode")

Rules:
- Search first, or pick a guide from the list below, and read the part you need before you \\
answer. Do not answer from memory: every name, option and command you give must be one you \\
read in a guide.
- If the guides do not cover the question, say so plainly and name the closest guide. Never \\
guess, and never describe something the guides do not mention.
- Answer in a few short steps or one short paragraph. Add a code block only when the \\
question is how to write or run something, and copy it from the guide, shortened if need be.
- Finish with a link to the guide you used, written as See [Title](link), using the link the \\
tools gave you.
- Execute immediately; never ask the user to say more unless the question has no subject.

The guides, by path:
{table_of_contents()}
"""

guide_agent: Agent[SensAIDeps, str] = Agent(
    deps_type=SensAIDeps,
    output_type=str,
    system_prompt=_SYSTEM_PROMPT,
)


@guide_agent.tool_plain
def search_guides(query: str) -> str:
    """
    Finds the parts of the Mojo user guides that best match some words, best first.

    Args:
        query: What to look for, in a few words such as "submit a job to SLURM" or "early termination of a requirement". Plain words are enough: how, the and similar words are ignored, and an ending such as -ing or -s does not matter.

    Returns:
        Up to five matches, each with the guide's path, the section, the line that matched best and the docs site link. Nothing matched is said in words.

    """
    hits = _search_guides(query)
    logger.info("SensAI search_guides %r: %d hit(s)", query, len(hits))
    if not hits:
        return "Nothing in the guides matches those words. Try other words, or pick a guide from your list."
    return "\n".join(
        f"{n}. {hit.section.path} | {hit.section.label}\n   {hit.snippet}\n   {hit.section.link}"
        for n, hit in enumerate(hits, start=1)
    )


@guide_agent.tool_plain
def read_guide(path: str, section: str = "") -> str:
    """
    Reads a Mojo user guide, or one section of it, with its title and docs site link on top.

    Args:
        path: The guide's path, as the list in your instructions and the search results give it, such as "workflow/running-jobs/running-jobs.md".
        section: Leave it out to read the whole guide. To read one part of it, a heading of that guide such as "SLURM Mode": the section and the ones under it are returned. A long guide comes back cut, with a list of its sections to ask for.

    Returns:
        The text of the guide or section. A path or section that is not there is answered with the ones that are.

    """
    logger.info("SensAI read_guide: %s %s", path, section)
    return _read_guide(path, section)
