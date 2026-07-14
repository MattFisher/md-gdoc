# Releasing

## One-time setup: PyPI trusted publishing

Publishing runs from GitHub Actions with no API tokens, via
[trusted publishing](https://docs.pypi.org/trusted-publishers/).

1. Log in to [pypi.org](https://pypi.org) → *Your account* → *Publishing*.
2. Under **Add a new pending publisher**, enter:
   - PyPI project name: `md-gdoc`
   - Owner: `MattFisher`
   - Repository name: `md-gdoc`
   - Workflow name: `publish.yml`
   - Environment name: `pypi`
3. In the GitHub repo, create the environment: *Settings → Environments →
   New environment* → name it `pypi`. (Optionally add yourself as a required
   reviewer so releases need a manual approval click.)

The first tagged release creates the PyPI project and converts the pending
publisher into a normal one.

## Each release

1. Update `__version__` in `src/md_gdoc/__init__.py` (single source of truth —
   `pyproject.toml` reads it).
2. Add a section to `CHANGELOG.md` and update its link references.
3. Commit, then tag and push:

   ```bash
   git tag v0.1.0
   git push origin main v0.1.0
   ```

4. The `publish.yml` workflow builds the sdist/wheel and uploads to PyPI.
5. Create a GitHub release from the tag, pasting the changelog section.

## Sanity checks before tagging

```bash
uv run pytest                        # unit tests
uv run ruff check .                  # lint
uv build                             # sdist + wheel into dist/
uvx twine check dist/*               # metadata renders on PyPI
RUN_MD_GDOC_E2E=1 uv run pytest tests/e2e -q   # live API round-trip (optional but recommended)
```
