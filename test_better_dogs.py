from __future__ import annotations

import abc
import datetime
import enum
import functools
import os
from dataclasses import dataclass, field
from time import sleep
from typing import Callable, Sequence

import pytest
import requests
from pytest_assume.plugin import assume

# Data folder & its path at Ya disk
_DATA_FOLDER_NAME = "test_folder"
_DATA_FOLDER = f"/{_DATA_FOLDER_NAME}"


class ResourceType(enum.Enum):
    """Yandex Disk Resource Type."""
    DIR = "dir"
    FILE = "file"


# NOTE: по-правильному, нейминги и структуры должны быть полностью скопированы отсюда
# https://yandex.ru/dev/disk-api/doc/ru/reference/response-objects
# Но эти доки устарели и реально стриктура данных другая.

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


class BaseApi(abc.ABC):
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

    def create_folder(self, path: str) -> None:
        """Creates a `path` folder."""
        self._send_request(
            requests.put,
            "/resources",
            params={"path": path},
        )
        self.__created_folders.append(path)

    def upload_photos_to_yd(self, path, url_file, name) -> None:
        """Upload photo to the `path` with name `name` from `url_file`."""
        self._send_request(
            requests.post,
            "/resources/upload",
            # Возможно тут можно юзать питоновый тру, скорее всего - нет.
            params={"path": f'/{path}/{name}', 'url': url_file, "overwrite": "true"},
        )

    def get_folder(self, folder_path: str) -> Folder:
        """Get `folder_path` from the disk."""
        res = self._send_request(
            requests.get,
            "/resources",
            params={"path": folder_path},
        )
        return Folder.build_from_response(res.json())

    def wait_for_folder_size(
            self,
            folder_path: str,
            expected_count: int,
    ) -> None:
        """Wait for at least `expected_count` items in folder `folder_path` for a minute."""
        attempt = 1
        attempts = 60
        while attempt <= attempts:
            folder = self.get_folder(folder_path)
            if len(folder.embedded.items) >= expected_count:
                return
            sleep(1)
        raise TimeoutError(f"{folder_path} is still empty!")

    def clean_up(self):
        """Clean up all folders created by this instance."""
        for folder in self.__created_folders:
            self._send_request(
                requests.delete,
                "/resources",
                params={"path": folder}
            ).raise_for_status()


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


def get_photos_and_upload_to_disk(breed: str, yandex_client: YaUploader) -> None:
    sub_breeds = DogCeoApi().get_sub_breeds(breed)
    urls = DogCeoApi().get_urls(breed, sub_breeds)
    yandex_client.create_folder(_DATA_FOLDER_NAME)
    for url in urls:
        part_name = url.split('/')
        name = '_'.join([part_name[-2], part_name[-1]])
        yandex_client.upload_photos_to_yd(_DATA_FOLDER_NAME, url, name)
    yandex_client.wait_for_folder_size(_DATA_FOLDER_NAME, len(urls))


@pytest.fixture(scope="session")
def token():
    """Provide OAUTH token."""
    try:
        return os.environ["OAUTH_TOKEN"]
    except KeyError:
        print(f"OAUTH_TOKEN is missing from the env!")


@pytest.fixture
def yandex_disk_api(token):
    """Provide Yandex Disk API handler."""
    with YaUploader(token=token) as disk_api:
        yield disk_api


@pytest.fixture
def dog_api(token):
    """Provide Dog Ceo API handler."""
    return DogCeoApi()


# NOTE: реализовано как фикстура,
# т.к. предполагается, что повторяется в каждом тесте файла/модуля.
@pytest.fixture
def upload_photos(breed, yandex_disk_api, dog_api):
    """Get photos and upload them to disk."""
    sub_breeds = dog_api.get_sub_breeds(breed)
    urls = dog_api.get_urls(breed, sub_breeds)
    yandex_disk_api.create_folder(_DATA_FOLDER_NAME)
    for url in urls:
        part_name = url.split('/')
        name = '_'.join([part_name[-2], part_name[-1]])
        yandex_disk_api.upload_photos_to_yd(_DATA_FOLDER_NAME, url, name)
    yandex_disk_api.wait_for_folder_size(_DATA_FOLDER_NAME, len(urls))


@pytest.mark.parametrize(
    'breed',
    # NOTE: если данные будут повторяться в других тестах, то нужен общий провайдер
    [
        'doberman',
        'bulldog',
        'collie',
        'spaniel',
    ]
)
def test_upload_dog_photo(breed, upload_photos, yandex_disk_api, dog_api):
    # Если бы не кэширование через декоратор,
    # то надо было вынести вычисление под-пород в фикстуру
    sub_breeds = dog_api.get_sub_breeds(breed)
    
    photo_folder = yandex_disk_api.get_folder(_DATA_FOLDER)
    assert photo_folder.type == ResourceType.DIR
    assert photo_folder.name == _DATA_FOLDER_NAME

    if len(sub_breeds) > 1:
        assert len(photo_folder.embedded.items) == len(sub_breeds)
    else:
        assert len(photo_folder.embedded.items) == 1
    for record in photo_folder.embedded.items:
        with assume:
            assert record.type == ResourceType.FILE
            assert record.name.startswith(breed)
