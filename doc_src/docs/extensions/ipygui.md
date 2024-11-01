# Legacy IPyGui 

The old `0.1.x` IPython widgets-based UI has been superseeded by the JupyterLab UI. This has been converted into an extension, which you can find in `cassini.ext.ipygui`.

You can use it by adding:

```python
...
from cassini.ext import ipygui
...
ipygui.extend_project(project)
```

to your `cas_project.py`.

You will also need to install its optional dependencies with:

```
pip install cassini[ipygui]
```

This UI is deprecated. Unlike the Jupyter Lab UI, it might be compatible with Jupyter Notebook. It also serves as an example for how to write an extension that implements a custom UI.
