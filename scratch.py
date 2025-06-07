import hypothesis.strategies as st
y = st.deferred(lambda: st.booleans() | st.tuples(y, y))
x = st.param('a').filter(lambda i: i > 1)
print(x)
# print(x.example())
x.validate()