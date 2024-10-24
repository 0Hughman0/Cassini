# jupyter_cassini

## Getting Set Up

The github repo for ``jupyter_cassini`` can be found [here](https://github.com/0Hughman0/jupyter_cassini). Issues with the JupyterLab UI should be submitted here rather than the Cassini repo.

Get the repo contents with:

    git clone https://github.com/0Hughman0/jupyter_cassini

This comprises a jupyterlab extension called ``jupyter_cassini``, found in ``src``. This is written in TypeScript. It also features a small python package called ``jupyter_cassini_server``, found in the ``jupyter_cassini_server`` directory.

The jupyerlab extension bundling infrastructure allows us to bundle the jupyerlab extension into the server extension and install them at the same time.

Getting this stuff working is complex, thus, we rely heavily on the tooling created by the jupyerlab devs. More information on all this stuff can be found in their [official docs](https://jupyterlab.readthedocs.io/en/latest/extension/extension_dev.html)

Dependencies and code isolation in jupyter_cassini are handled by [conda](https://docs.conda.io/en/latest/miniconda.html).

To get started, create a new conda environment:

    conda create -n jupyter_cassini python=3.8

Activate it!:

    conda activate jupyter_cassini

Install ``jupyter_cassini_server`` in editable mode (this allows any changes to the server extension to be applied without reinstalling the extension):

    cd jupyter_cassini
    pip install -e .[test]

The ``jupyter_cassini`` extension is written in TypeScript. This has to be built and transpiled into javascript. When you install ``jupyter_cassini_server``, this transpiled javascript is moved into the appropriate directory in you virtual environment, where it is accessed by jupyterlab.

This means if changes to the TypeScript code are made during development, we need these files to update for our changes to be reflected.

Running:

    jupyter labextension develop --overwrite .

Creates a symbolic link between your project directory and your virtual environment such that whenever you re-build the TypeScript code, your change will be reflected in JupyterLab - you just need to refresh the page!

Wew!...

Management of TypeScript is done using JupyterLab's bundled version of Yarn, which is ran using the command ``jlpm``.

To build ``jupyter_cassini`` run:

    jlpm build

Hopefully this should install any needed dependencies and build the extension.

You can check everything is working by navigating to the ``demo`` directory and running:

    cd demo
    python project.py

This should launch an instance of cassini with the version of the extension you just built!

Unit testing of TypeScript code is performed using jest. This can be ran using:

    jlpm test

From the top level directory.

Unit testing of python code is performed using pytest. This can be ran using:

    pytest

Integration tests are performed using playwright. These live in the ``ui-tests`` directory:

    cd ui-tests
    jlpm test

(You will likely need to perform some first-time setup of playwright).

Currently there is no linting or style enforcement for the Python-side code. This will probably eventually be changed to match Cassini.

TypeScript code is styled using ``prettier``. Which can be ran using:

    jlpm prettier

You can check for code-linting problems using:

    jlpm lint:check

As most users probably won't even know they're interacting with 2 python packages and a bunch of TypeScript code, the plan is to keep all the documentation in the Cassini repo - hence why you're reading this here!

None-the-less, docstrings should be provided to allow others (and you in a couple of months!) to make sense of your code.

Python Docstrings should use the [numpy standard](https://numpydoc.readthedocs.io/en/latest/format.html#docstring-standard>).

TypeScript docstrings should follow the [TypeDoc standard](https://typedoc.org/guides/tags/)

## Design Principles

### Models and Events

The UI represents objects to be displayed in the application with `Models`. Examples of models are the `NotebookTierModel` and the `TierBrowserModel`.

High level widgets then take a model and represent it, or parts of it.

If the model changes, the widgets that represent it should update.

Models should have _one_ `changed` property, which is a signal which is emitted when the contents of the model change. The payload of the signal should describe what has changed. This allows Widgets to have only one method to handle changes to the model. This should be called `handleModelChanged`.

Widgets which possess models are able to modify them. Naturally, any changes should cause `model.changed` to be emited so any other widgets which represent this model can update accordingly.

Widgets which possess models may have child widgets. If these widgets are not specialised to that type of model, they should not take that model. Instead, it is the responsiblity of the parent widget to modify the child widget appropriately when the model changes. Furthermore, if the child model wants to trigger a change to the model of its parent, this should be achieved by handing a callback to the child widget. 

To prevent needing to re-render widgets from scratch, widgets should be able to handle the model being set to a new value. When this happens, the widget should have a single handler called `handleNewModel` which handles this change. Ideally, widgets should be able to handle the model being set to `null`. When you handle new models coming in, you **must** remember to disconnect any signals from the old model and the widget. This can be done with `Signal.disconnectBetween(oldModel, this)`, for example.

### React Components

React components can be used. Ideally these should be function components. React widgets should have as little state as possible, these should only be used for things that are purely internal to the rendering of the widget, for example, column ordering.

Generally React components should not take models as props.

React components will need to be wrapped in Lumino ReactWidgets. These should act as a go-between for the model and the React Component. They should provide handlers that can update the model, and render() should provide the appropriate properties of the model to pass to the React Component as props.
