from typing import Optional, Any

from hypothesis.strategies import SearchStrategy, just
from hypothesis.strategies._internal.deferred import DeferredStrategy
from hypothesis.strategies._internal.utils import cacheable, defines_strategy


class ParamStrategyRegistry:
    _current_registry: Optional['ParamStrategyRegistry'] = None

    def __enter__(self) -> None:
        if not self.__class__._current_registry:
            self.__class__._current_registry = self
        else:
            raise RuntimeError("Cannot enter ParamStrategyRegistry more than once")

    def __exit__(self, *args, **kwargs) -> None:
        self.__class__._current_registry = None

    def __init__(self, kwargs: dict[str, Any], given_kwargs: dict[str, SearchStrategy[Any]]) -> None:
        self._strategies: dict[str, SearchStrategy[Any]] = {}
        self._register_param_values(kwargs, given_kwargs)

    def _register_param_value(self, name: str, strat: SearchStrategy[Any]) -> None:
        """Add a strategy under *name*, refusing duplicates."""
        if name in self._strategies:
            raise KeyError(f"Parameter {name!r} already registered")
        self._strategies[name] = strat

    def _register_param_values(self, kwargs: dict[str, Any], given_kwargs: dict[str, SearchStrategy[Any]]) -> None:
        maybe_strategies = {**given_kwargs, **kwargs}
        for name, strat in maybe_strategies.items():
            if not isinstance(strat, SearchStrategy):
                strat = just(strat)
            self._register_param_value(name, strat)

    @classmethod
    def get(cls, name: str) -> SearchStrategy[Any]:
        try:
            return cls._current_registry._strategies[name]
        except KeyError:
            raise RuntimeError(f"Strategy for parameter `{name}` has not been set up. Cannot resolve reference.")
        except AttributeError:
            raise RuntimeError(f"Cannot determine parameter value `{name}` outside of a hypothesis @given.")


class ParamStrategy(DeferredStrategy):
    def __init__(self, name: str):
        self._name = name
        super().__init__(lambda: ParamStrategyRegistry.get(self._name))



@cacheable
@defines_strategy(never_lazy=True)
def param(name: str) -> SearchStrategy[Any]:
    """Return a reference to a strategy by the name it will have as input into the test case.
    Resolution is deferred until the test is set up under @given.

    Example usage:
    >>> import hypothesis.strategies as st
    >>> x = st.param('a')
    >>> x.example()
    RuntimeError: Strategy for parameter `a` has not been set up. Cannot resolve reference.
    >>> from hypothesis import given, strategies as st
    >>> import pytest
    >>> @pytest.mark.parametrize('a', [1, 2, 3])
    ... @given(x=st.param('a'))
    ... def test_with_param(a):
    ...    assert a > 0
    """
    p = ParamStrategy(name)
    return p
