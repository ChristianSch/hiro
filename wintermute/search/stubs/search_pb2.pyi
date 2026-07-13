from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class OperationalState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = []
    OPERATIONAL_STATE_UNKNOWN: _ClassVar[OperationalState]
    OPERATIONAL_STATE_OPERATIONAL: _ClassVar[OperationalState]
    OPERATIONAL_STATE_UNAVAILABLE: _ClassVar[OperationalState]
OPERATIONAL_STATE_UNKNOWN: OperationalState
OPERATIONAL_STATE_OPERATIONAL: OperationalState
OPERATIONAL_STATE_UNAVAILABLE: OperationalState

class SearchRequest(_message.Message):
    __slots__ = ["query", "page_number", "result_per_page"]
    QUERY_FIELD_NUMBER: _ClassVar[int]
    PAGE_NUMBER_FIELD_NUMBER: _ClassVar[int]
    RESULT_PER_PAGE_FIELD_NUMBER: _ClassVar[int]
    query: str
    page_number: int
    result_per_page: int
    def __init__(self, query: _Optional[str] = ..., page_number: _Optional[int] = ..., result_per_page: _Optional[int] = ...) -> None: ...

class SearchResponse(_message.Message):
    __slots__ = ["results"]
    class Result(_message.Message):
        __slots__ = ["url", "title", "content", "description"]
        URL_FIELD_NUMBER: _ClassVar[int]
        TITLE_FIELD_NUMBER: _ClassVar[int]
        CONTENT_FIELD_NUMBER: _ClassVar[int]
        DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
        url: str
        title: str
        content: str
        description: str
        def __init__(self, url: _Optional[str] = ..., title: _Optional[str] = ..., content: _Optional[str] = ..., description: _Optional[str] = ...) -> None: ...
    RESULTS_FIELD_NUMBER: _ClassVar[int]
    results: _containers.RepeatedCompositeFieldContainer[SearchResponse.Result]
    def __init__(self, results: _Optional[_Iterable[_Union[SearchResponse.Result, _Mapping]]] = ...) -> None: ...

class StatusRequest(_message.Message):
    __slots__ = []
    def __init__(self) -> None: ...

class DependencyStatus(_message.Message):
    __slots__ = ["name", "state"]
    NAME_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    name: str
    state: OperationalState
    def __init__(self, name: _Optional[str] = ..., state: _Optional[_Union[OperationalState, str]] = ...) -> None: ...

class StatusResponse(_message.Message):
    __slots__ = ["state", "dependencies"]
    STATE_FIELD_NUMBER: _ClassVar[int]
    DEPENDENCIES_FIELD_NUMBER: _ClassVar[int]
    state: OperationalState
    dependencies: _containers.RepeatedCompositeFieldContainer[DependencyStatus]
    def __init__(self, state: _Optional[_Union[OperationalState, str]] = ..., dependencies: _Optional[_Iterable[_Union[DependencyStatus, _Mapping]]] = ...) -> None: ...
