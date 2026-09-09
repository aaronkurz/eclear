# Releasing eclear to PyPI

Everything below runs from the repo root. Nothing here is automated: the upload
is irreversible, so each step is yours to run.

## 0. Before the first release only

Check the name is free — open <https://pypi.org/project/eclear/>. A 404 means
it is available. If it is taken, change `name` in `pyproject.toml` (the GitHub
repo name can stay `eclear`).

## 1. Rebuild and re-verify

The committed bundle is what users get, so rebuild it before every release and
make sure the suites pass against what you are about to ship.

```bash
cd js && npm install && npm run typecheck && npm test && npm run build && cd ..
uv sync && uv run pytest
git status --short          # if enrichment.js changed, commit it
```

## 2. Build the distributions

```bash
rm -rf dist/
uv build
uvx twine check dist/*
```

Then look inside the wheel — this is the step that catches a packaging mistake
before it becomes a permanent version number:

```bash
unzip -l dist/*.whl
```

It must contain `eclear/static/enrichment.js` and `eclear/contracts/*.json`, and
must **not** contain `node_modules`, `js/`, or `tests/`.

## 3. Smoke-test the built wheel

Install it into a throwaway environment, from a directory that is *not* this
repo — otherwise Python imports the local `eclear/` folder and you have tested
nothing:

```bash
cd /tmp
uv run --isolated --no-project --with /home/aaron/Developer/eclear/dist/eclear-0.1.0-py3-none-any.whl \
  python -c "import eclear, pandas as pd; print(eclear.__file__); print(len(str(eclear.EnrichmentWidget._esm)))"
```

The path printed must be inside a `site-packages`, not `/home/aaron/Developer/eclear`.

## 4. Dry run on TestPyPI

TestPyPI is a separate site with its own account and its own tokens. Register at
<https://test.pypi.org/account/register/>, then create a token at
<https://test.pypi.org/manage/account/token/>.

```bash
uv publish --publish-url https://test.pypi.org/legacy/
```

It prompts for the token (username `__token__` if asked). Then install it back:

```bash
cd /tmp
uv run --isolated --no-project \
  --index https://test.pypi.org/simple/ --index-strategy unsafe-best-match \
  --with eclear python -c "import eclear; print(eclear.__file__)"
```

The extra index flags are needed because pandas and anywidget come from real
PyPI, not TestPyPI.

## 5. Publish for real

Create a token at <https://pypi.org/manage/account/token/>. For a project that
does not exist yet the token must be **account-scoped** — a project-scoped token
cannot create a new project. After the first successful upload, delete that
token and issue a project-scoped one.

```bash
uv publish
```

Or non-interactively, without the token touching your shell history:

```bash
read -rs UV_PUBLISH_TOKEN && export UV_PUBLISH_TOKEN && uv publish
```

## 6. Tag the release

```bash
git tag v0.1.0
git push origin main --tags
```

## The one-way door

A version number on PyPI can never be reused, even after you delete the release.
If 0.1.0 goes out wrong, the only fix is 0.1.1. Steps 2–4 exist to make that
unnecessary.

## Later: trusted publishing

Once the first manual release proves the package is sound, switch to PyPI
trusted publishing: a GitHub Actions workflow uploads on a pushed tag with no
token stored anywhere. Configure it at
<https://pypi.org/manage/project/eclear/settings/publishing/>.
