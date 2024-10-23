# Extensions

Cassini would like to encourage the creation of new extensions to add functionality to user's projects.

!!!Note
    We are still working out how best to support extensions, so these things may change!

## Extending Projects

To add features to user's projects, we recommend developers create a single callable named `extend_project`. This should take a cassini project as the first argument, and should modify a `project` instance to add new functionality. Users then simply have to make a small change to their `cas_project.py`. 

For example the `cassini_lib` extension is used by:

```python
# cas_project.py
from cassini import Project, ...
from cassini.ext import cassini_lib

project = Project(...)

cassini_lib.extend_project(project)  # does the business

...
```

You can have additional arguments to the `extend_project` callable that configures the extension.

The kinds of things we might expect extensions to do is add new methods and attributes to Tier objects, just as `cassini_lib` does:

```python
def extend_project(project: Project):
    ...
    for Tier in project.hierarchy:
        if issubclass(Tier, NotebookTierBase):
            # patch in the requried attributes to classes with notebooks!
            Tier.cas_lib_version = MetaAttr(  # type: ignore[attr-defined]
                json_type=str,
                attr_type=Version,
                post_get=lambda v: Version(v) if v else v,
                pre_set=str,
                name="cas_lib_version",
                cas_field="private",
            )

            Tier.cas_lib = create_cas_lib(cas_lib_dir)  # type: ignore[attr-defined]
```

We are embracing some of the naughtier sides of Python to make this possible, so please do so in a careful and conscientious way!

## Hooking into Setup or Launch

As part of your extension, you may need to perform some initial setup.

To do so, you can use of `project.__before_setup_files__`, `project.__after_setup_files__`, `project.__before_launch__` or `project.__after_launch__`.

These are lists of callables that you can append you own setup code to, which are called in order as indicated. 

For example, the `cassini_lib` extension uses the `__before_setup_files__` hook to create the `cas_lib` directory:

```python
def extend_project(project: Project, cas_lib_dir: Union[str, Path] = "cas_lib"):
    """
    Extend project to add `cas_lib` attribute to Tiers.
    """
    cas_lib_dir = project.project_folder / cas_lib_dir

    def make_cas_lib_folder(project, cas_lib_dir=cas_lib_dir):
        if not cas_lib_dir.exists():
            cas_lib_dir.mkdir()
            (cas_lib_dir / "0.1.0").mkdir()

    project.__before_setup_files__.append(
        make_cas_lib_folder
    )  # ensures will run even if project already setup.
```

## Customizing the UI

Extensions could also inject their own `gui_cls` as described in [customisation](../customization.md).

For example the `cassini.ext.ipygui` extension adds the old `ipygui` to your project:

```python
from cassini.ext.gui import GUIS

def extend_project(project: "Project") -> "Project":
    """
    Extend `project` to use the IPython gui.
    """
    for Tier in project.hierarchy:
        gui_cls = GUIS.get(Tier, BaseTierGui)
        Tier.gui_cls = gui_cls

    return project
```

## Custom Hierarchies

An extension could also define a custom `HIERARCHY` that's an alternative to the `DEFAULT_TIERS`.

```python
# cas_project.py
from my_ext import CUSTOM_TIERS
from cassini import Project # DEFAULT_TIERS

project = Project(CUSTOM_TIERS, __file__)
...
```
