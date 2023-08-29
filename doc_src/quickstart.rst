Quickstart
==========

Installation
-----------

This can all be done via pip::

    pip install cassini

Note that this project is still in its alpha stage and so may be unstable.

Setup
-----

Cassini splits your work into 'Tiers', which form a project heirarchy.

By default, these tiers are ``Home``, ``WorkPackage``, ``Experiment``, ``Sample`` and  ``DataSet``.

So ``Home`` consists of a set of ``WorkPackage`` s, ``WorkPackage`` s consist of a set of ``Experiment`` s etc. etc.

To setup cassini we create a ``project.py`` file in the folder we want the project to live. In this we first import ``Project`` and the set of ``DEFAULT_TIERS``::

    # project.py
    from cassini import Project, DEFAULT_TIERS
    
We then create a ``project`` instance, telling it, these are the tiers in my project and this is where my project lives::
    
    project = Project(DEFAULT_TIERS, __file__)

We then use ``project.launch()`` to launch our cassini project, but we still want ``project`` to be importable without launching another instance, so we write::
    
    if __name__ == '__main__':
        project.launch()

To make use of the new JupyterLab gui, we add couple more lines, so the final ``project.py`` looks like::

    # project.py
    from cassini import Project, DEFAULT_TIERS
    from cassini import jlgui

    project = Project(DEFAULT_TIERS, __file__)
    jlgui.extend_project(project)  # this will inject the new gui_cls

    if __name__ == '__main__':
        project.launch()
    
With these changes, you can then run::

    python project.py

From your terminal, which will launch jupyterlab and cassini.

To open the cassini browser, open the launcher and scroll down to the bottom and select Browser under the Cassini heading.

You can then create your first WorkPackage by clicking the little plus button in the empty table.

Notebook templates can be found in the templates folder that's created in the same directory as your ``project.py``.

What Next
---------

To look at other features, head to :doc:`features`.