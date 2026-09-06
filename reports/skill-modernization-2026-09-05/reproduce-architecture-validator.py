from pathlib import Path
import tempfile
from scripts.validate_skills import lint_markdown_file, validate_skill_frontmatter
root = Path(tempfile.mkdtemp(prefix='validator-repro-'))
(root / 'argparse_cli.py').write_text('import argparse\np=argparse.ArgumentParser()\ns=p.add_subparsers(dest="action",required=True)\ns.add_parser("search")\np.parse_args()\n')
md = root / 'SKILL.md'
md.write_text('---\nname: example\ndescription: Example\n---\n```bash\nuv run python argparse_cli.py nonexistent-subcommand\n```\n')
print('Invalid real argparse subcommand lint result:', [i.message for i in lint_markdown_file(md, root, True, False, {}, None, True)])
(root / 'broken_cli.py').write_text('raise ImportError("fixture dependency unavailable")\n')
md.write_text('---\nname: example\ndescription: Example\n---\n```bash\nuv run python broken_cli.py search --nonexistent-option\n```\n')
print('Broken help + invalid flag lint result:', [i.message for i in lint_markdown_file(md, root, True, False, {}, None, True)])
print('Native Claude option lint result:', validate_skill_frontmatter('---\nname: example\ndescription: Example\nuser-invocable: true\ndisable-model-invocation: true\ncontext: fork\n---\n'))
