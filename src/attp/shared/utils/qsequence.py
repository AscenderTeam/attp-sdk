from typing import Any, Callable, Generic, Iterable, Iterator, SupportsIndex, TypeVar, overload


T = TypeVar("T")
NT = TypeVar("NT")


class QSequence(list[T], Generic[T]):
    """
    QSequence is a list with LINQ-style helpers (where/filter/select/etc.) that
    supports lazy chaining. Query methods return new QSequences backed by
    iterables, and materialization happens only when list behavior is needed
    (iteration, indexing, length, mutation).

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
    def __init__(self, iterable: Iterable[T] | None = None) -> None:
        super().__init__()
        self._iterable: Iterable[T] | None = None

        if iterable is None:
            return

        if isinstance(iterable, (list, tuple, QSequence)):
            super().extend(iterable)
            return

        self._iterable = iterable

    def _ensure_materialized(self) -> None:
        if self._iterable is None:
            return
        super().extend(self._iterable)
        self._iterable = None

    def _iter_source(self) -> Iterator[T]:
        if self._iterable is not None:
            # Materialize to preserve list semantics when source is not re-iterable.
            self._ensure_materialized()
        return list.__iter__(self)

    def any(self, func: Callable[[T], bool] | None = None) -> bool:
        if func is None:
            return bool(self)
        return any(func(x) for x in self._iter_source())
    
    def all(self, func: Callable[[T], bool]) -> bool:
        return all(func(x) for x in self._iter_source())
    
    def count_where(self, func: Callable[[T], bool]) -> int:
        return sum(1 for x in self._iter_source() if func(x))

    _COUNT_MISSING = object()

    @overload
    def count(self, value: T, /) -> int: ...

    @overload
    def count(self, value: object = _COUNT_MISSING, /) -> int: ...

    def count(self, value: object = _COUNT_MISSING, /) -> int:
        if value is self._COUNT_MISSING:
            return len(self)
        self._ensure_materialized()
        return list.count(self, value)  # type: ignore[arg-type]
    
    def distinct(self) -> "QSequence[T]":
        seen: set[Any] = set()
        return QSequence(x for x in self._iter_source() if not (x in seen or seen.add(x)))

    def order_by(self, key: Callable[[T], Any]) -> "QSequence[T]":
        return QSequence(sorted(self._iter_source(), key=key))

    def select_many(self, func: Callable[[T], list[NT]]) -> "QSequence[NT]":
        return QSequence(item for x in self._iter_source() for item in func(x))

    def where(self, func: Callable[[T], Any]) -> "QSequence[T]":
        return QSequence(filter(func, self._iter_source()))
    
    def filter(self, func: Callable[[T], Any]) -> "QSequence[T]":
        return self.where(func)
    
    def find_or_none(self, func: Callable[[T], bool]) -> T | None:
        return next((s for s in self._iter_source() if func(s)), None)
    
    def find(self, func: Callable[[T], bool]) -> T:
        if (_found := self.find_or_none(func)) is None:
            raise IndexError("LINQ Index out of range.")
        
        return _found
    
    def find_or_default(self, func: Callable[[T], bool], default: NT | Any | None = None) -> NT | Any | None:
        return next((s for s in self._iter_source() if func(s)), default)
    
    def group_by(self, key: Callable[[T], NT]) -> dict[NT, "QSequence[T]"]:
        groups = {}
        for x in self._iter_source():
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
        return QSequence(map(func, self._iter_source()))
    
    def map(self, func: Callable[[T], NT]) -> "QSequence[NT]":
        return self.select(func)
    
    def to_list(self) -> list[T]:
        self._ensure_materialized()
        return list(self)
    
    def __add__(self, value: list[Any], /) -> "QSequence[Any]":
        self._ensure_materialized()
        return QSequence(super().__add__(value))

    def __iadd__(self, value: Iterable[T], /):
        self._ensure_materialized()
        return super().__iadd__(value)

    def __mul__(self, value: SupportsIndex, /):
        self._ensure_materialized()
        return QSequence(super().__mul__(value))

    def __imul__(self, value: SupportsIndex, /):
        self._ensure_materialized()
        return super().__imul__(value)

    def __iter__(self) -> Iterator[T]:
        self._ensure_materialized()
        return list.__iter__(self)

    def __len__(self) -> int:
        self._ensure_materialized()
        return list.__len__(self)

    def __contains__(self, item: object) -> bool:
        self._ensure_materialized()
        return list.__contains__(self, item)

    def append(self, item: T) -> None:
        self._ensure_materialized()
        super().append(item)

    def extend(self, other: Iterable[T]) -> None:
        self._ensure_materialized()
        super().extend(other)

    def insert(self, index: SupportsIndex, item: T) -> None:
        self._ensure_materialized()
        super().insert(index, item)

    def pop(self, index: SupportsIndex = -1) -> T:
        self._ensure_materialized()
        return super().pop(index)

    def remove(self, item: T) -> None:
        self._ensure_materialized()
        super().remove(item)

    def clear(self) -> None:
        self._ensure_materialized()
        super().clear()

    def sort(self, *args: Any, **kwargs: Any) -> None:
        self._ensure_materialized()
        super().sort(*args, **kwargs)

    def reverse(self) -> None:
        self._ensure_materialized()
        super().reverse()
    
    @overload
    def __getitem__(self, i: SupportsIndex, /) -> T: ...
    
    @overload
    def __getitem__(self, s: slice, /) -> "QSequence[T]": ...
    
    def __getitem__(self, item: Any):
        self._ensure_materialized()
        result = super().__getitem__(item)

        if isinstance(item, slice):
            return QSequence(result)
        
        return result

    def __setitem__(self, key: SupportsIndex | slice, value: Any) -> None:
        self._ensure_materialized()
        super().__setitem__(key, value)

    def __delitem__(self, key: SupportsIndex | slice) -> None:
        self._ensure_materialized()
        super().__delitem__(key)


class QSequenceIterator(QSequence[T]):
    pass
