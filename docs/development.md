# Development

This guide walks you through everything you need to develop, test, document, build, and release `pcdigitizer`.
It assumes you're comfortable with a terminal but doesn't assume you've used any of these tools before.

## What is pcdigitizer?

`pcdigitizer` is a Python library that programmatically downloads, parses, and digitizes chemical data and annotations from [PubChem](https://pubchem.ncbi.nlm.nih.gov/).
It talks to PubChem's REST API (called PUG-REST) and returns structured data using [Polars](https://pola.rs/) DataFrames.

The source code lives at [github.com/scienting/pcdigitizer](https://github.com/scienting/pcdigitizer).

## Prerequisites

Before you begin, make sure you have:

- Git installed and configured with your GitHub credentials.
    If you're new to Git, GitHub's [Getting Started guide](https://docs.github.com/en/get-started) covers installation and setup.
- A GitHub account with access to the `scienting/pcdigitizer` repository.
- pixi; the project's environment and dependency manager (explained next).

You do *not* need to install Python yourself.
Pixi handles that.

## Understanding pixi

`pcdigitizer` uses [pixi](https://pixi.sh/latest/) instead of the more common `pip` + `venv` workflow.
Pixi is a package manager that creates isolated environments and installs both Python and all dependencies for you: conda packages and PyPI packages alike.
This means every contributor works with the same Python version and the same library versions, which eliminates "works on my machine" problems.

### Installing pixi

Follow the instructions at [pixi.sh](https://pixi.sh/latest/) for your operating system.
On macOS or Linux, the quickest method is:

```bash
curl -fsSL https://pixi.sh/install.sh | bash
```

After installation, restart your terminal so the `pixi` command is available.
Verify it worked:

```bash
pixi --version
```

### How pixi organizes this project

The file `pixi.toml` at the root of the repository defines everything pixi needs to know: which Python version to use, which libraries to install, and which shortcut commands (called *tasks*) are available.

`pcdigitizer` defines three environments:

| Environment | Purpose | How to activate |
| :---------- | :------ | :-------------- |
| `default` | The runtime dependencies only (what a user of the library needs). | `pixi shell` |
| `dev` | Everything in default plus testing, linting, formatting, building, and publishing tools. | `pixi shell -e dev` |
| `docs` | Everything needed to build and preview the documentation site. | `pixi shell -e docs` |

You'll use `dev` for most day-to-day work and `docs` when editing documentation.
The separation keeps each environment lean: you don't need MkDocs installed to run tests, and you don't need pytest installed to preview docs.

## Setting up the Development Environment

1. Clone the repository:

    ```bash
    git clone git@github.com:scienting/pcdigitizer.git
    cd pcdigitizer
    ```

    This creates a local copy of the codebase.
    The `git@github.com:` prefix uses SSH authentication.
    If you haven't set up SSH keys with GitHub, see [GitHub's SSH guide](https://docs.github.com/en/authentication/connecting-to-github-with-ssh).

2. Install dependencies:

    ```bash
    pixi install
    ```

    This reads `pixi.toml`, downloads Python 3.13+, and installs every dependency for all three environments.
    The first run takes a few minutes because it's fetching everything from scratch.
    Subsequent runs are fast because pixi caches packages.

3. Activate the development environment:

    ```bash
    pixi shell -e dev
    ```

    Your terminal prompt changes to indicate you're inside the pixi environment.
    Every command you run now (e.g., `python`, `pytest`, `ruff`) points to the versions pixi installed, not whatever might be on your system path.

    When you're done working, type `exit` to leave the pixi shell.

    Alternatively, you can run one-off commands without entering the shell by using `pixi run -e dev <command>`.

## Project Layout

Here's a high-level view of the repository.
Source files inside `pcdigitizer/` aren't listed here because they change often; explore the package directory directly to see the current modules.

```text
.
├── pcdigitizer/          # The Python package (source code lives here)
├── tests/                # Test suite (pytest)
│   ├── conftest.py       # Shared fixtures and auto-enables debug logging
│   ├── test_*.py         # Test modules
│   └── tmp/              # Temporary test data
├── docs/                 # MkDocs documentation source
│   ├── css/              # Custom stylesheets
│   ├── js/               # JavaScript (MathJax config, etc.)
│   ├── img/              # Images used in docs
│   ├── gen_ref_pages.py  # Script that auto-generates API reference pages
│   ├── pages.yml         # Navigation structure
│   └── index.md          # Documentation home page
├── pixi.toml             # Pixi configuration (environments, dependencies, tasks)
├── pixi.lock             # Locked dependency versions (committed to Git)
├── pyproject.toml        # Python packaging metadata
├── mkdocs.yml            # MkDocs site configuration
├── CHANGELOG.md          # Release history
├── LICENSE.md            # Prosperity license
└── README.md
```

A few things worth noting about this layout:

The `pixi.lock` file pins every dependency to an exact version.
It's committed to Git so that `pixi install` reproduces the same environment on every machine.
You should never edit it by hand; pixi updates it automatically when you change `pixi.toml`.

The `pyproject.toml` file contains Python packaging metadata (package name, author, build system).
It works alongside `pixi.toml`, which handles the environment and task definitions.

The package installs in *editable mode* (note the `editable = true` in `pixi.toml`), which means changes you make to the source files take effect immediately without reinstalling.

## Code Formatting and Linting

`pcdigitizer` uses [Ruff](https://docs.astral.sh/ruff/) for both linting (catching potential bugs and style violations) and formatting (enforcing consistent code style).
Ruff is extremely fast, it replaces tools like flake8, isort, and black in a single binary.

To lint and format the entire codebase:

```bash
pixi run format
```

This command does two things in sequence (the `format` task depends on the `lint` task):

1. Lints the code with `ruff check --fix`, which catches errors and auto-fixes what it can.
2. Sorts imports and formats the code with `ruff format`, which enforces consistent spacing, line length, quote style, and so on.

Run this before every commit.
If Ruff finds issues it can't auto-fix, it prints them to the terminal with file names and line numbers.

You can also lint without formatting:

```bash
pixi run lint
```

The rules Ruff enforces are defined in `.ruff.toml` at the repository root.

## Documentation

The documentation site is built with [MkDocs](https://www.mkdocs.org/) using the [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/) theme.
The site configuration lives in `mkdocs.yml`, and the source files live in the `docs/` directory.

A few things worth knowing about the documentation setup:

- API reference pages are generated automatically.
    The `mkdocstrings` plugin reads docstrings from the Python source code and renders them as formatted documentation.
    If you write or update a docstring in the code, the API docs update too.
- Docstrings follow Google style.
    When writing docstrings, use the [Google docstring format](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings).
- Math is supported.
    The site loads MathJax, so you can write LaTeX in your documentation files.

### Previewing documentation locally

```bash
pixi run -e docs docs-serve
```

This starts a local web server.
Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/) in your browser.
The page reloads automatically whenever you save a file, so you can edit and preview side by side.

Press `Ctrl+C` in the terminal to stop the server.

### Building documentation for deployment

```bash
pixi run -e docs docs
```

This generates the static site in a `public/` directory (deleting any previous build first).
The CI/CD pipeline typically runs this command to produce the files that get deployed.

## Testing

Tests live in the `tests/` directory and run with [pytest](https://docs.pytest.org/).
The test configuration is in `.pytest.ini`.

A shared fixture in `conftest.py` automatically turns on debug-level logging for every test session, so you can see detailed log output when something goes wrong.

### Running tests

```bash
pixi run -e dev tests
```

Under the hood, this runs pytest with coverage tracking enabled.
It produces two reports: an XML coverage report (`report.xml`) and a JUnit-style test report, both used by CI pipelines.
The `--failed-first` flag re-runs previously failing tests first, which speeds up debugging.

### Checking test coverage

After running the tests, you can see a summary of which lines are covered:

```bash
pixi run -e dev coverage
```

This prints a table showing each source file and its coverage percentage.
Look for files with low coverage, those are good candidates for new tests.

### Writing tests

Place new test files in the `tests/` directory.
Pytest discovers any file named `test_*.py` or `*_test.py` automatically.
A minimal test looks like:

```python
from pcdigitizer import PubChemAPI


def test_build_url_basic():
    url = PubChemAPI.build_url(
        domain="compound",
        namespace="name",
        identifiers="aspirin",
    )
    assert "compound" in url
    assert "aspirin" in url
```

Keep in mind that tests calling PubChem's live API will make real HTTP requests.
For unit tests, consider mocking the network layer with `unittest.mock.patch` or a library like `responses`.

## Logging

`pcdigitizer` uses [Loguru](https://loguru.readthedocs.io/) for logging.
By default, logging is completely disabled; the library stays silent so it doesn't clutter output for end users.
When you need to see what the library is doing (debugging a failed API call, tracing how data gets parsed, confirming a request URL), you turn logging on explicitly.

### Log levels

Python's logging system uses numeric levels to control how much detail you see.
Each level includes everything above it: setting the level to `WARNING` shows warnings and errors but hides informational and debug messages.
Setting it to `DEBUG` shows everything.

| Level | Number | What it captures | When to use it |
| :---- | :----- | :--------------- | :------------- |
| `DEBUG` | 10 | Every internal detail: constructed URLs, raw response status codes, intermediate parsing steps. | Troubleshooting a specific bug. You want to see exactly what `pcdigitizer` sends to PubChem and what it gets back. This is the level the test suite uses. |
| `INFO` | 20 | High-level progress: which API endpoint was called, how many records were returned, which data source was queried. | Day-to-day development or monitoring a long-running script. Enough to confirm things are working without flooding the terminal. |
| `WARNING` | 30 | Unexpected but non-fatal situations: a deprecated endpoint, a retry after a transient failure, a missing optional field in the response. | Production scripts where you only want to hear about potential problems. |
| `ERROR` | 40 | Something went wrong and the operation couldn't complete: a failed HTTP request, an unparseable response, an invalid identifier. | Same as `WARNING`, but stricter. You only see actual failures. |
| `CRITICAL` | 50 | A catastrophic problem that likely means the program can't continue. | Rarely relevant for a library like `pcdigitizer`, but available if needed. |

If you're unsure which level to pick, start with `INFO` (20).
Drop to `DEBUG` (10) when you need to dig into a specific problem.

### Enabling logging in code

Call `enable_logging` at the top of your script, before you make any API calls:

```python
from pcdigitizer import enable_logging

enable_logging(level_set=20)  # INFO: shows progress without excessive detail
```

The `enable_logging` function accepts several arguments:

```python
enable_logging(
    level_set=10,                       # Log level (10=DEBUG, 20=INFO, etc.)
    stdout_set=True,                    # Print logs to the terminal
    file_path="/tmp/pcdigitizer.log",   # Also write logs to this file (optional)
)
```

When `stdout_set` is `True` (the default), log messages print to the terminal with color-coded formatting: timestamps in green, the log level highlighted by severity, and the source file, function, and line number in cyan.
When you provide a `file_path`, the same messages are also written to that file so you can review them later.

### Enabling logging with environment variables

If you don't want to modify code, say you're running someone else's script and need to see what's happening, you can enable logging through environment variables:

```bash
export PCDIGITIZER_LOG=True
export PCDIGITIZER_LOG_LEVEL=10
```

`pcdigitizer` reads these variables at import time
If `PCDIGITIZER_LOG` is `True`, it calls `enable_logging` automatically with whatever level, output, and file path you've specified.
The full set of variables:

| Variable | Default | What it controls |
| :------- | :------ | :--------------- |
| `PCDIGITIZER_LOG` | `False` | Whether logging is enabled at all. Must be `True` to activate. |
| `PCDIGITIZER_LOG_LEVEL` | `20` | The numeric log level (see the table above). |
| `PCDIGITIZER_STDOUT` | `True` | Whether to print logs to the terminal. |
| `PCDIGITIZER_LOG_FILE_PATH` | None | Path to a log file. Omit this to skip file logging. |

### Logging in tests

The test suite enables debug-level logging automatically.
The fixture in `conftest.py` calls `enable_logging(10)` at the start of every test session, so when a test fails you'll see the full trace of API calls and internal operations in the pytest output without any extra setup.

## Building the Package

When you're ready to create a distributable package (a `.tar.gz` and a `.whl` file):

```bash
pixi run build
```

This first removes any previous `build/` directory (to avoid stale artifacts), then runs `python3 -m build` to produce fresh distribution files in the `dist/` directory.

The build uses `setuptools` and `setuptools-scm`.
The `setuptools-scm` plugin derives the package version from Git tags automatically, so the version in `pixi.toml` stays in sync with the version embedded in the built package.

## Versioning and Releases

`pcdigitizer` uses [bump-my-version](https://github.com/callowayproject/bump-my-version) to manage version numbers.
The current version is stored in `pixi.toml` (currently `26.4.10`).

### Bumping the version

```bash
pixi run -e dev bump
```

This increments the patch number (e.g., `26.4.10` → `26.4.11`), updates the version string in the configured files, and creates a Git commit and tag.
For minor or major bumps, you'd run `bump-my-version bump minor` or `bump-my-version bump major` directly inside the dev shell.

### Publishing to PyPI

Publishing is a two-step process: build, then upload.

1. Build the package (if you haven't already):

    ```bash
    pixi run build
    ```

2. Publish to TestPyPI first to verify everything works:

    ```bash
    pixi run publish-test
    ```

    TestPyPI is a separate package index that mirrors PyPI's infrastructure.
    Publishing there lets you verify the package installs correctly without affecting real users.
    You can install from TestPyPI with:

    ```bash
    pip install --index-url https://test.pypi.org/simple/ pcdigitizer
    ```

3. Publish to production PyPI once you're confident:

    ```bash
    pixi run publish
    ```

Both commands use [twine](https://twine.readthedocs.io/) under the hood.
You'll need PyPI credentials configured either through a `~/.pypirc` file or environment variables.
See [twine's documentation](https://twine.readthedocs.io/en/stable/#configuration) for setup instructions.

## Quick Reference: All pixi Tasks

| Task | Environment | What it does |
| :--- | :---------: | :----------- |
| `pixi run lint` | dev | Lint the codebase with Ruff and auto-fix where possible |
| `pixi run format` | dev | Lint, sort imports, and format all code |
| `pixi run -e dev tests` | dev | Run the test suite with coverage tracking |
| `pixi run -e dev coverage` | dev | Print a coverage summary table |
| `pixi run -e dev bump` | dev | Increment the patch version number |
| `pixi run build` | dev | Clean and build distribution files |
| `pixi run publish-test` | dev | Upload to TestPyPI |
| `pixi run publish` | dev | Upload to production PyPI |
| `pixi run -e docs docs-serve` | docs | Serve documentation locally with live reload |
| `pixi run -e docs docs` | docs | Build the documentation site to `public/` |

## Maintenance Best Practices

Keep your local copy current by pulling from `main` regularly:

```bash
git pull origin main
```

After pulling, run `pixi install` to pick up any new or changed dependencies.

Review open issues and pull requests on GitHub frequently.
Write clear commit messages that explain *why* a change was made, not just *what* changed.
When updating dependencies, run the full test suite before pushing to make sure nothing broke.
