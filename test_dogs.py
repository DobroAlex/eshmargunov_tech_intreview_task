# Проблемы по убыванию критичности
# 1. Рандомная проверка -- сложности воспроизведения и отладки, неполное покрытие сценариев,
#    т.к. будет вызван только один из кейсов, а второй -- нет.
#    parametrize должен задавать оба сценария как 2 отдельных кейса внутри одного теста.
#    (Или сделать 2 отдельных теста, но не вижу бенефитов, пьюристы восхитятся)
# 2. У запросов нет проверок на статус коды,
#    что при ошибке приведет к парсингу неожиданного response body и соотв рантайм ошибке.
#    Вместо этого надо добавить проверки статус кода и рейзить исклчючения уже на эатпе неожиданного статус кода.
# 3. Нет док-стрингов, нужно открывать функцию чтоб понять что происходит
# 4. Нет тайп хинтов (type annotations) на аргументы функций  и возврат функций (def f_1(arg: int, ......) -> SomeType)
# 5. Класс YaUploader по сути не нужен в текущем виде,
#    т.к. не связывает и не инкаспсулирует ничего, все методы могут быть статическими -> клас не нужен.
#    Варианты:
#    1) (мне больше нравится) перенсти общие части/зависимости в поля/методы класса;
#    тогда класс будет не_бесполезен и будет выполнять ООП задачи
#    2) (мне не нравится, 1970ые стайл) Убрать класс, фукнции сделать незаисимыми как в процедруном программировании. 
#        Нужно будет хендлить общие зависимости - мне не нравится.
# 6. С другой стороны, работа с собачьим АПИ не абстарктизирована
#   (я знаю, что там 1 метод, но есть смысл закладывать архитектуру раньше).
#    Предлагаю сделать класс как в 5->1
# 7. Методы YaUploader слишком прямо взаимодействуют с запросами -- хедеры, бади, етс.
#    Также повторяются ссылки, хедеры, парсинг ошибок (если бы он был).
#    Нужно абстаргировать построение запросов в методах класса. 
#    В идеале -- получать из такого метода не сырые джсоны, а объекты, датакласс в помощь.
#    
# 8. Засвечен токен. Для тестового задания тестовый токен не катастрофа, но реального его нужно брать из
# - файла (гитигнорного чтоб не закомментить в репу)
# - переменной среды (задавать посредством CI раннера) (оптимальный вариант ИМО)
# - хранилища секретов по АПИ
# 9. Метод U имеет странный  нейминг и слишком много responsibilty.
# 10. Создание YaUploader в U нарушает Dependency Injection (soliD)
# 11. Тест не очищает мусор за собой, есть смысл юзать фикстуру
#     (например, контекстный менджер в YaUploader() который будет в __exit__() убирать за собой
# 12. Тест активно работает с сырыми словарями. Лучше получать из методов объекты
# 13. Это однофайльный тест, но в реальном приложении классы YaUploader и прочая должны быть вынесены в отельную папку
#     с фреймворком, в тестах должны быть только тесты.
#     Опять же, для такого маленького теста файла нет смысла заниматься таким переписыванием.
# 14. В u() -> for ulr in urls: происходит что-то непонятное, нужен коммент или вынос в функцию с содержательным именем.
# 15. Несмотря на наличие YaUploader класса, который должен абстрагировать и реализовывать всю работу с диском в себе,
#     тест напрямую ходит в АПИ.
# 16. f-строки для постарения параметров в реквестах, можно использовать params вместо.
# 17. assert True :D
# 18 [Опциональный] assert без сообщений о том что упало. Не во всех коллективах это считается плохо.
# 19. test_proverka -- bad English.
# 20. [Выяснилось в процессе] Файлы в папке могут создаваться не мгновенно, надо ждать синк
# 21. Постоянное дергание собачьего АПИ может исчерпать лимиты, надо кешировать результаты.


import random

import pytest
import requests


class YaUploader:
    def __init__(self):
        pass

    def create_folder(self, path, token):
        url_create = 'https://cloud-api.yandex.net/v1/disk/resources'
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json', 'Authorization': f'OAuth {token}'}
        response = requests.put(f'{url_create}?path={path}', headers = headers)

    def upload_photos_to_yd(self, token, path, url_file, name):
        url = "https://cloud-api.yandex.net/v1/disk/resources/upload"
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json', 'Authorization': f'OAuth {token}'}
        params = {"path": f'/{path}/{name}', 'url': url_file, "overwrite": "true"}
        resp = requests.post(url, headers=headers, params=params)


def get_sub_breeds(breed):
    res = requests.get(f'https://dog.ceo/api/breed/{breed}/list')
    return res.json().get('message', [])


def get_urls(breed, sub_breeds):
    url_images = []
    if sub_breeds:
        for sub_breed in sub_breeds:
            res = requests.get(f"https://dog.ceo/api/breed/{breed}/{sub_breed}/images/random")
            sub_breed_urls = res.json().get('message')
            url_images.append(sub_breed_urls)
    else:
        url_images.append(requests.get(f"https://dog.ceo/api/breed/{breed}/images/random").json().get('message'))
    return url_images


def u(breed):
    sub_breeds = get_sub_breeds(breed)
    urls = get_urls(breed, sub_breeds)
    yandex_client = YaUploader()
    yandex_client.create_folder('test_folder', "AgAAAAAJtest_tokenxkUEdew")
    for url in urls:
        part_name = url.split('/')
        name = '_'.join([part_name[-2], part_name[-1]])
        yandex_client.upload_photos_to_yd("AgAAAAAJtest_tokenxkUEdew", "test_folder", url, name)


@pytest.mark.parametrize('breed', ['doberman', random.choice(['bulldog', 'collie'])])
def test_proverka_upload_dog(breed):
    u(breed)
    # проверка
    url_create = 'https://cloud-api.yandex.net/v1/disk/resources'
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json', 'Authorization': f'OAuth AgAAAAAJtest_tokenxkUEdew'}
    response = requests.get(f'{url_create}?path=/test_folder', headers=headers)
    assert response.json()['type'] == "dir"
    assert response.json()['name'] == "test_folder"
    assert True
    if get_sub_breeds(breed) == []:
        assert len(response.json()['_embedded']['items']) == 1
        for item in response.json()['_embedded']['items']:
            assert item['type'] == 'file'
            assert item['name'].startswith(breed)

    else:
        assert len(response.json()['_embedded']['items']) == len(get_sub_breeds(breed))
        for item in response.json()['_embedded']['items']:
            assert item['type'] == 'file'
            assert item['name'].startswith(breed)

