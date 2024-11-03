# User Guide

## Installation

Cassini is built into the Python and [JupyterLab](https://jupyterlab.readthedocs.io/) ecosystem. 

!!!Note
    Cassini is currently only compatible with JupyterLab version `4.x.x`. 

Python will need to be installed before you install Cassini. 

We recommend using the [`conda`](https://docs.conda.io/projects/conda/en/stable/user-guide/getting-started.html) package management system to install Python and create an isolated environment for you to run it in.

Once you've installed Python (and maybe activated your `conda` environment), check it's set up properly by running:

```bash
python --version
```

If you get a bunch of info about the current Python version, you're all good! If not, check the help guides for your Python installation.

Now you can install the `cassini` package:

```bash
pip install cassini
```

!!!Note
    Currently cassini is _not_ available directly on the conda package manager, thus in a conda environment, you must still use `pip` for installation.


You can check `cassini` successfully installed with:

```bash
pip show cassini
```

Which should produce a bunch of info about your installation, including its version number.

## A Cassini Project

In essence, Cassini is a directory structure which contains folders, jupyter notebooks and datasets.

!!!Tip
    As everything is just stored on-disk in regular files, Cassini plays well with cloud backup (although we recommend not having multiple people editing files simulataneously).

Cassini organises these into an ordered hierarchy, where each `Tier` on the hierarchy branches out into multiple `children`, creating a tree-like structure, which lives on your hard-disk.

The default hierarchy comprises `WorkPackages`, `Experiments`, `Samples` and `Datasets`.

On disk, such a project may look like:

```yaml
WorkPackages/: # (1)!
    - WP1.ipynb # (2)!
    - WP1/: # (3)!
        - WP1.1.ipynb # (4)!
        - WP1.1/: # (5)!
            - WP1.1a.ipynb # (6)!
            - WP1.1b.ipynb
            - A/: # (7)!
                - a/: # (8)!
                    - WP1.1a-A-first.csv 
                    - WP1.1a-A-second.csv
                - b/:
                    - WP1.1b-A-first.csv
        - WP1.2.ipynb # (9)!
        - WP1.2/:
            - WP1.2a.ipynb # (10)!
            - A/:
                - a/:
                    - WP1.2a-data.csv 
    - WP2.ipynb # (11)!
    - WP2/: # (12)!
        ... # (13)!
```

1. Folder where WorkPackages are stored.
2. Jupyter Notebook file for WorkPackage, `WP1`
3. Folder where WorkPackage `WP1`'s children are stored.
4. Experiment, `WP1.1`'s Jupyter Notebook.
5. Folder where Experiment `WP1.1`'s children are stored.
6. Sample, `WP1.1a`'s Jupyter Notebook.
7. Folder where DataSets of type `A` are stored.
8. Folder where DataSet `WP1.1a-A` is stored.
9. Experiment, `WP1.2`'s Jupyter Notebook.
10. Sample, `WP1.2a`'s Jupyter Notebook.
11. Jupyter Notebook file for WorkPackage, `WP2`
12. Folder where WorkPackage `WP2`'s children are stored.
13. Tree structure continues!


Within Python, Cassini defines objects that represent each branch on the tree.

Each branch on the tree has a unique name. Which follows a set naming convention:

```
              "WP4.2d-ABC"
                 | ||  |
Work Package id -+ ||  |
                   ||  |
  Experiment id ---+|  |
                    |  |
      Sample id ----+  |
                       |
     DataSet id -------+
```

!!!Note
    Through [customization](../customization.md), all these things can be configured. However, it can be a little complicated, so we recommend sticking to the defaults if you can.

Cassini understands this project structure and naming convention. 

Thus Cassini will help you build your project with this ordered structure, help you quickly navigate around it and retrieve any part of your project by name.

So let's get a project set up...

## Setup

### The `cas_project.py` file

We define our `project` in a `cas_project.py` file. `project` is a python object that contains all the information about your project and its configuration.

The simplest `cas_project.py` is:

```python
# cas_project.py
from cassini import Project, DEFAULT_TIERS

project = Project(
    hierarchy=DEFAULT_TIERS, # (1)!
    project_folder=__file__ # (2)!
) 

if __name__ == '__main__': # (3)!
    project.launch() # (4)!

```

1. This defines the `hierarchy` of your project. Cassini provides the `DEFAULT_TIERS` which are `[Home, WorkPackage, Experiment, Sample, DataSet]`.
2. This tells Cassini this project lives in the same directory as this file.
3. This allows us to to import `project` without launching it.
4. If this file is ran as a script, this launches JupyterLab with this `project` configured.

This configures a `project` object and launches it.

### Launching your project

Now you have defined your `cas_project.py`, you can then run:

    python cas_project.py

This will run `project.launch()`, which does a number of things:

1. Launch JupyterLab.
2. Add `project_folder` to the `%PYTHONPATH%`, allowing `cas_project.py` to be imported from anywhere.
3. Tell the Cassini JupyterLab extension, this is where to find your project, so you can manage it from within JupyterLab.

!!! Tip
    If for some reason, you cannot run `project.launch()`, for example you are using JupyterLab Desktop, you can explicitly add `project_folder` to the `%PYTHONPATH%`, and point the Cassini JupyterLab extension to your project by setting the environment variable `CASSINI_PROJECT=path/to/cas_project.py`.

Next learn how to populate your project with `WorkPackages`, `Experiments`, `Samples` and `DateSets`!

[Next](./creating-tiers.md){ .md-button }
