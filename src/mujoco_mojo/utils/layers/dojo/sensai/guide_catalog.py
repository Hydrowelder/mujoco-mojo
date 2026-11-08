"""
Finding things in the user guides that ship with the package, for the guide agent SensAI answers "how do I use Mojo" with.

The guides are `mujoco_mojo/user_guide/*.md`, written by `scripts/gen_user_guide.py` from the docs as plain markdown. This reads them, splits each at its headings into sections, and ranks sections against a question by word (BM25, with the words of a heading counting for more). There are no embeddings and nothing is downloaded, so it works offline and gives the same ranking every time.
"""

from __future__ import annotations

import difflib
import math
import re
import unicodedata
from collections import Counter
from functools import cache
from pathlib import Path

from pydantic import BaseModel

from mujoco_mojo.meta import USER_GUIDE_DIR

__all__ = [
    "GUIDE_DIR",
    "SITE_URL",
    "Guide",
    "Hit",
    "Section",
    "guides",
    "read_guide",
    "search_guides",
    "slugify",
    "table_of_contents",
]

SITE_URL = "https://hydrowelder.github.io/mujoco-mojo/"
"""Where the docs site is, which the guide links are built on."""

GUIDE_DIR = USER_GUIDE_DIR
"""The bundled guides."""

_HEADING = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<title>.+?)\s*#*\s*$")
_FENCE = re.compile(r"^\s*(```|~~~)")
_WORD = re.compile(r"[a-z0-9]+")
_STOP_WORDS = frozenset(
    "a about an and are as at be by can do does for from how i if in into is it its me my of "
    "on or so that the their then there this to us we what when where which who why will with "
    "would you your".split()
)

# how much more a word of a heading counts than one of the text under it
_HEADING_WEIGHT = 3
_BM25_K1 = 1.5
_BM25_B = 0.75

_MAX_HITS_PER_GUIDE = 2
_SNIPPET_LENGTH = 220
_READ_LIMIT = 7000


class Section(BaseModel):
    """The part of a guide under one heading, up to the next heading of any level."""

    path: str
    headings: tuple[str, ...]
    """The guide's title, then each heading above this one, then this section's own."""
    level: int
    body: str

    @property
    def title(self) -> str:
        return self.headings[-1]

    @property
    def label(self) -> str:
        return " > ".join(self.headings)

    @property
    def link(self) -> str:
        """Where the section is on the docs site."""
        base = guide_url(self.path)
        return base if self.level == 1 else f"{base}#{slugify(self.title)}"


class Guide(BaseModel):
    """One bundled guide."""

    path: str
    """Its path under the bundle, such as `workflow/getting-started.md`."""
    title: str
    text: str
    sections: list[Section]

    @property
    def url(self) -> str:
        return guide_url(self.path)


class Hit(BaseModel):
    """A section that matched a search, with the line that matched best."""

    section: Section
    score: float
    snippet: str


def slugify(heading: str) -> str:
    """The anchor the docs site gives a heading: lowercase words joined by hyphens."""
    text = unicodedata.normalize("NFKD", heading).encode("ascii", "ignore").decode()
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "-", text)


def guide_url(path: str) -> str:
    """The docs site address of the guide at `path`. A path under `reference/` is a page of the site's Reference section, and any other is a user guide."""
    page = path.removesuffix(".md")
    section = "" if page.startswith("reference/") else "user-guides/"
    return f"{SITE_URL}{section}{page}/"


def _split_sections(path: str, text: str) -> tuple[str, list[Section]]:
    """The title of a guide, and its sections in order."""
    stack: list[tuple[int, str]] = []
    sections: list[Section] = []
    heading: tuple[int, str] | None = None
    body: list[str] = []
    in_code = False

    def close() -> None:
        if heading is not None:
            sections.append(
                Section(
                    path=path,
                    headings=tuple(title for _, title in stack),
                    level=heading[0],
                    body="\n".join(body).strip("\n"),
                )
            )

    for line in text.splitlines():
        if _FENCE.match(line):
            in_code = not in_code
        found = None if in_code else _HEADING.match(line)
        if found is None:
            body.append(line)
            continue
        close()
        level = len(found["hashes"])
        while stack and stack[-1][0] >= level:
            stack.pop()
        heading = (level, found["title"])
        stack.append(heading)
        body = []
    close()
    title = sections[0].title if sections else path
    return title, sections


@cache
def guides(directory: Path = GUIDE_DIR) -> tuple[Guide, ...]:
    """Every guide in `directory`, in path order."""
    found: list[Guide] = []
    for file in sorted(directory.rglob("*.md")):
        path = file.relative_to(directory).as_posix()
        text = file.read_text(encoding="utf-8")
        title, sections = _split_sections(path, text)
        found.append(Guide(path=path, title=title, text=text, sections=sections))
    return tuple(found)


def table_of_contents(directory: Path = GUIDE_DIR) -> str:
    """One line per guide, its path and title, for the agent's instructions."""
    return "\n".join(f"- {g.path}: {g.title}" for g in guides(directory))


def _stem(word: str) -> str:
    """The word with a common ending taken off, so `running`, `runs` and `run` meet. Crude on purpose: it only has to make a question's words and the guide's agree."""
    for ending in ("ing", "ed", "es", "s"):
        if word.endswith(ending) and len(word) - len(ending) >= 3:
            word = word[: -len(ending)]
            break
    # running -> runn -> run, and stopped -> stopp -> stop. done to every word, so a word
    # and its -ing form still meet even where this undoes a double letter the word has
    # (add and adding both become ad)
    if len(word) >= 3 and word[-1] == word[-2] and word[-1] not in "lsz":
        word = word[:-1]
    return word


def _terms(text: str) -> list[str]:
    words = _WORD.findall(text.lower())
    return [_stem(w) for w in words if w not in _STOP_WORDS and len(w) > 1]


class _Index:
    """The word counts of every section, for ranking."""

    def __init__(self, sections: list[Section]) -> None:
        self.sections = sections
        self.counts: list[Counter[str]] = []
        for section in sections:
            bag = Counter(_terms(section.body))
            for term in _terms(" ".join(section.headings)):
                bag[term] += _HEADING_WEIGHT
            self.counts.append(bag)
        self.lengths = [sum(c.values()) for c in self.counts]
        self.average = sum(self.lengths) / max(1, len(self.lengths))
        self.frequency: Counter[str] = Counter()
        for bag in self.counts:
            self.frequency.update(bag.keys())

    def score(self, i: int, terms: set[str]) -> float:
        total = 0.0
        n = len(self.sections)
        for term in terms:
            count = self.counts[i].get(term, 0)
            if not count:
                continue
            df = self.frequency[term]
            idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
            norm = _BM25_K1 * (1 - _BM25_B + _BM25_B * self.lengths[i] / self.average)
            total += idf * count * (_BM25_K1 + 1) / (count + norm)
        return total


@cache
def _index(directory: Path) -> _Index:
    return _Index([s for g in guides(directory) for s in g.sections])


def _snippet(section: Section, terms: set[str]) -> str:
    """The line of the section's text with the most of the query's words, cut short."""
    best, best_score = "", 0
    in_code = False
    for line in section.body.splitlines():
        if _FENCE.match(line):
            in_code = not in_code
            continue
        text = line.strip()
        if not text or in_code:
            continue
        score = len(terms & set(_terms(text)))
        if score > best_score:
            best, best_score = text, score
    if not best:
        best = next(
            (
                ln.strip()
                for ln in section.body.splitlines()
                if ln.strip() and not _FENCE.match(ln)
            ),
            section.label,
        )
    if len(best) > _SNIPPET_LENGTH:
        best = best[:_SNIPPET_LENGTH].rsplit(" ", 1)[0] + "..."
    return best


def search_guides(query: str, limit: int = 5, directory: Path = GUIDE_DIR) -> list[Hit]:
    """The sections that best answer `query`, best first, at most two from any one guide. Empty when no word of the query is in the guides."""
    terms = set(_terms(query))
    if not terms:
        return []
    index = _index(directory)
    ranked = sorted(
        (
            (index.score(i, terms), i)
            for i in range(len(index.sections))
            if index.score(i, terms) > 0
        ),
        key=lambda pair: (-pair[0], pair[1]),
    )
    hits: list[Hit] = []
    per_guide: Counter[str] = Counter()
    for score, i in ranked:
        section = index.sections[i]
        if per_guide[section.path] >= _MAX_HITS_PER_GUIDE:
            continue
        per_guide[section.path] += 1
        hits.append(Hit(section=section, score=score, snippet=_snippet(section, terms)))
        if len(hits) == limit:
            break
    return hits


def _find_guide(path: str, directory: Path) -> Guide | None:
    """The guide a path names. A model rarely writes it exactly, so a leading `docs/` or `user-guides/`, a missing `.md` and a bare file name are all accepted."""
    wanted = path.strip().strip("/")
    for prefix in ("docs/", "user-guides/"):
        wanted = wanted.removeprefix(prefix)
    wanted = wanted.removesuffix(".md") + ".md"
    every = guides(directory)
    for guide in every:
        if guide.path == wanted:
            return guide
    ends = [g for g in every if g.path.endswith("/" + wanted)]
    return ends[0] if len(ends) == 1 else None


def _find_section(guide: Guide, name: str) -> int | None:
    """The position of the section called `name` (its exact title, then any title that contains it), ignoring case."""
    wanted = name.strip().lower()
    for pred in (
        lambda t: t.lower() == wanted,
        lambda t: wanted in t.lower(),
    ):
        for i, section in enumerate(guide.sections):
            if pred(section.title):
                return i
    return None


def _section_text(guide: Guide, i: int) -> str:
    """A section and the sections under it, with their headings."""
    first = guide.sections[i]
    parts = []
    for section in guide.sections[i:]:
        if section is not first and section.level <= first.level:
            break
        parts.append(
            f"{'#' * section.level} {section.title}\n\n{section.body}".rstrip()
        )
    return "\n\n".join(parts)


def read_guide(
    path: str, section: str = "", limit: int = _READ_LIMIT, directory: Path = GUIDE_DIR
) -> str:
    """
    A guide, or one section of it, with its title and docs site link on top.

    A guide longer than `limit` characters is cut there with a note listing its sections, so a reader can ask for one. A path or section that is not there is answered with what is, not an error.
    """
    guide = _find_guide(path, directory)
    if guide is None:
        every = [g.path for g in guides(directory)]
        close = difflib.get_close_matches(
            path.strip().strip("/"), every, n=3, cutoff=0.4
        )
        hint = f" Closest: {', '.join(close)}." if close else ""
        return (
            f"There is no guide at '{path}'.{hint} The guides are: {', '.join(every)}."
        )
    top = f"{guide.title} ({guide.url})\n\n"
    if section:
        i = _find_section(guide, section)
        if i is None:
            titles = ", ".join(s.title for s in guide.sections)
            return f"{top}This guide has no section called '{section}'. Its sections are: {titles}."
        text = _section_text(guide, i)
        top = (
            f"{guide.title} > {guide.sections[i].title} ({guide.sections[i].link})\n\n"
        )
    else:
        text = guide.text.strip("\n")
    if len(text) <= limit:
        return top + text
    titles = ", ".join(s.title for s in guide.sections)
    cut = text[:limit].rsplit("\n", 1)[0]
    return (
        f"{top}{cut}\n\n[Cut here. The guide's sections are: {titles}. "
        "Call read_guide again with the path and section set to one of them.]"
    )
