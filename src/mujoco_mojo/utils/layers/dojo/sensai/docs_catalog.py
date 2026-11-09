"""
Finding things in the docs that ship with the package, for the docs agent SensAI answers "how do I use Mojo" with.

The pages are every `.md` file under `docs/` of the docs source that ships in the package (`DOCS_SOURCE_DIR`): the user guides, the command line reference, the changelog and the rest. Each is known by its path under `docs/`, and is read as plain markdown (`utils/docs_text.py` removes the site's markup). This splits each at its headings into sections, and ranks sections against a question by word (BM25, with the words of a heading counting for more). There are no embeddings and nothing is downloaded, so it works offline and gives the same ranking every time.
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

from mujoco_mojo.meta import DOCS_SOURCE_DIR
from mujoco_mojo.utils.docs_text import plain_text

__all__ = [
    "SITE_URL",
    "DocsPage",
    "Hit",
    "Section",
    "docs_pages",
    "read_docs",
    "search_docs",
    "slugify",
    "table_of_contents",
]

SITE_URL = "https://hydrowelder.github.io/mujoco-mojo/"
"""Where the docs site is, which the docs links are built on."""

_HEADING = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<title>.+?)\s*#*\s*$")
_FENCE = re.compile(r"^\s*(```|~~~)")
_ESCAPED = re.compile(r"\\([\\`*_{}\[\]()#+\-.!|<>~])")
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

_MAX_HITS_PER_PAGE = 2
_SNIPPET_LENGTH = 220
_READ_LIMIT = 7000


class Section(BaseModel):
    """The part of a page under one heading, up to the next heading of any level."""

    path: str
    headings: tuple[str, ...]
    """The page's title, then each heading above this one, then this section's own."""
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
        base = docs_url(self.path)
        return base if self.level == 1 else f"{base}#{slugify(self.title)}"


class DocsPage(BaseModel):
    """One bundled page of the docs."""

    path: str
    """Its path under `docs/`, such as `user-guides/workflow/getting-started.md`, `reference/cli.md` or `changelog.md`."""
    title: str
    text: str
    sections: list[Section]

    @property
    def url(self) -> str:
        return docs_url(self.path)


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


def docs_url(path: str) -> str:
    """The docs site address of the page at `path` (under `docs/`): `user-guides/workflow/x.md` is at `user-guides/workflow/x/`, and an `index.md` is the address of its folder."""
    page = path.removesuffix(".md")
    if page == "index":
        return SITE_URL
    return f"{SITE_URL}{page.removesuffix('/index')}/"


def _split_sections(path: str, text: str) -> tuple[str, list[Section]]:
    """The title of a page, and its sections in order."""
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
        # `mujoco\_mojo` is how a heading writes the underscore in `mujoco_mojo`
        heading = (level, _ESCAPED.sub(r"\1", found["title"]))
        stack.append(heading)
        body = []
    close()
    if not sections and text.strip():
        # a page with no heading at all is one section, named by its path
        body_text = text.strip("\n")
        sections = [Section(path=path, headings=(path,), level=1, body=body_text)]
    title = sections[0].title if sections else path
    return title, sections


def _docs_files(directory: Path) -> dict[str, Path]:
    """Every page of the docs source in `directory`, each by its path under `docs/`."""
    docs = directory / "docs"
    return {file.relative_to(docs).as_posix(): file for file in docs.rglob("*.md")}


@cache
def docs_pages(directory: Path = DOCS_SOURCE_DIR) -> tuple[DocsPage, ...]:
    """Every page of the docs source in `directory`, in path order."""
    found: list[DocsPage] = []
    # sorted by the parts of the path, as the files were when they were read from a folder, so a page comes before the folder of the same name
    for path, file in sorted(
        _docs_files(directory).items(), key=lambda item: Path(item[0]).parts
    ):
        text = plain_text(file)
        title, sections = _split_sections(path, text)
        found.append(DocsPage(path=path, title=title, text=text, sections=sections))
    return tuple(found)


def table_of_contents(directory: Path = DOCS_SOURCE_DIR) -> str:
    """One line per page, its path and title, for the agent's instructions."""
    return "\n".join(f"- {g.path}: {g.title}" for g in docs_pages(directory))


def _stem(word: str) -> str:
    """The word with a common ending taken off, so `running`, `runs` and `run` meet. Crude on purpose: it only has to make a question's words and the page's agree."""
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
    return _Index([s for g in docs_pages(directory) for s in g.sections])


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


def search_docs(
    query: str, limit: int = 5, directory: Path = DOCS_SOURCE_DIR
) -> list[Hit]:
    """The sections that best answer `query`, best first, at most two from any one page. Empty when no word of the query is in the docs."""
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
    per_page: Counter[str] = Counter()
    for score, i in ranked:
        section = index.sections[i]
        if per_page[section.path] >= _MAX_HITS_PER_PAGE:
            continue
        per_page[section.path] += 1
        hits.append(Hit(section=section, score=score, snippet=_snippet(section, terms)))
        if len(hits) == limit:
            break
    return hits


def _find_docs_page(path: str, directory: Path) -> DocsPage | None:
    """The page a path names. A model rarely writes it exactly, so a leading `docs/`, a missing `.md` and the end of a path (down to a bare file name) are all accepted."""
    wanted = path.strip().strip("/").removeprefix("docs/")
    wanted = wanted.removesuffix(".md") + ".md"
    every = docs_pages(directory)
    for page in every:
        if page.path == wanted:
            return page
    ends = [g for g in every if g.path.endswith("/" + wanted)]
    return ends[0] if len(ends) == 1 else None


def _find_section(page: DocsPage, name: str) -> int | None:
    """The position of the section called `name` (its exact title, then any title that contains it), ignoring case."""
    wanted = name.strip().lower()
    for pred in (
        lambda t: t.lower() == wanted,
        lambda t: wanted in t.lower(),
    ):
        for i, section in enumerate(page.sections):
            if pred(section.title):
                return i
    return None


def _section_text(page: DocsPage, i: int) -> str:
    """A section and the sections under it, with their headings."""
    first = page.sections[i]
    parts = []
    for section in page.sections[i:]:
        if section is not first and section.level <= first.level:
            break
        parts.append(
            f"{'#' * section.level} {section.title}\n\n{section.body}".rstrip()
        )
    return "\n\n".join(parts)


def read_docs(
    path: str,
    section: str = "",
    limit: int = _READ_LIMIT,
    directory: Path = DOCS_SOURCE_DIR,
) -> str:
    """
    A page, or one section of it, with its title and docs site link on top.

    A page longer than `limit` characters is cut there with a note listing its sections, so a reader can ask for one. A path or section that is not there is answered with what is, not an error.
    """
    page = _find_docs_page(path, directory)
    if page is None:
        every = [g.path for g in docs_pages(directory)]
        close = difflib.get_close_matches(
            path.strip().strip("/"), every, n=3, cutoff=0.4
        )
        hint = f" Closest: {', '.join(close)}." if close else ""
        return f"There is no page at '{path}'.{hint} The pages are: {', '.join(every)}."
    top = f"{page.title} ({page.url})\n\n"
    if section:
        i = _find_section(page, section)
        if i is None:
            titles = ", ".join(s.title for s in page.sections)
            return f"{top}This page has no section called '{section}'. Its sections are: {titles}."
        text = _section_text(page, i)
        top = f"{page.title} > {page.sections[i].title} ({page.sections[i].link})\n\n"
    else:
        text = page.text.strip("\n")
    if len(text) <= limit:
        return top + text
    titles = ", ".join(s.title for s in page.sections)
    cut = text[:limit].rsplit("\n", 1)[0]
    return (
        f"{top}{cut}\n\n[Cut here. The page's sections are: {titles}. "
        "Call read_docs again with the path and section set to one of them.]"
    )
