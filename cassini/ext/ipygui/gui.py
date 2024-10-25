from typing import Dict, TYPE_CHECKING, Type, Any

from IPython.display import display
from ipywidgets import Button, DOMWidget, HBox, SelectMultiple, Text

from .components import BaseTierGui, SearchWidget, widgetify_html, InputSequence

from cassini.defaults import Home, WorkPackage, Experiment, Sample, DataSet
from cassini.core import TierABC, TierGuiProtocol


class HomeGui(BaseTierGui[Home]):
    def _get_header_components(self) -> Dict[str, DOMWidget]:
        components = dict()
        components["Search"] = lambda: SearchWidget().as_widget()
        child = self.tier.child_cls
        if child:
            child_name = child.pretty_type
            components[f"{child_name}s"] = self._build_children
            components[f"New {child_name}"] = self.new_child

        return components


class ExperimentGui(BaseTierGui[Experiment]):
    def new_dataset(self) -> DOMWidget:
        """
        A handy widget for creating new `DataSets`.
        """
        samples = list(self.tier)
        option_map = {sample.name: sample for sample in samples}

        selection = SelectMultiple(options=option_map.keys(), description="Auto Add")

        def create(form, name, auto_add):
            with form.status:
                self.tier.setup_technique(name)
                if auto_add:
                    for sample in (option_map[name] for name in auto_add):
                        o = sample[name]
                        o.setup_files()
                        display(widgetify_html(o._repr_html_()))

        form = InputSequence(
            create, Text(description="Name:", placeholder="e.g. XRD"), selection
        )

        return form.as_widget()

    def _get_header_components(self) -> Dict[str, DOMWidget]:
        components = super()._get_header_components()
        components["New Data"] = self.new_dataset
        return components


class SampleGui(BaseTierGui[Sample]):
    def _build_children(self) -> DOMWidget:
        buttons = []
        for dataset in self.tier.datasets:
            b = Button(description=dataset.id)

            def make_callback(dataset):
                def open_folder(change):
                    dataset.open_folder()

                return open_folder

            b.on_click(make_callback(dataset))
            buttons.append(b)
        return HBox(tuple(buttons))

    def _get_header_components(self) -> Dict[str, DOMWidget]:
        components = super()._get_header_components()
        return components


GUIS: Dict[Any, Type[TierGuiProtocol]] = {  # Ideally would be Type[TierABC]
    Home: HomeGui,
    WorkPackage: BaseTierGui[WorkPackage],
    Experiment: ExperimentGui,
    Sample: SampleGui,
    DataSet: BaseTierGui[DataSet],
}
