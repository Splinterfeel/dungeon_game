# DungeonClient

Первый Windows-клиент для игрового сервера из корня репозитория.

## Структура

- `Runtime/App` — запуск клиента, выбранный пилот и навигация экранов.
- `Runtime/Contracts` — C#-модели REST/WS-контрактов сервера.
- `Runtime/Networking` — HTTP и WebSocket, появятся вместе с экраном входа.
- `Runtime/Screens` — логин, лобби, гараж, матч и результат.
- `Runtime/Battle` — отображение арены и управление в матче.
- `Editor` — команды Unity для повторяемой подготовки проекта.
- `Tests` — проверки чистой клиентской логики.

Сцену `Assets/DungeonClient/Scenes/Bootstrap.unity` создаёт команда
`Dungeon Client → Создать стартовую сцену`. Она также ставит эту сцену первой
в Build Settings. В неё входит UI Toolkit-экран выбора пилота. В пакетном
запуске Unity вызывается тот же код.

`PilotSelectionScreen` вызывает `GET /pilots`, `POST /pilots` и
`GET /garages/{player_id}`. Адрес сервера задан на `ClientApp` и по умолчанию
указывает на `http://127.0.0.1:8000`.
