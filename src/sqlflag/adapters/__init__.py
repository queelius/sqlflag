"""Framework adapters for mounting SqlFlag into existing CLI apps."""

from abc import ABC, abstractmethod
from typing import Any


class Adapter(ABC):
    """Contract for framework adapters.

    Each adapter knows how to mount sqlflag's commands (query group,
    sql, schema) into a specific CLI framework.
    """

    @abstractmethod
    def mount(
        self,
        app: Any,
        sqlflag: Any,
        query_name: str = "query",
    ) -> Any:
        """Mount sqlflag commands into a framework-specific app.

        Args:
            app: The target CLI app (framework-specific type).
            sqlflag: The SqlFlag instance.
            query_name: Name for the query subcommand group.

        Returns:
            The app (or a wrapper) suitable for invocation.
        """
        ...
