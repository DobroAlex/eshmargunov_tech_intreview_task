"""The basic abstract APIs."""

import abc
from typing import Callable

import requests


class BaseApi(abc.ABC):
    """The most basic abstract API."""
    BASE_URL: str

    @abc.abstractmethod
    def _send_request(
            self,
            method: Callable[..., requests.Response],
            endpoint: str,
            headers: dict[str, str] = None,
            params: dict[str, str] = None,
    ) -> requests.Response:
        """Request sender.

        Raises:
            HTTPError: if any unexpected status occurs.
        """
        ...
