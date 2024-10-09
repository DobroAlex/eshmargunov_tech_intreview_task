"""Yandex Disk API."""
from __future__ import annotations

import abc
import datetime
import enum
from dataclasses import dataclass, field
from time import sleep
from typing import Callable

import requests

from framework.apis.base import BaseApi


class ResourceType(enum.Enum):
    """Yandex Disk Resource Type."""
    DIR = "dir"
    FILE = "file"


class IBuildableFromResponse(abc.ABC):
    """Interface that indicates that a class can be built from a web response."""

    @classmethod
    @abc.abstractmethod
    # Python 3.11 allows for a generic Self, assuming it's python 3.10
    def build_from_response(cls, res: dict):
        raise NotImplementedError()


@dataclass
class HasCreationAndModificationDateMixIn:
    """MixIn for classes which has a creation and modification dates."""
    created: str | datetime.datetime
    modified: str | datetime.datetime

    def convert_to_dates(self) -> None:
        """Converts ISO date files to actual datetime instances."""
        if isinstance(self.created, str):
            self.created = datetime.datetime.fromisoformat(self.created)
        if isinstance(self.modified, str):
            self.modified = datetime.datetime.fromisoformat(self.modified)


@dataclass
class HasResourceTypeMixIn:
    """MixIn for class with a resource type field."""
    type: str | ResourceType

    def convert_resource_type(self) -> None:
        """Convert the `type` field to an enum. """
        self.type = ResourceType(self.type)


@dataclass
# NOTE: специально оставляю микс-ины,
# т.к. в будущем возможны другие классы, не связанные с этим,
# но использующее эти же методы для фикса полей.
class BaseNode(
    HasResourceTypeMixIn,
    HasCreationAndModificationDateMixIn,
    IBuildableFromResponse,
    abc.ABC,
):
    """Abstract basic node"""
    # NOTE: поля не отсортированы
    path: str
    name: str
    revision: str
    resource_id: str
    comment_ids: dict[str, str]
    exif: dict


@dataclass
class FolderItem(BaseNode):
    """Representation of a Yandex Disk Folder's item."""
    antivirus_status: str
    file: str
    media_type: str | None = field(default=None)
    preview: str | None = field(default=None)
    md5: str | None = field(default=None)
    sha256: str | None = field(default=None)
    mime_type: str | None = field(default=None)
    size: int | None = field(default=None)
    sizes: list[dict] | None = field(default=None)

    def __post_init__(self):
        self.convert_to_dates()
        self.convert_resource_type()

    @classmethod
    def build_from_response(cls, res: dict):
        return cls(**res)


@dataclass
class Folder(BaseNode):
    """Representation of a Yandex Disk folder."""
    # https://yandex.ru/dev/disk-api/doc/ru/reference/meta#response --  шляпа.
    # Данные о структуре добыты дебагом.

    embedded: 'Embedded'

    def __post_init__(self):
        self.convert_to_dates()
        self.convert_resource_type()

    @classmethod
    def build_from_response(cls, res: dict[str, str | dict]) -> 'Folder':
        embedded = Embedded.build_from_response(res.pop("_embedded"))
        return cls(embedded=embedded, **res)


@dataclass
class Embedded(IBuildableFromResponse):
    sort: str
    path: str
    items: list['FolderItem']
    limit: int
    offset: int
    total: int

    @classmethod
    def build_from_response(cls, res: dict) -> Embedded:
        items_raw: list = res.pop("items")
        items: list[FolderItem] = []
        if items_raw:
            items = list(FolderItem.build_from_response(f) for f in items_raw)
        return cls(
            items=items,
            **res,
        )


class YaUploader(BaseApi):
    """Ya Disk API provider."""
    BASE_URL = "https://cloud-api.yandex.net/v1/disk"

    def __init__(self, token: str):
        self.token = token
        self.__created_folders = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.clean_up()

    @property
    def oauth_token(self) -> str:
        """Header value for OAuth authorization."""
        return F"OAuth {self.token}"

    @property
    def _common_headers(self) -> dict[str, str]:
        """Common headers for all requests."""
        return {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': self.oauth_token,
        }

    def _send_request(
            self,
            method: Callable[..., requests.Response],
            endpoint: str,
            headers: dict[str, str] = None,
            params: dict[str, str] = None,
    ) -> requests.Response:
        if headers is None:
            headers = {}
        if params is None:
            params = {}

        if not endpoint.startswith('/'):
            endpoint = f'/{endpoint}'
        res: requests.Response = method(
            f"{self.BASE_URL}{endpoint}",
            headers=headers | self._common_headers,
            params=params,
        )
        res.raise_for_status()
        return res

    def _wait_operation_success(self, res: requests.Response) -> None:
        """Wait for given API operation to succeed."""
        operation_url: str = res.json()["href"]
        if "/disk/operations/" not in operation_url:
            return
        operation_endpoint = operation_url.removeprefix(self.BASE_URL)
        attempt = 1
        attempts = 60
        while attempt <= attempts:
            if (status := self._send_request(requests.get, operation_endpoint).json()["status"]) == "success":
                return
            elif status == "failed":
                raise requests.HTTPError(f"Failed for {res.url}!")
            print(f"Current status: {status}\nAttempt: {attempt} / {attempts}")
            sleep(1)
            attempt += 1
        raise TimeoutError(f"Creation did not not succeeded")

    def create_folder(self, path: str) -> None:
        """Creates a `path` folder."""
        res = self._send_request(
            requests.put,
            "/resources",
            params={"path": path},
        )
        self._wait_operation_success(res)
        self.__created_folders.append(path)

    def upload_photos_to_yd(self, path: str, url_file: str, name: str) -> None:
        """Upload photo to the `path` with name `name` from `url_file`."""
        res = self._send_request(
            requests.post,
            "/resources/upload",
            # Возможно тут можно юзать питоновый тру, скорее всего - нет.
            params={"path": f'/{path}/{name}', 'url': url_file, "overwrite": "true"},
        )
        self._wait_operation_success(res)

    def get_folder(self, folder_path: str) -> Folder:
        """Get `folder_path` from the disk."""
        res = self._send_request(
            requests.get,
            "/resources",
            params={"path": folder_path},
        )
        return Folder.build_from_response(res.json())

    def clean_up(self):
        """Clean up all folders created by this instance."""
        for folder in self.__created_folders:
            res = self._send_request(
                requests.delete,
                "/resources",
                params={"path": folder, "permanently": "true", }
            )
            if res.status_code != 204:
                self._wait_operation_success(res)
