# Grid Resilience

A dependency-free graph model for N-1 topological screening of small power,
water or communication networks.

```python
from grid_resilience import critical_lines

critical = critical_lines({"A", "B", "C"}, [("A", "B"), ("B", "C")])
```

Run `python -m unittest -v`. This evaluates connectivity only; electrical load
flow, thermal ratings, voltage limits and dynamic stability are outside scope.
