Customizing Cassini
===================

Customizing Cassini's behaviour is simply done by making changes to your ``project.py`` file.

Simply define your own ``Tier`` classes by either subclassing some of the defaults, or using
the base class ``TierBase``::

    from cassini import TierBase, Project, Home


    class MyHome(Home):
        ...


    class TopTier(TierBase):
        ...

    project = Project([MyHome, TopTier], __file__)

    if __name__ == '__main__':
        project.setup_files()

Check out the API to see the methods and attributes that you might want to overload.

To make changes to the gui, create you own gui class and then simply set the ``gui_cls`` attribute of your ``Tier``::

    from cassini.ipygui import BaseGui

    class MyGui(BaseGui):
        ...

    Home.gui_cls = MyGui

    # or

    class MyTier(BaseTier):
        gui_cls = MyGui

Each ``Tier`` creates its own ``gui_cls`` instance upon ``__init__``, passing itself as the first argument.
