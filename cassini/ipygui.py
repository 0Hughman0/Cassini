import html

from typing import Any, Callable, Dict, Union, List, Mapping, Hashable, TYPE_CHECKING

import pandas as pd
import pandas.api.types as pd_types

from ipywidgets import Select, VBox, Button, Output, Text, Textarea, HBox, Layout, Accordion, DOMWidget # type: ignore[import]
from IPython.display import display, Markdown, publish_display_data

from .environment import env

if TYPE_CHECKING:
    from .core import TierBase




class WHTML:
    """
    Magic class that takes html text and creates an object that is rendered with that text.

    `ipywidget.HTML` widgets do not get their links XSRF protected, but `obj._repr_html_` does!

    Warnings
    --------
    This HTML is not escaped, so could do bad stuff!
    """

    def __init__(self, html: str):
        self.html = html

    def _repr_html_(self):
        return self.html


def widgetify(obj: Any) -> Output:
    """
    Allows any object to be treated like an `ipywidget` so it can be used in `ipywidget` layouts - handy!
    """
    output = Output(height='auto', width='auto')
    with output:
        display(obj)
    return output


def widgetify_html(html: str) -> Output:
    """
    Required for html which has links rather than ipywidgets HTML widget.

    Parameters
    ----------
    html: str
        HTML to render

    Returns
    -------
    Output widget containing the HTML
    """
    return widgetify(WHTML(html))


class UnescapedDataFrame(pd.DataFrame):
    """
    Subclass of `pd.DataFrame` that slightly dangerously does not escape any html in its `self._repr_html_` method.

    Warnings
    --------
    This class deliberately does not escape HTML for objects it contains. This means you need to trust these objects.
    """

    @staticmethod
    def try_html_repr(obj: object) -> str:
        """
        Get text form of obj, first try `obj._repr_html_`, fallback on `str(obj)`.

        Warnings
        --------
        This method does not escape `obj._repr_html_`. So make sure your reprs are trustworthy!
        """
        if hasattr(obj, '_repr_html_'):
            return obj._repr_html_()
        return html.escape(str(obj))

    @property
    def _constructor(self):
        return UnescapedDataFrame

    def _repr_html_(self) -> str:
        formatters: Mapping[Hashable, Callable[[object], str]] = {name: self.try_html_repr
                      for name, dtype in self.dtypes.items() if pd_types.is_object_dtype(dtype)}
        return self.to_html(escape=False, formatters=formatters)


class InputSequence:
    """
    Helper class for creating 'input sequences' i.e. a sequency of widgets that you fill in, and then click confirm.

    Parameters
    ----------
    done_action : callable
        function to call when confirm is clicked. Each child (see next parameter!) is passed to done_action
    *children : ipywidget
        widgets to display in order. When confirm clicked, these widget objects are passed to done_action.
    """

    stored_traits = ['value', 'disabled']

    def __init__(self, done_action: Callable, *children: DOMWidget):
        self.done_action = done_action
        self.children = children
        self.initial_traits = {}

        self.confirm = Button(description="Confirm", disabled=True)
        self.new = Button(description="New")
        self.status = Output()

        self.output = Output(layout=Layout(width='auto'))

        self.confirm.on_click(self._do_done)
        self.new.on_click(self.reset)

        for child in self.children:
            child.layout.width = 'auto'
            child.style.description_width = '10%'
            self.initial_traits[child] = {k: v for k, v in child.get_state().items() if k in self.stored_traits}
            child.observe(self.child_updated, 'value')

    def reset(self, change):
        """
        Reset the state of the InputSequence. Called when `new` button clicked.
        """
        for child in self.children:
            child.open()
            traits = self.initial_traits[child]
            for k, v in traits.items():
                setattr(child, k, v)

        self.confirm.disabled = True

    def child_updated(self, change):
        """
        Called when a child is updated, meant to stop you pressing confirm until you've entered something into every
        widget... don't think it actually works tho!
        """
        if all(map(lambda val: val is not None, self.children)):
            self.confirm.disabled = False

    def as_widget(self) -> DOMWidget:
        """
        Build `self` into `ipywidget`

        Returns
        -------
        widget : DOMWidget
            widget form of self.
        """
        return VBox((*self.children, HBox((self.confirm, self.new)), self.status))

    def display(self):
        """
        Displays `self.as_widget()`.

        Returns
        -------
        output : Output
            output widget which we displayed into...
        """
        self.output.append_display_data(self.as_widget())
        return self.output

    def _do_done(self, pressed):
        """
        Internal function called when confirm clicked.
        """
        values = []

        self.confirm.disabled = True

        for child in self.children:
            child.disabled = True
            values.append(child.value)

        with self.output:
            self.done_action(*values)


class SearchWidget:

    def __init__(self):
        self.search = Text(placeholder='Name')
        self.go_btn = Button(description='Search')
        self.clear_btn = Button(description='Clear')
        self.out = Output()

        self.search.continuous_update = False
        self.search.observe(self.do_search, 'value')
        self.go_btn.on_click(self.do_search)
        self.clear_btn.on_click(self.do_clear)

    def do_clear(self, cb):
        self.out.clear_output()

    def do_search(self, cb):
        name = self.search.value

        self.out.clear_output()

        with self.out:
            obj = env.project[name]
            if obj.exists():
                display(obj.gui.header())
            else:
                print(f"{obj.name} valid, but doesn't exist")

    def as_widget(self):
        return VBox([HBox([self.search, self.go_btn, self.clear_btn]), self.out])


class BaseTierGui:
    """
    Mixin to provide nice notebook outputs for Jupyter Notebooks.
    """
    def __init__(self, tier: 'TierBase'):
        self.tier = tier

    def _get_header_components(self) -> Dict[str, Callable[[], DOMWidget]]:
        """
        Creates the dictionary that forms the components of the header.

        Returns
        -------
        components : dict
            Dictionary of callables in form (key: value) = (header, callable), where the callable creates a returns a
            widget.

        Notes
        -----
        The order of the elements dictates what order they're rendered so insert them in the order you want!

        Overload this method to customise the appearance of your `Tier` header.
        """
        components: Dict[str, Callable[[], Any]] = dict()
        components['Description'] = self._build_description
        components['Highlights'] = self._build_highlights_accordion
        components['Conclusion'] = self._build_conclusion

        child = self.tier.child_cls
        if child:
            child_name = child.pretty_type
            components[f'{child_name}s'] = self._build_children
            components[f'New {child_name}'] = self.new_child

        return components

    def _build_header_title(self, *, parent=None) -> DOMWidget:
        """
        Creates a widget that displays the title a `Tier` along side clickable links and buttons to its components
        """
        open_btn = Button(description="Folder")
        open_btn.on_click(lambda cb: self.tier.open_folder())
        title = f'<h1 style="display: inline;"><a href="{self.tier.href}">{self.tier.name}</a></h1>'
        parts = []
        parent = self.tier.parent
        while parent:
            parts.append(f'<a href="{parent.href}" target="_blank">{parent.name}</a>')
            parent = parent.parent

        text = title + '<h3 style="display: inline;">'

        if parts:
            text += f"({'->'.join(parts[::-1])})"

        text += '</h3>'
        return VBox((widgetify_html(text), open_btn))

    def _build_description(self, *, parent=None) -> Union[DOMWidget, None]:
        """
        Creates a widget that displays the motivation for a `Tier`.
        """
        description = self.tier.description
        if not description:
            return None
        return widgetify(Markdown(description))

    def _build_highlights_accordion(self, *, parent=None) -> Union[DOMWidget, None]:
        """
        Creates a widget that displays highlights for this `Tier` in an `ipywidgets.Accordion` - which is nice!
        """
        highlights = self.tier.get_highlights()

        if not highlights:
            return None

        widget = Accordion()

        for i, (name, highlight) in enumerate(highlights.items()):
            out = Output()
            widget.children = (*widget.children, out)
            with out:
                for item in highlight:
                    publish_display_data(**item)
            widget.set_title(i, name)
        widget.selected_index = None
        return widget

    def _build_conclusion(self, *, parent=None) -> Union[DOMWidget, None]:
        """
        Build widget to display conclusion of this `Tier` object.
        """
        conclusion = self.tier.conclusion
        if not conclusion:
            return None
        return widgetify(Markdown(self.tier.conclusion))

    def _build_children(self, *, parent=None) -> DOMWidget:
        """
        Build a widget to display an `UnescapedDataFrame` containing this `Tier`'s children.
        """
        children_df = self.children_df()
        return widgetify(children_df)

    def header(self, *, include: Union[List[str], None] = None, exclude: Union[List[str], None] = None) -> DOMWidget:
        """
        Builds header widget from its components.

        Parameters
        ----------
        include : Sequence[str]
            names of components to render in header widget.
        exclude : Sequence[str]
            names of components not to render in header widget.

        Notes
        -----
        Parameters include and exclude are mutually exclusive.

        Returns
        -------
        header : DOMWidget
            Widget that can be displayed containing all the components of this `Tier`'s header.
        """
        if include and exclude:
            raise ValueError("Only one of include or exclude can be provided")

        component_makers = self._get_header_components()

        if include:
            component_makers = {k: v for k, v in component_makers.items() if k in include}

        if exclude:
            component_makers = {k: v for k, v in component_makers.items() if k not in exclude}

        components = [self._build_header_title()]

        for name, component_builder in component_makers.items():
            component = component_builder()
            if component:
                components.append(widgetify_html(f'<h3>{name}</h3>'))
                components.append(component)

        return VBox(components)

    def display_highlights(self):
        """
        Display an `ipywidgets.Accordian` with this `Tier`'s highlights.
        """
        return display(self._build_highlights_accordion())

    def children_df(self, *, include: Union[List[str], None] = None, exclude: Union[List[str], None] = None) -> Union[UnescapedDataFrame, None]:
        """
        Calls `tier.children_df` but returns an `UnescapedDataFrame` instead.
        """
        return UnescapedDataFrame(self.tier.children_df(include=include, exclude=exclude))

    def new_child(self, *, parent=None) -> DOMWidget:
        """
        Widget for creating new child for this `Tier`.
        """
        child = self.tier.child_cls

        if not child:
            return
        
        options = child.get_templates()

        mapping = {path.name: path for path in options}

        selection = Select(
            options=mapping.keys(),
            description='Template')

        def create(name, template, description):
            with form.status:
                obj = child(*self.tier.identifiers, name)
                obj.setup_files(mapping[template])
                obj.description = description
                display(widgetify_html(obj._repr_html_()))
            parent.update('Children')

        form = InputSequence(create,
                             Text(description=f'Identifier', placeholder=f'{child.id_regex}'),
                             selection,
                             Textarea(description='Motivation'))

        return form.as_widget()
