from __future__ import annotations

import contextlib
import os
from lib2to3.fixes.fix_input import context
from time import sleep

import pytest
import requests
from pytest_assume.plugin import assume

from framework.apis.dog_ceo import DogCeoApi
from framework.apis.yandex_disk import YaUploader, ResourceType

# Data folder & its path at Ya disk
_DATA_FOLDER_NAME = "test_folder"
_DATA_FOLDER = f"/{_DATA_FOLDER_NAME}"


# NOTE: по-правильному, нейминги и структуры должны быть полностью скопированы отсюда
# https://yandex.ru/dev/disk-api/doc/ru/reference/response-objects
# Но эти доки устарели и реально стриктура данных другая.


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
    for task_num, url in enumerate(urls):
        url_as_split = url.split('/')
        extension, specific_breed = url_as_split[-1], url_as_split[-2]
        name = '_'.join((specific_breed, extension))
        max_attempts = 4
        for attempt in range(0, max_attempts + 1):
            try:
                print(f"[Attempt [{attempt + 1}] Executing task # {task_num} {name}")
                yandex_disk_api.upload_photos_to_yd(_DATA_FOLDER_NAME, url, name)
                break
            except requests.HTTPError:
                if attempt == max_attempts:
                    raise
                sleep((attempt + 1) * 10)


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
