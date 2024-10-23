# Contributing

Contributions to Cassini are incredibly welcome. This includes reporting bugs, making suggestions all the way to implementing whole new features.

The [issues section](https://github.com/0Hughman0/Cassini/issues) is the best place to start, this is where to submit bug reports and discuss new feature ideas.

If you find something you'd really like to contribute, but don't know how, don't hesitate to ask of help or suggestions on how best to approach problems.

At the moment a few priorities for the project are:
        
3. **Discussing new feature ideas** - The project is young and its not clear who will use it and for what. If you wish it did xyz, start a discussion - there's a good chance others would like that feature too.
    
4. **Implementing new features** - There is no shortage of new features in the [issues section](https://github.com/0Hughman0/Cassini/issues) but someone needs to write the code! 

No need to ask for permission to get started... just fork the repo, have a go at making some improvements and [submit a pull request](https://github.com/0Hughman0/Cassini/pulls) once you are happy for someone to take a look at it.

We run some CI tools to help streamline things. This includes running the test suite, linting, checking formatting and checking test coverage.

As test coverage is a big issue at the moment, please make sure your PR *increases* the test coverage!


## Codebase Orientation


Cassini is currently split into two packages:

1. [Cassini](https://github.com/0Hughman0/Cassini) - This provides the Python side code, including defining the structure of projects and providing a few magic methods.
2. [jupyter_cassini](https://github.com/0Hughman0/jupyter_cassini) - This provides a UI for the Python side via a JupyterLab extension. This package also includes a JupyterLab server extension that serves up data from a cassini project allowing it to be used by the UI.

Both packages use semantic versioning. The plan is to maybe keep both packages separate and to have the rule that compatible versions of cassini and the UI will have matching MAJOR versions. So both will be bumped in sync.

Why is it split into two? At some point in the future it may be possible to port the cassini codebase into other languages within the Jupyter remit e.g. Julia. By separating the UI code from the client-side code, it should be possible to make the UI universally compatible with any language.


## GitHub Repos/ Release Cycle


**It's not worth worrying about getting these bits right, if you have a new feature or fix, just submit the PR and we can work around any versioning issues**

We have a branch for each minor version e.g. 0.1.x and 0.2.x, the head of which should always be the latest patch of that minor release.

For development, we specify the whole planned version number, but add -pre for pre-release e.g. 0.2.4-pre.

We then create branches for implementing specific features, and submit PRs into those pre-release branches as progress is made.

If necessary, we publish a pre-release version, but within pyproject.toml will have to use the poetry spec:

https://python-poetry.org/docs/cli/#version

e.g. the version would be something like 0.2.4a0 for the first pre-release.

Once we are happy with the pre-release, it can be merged (via PR) into the appropriate minor version branch and the pre-release branch can be deleted.

Then we can publish the new minor version using the create-release feature.

To publish a release or pre-release we use the publish feature in GitHub. 

We create a new tag for that version, prepending with "v" e.g. `v1.2.3`, the tag should be on the branch, not on main.


