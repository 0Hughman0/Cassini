Quickstart
==========

1. Install with ``pip``::

    pip install cassini


2. Navigate to the directory you wish to create your project, make a ``project.py``::


    from cassini import Project, DEFAULT_HIERARCHY

    project = Project(DEFAULT_HIERARCHY, __file__)

    if __name__ == '__main__':
        project.setup_files()

3. Run ``python project.py`` - this will setup the files for your project.
4. Make ```project.py`` importable within your project - easiest way is to add the current directory to the ``PYTHON_PATH`` environment variable e.g.
   with ``set PYTHON_PATH=%CD%``.
5. Run jupyter lab using ``jupyter lab --notebook-dir="%CD%"``

Once your browser window opens, navigate to ``Home.ipynb``, run the top cell and from there you can create your project.