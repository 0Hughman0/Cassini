# Cassini

A virtual lab-book, using Jupyter Lab and Python. 

Cassini's goal is to help you explore, analyse and organise your data.

![Screenshot](demo.gif)

## Features

* Structures your project into an easy to navigate hierarchy of workpackages, experiments, samples and datasets.
* Allows retrieval of data by name e.g. `project['WP3.2f-XRD'] / 'XRD_data.csv`.
* Create new sample, experiment (etc.) notebooks through custom dialogs.
* Create notebook templates for standardised proceedures.
* Browse and explore your project through a custom browser, including previewing cell outputs in-browser.

Check out the demo/walkthrough binder:

[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/0Hughman0/Cassini/HEAD?urlpath=lab/tree/Home.ipynb)

## Installation and Setup

    > pip install cassini

Create a `project.py`:

    # project.py
    from cassini import Project, DEFAULT_TIERS
    from cassini import jlgui

    project = Project(DEFAULT_TIERS, __file__)
    jlgui.extend_project(project)

    if __name__ == '__main__':
        project.launch()

And launch it:

    > python project.py

Head to [Quickstart](https://0hughman0.github.io/Cassini/latest/quickstart.html) for more info.
