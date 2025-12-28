import kuzu
import inspect

print(inspect.signature(kuzu.Database.__init__))
print(kuzu.Database.__doc__)
