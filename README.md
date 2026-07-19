# Razecheck

[![Discord](https://img.shields.io/badge/Discord-razeteam-E8331A?logo=discord)](https://discord.gg/razeteam)
**Discord:** https://discord.gg/razeteam

Программа для **проверки ПК на наличие читов** на серверах **Majestic RP**, **AltV** и других GTA-проектах.  
Игрок запускает программу сам или по просьбе администратора — она автоматически собирает все улики.

---

## Интерфейс

- Тёмное окно без рамки, сигнально-красный акцент `#E8331A`
- Анимированная рамка-сканер, бегущая по периметру окна
- Глитч-эффект на заголовке — символы случайно меняются и возвращаются обратно
- Кнопка **CHECK** с механической sweep-анимацией при наведении
- После проверки — терминальная панель с CRT-эффектом и typewriter-вводом строк

---

## Что проверяет при нажатии CHECK

### Открывает сайты в браузере

| Сайт | Что ищет |
|------|----------|
| Google Activity × 6 | История поиска: `cheats`, `spoofer`, `cheat`, `altv`, `yougame`, `unknowncheats` |
| FunPay | Покупка игровых ценностей |
| GGSel | Покупка читов / аккаунтов |
| PayGame (Majestic RP) | Покупка внутриигровой валюты |
| Oplata.info | История платежей |
| Discord | Переписка, серверы с читами |
| Gmail | Переписка по почте |
| Raze.team | Сайт проекта |

### Открывает папки

- `%LocalAppData%` — локальные данные всех программ
- `%AppData%\Microsoft\Windows\Recent` — недавно открытые файлы
- `C:\` — корень диска

---

## Панель результатов (после проверки)

После завершения прогресс-бара окно трансформируется в терминальную панель с 7 секциями:

### USB-флешки — последние 10 часов
Читает реестр `USBSTOR` — показывает все USB-накопители, подключавшиеся к ПК за последние 10 часов. Имя устройства + время подключения.

### Recycle Bin — файлы из Корзины
Показывает удалённые файлы с оригинальным путём и датой удаления.  
**Клик по строке** — восстанавливает файл на исходное место и открывает его.

### Deleted Files — Shadow Copy
Сравнивает текущий диск с последним снимком Windows (VSS). Показывает файлы, которые были **полностью удалены** (минуя корзину) — сканирует Desktop, Documents, Downloads, Pictures, Videos, Music.  
**Клик по строке** — восстанавливает файл из снимка.

> Shadow Copy — встроен в Windows, ничего не нужно устанавливать.

### BAM — история всех запусков
Реестровый ключ `HKLM\SYSTEM\...\bam\State\UserSettings\{SID}` хранит **все** когда-либо запускавшиеся `.exe` с временными метками — даже если программа уже удалена.  
Фильтрует по базе известных читов.

### Prefetch — недавние запуски
Сканирует `C:\Windows\Prefetch\*.pf` — системные файлы, которые Windows создаёт для каждой запущенной программы.  
Фильтрует по базе известных читов.

### Браузеры
Показывает все установленные браузеры с путями к исполняемому файлу.  
**Клик по строке** — открывает браузер напрямую.  
Поддерживаются: Chrome, Firefox, Edge, Brave, Opera, Opera GX, Yandex.

### Process Hacker
Проверяет, установлен ли Process Hacker 2 или System Informer (PH3).  
Если программа не найдена, но след остался в Prefetch — тоже будет отмечено.

---

## База читов (фильтр для BAM и Prefetch)

**Majestic RP / AltV:**
```
Euphoria, Amidone, MASON, Mason Private, ProCheat Mason,
Hydrogen, Hydrogen Mod Menu, Ret9, Ret9 AltV,
SKRIPT.gg Menu, Menace, Menace GTA V Mod Menu,
Omni Spoofer, WoodVanish, Wood Vanish, Vanish,
Leet, Leet Majestic, 1337 Cheats, Phoenix Cheat, Elite Hacks
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
- **PyQt6** — интерфейс, кастомная отрисовка через QPainter, анимации QPropertyAnimation
- **winreg** — чтение реестра Windows (USBSTOR, BAM)
- **struct** — парсинг бинарных файлов Корзины (`$I` метаданные)
- **subprocess** — запуск браузера, Explorer, vssadmin
- **PyInstaller** — сборка в `.exe`

---

## Сборка из исходников

```bash
pip install -r client/requirements.txt pyinstaller
python client/assets/create_icon.py
pyinstaller --onefile --noconsole --name Razecheck \
    --icon=client/assets/icon.ico \
    --add-data "client/config.json;." \
    --add-data "client/assets/icon.ico;assets" \
    --paths client \
    client/main.py
```

Готовый файл: `dist/Razecheck.exe`

---

## Структура проекта

```
razecheck/
├── build/
│   └── release.py           # автоматизированный релиз + VirusTotal
└── client/
    ├── main.py
    ├── requirements.txt
    ├── config.json
    ├── assets/
    │   ├── icon.ico
    │   └── create_icon.py   # генератор иконки (без зависимостей)
    └── ui/
        ├── main_window.py   # главное окно, анимации, логика проверки
        └── cmd_window.py    # сканеры: USB, Recycle, Shadow, BAM, Prefetch, PH
```

---

## Важно

- Программа **не отправляет данные** на сервер и не требует интернета
- Все данные читаются локально с ПК игрока
- Работает только на Windows 10 / 11
- Для чтения Prefetch может потребоваться запуск от администратора
