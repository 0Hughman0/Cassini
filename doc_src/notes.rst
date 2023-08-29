======================
Slightly Helpful Notes
======================

Models
======

The data you want to represent has a model, particularly if this data is 'high level' i.e. represented in different parts of the application.

There are widgets that have a reference to this model and they represent the data within the model in some way.

The model is *Observable* so when things change, the widget should update to reflect this.

There is some guidance from the devs on how to implement the model:

https://jupyterlab.readthedocs.io/en/stable/developer/patterns.html#models

They want the model to be initialisable outside the widget and to also be possible to be null.

They also recommend having a modelChanged signal that widgets can emit when they host a new model!

Context
=======

A context is like a model but it is also associated with a file.

Layouts
=======

Laying out things is a bit of a nightmare.

It seems like BoxPanel is really only if you want to divide an area up into widgets, where some take up different proportions. Honestly looks a lot like flex display...

AccordianPanel only works if your widgets have a title attribute... which is readonly.

StackedPanel stacks them in the z direction!

Panel plus some css seems to be ok.

If you combine addWidget with node.appendChild, things generally seem to go badly...

I think actually, node.appendChild(widget.node) is not the done thing, and in-fact I should use Widget.attach(widget, node)... yes because according to

https://github.com/jupyterlab/lumino/blob/c90d19e7a4706c37c31961052206aa2a0d5144b9/packages/widgets/src/widget.ts#L1081

This otherwise fails to call onAttach and beforeAttach, which could do bad things with Widget lifecycle.

Architecture
============

For widgets that host other widgets or components that display content from their model, to keep general, these components should take data on a need to know basis. If these widgets need to make changes to the model, they should be provided with callbacks from the 'model host' that handle this for them.

Where models are comprised of other objects inside, these should be interfaced such that widgets that rely on that model don't access the model's children.
