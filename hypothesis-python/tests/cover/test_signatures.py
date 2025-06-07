import inspect
from operator import attrgetter

import hypothesis
from hypothesis import strategies as st, given, settings
from hypothesis.signatures import signature_strategy, NAME_STRATEGY, parameter_strategy, is_var_kwargs, is_var_args


@given(NAME_STRATEGY)
def test_name_regex(name):
    pass

@given(st.lists(NAME_STRATEGY, unique=True))
def test_name(names):
    for name in names:
        exec(f"def {name}():...")

@given(signature_strategy(n_args=10))
@settings(max_examples=100)
def test_sig(sig):
    hypothesis.note(sig)
#
# @given(func=function_strategy(st.shared(signature_strategy(), key='sig')),
#        sig=st.shared(signature_strategy(), key='sig'))
# def test_function_signatures(func, sig):
#     assert inspect.signature(func) == sig
#
#
# sig = st.shared(signature_strategy(), key='sig')
# @given(
#     signature=sig,
#     func=function_strategy(signature=sig),
#     inputs=function_inputs(signature=sig, fallback_strategy=st.integers())
# )
# def test_function_returns_locals(func, inputs):
#     bound, args, kwargs = inputs
#     assert bound.arguments == func(*args, **kwargs)
