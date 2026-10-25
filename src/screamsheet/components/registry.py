"""Registry mapping string component type keys to ScreamsheetComponent classes."""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Type, Union, overload

from .base import ScreamsheetComponent


class ComponentRegistry:
    """Central registry for looking up and instantiating screamsheet components by key."""

    _registry: Dict[str, Type[ScreamsheetComponent]] = {}

    @classmethod
    def register_component(
        cls,
        key: str,
        component_cls: Type[ScreamsheetComponent],
    ) -> Type[ScreamsheetComponent]:
        """Register ``component_cls`` under ``key``."""
        normalized_key = key.strip().lower()
        if not normalized_key:
            raise ValueError("Component key must be a non-empty string")
        if not isinstance(component_cls, type) or not issubclass(
            component_cls, ScreamsheetComponent
        ):
            raise TypeError(
                f"Registered class {component_cls!r} must be a ScreamsheetComponent subclass"
            )
        component_cls.component_key = normalized_key
        cls._registry[normalized_key] = component_cls
        return component_cls

    @overload
    @classmethod
    def register(
        cls, key_or_cls: Type[ScreamsheetComponent]
    ) -> Type[ScreamsheetComponent]: ...

    @overload
    @classmethod
    def register(
        cls, key_or_cls: Optional[str] = None
    ) -> Callable[[Type[ScreamsheetComponent]], Type[ScreamsheetComponent]]: ...

    @classmethod
    def register(
        cls,
        key_or_cls: Union[str, Type[ScreamsheetComponent], None] = None,
    ) -> Any:
        """Class decorator to register a :class:`ScreamsheetComponent` subclass.

        Can be used either as ``@ComponentRegistry.register`` (uses ``cls.component_key``)
        or ``@ComponentRegistry.register("mlb_standings")``.
        """
        if isinstance(key_or_cls, type) and issubclass(key_or_cls, ScreamsheetComponent):
            key = getattr(key_or_cls, "component_key", "")
            return cls.register_component(key, key_or_cls)

        def _decorator(
            component_cls: Type[ScreamsheetComponent],
        ) -> Type[ScreamsheetComponent]:
            key = key_or_cls if isinstance(key_or_cls, str) else getattr(
                component_cls, "component_key", ""
            )
            return cls.register_component(key, component_cls)

        return _decorator

    @classmethod
    def get(cls, key: str) -> Type[ScreamsheetComponent]:
        """Return the component class registered for ``key``.

        Raises:
            KeyError: If no component is registered under ``key``.
        """
        normalized_key = key.strip().lower()
        if normalized_key not in cls._registry:
            available = ", ".join(sorted(cls._registry.keys())) or "<none>"
            raise KeyError(
                f"Unknown screamsheet component type {key!r}. Available: {available}"
            )
        return cls._registry[normalized_key]

    @classmethod
    def create(cls, key: str, **kwargs: Any) -> ScreamsheetComponent:
        """Instantiate the component registered under ``key`` with ``**kwargs``."""
        component_cls = cls.get(key)
        return component_cls(**kwargs)

    @classmethod
    def is_registered(cls, key: str) -> bool:
        """Return True if ``key`` is registered."""
        return key.strip().lower() in cls._registry

    @classmethod
    def list_keys(cls) -> List[str]:
        """Return sorted list of all registered component keys."""
        return sorted(cls._registry.keys())
