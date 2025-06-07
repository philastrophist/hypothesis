import functools
import inspect
from abc import abstractmethod
from typing import Any, Callable, TypeVar, Union, Generic, TYPE_CHECKING

from hypothesis.internal.reflection import proxies

if TYPE_CHECKING:
    from hypothesis.strategies import SearchStrategy

#
# class ParamStrategyRegistry:
#     _current_registry: Optional['ParamStrategyRegistry'] = None
#
#     def __enter__(self) -> 'ParamStrategyRegistry':
#         if not self.__class__._current_registry:
#             self.__class__._current_registry = self
#         else:
#             raise RuntimeError("Cannot enter ParamStrategyRegistry more than once")
#         return self
#
#     def __exit__(self, *args, **kwargs) -> None:
#         self.__class__._current_registry = None
#
#     def __init__(self, kwargs: dict[str, Any], given_kwargs: dict[str, SearchStrategy[Any]]) -> None:
#         self._strategies: dict[str, SearchStrategy[Any]] = {}
#         self._register_param_values(kwargs, given_kwargs)
#
#     def _register_param_value(self, name: str, strat: SearchStrategy[Any]) -> None:
#         """Add a strategy under *name*, refusing duplicates."""
#         if name in self._strategies:
#             raise KeyError(f"Parameter {name!r} already registered")
#         self._strategies[name] = strat
#
#     def _register_param_values(self, kwargs: dict[str, Any], given_kwargs: dict[str, SearchStrategy[Any]]) -> None:
#         maybe_strategies = {**given_kwargs, **kwargs}
#         for name, strat in maybe_strategies.items():
#             if not isinstance(strat, SearchStrategy):
#                 strat = just(strat)
#             self._register_param_value(name, strat)
#
#     @classmethod
#     def get(cls, name: str) -> SearchStrategy[Any]:
#         try:
#             return cls._current_registry._strategies[name]
#         except KeyError:
#             raise RuntimeError(f"Strategy for parameter `{name}` has not been set up. Cannot resolve reference.")
#         except AttributeError:
#             raise RuntimeError(f"Cannot determine parameter value `{name}` outside of a hypothesis @given.")
#
#
# class ParamStrategy(DeferredStrategy):
#     def __init__(self, name: str):
#         self._name = name
#         super().__init__(lambda: ParamStrategyRegistry.get(self._name), cache=False)
#
#     def __repr__(self) -> str:
#         try:
#             return f"{self.__class__.__name__}({repr(self.wrapped_strategy)})"
#         except RuntimeError:
#             return f"{self.__class__.__name__}(deferred@{self._name})"
#
#
# @defines_strategy(never_lazy=True)
# def param(name: str) -> SearchStrategy[Any]:
#     """Return a reference to a strategy by the name it will have as input into the test case.
#     Resolution is deferred until the test is set up under @given.
#
#     Example usage:
#     >>> import hypothesis.strategies as st
#     >>> x = st.param('a')
#     >>> x.example()
#     RuntimeError: Strategy for parameter `a` has not been set up. Cannot resolve reference.
#     >>> from hypothesis import given, strategies as st
#     >>> import pytest
#     >>> @pytest.mark.parametrize('a', [1, 2, 3])
#     ... @given(x=st.param('a'))
#     ... def test_with_param(a):
#     ...    assert a > 0
#     """
#     p = ParamStrategy(name)
#     return p


T = TypeVar('T')

class ExpectingParameters(Generic[T]):
    def __init__(self, *required_params: str):
        self.required_params = required_params

    @abstractmethod
    def resolve_parameters(self, **parameters: 'SearchStrategy[Any]') -> Union['ExpectingParameters', 'SearchStrategy[Any]']:
        ...


def defer_call(method: str):
    def wrapped(self, *args, **kwargs) -> 'DerivedFromParameter':
        meth = getattr(self.strategy_call, method)  # type: ignore[attr-defined]
        return DerivedFromParameters(lambda *args, **kwargs: meth(*args, **kwargs))

    return wrapped

class HypothesisParameter(ExpectingParameters[T]):

    def __init__(self, name: str):
        self.name = name
        super().__init__(name)

    def resolve_parameters(self, **parameters: 'SearchStrategy[Any]') -> Union[ExpectingParameters, 'SearchStrategy[Any]']:
        return parameters[self.name]

    map = defer_call("map")
    flatmap = defer_call("flatmap")
    filter = defer_call("filter")
    _filter_for_filtered_draw = defer_call("_filter_for_filtered_draw")
    __or__ = defer_call("__or__")




class DerivedFromParameters(ExpectingParameters[T]):
    def __init__(
            self, strategy_call: Callable[..., Union[ExpectingParameters[T], 'SearchStrategy[T]']],
            bound_args: inspect.BoundArguments,
            needs_parameters: dict[str, ExpectingParameters[T]],
            needs_parameters_args: tuple[ExpectingParameters[T],...],
            needs_parameters_kwargs: dict[str, ExpectingParameters[T]]
    ):
        self.strategy_call = strategy_call
        self.bound_args = bound_args
        self.needs_parameters = needs_parameters
        self.needs_parameters_args = needs_parameters_args
        self.needs_parameters_kwargs = needs_parameters_kwargs
        required_params = {v.name for v in (*needs_parameters.values(), needs_parameters_args, *needs_parameters_kwargs)}
        super().__init__(*required_params)

    def __call__(self, **parameters: 'SearchStrategy[Any]') -> Union[ExpectingParameters,'SearchStrategy[Any]']:
        needs_parameters = {k: parameters[k] for k in self.needs_parameters}
        return self.strategy_call()



def parametrizable(strategy_definition: T) -> Union[DerivedFromParameters[T], T]:
    """A decorator that holds a call to the strategy definition a
    """
    @proxies(strategy_definition)
    def wrapper(*args, **kwargs) -> T:
        signature = inspect.signature(strategy_definition)
        arguments = signature.bind(*args, **kwargs)
        needs_parameters = {k: v for k, v in arguments.arguments.items() if isinstance(v, ExpectingParameters) and not k in ['args', 'kwargs']}
        needs_parameters_kwargs = {k: v for k, v in arguments.kwargs.items() if isinstance(v, ExpectingParameters)}
        needs_parameters_args = tuple([v for v in arguments.args if isinstance(v, ExpectingParameters)])
        if not needs_parameters:
            return strategy_definition(*args, **kwargs)
        return DerivedFromParameters(strategy_definition, arguments, needs_parameters, needs_parameters_args, needs_parameters_kwargs)

    return wrapper


# UnresolvedType: TypeAlias = SearchStrategy[Ex] | ExpectingParameters[SearchStrategy[Ex]]

def resolve_parameters(available_parameters, *containers):
    resolved = []
    for container in containers:
        if isinstance(container, tuple):
            container = tuple([arg.resolve_parameters(**available_parameters) if isinstance(arg, ExpectingParameters) else arg for arg in container])
        else:
            container = {n: v.resolve_parameters(**available_parameters) if isinstance(v, ExpectingParameters) else v for n, v in container.items()}
        resolved.append(container)
    return resolved



def param(name: str) -> HypothesisParameter:
    """Return a reference to a strategy by the name it will have as input into the test case.
    Resolution is deferred until the test is set up under @given.

    Example usage:
    >>> from hypothesis import given, strategies as st, param
    >>> import pytest
    >>> @pytest.mark.parametrize('a', [st.just(1), st.integers(), st.floats()])
    ... @given(x=param('a'))
    ... def test_with_param(a):
    ...    assert a > 0
    """
    return HypothesisParameter(name)
