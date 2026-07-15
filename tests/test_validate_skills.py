"""Tests for the repo-aware SKILL.md frontmatter validation in validate_skills.

The skill-creator plugin's quick_validate.py hardcodes its frontmatter
allowlist and rejects this repo's `user_invocable` key; these tests pin the
repo validator's contract: repo keys pass, unknown keys and malformed
frontmatter fail with clear errors.
"""

from __future__ import annotations

from pathlib import Path

from scripts.validate_skills import (
    ALLOWED_SKILL_KEYS,
    main,
    validate_skill_frontmatter,
)


def make_skill(root: Path, name: str, frontmatter: str, body: str = "# skill\n") -> Path:
    skill_dir = root / name
    skill_dir.mkdir(parents=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(f"---\n{frontmatter}\n---\n\n{body}", encoding="utf-8")
    return skill_md


class TestValidateSkillFrontmatter:
    def test_valid_skill_with_user_invocable_passes(self) -> None:
        text = "---\nname: my-skill\ndescription: Does a thing\nuser_invocable: true\n---\n\n# body\n"
        assert validate_skill_frontmatter(text) == []

    def test_valid_skill_without_user_invocable_passes(self) -> None:
        # The .codex mirror tree omits user_invocable by convention.
        text = "---\nname: my-skill\ndescription: Does a thing\n---\n\n# body\n"
        assert validate_skill_frontmatter(text) == []

    def test_unknown_key_fails_and_is_named(self) -> None:
        text = "---\nname: my-skill\ndescription: Does a thing\nfavorite_color: blue\n---\n"
        errors = validate_skill_frontmatter(text)
        assert len(errors) == 1
        assert "favorite_color" in errors[0]
        assert "user_invocable" in errors[0]  # allowlist shown in the message

    def test_missing_description_fails(self) -> None:
        text = "---\nname: my-skill\n---\n"
        errors = validate_skill_frontmatter(text)
        assert errors == ["Missing `description` in frontmatter"]

    def test_missing_name_fails(self) -> None:
        text = "---\ndescription: Does a thing\n---\n"
        errors = validate_skill_frontmatter(text)
        assert errors == ["Missing `name` in frontmatter"]

    def test_missing_frontmatter_fails(self) -> None:
        assert validate_skill_frontmatter("# no frontmatter\n") == ["No YAML frontmatter found"]

    def test_unclosed_frontmatter_fails(self) -> None:
        errors = validate_skill_frontmatter("---\nname: my-skill\n")
        assert errors == ["Invalid frontmatter format (missing closing '---')"]

    def test_non_dict_frontmatter_fails(self) -> None:
        errors = validate_skill_frontmatter("---\n- just\n- a list\n---\n")
        assert errors == ["Frontmatter must be a YAML dictionary"]

    def test_non_kebab_case_name_fails(self) -> None:
        text = "---\nname: My Skill\ndescription: Does a thing\n---\n"
        errors = validate_skill_frontmatter(text)
        assert len(errors) == 1
        assert "kebab-case" in errors[0]

    def test_angle_brackets_in_description_fail(self) -> None:
        text = "---\nname: my-skill\ndescription: Use <target> here\n---\n"
        errors = validate_skill_frontmatter(text)
        assert errors == ["Description cannot contain angle brackets (< or >)"]

    def test_overlong_description_fails(self) -> None:
        text = f"---\nname: my-skill\ndescription: {'x' * 1025}\n---\n"
        errors = validate_skill_frontmatter(text)
        assert len(errors) == 1
        assert "too long" in errors[0]

    def test_non_boolean_user_invocable_fails(self) -> None:
        text = '---\nname: my-skill\ndescription: Does a thing\nuser_invocable: "sometimes"\n---\n'
        errors = validate_skill_frontmatter(text)
        assert errors == ["`user_invocable` must be a boolean, got str"]

    def test_base_plugin_keys_are_allowed(self) -> None:
        # Keys from the skill-creator plugin spec must not be rejected.
        text = (
            "---\nname: my-skill\ndescription: Does a thing\nlicense: MIT\n"
            "allowed-tools: Bash\nmetadata:\n  author: me\ncompatibility: claude-code\n---\n"
        )
        assert validate_skill_frontmatter(text) == []

    def test_allowlist_includes_repo_and_base_keys(self) -> None:
        assert "user_invocable" in ALLOWED_SKILL_KEYS
        assert {"name", "description", "metadata"} <= ALLOWED_SKILL_KEYS


class TestMainCli:
    def test_all_valid_skills_exit_zero(self, tmp_path: Path) -> None:
        skills = tmp_path / "skills"
        make_skill(skills, "good-skill", "name: good-skill\ndescription: Fine\nuser_invocable: true")
        assert main(["--workspace", str(tmp_path), "--skills-dir", str(skills)]) == 0

    def test_unknown_key_skill_exits_nonzero(self, tmp_path: Path, capsys) -> None:
        skills = tmp_path / "skills"
        make_skill(skills, "bad-skill", "name: bad-skill\ndescription: Fine\nfoo: bar")
        assert main(["--workspace", str(tmp_path), "--skills-dir", str(skills)]) == 1
        out = capsys.readouterr().out
        assert "ERROR" in out
        assert "foo" in out

    def test_missing_description_skill_exits_nonzero(self, tmp_path: Path, capsys) -> None:
        skills = tmp_path / "skills"
        make_skill(skills, "bad-skill", "name: bad-skill\nuser_invocable: true")
        assert main(["--workspace", str(tmp_path), "--skills-dir", str(skills)]) == 1
        assert "Missing `description`" in capsys.readouterr().out


class TestRealSkillTrees:
    def test_all_repo_skills_pass(self, repo_root: Path) -> None:
        skill_files = sorted(
            skill_md
            for tree in (repo_root / ".claude" / "skills", repo_root / ".codex" / "skills")
            for skill_md in tree.glob("*/SKILL.md")
        )
        assert len(skill_files) >= 60, "expected both repo skill trees to be populated"
        failures = {
            str(skill_md.relative_to(repo_root)): errors
            for skill_md in skill_files
            if (errors := validate_skill_frontmatter(skill_md.read_text(encoding="utf-8")))
        }
        assert failures == {}
