import pytest

import hypothesis.params
import hypothesis.strategies._internal.strategies
from hypothesis import given, strategies as st


@pytest.fixture(scope="session", params=[0, 1, 2])
def d(request):
    return st.integers(max_value=hypothesis.params.param)


@st.composite
def custom_dynamic_strategy(draw, a, b):
    a, b = (draw(a)*2, draw(b)*-2)
    return a, b


@pytest.mark.parametrize("a,b", [(st.integers(max_value=2), st.integers(max_value=2))], ids=repr)
@given(a='a', b='b', c=st.integers(min_value=2), d='d', e=custom_dynamic_strategy)
def test_parameterized(a: int , b: int, c: int, d: int, e: int):
    assert a <= c and b <= c and d <= c
