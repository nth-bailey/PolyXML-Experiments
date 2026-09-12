from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
import importlib
from typing import Any, Callable, Dict, List, Optional, Tuple, Type
from dataclasses import is_dataclass

import cloudpickle
import lz4.frame
import msgspec
import pickle


class ObjectSerializer(ABC):
    """Abstract object serializer interface matching Badger's contract."""

    @abstractmethod
    def dumps(self, obj: Any) -> bytes:
        ...

    @abstractmethod
    def loads(self, data: bytes) -> Any:
        ...


class Lz4Codec:
    """LZ4 compression codec matching Badger's storage.objectserializer.codecs.lz4."""

    def encode(self, data: bytes) -> bytes:
        return lz4.frame.compress(data)

    def decode(self, data: bytes) -> bytes:
        return lz4.frame.decompress(data)


class PipelineSerializer(ObjectSerializer):
    """Pipeline serializer that chains compression codecs after object serialization."""

    def __init__(self, object_serializer: ObjectSerializer, codecs: Optional[List[Any]] = None):
        self.object_serializer = object_serializer
        self.codecs = codecs or []

    def dumps(self, obj: Any) -> bytes:
        data = self.object_serializer.dumps(obj)
        for codec in self.codecs:
            data = codec.encode(data)
        return data

    def loads(self, data: bytes) -> Any:
        for codec in reversed(self.codecs):
            data = codec.decode(data)
        return self.object_serializer.loads(data)


class CloudPickleSerializer(ObjectSerializer):
    """Current Badger baseline serializer based on cloudpickle."""

    def __init__(self, protocol: Optional[int] = None):
        self._protocol = protocol

    def dumps(self, obj: Any) -> bytes:
        return cloudpickle.dumps(obj, protocol=self._protocol)

    def loads(self, data: bytes) -> Any:
        return cloudpickle.loads(data)


class Pickle5Serializer(ObjectSerializer):
    """Standard library pickle with protocol 5 (C-accelerated)."""

    def dumps(self, obj: Any) -> bytes:
        return pickle.dumps(obj, protocol=5)

    def loads(self, data: bytes) -> Any:
        return pickle.loads(data)


class MsgspecSerializer(ObjectSerializer):
    """High-performance MessagePack serializer implemented in C via msgspec.

    Supports:
    1. Seamless serialization of Python dataclasses without schema definitions.
    2. Transparent roundtripping preserving exact types and Decimals.
    3. Self-describing tagged envelopes (class path + msgpack payload) for untyped loads().
    4. Direct typed decoding when target class is known.
    """

    _class_cache: Dict[str, Type[Any]] = {}

    @staticmethod
    def _enc_hook(obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return str(obj)
        raise NotImplementedError(f"Cannot serialize object of type {type(obj)}")

    @staticmethod
    def _dec_hook(target_type: Type[Any], obj: Any) -> Any:
        if target_type is Decimal:
            return Decimal(obj)
        raise NotImplementedError(f"Cannot deserialize object of type {target_type}")

    def __init__(self, target_type: Optional[Type[Any]] = None):
        self._target_type = target_type
        self._encoder = msgspec.msgpack.Encoder(enc_hook=self._enc_hook)

    @classmethod
    def _resolve_class(cls, class_identifier: str) -> Optional[Type[Any]]:
        if not class_identifier:
            return None
        if class_identifier in cls._class_cache:
            return cls._class_cache[class_identifier]

        module_name, class_name = class_identifier.rsplit(":", 1)
        mod = importlib.import_module(module_name)
        resolved = getattr(mod, class_name)
        cls._class_cache[class_identifier] = resolved
        return resolved

    def dumps(self, obj: Any) -> bytes:
        if self._target_type is not None:
            # Direct typed encoding without envelope
            return self._encoder.encode(obj)

        # Self-describing envelope
        if is_dataclass(obj):
            cls = obj.__class__
            identifier = f"{cls.__module__}:{cls.__qualname__}"
            self._class_cache[identifier] = cls
            payload = self._encoder.encode(obj)
            # Encode as a 2-tuple: (class_identifier, msgpack_payload)
            return msgspec.msgpack.encode((identifier, payload))

        # Plain builtin object
        payload = self._encoder.encode(obj)
        return msgspec.msgpack.encode(("", payload))

    def loads(self, data: bytes) -> Any:
        if self._target_type is not None:
            # Direct typed decode
            return msgspec.msgpack.decode(
                data,
                type=self._target_type,
                dec_hook=self._dec_hook,
            )

        # Decode envelope
        tag, payload = msgspec.msgpack.decode(data)
        if tag:
            target_cls = self._resolve_class(tag)
            if target_cls is not None:
                return msgspec.msgpack.decode(
                    payload,
                    type=target_cls,
                    dec_hook=self._dec_hook,
                )
        return msgspec.msgpack.decode(payload, dec_hook=self._dec_hook)
