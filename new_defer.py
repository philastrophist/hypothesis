import copy
import inspect, functools
from inspect import BoundArguments
from typing import Self


class ExpectsParameter:
    """Sentinel meaning: ‘a concrete value will be supplied later’."""
    __slots__ = ("name",)

    def __init__(self, name: str | None = None):
        self.name = name

    def __repr__(self):
        return f"ExpectsParameter({self.name or ''})"

class MyBound(inspect.BoundArguments):
    @classmethod
    def from_bound(cls, bound: inspect.BoundArguments) -> Self:
        return cls(bound.signature, bound.arguments)

    def copy(self):
        return self.__class__(self.signature, self.arguments)  # shallow copy

    def resolve_placeholders(self, bound: 'MyBound'):
        bound = BoundArguments(bound.signature, bound.arguments)  # shallow copy

        self.arguments.update(bound.arguments)
        # *args of self is complete and *args of bound is incomplete (since it only contains placeholders)
        if 'args' in self.arguments:
            args = list(bound.arguments.pop('args', ()))
            self.arguments['args'] = [args.pop() if _is_placeholder(a) else a for a in self.arguments['args']]
        if 'kwargs' in self.arguments:
            kwargs = bound.arguments.pop('kwargs', {})
            self.arguments['kwargs'].update(kwargs)

    def __len__(self):
        return len(self.arguments) + len(self.args) + len(self.kwargs)





def parametrize(fn):
    sig = inspect.signature(fn)             # single source of truth

    class _DeferredCall(ExpectsParameter):
        def __init__(self, bound: inspect.BoundArguments):
            super().__init__(f"deferred_{fn.__name__}")
            self._bound = MyBound.from_bound(bound)
            self._param_arguments = []

        def __call__(self, *args, **kwargs):
            extra = MyBound.from_bound(sig.bind_partial(*args, **kwargs))
            if _has_placeholders(extra):
                raise TypeError("Deferred call requires concrete values, not ExpectsParameter placeholders")
            completed_bound = self._bound.copy()
            completed_bound.resolve_placeholders(extra)
            if len(completed_bound.arguments) > len(self._bound.arguments):
                raise TypeError("Too many arguments for deferred call")

            if _has_placeholders(completed_bound):
                missing = [name for name, val in self._bound.arguments.items() if _is_placeholder(val)]
                raise TypeError("Missing argument(s) for deferred call: " + ", ".join(missing))

            return fn(*completed_bound.args, **completed_bound.kwargs)


    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        bound = sig.bind(*args, **kwargs)  # raises TypeError if invalid

        if _has_placeholders(bound):
            return _DeferredCall(bound)

        return fn(*args, **kwargs)

    return wrapper


def _is_placeholder(v):
    return isinstance(v, ExpectsParameter)


def _has_placeholders(bound: inspect.BoundArguments):
    return any(_is_placeholder(v) for v in bound.arguments.values())


if __name__ == '__main__':
    @parametrize
    def demo(x, *args, other=None):
        return (x, args, other)

    # 1. All arguments concrete – executes immediately.
    print(demo(0, 1, other=3))
    # → (0, (1,), 2)

    # 2. Some placeholders – returns callable placeholder object.
    step2 = demo(ExpectsParameter(), 1, ExpectsParameter(), other=3)
    print(step2)               # ExpectsParameter(deferred_demo)

    # Complete the call.
    print(step2(0, 1))
    # → (10, (11,), 2)
