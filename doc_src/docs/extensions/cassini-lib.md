# Cassini Lib

### Installation and Setup

Cassini lib is bundled with cassini, but requires some additional dependencies (the Semantic Version package). These can be installed with:

```bash
pip install cassini[cassini_lib]
```

To add Cassini Lib to your project, modify your `cas_project.py`:

```
from cassini import Project, ...
from cassini.ext import cassini_lib

project = Project(...)

cassini_lib.extend_project(project)  # does the business

...
```

Now, relaunch Cassini:

```bash
python cas_project.py
```

You should now find a folder `cas_lib` in your projects directory, and within that a folder called `0.1.0`.

### Usage

Within this `cas_lib/0.1.0` folder, place python modules, including scripts or utilities you want to be available thoughout your project.

For example, you could add a hello world module:

```python
# cas_lib/0.1.0/hello_world.py
print("Hello world!")
```

To access these utilities, open a tier's notebook, and use the following:

```python
>>> smpl = project['WP1.1a']
>>> with smpl.cas_lib():
>>>     import hello_world
Set <Sample "WP1.1a">.cas_lib_version = 0.1.0
Hello world!
```

This did a number of things.

1. Checked if cas_lib() had been called before. Because it hadn't, found the folder with the highest [Semantic Version](https://semver.org/) in `cas_lib` i.e. '0.1.0'
2. Added this folder to `sys.path`.
3. Imported the module `hello_world` from that directory.
4. Removed the folder from `sys.path`.
5. Stored '0.1.0' in the smpl's meta-data, such that next time, `hello_world` will be imported from the same place.

You can check the `cas_lib_version` for a `tier` with:

```python
>>> smpl.cas_lib_version
Version('0.1.0')
```

Now, imagine we want to make a backwards incompatible change to `hello_world.py`. We can keep the old version in `cas_lib/0.1.0`, and create a new folder `cas_lib/0.2.0`, and put the new `hello_world.py` in there.

```python
# cas_lib/0.2.0/hello_world.py
print("Hello universe! 🌠")
```

The advantage of this is `WP1.1a` remembers that it uses `cas_lib/0.1.0/hello_world.py`, so even though we created this new version:

```python
>>> smpl = project['WP1.1a']
>>> with smpl.cas_lib():
>>>     import hello_world
Hello world!
```

But if we want to use the newer version in a new tier:

```python
>>> smpl = project['WP1.1b']
>>> with smpl.cas_lib():
>>>     import hello_world
Set <Sample "WP1.1a">.cas_lib_version = 0.2.0
Hello universe! 🌠
```

This is effortless and allows you to keep iterating on your tools, without breaking backwards compatibility with your older notebooks - lovely!

If you do decide you want `WP1.1a` to update to the newer version, you can force a particular import with:

```python
>>> smpl = project['WP1.1a']
>>> with smpl.cas_lib('0.2.0'):  # forces use of 0.2.0
>>>     import hello_world
Hello universe! 🌠
```

!!!Note
    This syntax does not overwrite `smpl.cas_lib_version` (which alternativelly you can do!).

`cassini_lib` uses [Semantic Versioning](https://semver.org) to find the highest compatible folder when importing, so, for example, you can make backwards compatible bug-fixes, and bump the final digit and `cassini_lib` will still find the modules.
