"""Dog CEO API."""

import functools
from typing import Callable, Sequence

import requests

from framework.apis.base import BaseApi


class DogCeoApi(BaseApi):
    """Dog.Ceo API handler."""

    # NOTE: данные в классе слишком простые чтоб строить поверх них dataclass модели как в Yandex Disk
    BASE_URL = "https://dog.ceo/api"

    def _send_request(
            self,
            method: Callable[..., requests.Response],
            endpoint: str,
            headers: dict[str, str] = None,
            params: dict[str, str] = None,
    ) -> requests.Response:
        res = method(
            f"{self.BASE_URL}{endpoint}",
            headers=headers,
            params=params,
        )
        res.raise_for_status()
        return res

    @functools.lru_cache
    def get_sub_breeds(self, breed: str) -> tuple[str, ...]:
        """Get sub breeds of `breed`."""
        return tuple(self._send_request(
            requests.get,
            f"/breed/{breed}/list",
        ).json().get("message", []))

    @functools.lru_cache
    def get_urls(self, breed: str, sub_breeds: Sequence[str]) -> tuple[str, ...]:
        """Get image urls for `sub_breeds` if any or `breed` itself."""
        if sub_breeds:
            return tuple(
                self._send_request(
                    requests.get,
                    f"/breed/{breed}/{sub_breed}/images/random",
                ).json()['message']
                for sub_breed in sub_breeds
            )
        else:
            return (
                self._send_request(
                    requests.get,
                    f"/breed/{breed}/images/random",
                ).json()['message'],
            )
