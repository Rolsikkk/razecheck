# Razecheck

[![Discord](https://img.shields.io/discord/gRHWVXGVKa?label=Discord&logo=discord&color=5b8cff)](https://discord.gg/gRHWVXGVKa)
**Сервер Discord:** https://discord.gg/gRHWVXGVKa

Инструмент для проверки читеров на серверах **Majestic RP**, **AltV** и других GTA-проектах.  
Запускается на ПК игрока администратором/модератором во время проверки.

---

## Как выглядит

- Тёмное окно 738×372px без рамки с анимированным фоном
- Одна кнопка **CHECK** — нажал и программа всё сделала сама
- После проверки внутри окна появляется панель с результатами

---

## Что делает при нажатии CHECK

### Открывает сайты в браузере

| Сайт | Зачем |
|------|-------|
| Google Activity × 6 | История поиска по словам: `cheats`, `spoofer`, `cheat`, `altv`, `yougame`, `unknowncheats` |
| FunPay | Проверка покупок игровых ценностей |
| GGSel | Проверка покупок |
| PayGame (Majestic RP) | Покупка внутриигровой валюты |
| Oplata.info | История платежей |
| Discord | Переписка, серверы |
| Gmail | Почта |
| Raze.team | Сайт проекта |

### Открывает папки

- `%LocalAppData%` — локальные данные всех программ
- `%AppData%\Microsoft\Windows\Recent` — недавно открытые файлы
- `C:\` — корень диска

### Открывает txt-файл с браузерами

Находит все установленные браузеры (Chrome, Firefox, Edge, Brave, Opera, Opera GX, Yandex) и открывает текстовый файл с их именами и путями.

---

## Панель результатов (после проверки)

После завершения прогресс-бара окно трансформируется в терминальную панель с 5 секциями:

### USB-флешки — последние 10 часов
Читает реестр `USBSTOR` и показывает все USB-накопители (тип Disk), подключавшиеся к ПК за последние 10 часов. Имя устройства + время подключения.

### Recycle Bin — файлы из Корзины
Читает `C:\$Recycle.Bin` текущего пользователя. Показывает оригинальный путь файла и дату удаления.  
**Клик по строке** — восстанавливает файл на место и открывает его.

### Deleted Files — Shadow Copy
Сравнивает текущую файловую систему с последним снимком Windows (VSS).  
Показывает файлы которые были удалены навсегда (не через корзину) — Desktop, Documents, Downloads, Pictures, Videos, Music.  
**Клик по строке** — копирует файл из снимка обратно на место и открывает его.

> Требует наличия хотя бы одного Shadow Copy на компьютере (`vssadmin list shadows`).

### BAM — история запусков
Реестровый ключ `HKLM\SYSTEM\...\bam\State\UserSettings\{SID}` хранит **все** когда-либо запускавшиеся `.exe` файлы с временными метками — даже если программа уже удалена.  
Показывает только подозрительные записи (фильтр по базе имён читов).

### Prefetch — недавние запуски
Сканирует `C:\Windows\Prefetch\*.pf` — системные файлы которые Windows создаёт для каждой запущенной программы.  
Показывает только подозрительные файлы по имени.

---

## База читов (фильтр для BAM и Prefetch)

Программа ищет совпадения со следующими ключевыми словами:

**Majestic RP / AltV:**
```
Euphoria, Amidone, MASON, Mason Private, ProCheat Mason,
Hydrogen, Hydrogen Mod Menu, Ret9, Ret9 AltV,
SKRIPT.gg Menu, Menace, Menace GTA V Mod Menu,
Omni Spoofer, WoodVanish, Wood Vanish, Vanish,
Leet, Leet Majestic, 1337 Cheats,
Phoenix Cheat, Elite Hacks
```

**Общие:**
```
eulen, stand, kiddion, midnight, cherax, lynx, luna, scarlet, flare,
rage, ozark, bigbase, yimmenu, phantom, modest, skuller,
aimbot, wallhack, triggerbot, cheat, hack, inject, injector,
bypass, spoofer, hwid, loader, trainer, menu, external, internal, overlay,
neverlose, fatality, gamesense, aimware, skeet, onetap,
interium, nixware, wearedevs, primordial, pandora, narcotic
```

---

## Стек технологий

- **Python 3.11**
- **PyQt6** — интерфейс, кастомная отрисовка через QPainter
- **winreg** — чтение реестра Windows (USBSTOR, BAM)
- **struct** — парсинг бинарных файлов Корзины (`$I` метаданные)
- **subprocess** — запуск браузера, Explorer, vssadmin
- **PyInstaller** — сборка в `.exe`

---

## Сборка из исходников

```bash
# 1. Установить зависимости
pip install -r client/requirements.txt
pip install pyinstaller

# 2. Сгенерировать иконку
python client/assets/create_icon.py

# 3. Собрать .exe
pyinstaller --onefile --noconsole --name Razecheck \
    --icon=client/assets/icon.ico \
    --add-data "client/config.json;." \
    --add-data "client/assets/icon.ico;assets" \
    --paths client \
    client/main.py
```

Либо запусти `build/build_exe.bat`.

Готовый файл: `dist/Razecheck.exe`

---

## Структура проекта

```
razecheck/
├── build/
│   └── build_exe.bat       # скрипт сборки
└── client/
    ├── main.py              # точка входа
    ├── requirements.txt
    ├── config.json
    ├── assets/
    │   └── create_icon.py   # генератор иконки
    └── ui/
        ├── main_window.py   # главное окно, анимации, логика проверки
        └── cmd_window.py    # панель результатов, BAM, Prefetch, Shadow Copy
```

---

## Важно

- Программа **не отправляет данные** на сервер и не требует интернета
- Все данные читаются локально с ПК
- Предназначена для использования администраторами при живой проверке игрока
