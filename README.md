# eshmargunov_tech_intreview_task
Fork of https://github.com/eshmargunov/tech_intreview_task

# Замечания по итогу тестирования АПИ
Самая большая проблема -- Диск АПИ может жестко зависать на загрузке тяжелых картинок с Dog API 
и возвращать асинхронный failed status. 
Лечится потенциально ретрай механизмом. 
Похоже на рейт лимит со стороны Dog API, воспроизвести точно не удалось.



# Милые пёсики
У нас есть программа для загрузки [картинок собак](https://dog.ceo/dog-api/documentation).  
На вход подается порода собаки. Функция находит одну случайную картинку этой собаки и загружает её на [Я.Диск](https://yandex.ru/dev/disk/poligon/).
Если у породы есть подпороды, то для каждой подпороды загружается по одной картинки.
Например, для doberman будет одна картинка, а для spaniel 7 картинок по одной на каждую породу.

# Задание:
Для этой программы уже написан тест. Нужно перечислить 10 основных проблем в коде.  
Все найденные проблемы нужно отранжировать по критичности.

# Задание со звёздочкой:
Переписать код, так как Вы считаете нужным, исправив все проблемы.
