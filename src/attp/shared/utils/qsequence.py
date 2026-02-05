from typing import Any, Callable, Generic, SupportsIndex, TypeVar, overload


T = TypeVar("T")
NT = TypeVar("NT")


class QSequence(list[T], Generic[T]):
    """
    I'm fucking pissed of by python's ugly `next(...)`, `filter(...)`, `map(...)` and other crutchy ways to query-operate with lists.
    So I implemented my own LINQ style of query.
    
    Example:
    ```
    my_list = QSequence([{"name": "Zahcoder34"}])
    
    zahcoder = my_list.where(lambda s: s["name"] == "Zahcoder34").select(lambda s: s["name"]).first()
    
    if zahcoder is None:
        print("Not found")
    
    print(zahcoder)
    
    >> Zahcoder34
    ```
    """
    def any(self, func: Callable[[T], bool] | None = None) -> bool:
        if func is None:
            return bool(self)
        return any(func(x) for x in self)
    
    def all(self, func: Callable[[T], bool]) -> bool:
        return all(func(x) for x in self)
    
    def count_where(self, func: Callable[[T], bool]) -> int:
        return sum(1 for x in self if func(x))

    def count(self) -> int:
        return len(self)
    
    def distinct(self) -> "QSequence[T]":
        seen = set()
        return QSequence(x for x in self if not (x in seen or seen.add(x)))

    def order_by(self, key: Callable[[T], Any]) -> "QSequence[T]":
        return QSequence(sorted(self, key=key))

    def select_many(self, func: Callable[[T], list[NT]]) -> "QSequence[NT]":
        return QSequence(item for x in self for item in func(x))

    def where(self, func: Callable[[T], Any]) -> "QSequence[T]":
        return QSequence(filter(func, self))
    
    def find_or_none(self, func: Callable[[T], bool]) -> T | None:
        return next((s for s in self if func(s)), None)
    
    def find(self, func: Callable[[T], bool]) -> T:
        if (_found := self.find_or_none(func)) is None:
            raise IndexError("LINQ Index out of range.")
        
        return _found
    
    def find_or_default(self, func: Callable[[T], bool], default: NT | Any | None = None) -> NT | Any | None:
        return next((s for s in self if func(s)), default)
    
    def group_by(self, key: Callable[[T], NT]) -> dict[NT, "QSequence[T]"]:
        groups = {}
        for x in self:
            k = key(x)
            groups.setdefault(k, QSequence()).append(x)
        return groups
    
    def first(self) -> T | None:
        if not len(self):
            return None
        return self[0]
    
    def last(self) -> T | None:
        if not len(self):
            return None
        return self[-1]
    
    def select(self, func: Callable[[T], NT]) -> "QSequence[NT]":
        return QSequence(map(func, self))
    
    def to_list(self) -> list[T]:
        return list(self)
    
    def __add__(self, value: "list[T] | QSequence[T]") -> "QSequence[T]":
        return QSequence(super().__add__(value))
    
    @overload
    def __getitem__(self, i: SupportsIndex, /) -> T: ...
    
    @overload
    def __getitem__(self, s: slice, /) -> "QSequence[T]": ...
    
    def __getitem__(self, item: Any):
        result = super().__getitem__(item)

        if isinstance(item, slice):
            return QSequence(result)
        
        return result