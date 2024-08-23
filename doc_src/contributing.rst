============
Contributing
============

Contributions to Cassini are incredibly welcome. This includes reporting bugs, making suggestions all the way to implementing whole new features.

The `issues section <https://github.com/0Hughman0/Cassini/issues>`_ is the best place to start, this is where to submit bug reports and discuss new feature ideas.

If you find something you'd really like to contribute, but don't know how, don't hesitate to ask of help or suggestions on how best to approach problems.

At the moment a few priorities for the project are:

    1. **Improving test coverage** - The test coverage of the codebase is quite low as this project is still in its infancy. Getting a good 'n' proper test suite will help make `cassini` into adulthood and is a great way to get orientated with the codebase!
    
    2. **CSS/ HTML improvements** - The fancy new Jupyterlab UI (see :ref:`codebase orientation <codebase-orientation>` still looks a bit ugly and could be vastly improved by users who are have a knack for css and HTML.
    
    3. **Discussing new feature ideas** - The project is young and its not clear who will use it and for what. If you wish it did xyz, start a discussion - there's a good chance others would like that feature too.
    
    4. **Implementing new features** - There is no shortage of new features in the `issues section <https://github.com/0Hughman0/Cassini/issues>`_ but someone needs to write the code! 

No need to ask for permission to get started... just fork the repo, have a go at making some improvements and `submit a pull request <https://github.com/0Hughman0/Cassini/pulls>`_ once you are happy for someone to take a look at it.

We run some CI tools to help streamline things. This includes running the test suite, linting, checking formatting and checking test coverage.

As test coverage is a big issue at the moment, please make sure your PR *increases* the test coverage!

.. _codebase-orientation:

Codebase Orientation
====================

Cassini is currently split into two packages:

    1. `Cassini <https://github.com/0Hughman0/Cassini>`_ - This provides the Python side code, including defining the structure of projects and providing a few magic methods.
    2. `jupyter_cassini <https://github.com/0Hughman0/jupyter_cassini>`_ - This provides a UI for the Python side via a JupyterLab extension. This package also includes a JupyterLab server extension that serves up data from a cassini project allowing it to be used by the UI.

Both packages use semantic versioning. The plan is to maybe keep both packages separate and to have the rule that compatible versions of cassini and the UI will have matching MAJOR versions. So both will be bumped in sync.

Why is it split into two? At some point in the future it may be possible to port the cassini codebase into other languages within the Jupyter remit e.g. Julia. By separating the UI code from the client-side code, it should be possible to make the UI universally compatible with any language.

Cassini
-------

The Cassini package uses `poetry <https://python-poetry.org/>`_ for managing dependencies and code isolation.

To start working on Cassini, make sure poetry and git is set up and working then::

    git clone https://github.com/0Hughman0/Cassini

Then head into the directory::

    cd Cassini

Let poetry install the project dependencies and set up a virtual environment::

    poetry install --with dev

You can then run the test suite with::

    poetry run pytest

We make use of the `black code formatter <https://black.readthedocs.io/en/stable/index.html>`_. This will automatically format your code appropriately using::

    poetry run black cassini

We also use mypy for static type analysis, we just use the default ruleset::

    poetry run mypy cassini

Code linting is performed by flake8. The CI will only complain if your project can't pass::

    poetry run flake8 . --select=E9,F63,F7,F82

Documentation-wise, we use the `numpy docstring standard <https://numpydoc.readthedocs.io/en/latest/format.html#docstring-standard>`_ and these are built using sphinx.

This can be installed with::

    poetry install --with docs

And run with::

    poetry run python -m sphinx doc_src docs

jupyter_cassini
---------------

The github repo for ``jupyter_cassini`` can be found `here <https://github.com/0Hughman0/jupyter_cassini>`_. Issues with the JupyterLab UI should be submitted here rather than the Cassini repo.

Get the repo contents with::

    git clone https://github.com/0Hughman0/jupyter_cassini

This comprises a jupyterlab extension called ``jupyter_cassini``, found in ``src``. This is written in TypeScript. It also features a small python package called ``jupyter_cassini_server``, found in the ``jupyter_cassini_server`` directory.

The jupyerlab extension bundling infrastructure allows us to bundle the jupyerlab extension into the server extension and install them at the same time.

Getting this stuff working is complex, thus, we rely heavily on the tooling created by the jupyerlab devs. More information on all this stuff can be found in their `official docs <https://jupyterlab.readthedocs.io/en/latest/extension/extension_dev.html>`_.

Dependencies and code isolation in jupyter_cassini are handled by `conda <https://docs.conda.io/en/latest/miniconda.html>`_.

To get started, create a new conda environment::

    conda create -n jupyter_cassini python=3.8

Activate it!::

    conda activate jupyter_cassini

Install ``jupyter_cassini_server`` in editable mode (this allows any changes to the server extension to be applied without reinstalling the extension)::

    cd jupyter_cassini
    pip install -e .[test]

The ``jupyter_cassini`` extension is written in TypeScript. This has to be built and transpiled into javascript. When you install ``jupyter_cassini_server``, this transpiled javascript is moved into the appropriate directory in you virtual environment, where it is accessed by jupyterlab.

This means if changes to the TypeScript code are made during development, we need these files to update for our changes to be reflected.

Running::

    jupyter labextension develop --overwrite .

Creates a symbolic link between your project directory and your virtual environment such that whenever you re-build the TypeScript code, your change will be reflected in JupyterLab - you just need to refresh the page!

Wew!...

Management of TypeScript is done using JupyterLab's bundled version of Yarn, which is ran using the command ``jlpm``.

To build ``jupyter_cassini`` run::

    jlpm build

Hopefully this should install any needed dependencies and build the extension.

You can check everything is working by navigating to the ``demo`` directory and running::

    cd demo
    python project.py

This should launch an instance of cassini with the version of the extension you just built!

Unit testing of TypeScript code is performed using jest. This can be ran using::

    jlpm test

From the top level directory.

Unit testing of python code is performed using pytest. This can be ran using::

    pytest

Integration tests are performed using playwright. These live in the ``ui-tests`` directory::

    cd ui-tests
    jlpm test

(You will likely need to perform some first-time setup of playwright).

Currently there is no linting or style enforcement for the Python-side code. This will probably eventually be changed to match Cassini.

TypeScript code is styled using ``prettier``. Which can be ran using::

    jlpm prettier

You can check for code-linting problems using::

    jlpm lint:check

As most users probably won't even know they're interacting with 2 python packages and a bunch of TypeScript code, the plan is to keep all the documentation in the Cassini repo - hence why you're reading this here!

None-the-less, docstrings should be provided to allow others (and you in a couple of months!) to make sense of your code.

Python Docstrings should use the `numpy standard <https://numpydoc.readthedocs.io/en/latest/format.html#docstring-standard>`_.

TypeScript docstrings should follow the `TypeDoc standard <https://typedoc.org/guides/tags/>`_

GitHub Repos/ Release Cycle
---------------------------

**It's not worth worrying about getting these bits right, if you have a new feature or fix, just submit the PR and we can work around any versioning issues**

We have a branch for each minor version e.g. 0.1.x and 0.2.x, the head of which should always be the latest patch of that minor release.

For development, we specify the whole planned version number, but add -pre for pre-release e.g. 0.2.4-pre.

We then create branches for implementing specific features, and submit PRs into those pre-release branches as progress is made.

If necessary, we publish a pre-release version, but within pyproject.toml will have to use the poetry spec:

https://python-poetry.org/docs/cli/#version

e.g. the version would be something like 0.2.4a0 for the first pre-release.

Once we are happy with the pre-release, it can be merged (via PR) into the appropriate minor version branch and the pre-release branch can be deleted.

Then we can publish the new minor version using the create-release feature.

To publish a release or pre-release we use the publish feature in GitHub. 

We create a new tag for that version, prepending with "v" e.g. `v1.2.3`, the tag should be on the branch, not on main.


