import httpx


class Client:
    def __init__(
        self,
        url: str = "",
        headers: dict[str, str] | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        """Stub so that fixture code will not throw import errors, even before full codegen has taken place."""
