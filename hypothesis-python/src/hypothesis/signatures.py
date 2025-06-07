"""Strategies that fabricate inspect.Parameter and inspect.Signature objects.
"""
import inspect
import keyword
import types
from typing import Any

from hypothesis import strategies as st
from hypothesis.strategies import SearchStrategy, DrawFn


def valid_name(x: str) -> bool:
    return (not (keyword.iskeyword(x) or keyword.issoftkeyword(x))) and not x.startswith("_") and len(x) > 0

ascii_pre_text = st.characters(codec='ascii', categories=("L",))
ascii_text = st.characters(codec='ascii',  categories=("L", "N"), include_characters='_')
NAME_STRATEGY = st.builds(''.join, st.tuples(st.text(ascii_pre_text, min_size=1), st.text(ascii_text))).filter(valid_name)
KIND_STRATEGY = st.sampled_from(inspect._ParameterKind)
KIND_NON_VAR_STRATEGY = st.sampled_from([inspect._ParameterKind.KEYWORD_ONLY, inspect._ParameterKind.POSITIONAL_OR_KEYWORD, inspect._ParameterKind.POSITIONAL_ONLY])
KIND_VAR_STRATEGY = st.sampled_from([inspect._ParameterKind.VAR_POSITIONAL, inspect._ParameterKind.VAR_KEYWORD])

DEFAULT_STRATEGY = st.one_of(
    st.just(inspect.Parameter.empty),
    st.none(),
)


@st.composite
def parameter_strategy(
    draw,
    *,
    name_strategy: st.SearchStrategy[str] = NAME_STRATEGY,
    kind_strategy: st.SearchStrategy[inspect._ParameterKind] = KIND_STRATEGY,
    default_strategy: st.SearchStrategy[object] = DEFAULT_STRATEGY,
) -> inspect.Parameter:
    """
    Build a single `inspect.Parameter`.

    * For * and ** parameters (VAR_POSITIONAL / VAR_KEYWORD) we always use
      `Parameter.empty` for the default – Python disallows other values.
    """
    kind = draw(kind_strategy)
    name = draw(name_strategy)

    if kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
        default = inspect.Parameter.empty
    else:
        default = draw(default_strategy)

    return inspect.Parameter(name, kind, default=default)

def is_var_kwargs(param: inspect.Parameter) -> bool:
    return param.kind == inspect.Parameter.VAR_KEYWORD

def is_var_args(param: inspect.Parameter) -> bool:
    return param.kind == inspect.Parameter.VAR_POSITIONAL

@st.composite
def signature_strategy(
    draw,
    n_args,
    defaults_strategy: st.SearchStrategy[object] = st.none(),
) -> inspect.Signature:
    """
    Generate a *valid* `inspect.Signature` (no duplicate names, correct order).

    You can plug in your own `parameter_strat` if you need annotations or
    exotic defaults.
    """
    names = draw(st.lists(NAME_STRATEGY, unique=True, min_size=n_args, max_size=n_args))
    kinds: list[inspect._ParameterKind] = []

    # add in VAR_POSITIONAL and VAR_KEYWORD
    kinds += draw(st.lists(st.just(inspect._ParameterKind.VAR_POSITIONAL), max_size=min([1, len(names) - len(kinds)])))
    kinds += draw(st.lists(st.just(inspect._ParameterKind.VAR_KEYWORD), max_size=min([1, len(names) - len(kinds)])))
    n_non_variadic = len(names) - len(kinds)
    remaining_kinds = [inspect._ParameterKind.KEYWORD_ONLY, inspect._ParameterKind.POSITIONAL_OR_KEYWORD, inspect._ParameterKind.POSITIONAL_ONLY]
    if inspect._ParameterKind.VAR_POSITIONAL in kinds:
        remaining_kinds.remove(inspect._ParameterKind.KEYWORD_ONLY)
    kinds += draw(st.lists(st.sampled_from(remaining_kinds), min_size=n_non_variadic, max_size=n_non_variadic))
    kinds.sort()

    var_kinds = [inspect._ParameterKind.VAR_POSITIONAL, inspect._ParameterKind.VAR_KEYWORD]

    added_defaults = draw(st.lists(defaults_strategy, max_size=n_non_variadic))
    defaults = []
    for i, kind in enumerate(kinds):
        if kind not in var_kinds and len(added_defaults):
            defaults.append(added_defaults.pop())
        else:
            defaults.append(inspect.Parameter.empty)

    params = [inspect.Parameter(name, kind, default=default) for name, kind, default in zip(names, kinds, defaults)]
    return inspect.Signature(params)

def create_function(name: str, signature: inspect.Signature) -> types.FunctionType:
    """
    Return a new function whose call signature exactly matches *signature*.
    The body simply returns its local namespace for easy inspection.
    """
    if not isinstance(signature, inspect.Signature):
        raise TypeError("signature must be an inspect.Signature")
    params_src = ", ".join(str(p) for p in signature.parameters.values())
    func_src = f"def {name}({params_src}): return locals()"
    namespace: dict[str, types.FunctionType] = {}
    exec(func_src, namespace)
    fn = namespace[name]
    fn.__signature__ = signature
    return fn


def function_strategy(
        signature: SearchStrategy[inspect.Signature] | None = None, name: SearchStrategy[str] | None = None
) -> SearchStrategy[types.FunctionType]:
    if name is None:
        name = NAME_STRATEGY
    if signature is None:
        signature = signature_strategy()
    return st.builds(create_function, name=name, signature=signature)


@st.composite
def function_inputs(draw: DrawFn, signature: SearchStrategy[inspect.Signature], fallback_strategy: SearchStrategy[Any]):
    """Returns valid inputs to a function based on its signature.
    If the signature specifies type annotations, the strategy is inferred from them
    otherwise, it uses strategy_pool.
    uses st.fixed_dictionaries
    """
    signature = draw(signature)
    args: list[SearchStrategy[Any]] = []
    kwargs: dict[str, SearchStrategy[Any]] = {}
    either = [p for p in signature.parameters.values() if p.POSITIONAL_OR_KEYWORD]
    cut = draw(st.integers(min_value=0, max_value=len(either)))
    count = 0
    for p in signature.parameters.values():
        base = fallback_strategy if p.annotation is inspect.Parameter.empty else st.from_type(p.annotation)
        if p.kind is p.POSITIONAL_ONLY:
            args.append(draw(base))
        elif p.kind is p.POSITIONAL_OR_KEYWORD:
            if count < cut:
                args.append(draw(base))
            else:
                kwargs[p.name] = draw(base)
            count += 1
        elif p.kind is p.KEYWORD_ONLY:
            kwargs[p.name] = draw(base)
        elif p.kind is p.VAR_POSITIONAL:
            args += draw(st.lists(base))
        else:
            kwargs.update(draw(st.dictionaries(keys=NAME_STRATEGY, values=base)))
    bound = signature.bind(*args,  **kwargs)
    return bound, args, kwargs
