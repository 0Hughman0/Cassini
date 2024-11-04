# Sharing Cassini Notebooks

You may find that you need to share a notebook with a collegue. Unless they have an identical file system to you, without making a number of changes to the notebook, they will not be able to run the notebook as-is.

To help make this easier, in version `0.3.0`, Cassini provides the `cassini.sharing` module, which includes the `ShareableProject` class.

!!!Warning
    This feature is both new and complex. Whilst it's unit-tested, it is not yet field tested, so you may encounter bugs and issues. Please report them, so we can iron them out!

To share a notebook, you need to make a small number of changes at the top of the file.

Imagine your notebook starts with:

```python
from cas_project import project

smpl = project.env('WP1.1a')
smpl.gui.header()
```

To share it, make the substitution of `project` for a `ShareableProject` instance:

```python
# from cas_project import project
from cassini.sharing import SharableProject

project = ShareableProject()
smpl = project.env('WP1.1a')
smpl.gui.header()
```

When you re-run this cell, you should see nothing changes! What has happened behind the scences is Cassini has wrapped `smpl` with a `SharingTier`:

```pycon
>>> smpl
<SharingTier>
>>> smpl._tier
<Sample 'WP1.1a'>
```

This object passes all calls back to the original wrapped `smpl` object, but it keeps track of them, as you go along.

```pycon
>>> smpl / 'a path.csv'
<NoseyPath (...\WorkPackages\WP2\a path.csv)>
>>> smpl._called['__truediv__']
{(('data.csv',),
  ()): WindowsPath('.../WorkPackages/WP2/a path.csv')}
```

So proceede to re-run every cell in your notebook. 

Once you've ran through your whole notebook, to get it ready for sharing, you need to run the line:

```pycon
>>> project.make_shared()
Creating shared directory: Shared
Success
Making Requires directory
Success
Creating shared version of WP1.1a
Copying Meta
Success
Freezing attributes/ calls
Success
Making a copy of required files
```

This creates a new subdirectory called `Shared`. In that, Cassini will create a `Required` folder, which Cassini will fill with all the files you accessed throughout the notebook.

In `Shared` it will also create a directory called `WP1.1a`, within which, Cassini will place a copy of `WP1.1a`'s meta and a cache of the result of any calls and attribute accesses.

To share your notebook. Send it alongside the `Shared` folder, and ensure your collegue also has Cassini installed.

When they come to run the notebook, Cassini will recognise it is in a `Shared` environment, and will divert all calls, attribute access and path access to the accompanying `Shared` folder, meaning your colleague can re-run your notebook as-is without copying over any other files.
