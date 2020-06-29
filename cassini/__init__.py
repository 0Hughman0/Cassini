from .defaults.tiers import DEFAULT_TIERS
from .environment import Project
from .core import TierBase
from cassini.defaults.tiers import Home

try:
    __IPYTHON__
    from .magics import register
    register()
except NameError:
    pass
