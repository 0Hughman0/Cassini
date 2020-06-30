Features
=================

Templating
----------

Often you may find yourself repeating the same protocol over multiple samples, tweaking and recording various parameters
and producing various outputs. To help streamline this process Cassini supports Jinja2 templating of ``.ipynb`` files.

Simply navigate to your project's template folder::

    project.template_folder
    Path('.../my_project_home/templates')

In here you'll find the basic default templates for each ``Tier``. This can be tweaked as you please, or you can create
your own. Cassini passes the new ``Tier`` to the template as ``tier``.

For example if I made a template, ``templates/Sample/simple.tmplt.txt``::

    This tier object's name is: {{ tier.name }}

Cassini fills it in::

    >>> sample = project['WP1.2c']
    >>> sample.render_template('Sample/simple.tmplt.txt')
    "This tier object's name is: WP1.2c"

For more info on using Jinja2 templates see their documentation.

Your templates will be visible in the Cassini gui for easy use, or you can pass them to ``setup_files`` if you're
calling that directly.

.. image:: _static/templating.png

Highlights
----------

Often the outcome of some lab work can be summarised with a few results.

Cassini provides the ``%%hlt`` magic that automatically saves the output of a cell as a highlight.

The highlight can also be titled and captioned::

    In [1]: %%hlt My Title
       ...: x = np.linspace(0, 10)
       ...: plt.plot(x, x * x)
       ...: """
       ...: A caption for WP2.1c
       ...: """

The output can then be retrieved elsewhere, without re-running the cell::

    In [1]: sample = project['WP2.1c']
    In [2]: sample.display_highlights()

.. image:: _static/Highlights.PNG

It's also automatically added to the that ``Tier``'s highlights widget.


Tier Meta data
--------------

Easily store and retrieve arbitrary meta data for any WorkPackage, Experiment or Sample to be shared with other programs,
or just for reference.

Each ``Tier`` object (except ``DataSets``) has a meta attribute::

    >>> sample = project['WP2.1c']
    >>> sample.meta
    {'description': 'an experiment', 'started': '17/06/2020'}

This is just the contents of a ``.json`` file found on your disk::

    >>> sample.meta.file # physically stored on disk
    Path('.../WP2.1c.json')

We can arbitrarily add attributes to ``meta``::

    >>> sample.meta.temperature = 100
    >>> sample.meta
    {'description': 'an experiment', 'started': '17/06/2020', 'temperature': 100}

These are permanently written to the ``.json`` file::

    >>> sample.meta.file.read_text()  # changes applied to json
    '{"description": "an experiment", "started": "17/06/2020", "temperature": 100}

Meaning they can be retrieved later.

Paths
-----

Work with files and folders intuitively using functionality based on ``pathlib``.

Every ``Tier`` object has a folder::

    >>> sample = project['WP2.1c']
    >>> sample.folder
    Path('.../WP2.1/')

Which we can find paths relative to with ease::

    >>> sample / 'diagram.png'
    Path('.../WP2.1/diagram.png')

Additionally, iterating over a ``DataSets`` is equivalent to using ``os.scandir``::

    >>> raman_dataset = sample['Raman']
    >>> for entry in raman_dataset:
    ...     print(data)
    DirEntry('.../WP2.1/Raman/c/data1.txt')
    DirEntry('.../WP2.1/Raman/c/data2.txt')

Exploring Work
--------------

Each ``Tier`` has a ``children_df()`` method which automatically generates a DataFrames with each child, including
custom metadata, allowing you to quickly query your work::

    >>> wp = project['WP2.1']
    >>> wp.children_df().query("'temperature' > 90")

The ``wp.gui.children_df()`` provides clickable links to these ``Tiers``.



