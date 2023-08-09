from .defaults.tiers import DEFAULT_TIERS
from .environment import Project, env
from .core import TierBase
from cassini.defaults.tiers import Home

try:
    __IPYTHON__  # type: ignore[name-defined]
    from .magics import register

    register()
except NameError:
    pass
