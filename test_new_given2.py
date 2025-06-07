"""
As a semi-regular user of hypothesis I have found myself more and writing tests which follow this structure:

```
@pytest.mark.parametrize("cls,parameter_strategies", [(cls1, {key: strategy}), (cls2, {key: strategy})])
@pytest.mark.parametrize("other", [1, 2])
@given(
    another=strategy,
    data=st.data(),
)
def test_objects(
    data: DataObject,
    another: Any
    cls: type[MyObject],
    parameter_strategies: dict[str, Any],
    other: Any,
) -> None:
    objects = data.draw(st.builds(partial(cls, other=other), another, **parameter_strategies))
    assert True
```
We are testing identical behaviour across many different objects instantiated by drawing from strategies. However, we must guarantee that each object/param combination is tested. This is something that we can only do with the addition of a `parametrize` mark; `hypothesis` doesn't and shouldn't support guaranteed sampling.

Hypothesis plays nicely with pytest so all is well and this example runs (see below for the runnable script)

However, having showed this flow to a colleague new to hypothesis, they found it a bit confusing and annoying to have to draw the examples yourself when all you're doing is parameterizing. Further to that, the thing I really like about hypothesis' structure is how we lay out `@given` as a decorator before the test leaving only the actual testing logic inside the function. It's a nice separation that makes it very clear what is generation and what is testing. This is somewhat polluted when we have to do the drawing ourselves.

Ideally, we'd like to do something like this:
```
@pytest.mark.parametrize("object", [
    st.builds(cls1, another=strategy, **strategies),
    ...
])
@pytest.mark.parametrize("other", [1, 2])
@given(object='object', another=strategy)
def test_objects_new(object: MyObject) -> None:
    object
    assert True

There are two hidden requirements in the above:
    1. External strategies (e.g. from parameterizations/fixtures) are drawn automatically in a wrapper (inside `given`) around the test function by declaring their expected names.
    2. External strategies that depend
```
"""
from typing import Any

import pytest

from hypothesis import given, strategies as st
from hypothesis.strategies import DataObject
from hypothesis.params import param


class MyObject:
    def __init__(self, dim: int, **kwargs: Any):
        self.dim = dim
        self.kwargs = kwargs

class SubClassed(MyObject):
    def __init__(self, dim: int, **kwargs: Any):
        super().__init__(dim, **kwargs)

dim_strategy = st.integers(min_value=1, max_value=10)

@st.composite
def cls_strategy(draw, cls, dim, parameter_strategies):
    params = {k: draw(v) for k, v in parameter_strategies.items()}
    return cls(dim, **params)

@pytest.mark.parametrize("cls,parameter_strategies", [(MyObject, {'a': st.integers(max_value=1)}), (MyObject, {'a': st.text()})])
@pytest.mark.parametrize("other", [1, 2])
@given(
    dim=dim_strategy,
    data=st.data(),
)
def test_objects_original(
    data: DataObject,
    dim: int,
    cls: type[MyObject],
    parameter_strategies: dict[str, Any],
    other: Any,
) -> None:
    objects = data.draw(cls_strategy(cls, dim, parameter_strategies))
    assert True


@pytest.fixture(scope="session", params=[0, 1, 2])
def d(request):
    return st.integers(max_value=request.param)


@st.composite
def custom_dynamic_strategy(draw, a, b):
    a, b = (draw(a)*2, draw(b)*-2)
    return a, b


@pytest.mark.parametrize("a,b", [(st.integers(max_value=2), st.integers(max_value=2))], ids=repr)
@given(a='a', b='b', c=st.integers(min_value=2), d='d', e=custom_dynamic_strategy(param('a'), param('b')))
def test_parameterized(a: int , b: int, c: int, d: int, e: int):
    assert a <= c and b <= c and d <= c


@pytest.mark.parametrize("object", [
    st.builds(MyObject, st.shared(dim_strategy, key='k'), a=st.integers(max_value=1)),
    st.builds(SubClassed, st.shared(dim_strategy, key='k'), a=st.text()),
])
@given(dim=st.shared(dim_strategy, key='k'), object='object')
def test_objects_new1(dim, object: MyObject) -> None:
    assert object.dim == dim
    if isinstance(object.kwargs['a'], int):
        assert type(object) is MyObject
    else:
        assert type(object) is SubClassed



# but now another dependency of `other`: mix and match parameterized/non-parameterized strategies/concrete values

@pytest.mark.parametrize("object", [
    st.builds(MyObject, st.shared(dim_strategy, key='k'), a=st.integers(max_value=1), other=param('other')),
    st.builds(SubClassed, st.shared(dim_strategy, key='k'), a=st.text(), other=param('other')),
    # this doesn't work because builds caches the inputs
])
@pytest.mark.parametrize("other", [1, 2])
@given(dim=st.shared(dim_strategy, key='k'), object='object')
def test_objects_new3(dim, object: MyObject, other: Any) -> None:
    assert object.dim == dim
    if isinstance(object.kwargs['a'], int):
        assert type(object) is MyObject
    else:
        assert type(object) is SubClassed
    assert object.kwargs['other'] == other
