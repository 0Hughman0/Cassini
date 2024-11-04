# Customizing Cassini

## The Basics

Cassini is written to be customizable.

This is done by making changes to your ``cas_project.py`` file.

!!!Warning
    Whilst Cassini is written to be customisable, straying from the default configuration makes it more likely you will
    run into bugs or issues that may be harder to debug or get help on.

The main entrypoint for customisation is changing your hierarchy from the defaults.

For example, if you want to change your naming format, you can change [`WorkPackage.name_part_template`][cassini.core.TierABC]:

```python
from cassini import Home, WorkPackage, Experiment, Sample, DataSet

WorkPackage.name_part_template = 'HR{}'  # (1)!

project = Project([Home, WorkPackage, Experiment, Sample, DataSet], __file__)
...
```

1. This replaces the old `name_part_template`, which was `WP{}` with `HR{}`.

This will make your names start with `HR`, e.g. `HR1.5a`.

!!!Warning
    Be wary making changes _after_ your project is set up. e.g. if you are changing how things are named, old refrences will break.

## Creating New Tier Classes

You can define your own `Tier` classes from scratch, by inheriting from the base classes `FolderTierBase` or `NotebookTierBase`.

The `FolderTierBase` is for tier's with no notebook or meta, just a folder e.g. DataSets.

The `NotebookTierBase` is, as you'd expect, for tier's with a folder, notebook and meta.

Simply define your own ``Tier`` classes by either subclassing some of the defaults, or using
the base class ``TierBase``:

```python
from cassini import Project, Home, NotebookTierBase

class Part(NotebookTierBase):
    pretty_type = 'Part'  # (1)!
    name_part_template = 'Part: {}'  # (2)!


project = Project([Home, Part], __file__)

if __name__ == '__main__':
    project.launch()
```

1. This is like the full name of this tier.
2. With this template, `Part` will be named like `Part: 1`, this allows getting `parts` with `part = project['Part: 1']`.

Check out the [FolderTierBase][cassini.core.FolderTierBase] and [NotebookTierBase][cassini.core.NotebookTierBase] for information on all the different attributes you can overwrite to customise Cassini's behaviour. You can also look at the implementations of [the defaults][cassini.defaults.tiers] to see how this can be done.

## Naming Conventions

The naming system in Cassini is complex, to allow names to be as compact as possible, whilst still parseable!

The name of a tier is created by taking its `tier.id`, and inserting that into the `name_part_template`. This is done for each of its parents, prepending the resulting string until we reach the tier before Home.

For example:

```pycon
>>> dset = project['WP5.2c-ABC']
>>> dset.id
'ABC'
>>> dset.identifiers
('5', '2', 'c', 'ABC')
>>> dset.name_part_template
'-{}'
```

`dset` is a `DataSet` instance, which has `name_part_template="-{}"`, as `dset.id = 'ABC'`, this gets inserted into `-{}` resulting in `-ABC`.

```pycon
>>> smpl = dset.parent
>>> smpl.name
'WP5.2c'
>>> smpl.name_part_template
'{}'
```

Giving just the `'c'` character

```pycon
>>> exp = smpl.parent
>>> exp.name
'WP5.2'
>>> exp.name_part_template
'.{}'
```

Giving `'.2'`.

```pycon
>>> wp = wp.parent
>>> wp.name
'WP5'
>>> exp.name_part_template
'WP{}'
```

Giving `'WP5'`.

Hence the name has the form `'WP5' + '.2' + 'c' + '-ABC' = 'WP5.2c-ABC'`!

That's how names are build... but how are they parsed? e.g. Why aren't the Experiment id and Sample id lumped together?

The answer is we add a final class attribute, the `tier.id_regex`. This restricts the _form_ of the id. E.g. for WorkPackages and Experiments, the `id` must always be a digit. For Samples, the id mustn't start with a number or end in a dash and DataSets, id can actually be anything!

```python
>>> dset.id_regex # (1)!
'(.+)'
>>> smpl.id_regex # (2)!
'([^0-9^-][^-]*)'
>>> exp.id_regex # (3)!
'(\d+)'
>>> wp.id_regex # (4)!
'(\d+)'
```

1. Any character allowed.
2. Cannot start with a number and cannot include a dash `-`.
3. Must be a number.
4. Must be a number.

Through setting `name_part_template` and `id_regex`, it is possible to create your own naming convention.

## The Notebook Gui

To make changes to the gui, you can create you own gui class and then simply set the ``gui_cls`` attribute of your ``Tier``:

=== "Quick and Dirty"
    ```python
    from cassini import Home, WorkPackage, Experiment, Sample, DataSet
    from cassini.core import TierGuiProtocol # (1)!

    class MyGui(TierGuiProtocol):
        
        def __init__(self, tier):
            self.tier = tier

        def header(self):
            print(self.tier.name)

    WorkPackage.gui_cls = MyGui  # (2)!

    project = Project([Home, WorkPackage, Experiment, Sample, DataSet], __file__)
    ...
    ```
    
    1. The [TierGuiProtocol][cassini.core.TierGuiProtocol] helps enforce the right interface of the Gui class.
    2. A bit naughty.

=== "Classy"
    ```python 
    from cassini import Home, WorkPackage, Experiment, Sample, DataSet
    from cassini.core import TierGuiProtocol # (1)!

    class MyGui(TierGuiProtocol):
        
        def __init__(self, tier):
            self.tier = tier

        def header(self):
            print(self.tier.name)

    class MyWorkPackage(WorkPackage):  # (2)!
        gui_cls = MyGui

    project = Project([Home, MyWorkPackage, Experiment, Sample, DataSet], __file__)
    ...
    ```
    1. The [TierGuiProtocol][cassini.core.TierGuiProtocol] helps enforce the right interface of the Gui class.
    2. Bit more boilerplate.

Each ``Tier`` creates its own ``gui_cls`` instance upon ``__init__``, passing itself as the first argument.

```pycon
>>> WP1 = project['WP1']
>>> WP1.gui
<MyGui instance>
>>> mytier.gui.header()
WP1
```

## Meta Attributes (`MetaAttr`)

You may have noticed `smpl.description` and `smpl.started` are attributes, that are linked to the contents of the `smpl`'s meta file.

These also have strict types:

```python
>>> smpl = project['WP1.1a']
>>> smpl.description = 10
ValidationError: 1 validation error for WorkPackageMetaCache
description
  Input should be a valid string [type=string_type, input_value=3, input_type=int]
```

Including if you try to directly set on the meta:

```python
>>> smpl.meta['description'] = 10
ValidationError: 1 validation error for WorkPackageMetaCache
description
  Input should be a valid string [type=string_type, input_value=3, input_type=int]
```

These special stricter attributes, linked to the meta file are defined using `MetaAttr`, which are an example of a [descriptor](https://docs.python.org/3/howto/descriptor.html#primer).

```python
>>> smpl.__class__.description
<MetaAttr ...>
```

All the `MetaAttr` for a `Tier` are used to create a Pydantic model for the meta file:

```python
>>> smpl.meta_model.model_fields
{'started': FieldInfo(annotation=AwareDatetime, required=False, default=None, json_schema_extra={'x-cas-field': 'core'}),
 'description': FieldInfo(annotation=str, required=False, default=None, json_schema_extra={'x-cas-field': 'core'}),
 'conclusion': FieldInfo(annotation=str, required=False, default=None, json_schema_extra={'x-cas-field': 'core'})}
```

This model is then used by Cassini to ensure the meta file stays in a valid state. A schema of this model is shared with the browser-side JupyterLab extension to also perform validation.

You can add your own `MetaAttr` to `Tiers`, for example, the `cassini_lib` extension adds a `cas_lib_version` attribute:

```python
Tier.cas_lib_version = MetaAttr(
                json_type=str,  # (1)!
                attr_type=Version, # (2)!
                post_get=lambda v: Version(v) if v else v,  # (3)!
                pre_set=str,  # (4)!
                name="cas_lib_version",  # (5)!
                cas_field="private",  # (6)!
            )
```

1. The type passed to `pydantic`.
2. The type the attribute returns when accessed (this is mostly used to help with internal type checking). 
3. Function called _after_ the value is loaded from the `json` file.
4. Function called _before_ the value is inserted back into the `json` file.
5. The name/ key used for this attribute in the `json` file. (If none, this takes the same value as the attribute name).
6. Indicates this attribute should not be displayed to the user and is internal.


Whilst Pydantic provides its own methods for customising serialisation and deserialisation, these can be a bit confusing(!), we provide `post_get` and `pre_set` parameters, which are callables, which act on the values after they are fetched from the file (`post_get`) and before the attributes are set (`pre_set`). 

The final parameter `cas_field` is a custom parameter which tells Cassini who should see/ access this attribute. From above, you can see for 'core' meta values, such as description, these are set to `'core'`. If you don't want your MetaAttr to appear in the Cassini UI, you should set this to `'private'`. Otherwise `MetaAtt` will always be included in the Meta Editor, both in the New Child Dialogue and the Tier Viewer. The Cassini UI will enforce the same type constraints you set in `json_type` and will try and render the most appropriate widget for setting this value e.g. a calendar for a date.

You will notice that all meta values are optional, this is a requirement of Cassini.

You can find more information on [Meta][cassini.meta.Meta] and [MetaAttr][cassini.meta.MetaAttr] in the [meta api docs][cassini.meta].

## Extensions

If you've come up with a great set of customizations, you might want to turn them into [an extension](./extensions/development.md).

[Next](./extensions/development.md){ .md-button }
