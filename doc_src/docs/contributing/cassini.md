# Cassini

## Getting Set Up

The Cassini package uses [poetry](https://python-poetry.org/) for managing dependencies and code isolation.

To start working on Cassini, make sure poetry and git is set up and working then:

    git clone https://github.com/0Hughman0/Cassini

Then head into the directory:

    cd Cassini

Let poetry install the project dependencies and set up a virtual environment:

    poetry install --with dev

You can then run the test suite with:

    poetry run pytest

We make use of the [black code formatter](https://black.readthedocs.io/en/stable/index.html). This will automatically format your code appropriately using:

    poetry run black cassini

We also use mypy for static type analysis, we just use the default ruleset:

    poetry run mypy cassini

Code linting is performed by flake8. The CI will only complain if your project can't pass:

    poetry run flake8 . --select=E9,F63,F7,F82

Documentation-wise, we use the [numpy docstring standard](https://numpydoc.readthedocs.io/en/latest/format.html#docstring-standard) and these are built using sphinx.

This can be installed with:

    poetry install --with docs

And run with:

    poetry run python -m sphinx doc_src docs
