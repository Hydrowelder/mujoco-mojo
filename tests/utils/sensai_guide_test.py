"""Tests for how SensAI's guide agent finds things in the user guides bundled with the package: splitting them into sections, ranking sections against a question, and reading a guide or a part of one."""

from pathlib import Path

import pytest

from mujoco_mojo.utils.layers.dojo.sensai.guide_catalog import (
    GUIDE_DIR,
    SITE_URL,
    guides,
    read_guide,
    search_guides,
    slugify,
    table_of_contents,
)

JOBS = """\
# Running Jobs

Run a job with the runner. This page is about jobs.

## SLURM Mode (`slurm`)

Submit with `submit_slurm` and the cluster runs the workers.

```python
# Not a heading, a comment in code
runner.submit_slurm(config)
```

### Time limits

Set `time_limit` in the config, in any sbatch format.

## Video Recording

Record a video with the runtime manager. Videos are written to the trial folder.
"""

DOJO = """\
# Dojo Dashboard

The Dojo shows telemetry in the browser.

## Getting Started

Start it with the `dojo` command.
"""


def make_guides(root: Path, files: dict[str, str]) -> Path:
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


@pytest.fixture
def small(tmp_path: Path) -> Path:
    return make_guides(
        tmp_path, {"workflow/running-jobs.md": JOBS, "features/dojo.md": DOJO}
    )


class TestSections:
    def test_a_guide_is_split_at_its_headings(self, small: Path) -> None:
        guide = next(g for g in guides(small) if g.path == "workflow/running-jobs.md")

        assert [s.title for s in guide.sections] == [
            "Running Jobs",
            "SLURM Mode (`slurm`)",
            "Time limits",
            "Video Recording",
        ]
        assert [s.level for s in guide.sections] == [1, 2, 3, 2]

    def test_the_title_is_the_first_heading(self, small: Path) -> None:
        assert {g.path: g.title for g in guides(small)} == {
            "features/dojo.md": "Dojo Dashboard",
            "workflow/running-jobs.md": "Running Jobs",
        }

    def test_a_section_knows_the_headings_above_it(self, small: Path) -> None:
        guide = next(g for g in guides(small) if g.path == "workflow/running-jobs.md")
        time_limits = guide.sections[2]

        assert time_limits.headings == (
            "Running Jobs",
            "SLURM Mode (`slurm`)",
            "Time limits",
        )
        assert time_limits.label == "Running Jobs > SLURM Mode (`slurm`) > Time limits"

    def test_the_next_section_at_the_same_level_does_not_inherit_the_last_ones_headings(
        self, small: Path
    ) -> None:
        guide = next(g for g in guides(small) if g.path == "workflow/running-jobs.md")

        assert guide.sections[3].headings == ("Running Jobs", "Video Recording")

    def test_a_hash_line_inside_a_code_block_is_not_a_heading(
        self, small: Path
    ) -> None:
        guide = next(g for g in guides(small) if g.path == "workflow/running-jobs.md")

        slurm = guide.sections[1]
        assert "# Not a heading" in slurm.body
        assert "Not a heading" not in [s.title for s in guide.sections]

    def test_the_text_under_a_heading_is_its_body(self, small: Path) -> None:
        guide = next(g for g in guides(small) if g.path == "workflow/running-jobs.md")

        assert (
            guide.sections[0].body
            == "Run a job with the runner. This page is about jobs."
        )

    def test_a_guide_with_no_heading_is_named_by_its_path(self, tmp_path: Path) -> None:
        make_guides(tmp_path, {"loose.md": "Just some text.\n"})

        assert guides(tmp_path)[0].title == "loose.md"

    def test_the_guides_come_in_path_order(self, small: Path) -> None:
        assert [g.path for g in guides(small)] == [
            "features/dojo.md",
            "workflow/running-jobs.md",
        ]


class TestLinks:
    def test_a_guide_links_to_its_page_on_the_docs_site(self, small: Path) -> None:
        guide = next(g for g in guides(small) if g.path == "workflow/running-jobs.md")

        assert guide.url == f"{SITE_URL}user-guides/workflow/running-jobs/"

    def test_a_section_links_to_its_anchor(self, small: Path) -> None:
        guide = next(g for g in guides(small) if g.path == "workflow/running-jobs.md")

        assert guide.sections[1].link == (
            f"{SITE_URL}user-guides/workflow/running-jobs/#slurm-mode-slurm"
        )

    def test_the_top_section_links_to_the_page_itself(self, small: Path) -> None:
        guide = next(g for g in guides(small) if g.path == "workflow/running-jobs.md")

        assert guide.sections[0].link == guide.url

    def test_a_reference_page_links_to_the_reference_section_not_the_user_guides(
        self, tmp_path: Path
    ) -> None:
        make_guides(
            tmp_path,
            {
                "reference/cli.md": "# Command Line Reference\n\n## `mujoco-mojo dojo`\n\nText.\n"
            },
        )
        guide = guides(tmp_path)[0]

        assert guide.url == f"{SITE_URL}reference/cli/"
        assert guide.sections[1].link == f"{SITE_URL}reference/cli/#mujoco-mojo-dojo"

    def test_a_reference_page_is_read_by_its_bare_name_too(
        self, tmp_path: Path
    ) -> None:
        make_guides(
            tmp_path, {"reference/cli.md": "# Command Line Reference\n\nText.\n"}
        )

        for path in ("reference/cli.md", "docs/reference/cli.md", "cli.md", "cli"):
            assert read_guide(path, directory=tmp_path).startswith(
                f"Command Line Reference ({SITE_URL}reference/cli/)"
            ), path

    @pytest.mark.parametrize(
        ("heading", "anchor"),
        [
            ("Getting Started", "getting-started"),
            ("SLURM Mode (`slurm`)", "slurm-mode-slurm"),
            ("The RuntimeManager (`rm`)", "the-runtimemanager-rm"),
            ("Pass  arguments -- to scripts", "pass-arguments-to-scripts"),
            ("Café menu", "cafe-menu"),
        ],
    )
    def test_the_anchor_is_what_the_docs_site_makes(
        self, heading: str, anchor: str
    ) -> None:
        assert slugify(heading) == anchor


def test_the_table_of_contents_has_a_line_for_each_guide(small: Path) -> None:
    assert table_of_contents(small).splitlines() == [
        "- features/dojo.md: Dojo Dashboard",
        "- workflow/running-jobs.md: Running Jobs",
    ]


class TestSearching:
    def test_the_section_about_it_comes_first(self, small: Path) -> None:
        hits = search_guides("submit a job to SLURM", directory=small)

        assert hits[0].section.title == "SLURM Mode (`slurm`)"

    def test_a_word_in_a_heading_counts_for_more_than_one_in_the_text(
        self, tmp_path: Path
    ) -> None:
        make_guides(
            tmp_path,
            {
                "a.md": "# A\n\n## Plots\n\nSomething.\n\n## Other\n\nPlots plots plots are drawn here.\n",
            },
        )

        hits = search_guides("plots", directory=tmp_path)

        assert hits[0].section.title == "Plots"

    def test_words_like_how_and_the_are_ignored(self, small: Path) -> None:
        assert search_guides("how do I the", directory=small) == []

    def test_an_ending_does_not_matter(self, small: Path) -> None:
        for query in ("recording videos", "record video", "records a video"):
            assert search_guides(query, directory=small)[0].section.title == (
                "Video Recording"
            ), query

    def test_a_word_is_found_in_another_form_that_only_the_text_has(
        self, tmp_path: Path
    ) -> None:
        """Only `runs` is in the guide and only `running` is asked, so the match is the ending being ignored and not a shared word."""
        make_guides(
            tmp_path,
            {
                "a.md": "# A\n\n## Alpha\n\nIt runs everything.\n\n## Beta\n\nIt stops.\n"
            },
        )

        hits = search_guides("running", directory=tmp_path)

        assert [h.section.title for h in hits] == ["Alpha"]

    @pytest.mark.parametrize(
        ("asked", "written"),
        [
            ("run", "running"),
            ("running", "runs"),
            ("stop", "stopped"),
            ("submit", "submitted"),
            ("set", "setting"),
            ("add", "adding"),
            ("record", "recording"),
            ("video", "videos"),
        ],
    )
    def test_a_word_meets_its_other_forms_including_ones_that_double_a_letter(
        self, tmp_path: Path, asked: str, written: str
    ) -> None:
        make_guides(
            tmp_path,
            {
                "a.md": f"# A\n\n## Alpha\n\nIt is about {written}.\n\n## Beta\n\nNothing here.\n"
            },
        )

        hits = search_guides(asked, directory=tmp_path)

        assert [h.section.title for h in hits] == ["Alpha"]

    def test_snake_case_is_read_as_words(self, small: Path) -> None:
        assert search_guides("time_limit", directory=small)[0].section.title == (
            "Time limits"
        )

    def test_nothing_matching_gives_nothing(self, small: Path) -> None:
        assert search_guides("zzzqqq", directory=small) == []

    def test_an_empty_question_gives_nothing(self, small: Path) -> None:
        assert search_guides("", directory=small) == []
        assert search_guides("   ", directory=small) == []

    def test_the_number_of_matches_is_limited(self, small: Path) -> None:
        assert len(search_guides("job", limit=1, directory=small)) == 1

    def test_no_guide_fills_the_results_with_its_own_sections(
        self, tmp_path: Path
    ) -> None:
        many = "# Big\n\n" + "".join(
            f"## Part {i}\n\nwidget text\n\n" for i in range(6)
        )
        make_guides(tmp_path, {"big.md": many, "small.md": "# Small\n\nA widget.\n"})

        paths = [
            h.section.path for h in search_guides("widget", limit=5, directory=tmp_path)
        ]

        assert paths.count("big.md") == 2
        assert "small.md" in paths

    def test_the_same_question_always_gives_the_same_order(self, small: Path) -> None:
        first = [h.section.label for h in search_guides("run job", directory=small)]

        assert first == [
            h.section.label for h in search_guides("run job", directory=small)
        ]

    def test_a_hit_shows_the_line_that_matched_best(self, small: Path) -> None:
        hit = search_guides("record video runtime manager", directory=small)[0]

        assert hit.snippet == (
            "Record a video with the runtime manager. Videos are written to the trial folder."
        )

    def test_a_snippet_is_never_a_line_of_code(self, small: Path) -> None:
        hit = search_guides("submit_slurm runner config", directory=small)[0]

        assert "runner.submit_slurm" not in hit.snippet

    def test_a_long_snippet_is_cut_with_an_ellipsis(self, tmp_path: Path) -> None:
        make_guides(tmp_path, {"a.md": f"# A\n\n{'widget ' * 100}\n"})

        snippet = search_guides("widget", directory=tmp_path)[0].snippet

        assert snippet.endswith("...")
        assert len(snippet) <= 223


class TestReading:
    def test_a_guide_is_read_whole_with_its_title_and_link_on_top(
        self, small: Path
    ) -> None:
        text = read_guide("features/dojo.md", directory=small)

        assert text.startswith(
            f"Dojo Dashboard ({SITE_URL}user-guides/features/dojo/)\n\n"
        )
        assert "Start it with the `dojo` command." in text

    def test_a_section_comes_with_the_sections_under_it(self, small: Path) -> None:
        text = read_guide("workflow/running-jobs.md", "SLURM Mode", directory=small)

        assert "Submit with `submit_slurm`" in text
        assert "### Time limits" in text
        assert "Videos are written" not in text

    def test_a_section_ends_at_the_next_one_of_its_level(self, small: Path) -> None:
        text = read_guide("workflow/running-jobs.md", "Time limits", directory=small)

        assert "Set `time_limit`" in text
        assert "Video Recording" not in text

    def test_a_title_that_matches_exactly_wins_over_one_that_only_contains_it(
        self, tmp_path: Path
    ) -> None:
        make_guides(
            tmp_path,
            {"a.md": "# A\n\n## Time limits\n\nlong one\n\n## Time\n\nshort one\n"},
        )

        assert "short one" in read_guide("a.md", "time", directory=tmp_path)

    def test_a_section_is_found_by_part_of_its_title_in_any_case(
        self, small: Path
    ) -> None:
        text = read_guide("workflow/running-jobs.md", "slurm", directory=small)

        assert "Submit with `submit_slurm`" in text

    def test_a_section_read_links_to_its_own_anchor(self, small: Path) -> None:
        text = read_guide("workflow/running-jobs.md", "Video", directory=small)

        assert text.startswith(
            f"Running Jobs > Video Recording ({SITE_URL}user-guides/workflow/running-jobs/#video-recording)"
        )

    def test_a_section_that_is_not_there_is_answered_with_the_ones_that_are(
        self, small: Path
    ) -> None:
        text = read_guide("workflow/running-jobs.md", "Nope", directory=small)

        assert "no section called 'Nope'" in text
        assert "Video Recording" in text

    @pytest.mark.parametrize(
        "path",
        [
            "workflow/running-jobs.md",
            "workflow/running-jobs",
            "/workflow/running-jobs.md",
            "docs/user-guides/workflow/running-jobs.md",
            "user-guides/workflow/running-jobs.md",
            "running-jobs.md",
            "running-jobs",
        ],
    )
    def test_a_path_is_accepted_however_a_model_writes_it(
        self, small: Path, path: str
    ) -> None:
        assert read_guide(path, directory=small).startswith("Running Jobs (")

    def test_a_path_that_is_not_there_is_answered_with_the_guides_and_the_closest(
        self, small: Path
    ) -> None:
        text = read_guide("workflow/running-job.md", directory=small)

        assert "There is no guide at" in text
        assert "Closest: workflow/running-jobs.md" in text
        assert "features/dojo.md" in text

    def test_a_bare_name_two_guides_share_is_not_guessed(self, tmp_path: Path) -> None:
        make_guides(tmp_path, {"a/report.md": "# A\n", "b/report.md": "# B\n"})

        assert "There is no guide at" in read_guide("report.md", directory=tmp_path)

    def test_a_long_guide_is_cut_with_a_list_of_its_sections(self, small: Path) -> None:
        text = read_guide("workflow/running-jobs.md", limit=150, directory=small)

        assert "[Cut here." in text
        assert "Video Recording" in text.split("[Cut here.")[1]
        assert "Videos are written" not in text

    def test_a_short_guide_is_not_cut(self, small: Path) -> None:
        assert "[Cut here" not in read_guide("features/dojo.md", directory=small)


class TestTheBundledGuides:
    """The real guides, so a reorganized docs folder or a broken bundle shows up here and not as a bad answer."""

    def test_the_bundle_is_found_and_every_guide_has_a_title_and_sections(self) -> None:
        assert GUIDE_DIR.is_dir()
        every = guides()

        assert len(every) >= 20
        for guide in every:
            assert guide.title and guide.title != guide.path, guide.path
            assert guide.sections, guide.path

    def test_the_table_of_contents_names_every_guide(self) -> None:
        contents = table_of_contents()

        for guide in guides():
            assert f"- {guide.path}: {guide.title}" in contents

    @pytest.mark.parametrize(
        ("question", "guide"),
        [
            (
                "How do I submit a job to SLURM?",
                "workflow/running-jobs/running-jobs.md",
            ),
            ("how do I record a video of a trial", "workflow/runtime-script.md"),
            (
                "make a requirement terminate the trial early",
                "features/requirements.md",
            ),
            ("how do I start the Dojo dashboard", "features/dojo/dojo.md"),
            ("what is pose context", "features/pose-context.md"),
            ("how do I install the optimization extra", "features/optimization.md"),
            ("how do I write the generate function", "workflow/generate-script.md"),
            ("what does the Mosaic page show", "features/dojo/mosaic.md"),
            (
                "what options does the monte-carlo command take",
                "reference/cli.md",
            ),
            (
                "how do I run a single trial from the command line",
                "reference/cli.md",
            ),
            (
                "what does the watch-workdir command do",
                "reference/cli.md",
            ),
            ("which flags does mujoco-mojo init take", "reference/cli.md"),
            (
                "how do I change a setting from the command line",
                "reference/cli.md",
            ),
        ],
    )
    def test_a_question_finds_the_guide_about_it_among_the_first_three(
        self, question: str, guide: str
    ) -> None:
        paths = [h.section.path for h in search_guides(question, limit=3)]

        assert guide in paths, paths

    def test_the_command_line_reference_is_one_of_the_guides_and_a_command_can_be_read_alone(
        self,
    ) -> None:
        assert "- reference/cli.md: Command Line Reference" in table_of_contents()

        text = read_guide("reference/cli.md", "mujoco-mojo dojo")

        assert text.startswith("Command Line Reference > `mujoco-mojo dojo` (")
        assert "mujoco-mojo dojo [OPTIONS] WORKDIR" in text
        assert "| `--port`, `-p` | integer | `8000` |" in text
        assert "mujoco-mojo init" not in text

    def test_the_code_of_a_guide_that_was_an_include_can_be_read(self) -> None:
        text = read_guide("workflow/generate-script.md")

        assert "def generate(" in text

    def test_every_guide_can_be_read_whole_or_cut_to_a_list_of_sections(self) -> None:
        for guide in guides():
            text = read_guide(guide.path)

            assert text.startswith(f"{guide.title} (")
            assert len(text) < 7500 + 600, guide.path
