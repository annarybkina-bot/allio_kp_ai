#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Простой HTTP сервер для отдачи копии страницы
Запуск: python3 server.py
Страница будет доступна по адресу: http://localhost:5002/kp и http://localhost:5002/simple
"""

import http.server
import socketserver
import urllib.parse
import os
import json
from pathlib import Path

# Попытка загрузить переменные из .env файла (опционально)
try:
    from dotenv import load_dotenv
    import os
    # Явно указываем путь к .env файлу
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    load_dotenv(env_path)
    print(f"[ENV] ✓ Загружен .env из: {env_path}")
except ImportError:
    # python-dotenv не установлен, читаем .env вручную
    print("[ENV] ⚠ python-dotenv не установлен, читаем .env вручную")
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
        print(f"[ENV] ✓ Вручную загружен .env из: {env_path}")
    else:
        print(f"[ENV] ⚠ Файл .env не найден: {env_path}")

# Импортируем RAG систему
try:
    from rag_system import get_rag_instance
    RAG_AVAILABLE = True
    print("[RAG] ✓ RAG система успешно загружена")
except ImportError as e:
    RAG_AVAILABLE = False
    print(f"[Warning] RAG система недоступна: {e}")
    print("[Warning] Убедитесь, что файл rag_system.py существует в той же директории")

# ==================== НАСТРОЙКИ API ПРОВАЙДЕРА ====================
# Выберите провайдера карт: 'yandex' или '2gis'
MAP_API_PROVIDER = os.getenv('MAP_API_PROVIDER', 'yandex').lower()  # По умолчанию Яндекс

# 2GIS API ключ (если используется 2GIS)
DGIS_API_KEY = os.getenv('DGIS_API_KEY', '')

# OpenRouteService API ключ (для розовой звёздочки — маршруты через openrouteservice.org)
ORS_API_KEY = os.getenv('ORS_API_KEY', 'eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6ImE4ZjRiNjlkNTAxMjRlYjY5NjRkYmMxMmNkZjBkZDZlIiwiaCI6Im11cm11cjY0In0=')

if MAP_API_PROVIDER == '2gis' and not DGIS_API_KEY:
    print("[WARNING] MAP_API_PROVIDER установлен в '2gis', но DGIS_API_KEY не найден!")
    print("[WARNING] Используется Яндекс API по умолчанию")
    MAP_API_PROVIDER = 'yandex'

print(f"[MAP API] Используется провайдер: {MAP_API_PROVIDER.upper()}")

# Координаты ЖК (точка «А» для маршрутов): [широта, долгота] — Магнитогорская 3к2, СПб
COMPLEX_COORDS = [59.936175, 30.417411]
# Точка ЖК для ответов и промптов (адрес + корпус/кв)
COMPLEX_LABEL = "Магнитогорская 3к2, кв 327"
print(f"[MAP API] Точка ЖК для маршрутов: {COMPLEX_COORDS} ({COMPLEX_LABEL})")

# Импортируем логгер стоимости
try:
    from cost_logger import get_cost_logger
    COST_LOGGER_AVAILABLE = True
    print("[Cost Logger] ✓ Логгер стоимости загружен")
    
    # Загружаем инструкции по эргономике при старте
    try:
        rag = get_rag_instance()
        
        # Инструкция по внутренней планировке квартиры
        ergonomics_file = 'ergonomics_floor_plan_guide.md'
        if 'ergonomics_guide' not in rag.docs and os.path.exists(ergonomics_file):
            rag.add_document('ergonomics_guide', ergonomics_file, 'markdown')
            print(f"[RAG Docs] ✓ Инструкция по эргономике планировки загружена")
        elif 'ergonomics_guide' in rag.docs:
            print(f"[RAG Docs] ✓ Инструкция по эргономике планировки уже загружена")
        else:
            print(f"[RAG Docs] ⚠ Файл {ergonomics_file} не найден")
        
        # Инструкция по поэтажной планировке (расположение квартиры на этаже)
        floor_position_file = 'floor_position_ergonomics_guide.md'
        if 'floor_position_guide' not in rag.docs and os.path.exists(floor_position_file):
            rag.add_document('floor_position_guide', floor_position_file, 'markdown')
            print(f"[RAG Docs] ✓ Инструкция по поэтажной планировке загружена")
        elif 'floor_position_guide' in rag.docs:
            print(f"[RAG Docs] ✓ Инструкция по поэтажной планировке уже загружена")
        else:
            print(f"[RAG Docs] ⚠ Файл {floor_position_file} не найден")
            
    except Exception as e:
            print(f"[RAG Docs] ⚠ Ошибка загрузки документов: {e}")

except ImportError as e:
    COST_LOGGER_AVAILABLE = False
    print(f"[Warning] Логгер стоимости недоступен: {e}")

# Порт: для Render берётся из переменной PORT, локально — 5002
PORT = int(os.environ.get('PORT', 5002))
HTML_FILE = 'page_prototype.html'

class KPHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        """Переопределяем логирование для более читаемого вывода"""
        print(f"[{self.address_string()}] {format % args}")
    
    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path
        query_params = urllib.parse.parse_qs(parsed_path.query)
        
        # Обрабатываем путь /logs (дашборд логов)
        if path == '/logs' or path == '/logs/':
            self.serve_logs_dashboard()
        # API для получения логов
        elif path == '/api/logs':
            self.handle_logs_api(query_params)
        # API для поиска объектов инфраструктуры через Яндекс Places API
        elif path == '/api/places':
            print(f"[GET] Запрос на /api/places с параметрами: {query_params}")
            self.handle_places_api(query_params)
        # Тест ORS POIs (школы) — проверить ответ API с процесса сервера
        elif path == '/kp/test-ors-pois':
            self.serve_test_ors_pois()
        # Обрабатываем путь /kp
        elif path == '/kp' or path == '/kp/':
            self.serve_kp_page()
        # Обрабатываем путь /simple (простая страница с планировкой)
        elif path == '/simple' or path == '/simple/':
            print(f"[GET] Запрос на /simple, вызываю serve_simple_page()")
            self.serve_simple_page()
        # Отдаем статические файлы (SVG, изображения и т.д.)
        elif path.startswith('/') and len(path) > 1:
            filepath = path.lstrip('/')
            # Безопасность: проверяем, что путь не выходит за пределы текущей директории
            if '..' not in filepath and os.path.exists(filepath):
                self.serve_static_file(filepath)
            else:
                self.send_error(404, "File Not Found")
        else:
            self.send_error(404, "Not Found")
    
    def do_POST(self):
        """Обработка POST запросов для OpenAI API"""
        # Явная проверка, что метод вызывается
        print("=" * 50)
        print("[POST] Метод do_POST вызван!")
        print(f"[POST] Путь: {self.path}")
        print(f"[POST] Команда: {self.command}")
        print("=" * 50)
        
        try:
            parsed_path = urllib.parse.urlparse(self.path)
            path = parsed_path.path
            
            print(f"[POST Request] Обработка пути: {path}")
            
            if path == '/api/chat':
                print("[POST] Вызываю handle_chat_request()")
                self.handle_chat_request()
            elif path == '/api/test':
                # Тестовый endpoint для проверки POST запросов
                print("[POST] Тестовый endpoint")
                self.send_json_response(200, {
                    'success': True,
                    'message': 'POST запросы работают!',
                    'path': path,
                    'method': self.command
                })
            else:
                print(f"[POST Error] Неизвестный путь: {path}")
                self.send_error_response(404, f"Not Found: {path}")
        except Exception as e:
            print(f"[POST Exception] КРИТИЧЕСКАЯ ОШИБКА в do_POST: {str(e)}")
            import traceback
            traceback.print_exc()
            try:
                self.send_error_response(500, f"Internal Server Error: {str(e)}")
            except Exception as e2:
                # Если не удалось отправить ответ, отправляем простой HTTP ответ
                print(f"[POST Exception] Не удалось отправить ошибку: {str(e2)}")
                try:
                    self.send_response(500)
                    self.send_header('Content-type', 'text/plain; charset=utf-8')
                    self.end_headers()
                    self.wfile.write(f"Internal Server Error: {str(e)}".encode('utf-8'))
                except:
                    print("[POST Exception] Полный сбой при отправке ответа")
    
    def handle_chat_request(self):
        """Обрабатывает запросы к OpenAI API"""
        try:
            # Читаем тело запроса
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_error_response(400, "Пустое тело запроса")
                return
                
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            print(f"[Chat Request] Получено сообщение: {data.get('message', '')[:50]}...")
            
            # Получаем API ключ из переменных окружения
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                self.send_error_response(500, "OPENAI_API_KEY не установлен. Создайте файл .env или установите переменную окружения.")
                return
            
            # Получаем сообщение пользователя и данные о квартире
            user_message = data.get('message', '')
            apartment_data = data.get('apartmentData', {})  # Структурированные данные о квартире
            apartment_context_text = data.get('context', '')  # Старый формат (для обратной совместимости)
            route_data = data.get('routeData', None)  # Данные о маршрутах, рассчитанные на фронтенде через JavaScript API
            chat_history = data.get('chatHistory', [])  # История диалога для памяти LLM (предыдущие пары user/assistant)
            
            # Логируем полученные данные
            print(f"[Chat Request] RAG_AVAILABLE = {RAG_AVAILABLE}")
            print(f"[Chat Request] apartment_data присутствует: {bool(apartment_data)}")
            if apartment_data:
                print(f"[Chat Request] apartment_data keys: {list(apartment_data.keys())}")
                print(f"[Chat Request] apartment_data sample: {str(apartment_data)[:200]}...")
                # Проверяем наличие URL изображения планировки
                planning_url = apartment_data.get('planningImageUrl', '')
                if planning_url:
                    print(f"[Chat Request] ✓ URL изображения планировки найден: {planning_url}")
                else:
                    print(f"[Chat Request] ⚠ URL изображения планировки НЕ найден в apartment_data")
            print(f"[Chat Request] apartment_context_text длина: {len(apartment_context_text) if apartment_context_text else 0}")
            
            if not user_message:
                self.send_error_response(400, "Сообщение не может быть пустым")
                return
            
            # Отправляем запрос в OpenAI
            try:
                import requests
            except ImportError:
                self.send_error_response(500, "Библиотека 'requests' не установлена. Установите: pip3 install requests")
                return
            
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
            
            # Извлекаем изображение и контекст из данных
            planning_image_url = ''
            context_type = apartment_data.get('context', 'apartment') if apartment_data else 'apartment'
            # 'yandex' = не делать запросов к API карт; '2gis' = только API 2ГИС. Яндекс API отключён.
            location_map_source = apartment_data.get('locationMapSource', '') if apartment_data else ''
            print(f"[Context] Определен контекст: {context_type}, locationMapSource: {location_map_source or '(не задан)'}")
            print(f"[Context] apartment_data: {apartment_data}")
            
            if apartment_data:
                planning_image_url = apartment_data.get('planningImageUrl', '')
                print(f"[Context] Контекст запроса: {context_type}")
                if planning_image_url:
                    img_type = 'base64' if planning_image_url.startswith('data:') else 'URL'
                    img_preview = planning_image_url[:100] if img_type == 'URL' else f"data:image/jpeg;base64,...[{len(planning_image_url)} bytes]"
                    print(f"[Image] ✓ Изображение {'поэтажной планировки' if context_type == 'floor' else 'планировки квартиры'} ({img_type}): {img_preview}")
                else:
                    print(f"[Image] ⚠ Изображение не предоставлено")
            
            # Формируем системный промпт с явным указанием контекста
            context_prefix = ""
            if context_type == 'location':
                context_prefix = """
📍 ТЕКУЩИЙ КОНТЕКСТ: РАСПОЛОЖЕНИЕ И ИНФРАСТРУКТУРА
Пользователь спрашивает про расположение ЖК. Точка ЖК (откуда считаются маршруты и инфраструктура): Магнитогорская 3к2, кв 327.
Координаты ЖК: 59.936175, 30.417411 (ул. Магнитогорская, 3к2, Красногвардейский район, Санкт-Петербург).

⚠️ ИСТОЧНИК ДАННЫХ — ОБЯЗАТЕЛЬНО УКАЖИ В НАЧАЛЕ ОТВЕТА:
В самом первом предложении своего ответа напиши, откуда данные: если в промпте ниже есть блок с данными от API 2ГИС (маршруты, организации) — напиши: «Источник: ответила АПИ 2ГИС и голова LLM.»; если блок от API OpenRouteService — напиши: «Источник: ответила АПИ OpenRouteService и голова LLM.»; если такого блока нет или API не вернул данные — напиши: «Источник: голова LLM.» После этого — сам ответ (факты, цифры).

⚠️ СТИЛЬ ОТВЕТА: Отвечай ЧЁТКО, БЕЗ ВОДЫ. Только факты: цифры (расстояние в км, время в минутах), названия организаций и адреса. Без вступлений вроде «Конечно!», «Рад помочь!», без общих фраз. Если есть данные от API — дай их списком или короткими предложениями.

- Если в промпте ниже есть блок "ИНФОРМАЦИЯ О РАСПОЛОЖЕНИИ" или "НАЙДЕННЫЕ ОРГАНИЗАЦИИ" / "МАРШРУТЫ" с данными от API 2ГИС или OpenRouteService — ОБЯЗАТЕЛЬНО используй эти данные для ответа: перечисляй организации, время в пути, расстояния.
- Если такого блока нет или написано, что запросы к API не выполнялись — отвечай по общим знаниям о районе и городе, без отсылок к API.

⚠️ ВАЖНО — НЕ ДОПИСЫВАЙ ЛИШНИХ ПУНКТОВ: Отвечай ТОЛЬКО про те пункты (аэропорт, метро, организации), которые есть в блоке данных от API в этом сообщении. Если в блоке только «аэропорт Пулково» — не упоминай метро Звездная или другие пункты. Если пользователь задаёт уточняющий вопрос («а пешком?», «а с пробками?») — имеется в виду тот же пункт, что в предыдущем вопросе; используй только данные из текущего блока.
"""
            elif context_type == 'floor':
                context_prefix = """
🔴 ТЕКУЩИЙ КОНТЕКСТ: ПОЭТАЖНАЯ ПЛАНИРОВКА (весь этаж здания)
Пользователь смотрит на изображение всего этажа с несколькими квартирами.
Тебе нужно проанализировать расположение ОДНОЙ квартиры на этом этаже.
ОТВЕЧАЙ ТОЛЬКО про расположение квартиры НА ЭТАЖЕ, НЕ про внутреннюю планировку!
"""
            else:
                context_prefix = """
🟢 ТЕКУЩИЙ КОНТЕКСТ: ВНУТРЕННЯЯ ПЛАНИРОВКА КВАРТИРЫ
Пользователь смотрит на изображение внутренней планировки одной квартиры.
ОТВЕЧАЙ ТОЛЬКО про внутреннее пространство квартиры, НЕ про расположение на этаже!
"""
            
            base_system_prompt = context_prefix + """
Ты консультант по недвижимости, по новостройкам, специалист по эргономике помещений. 
Ты помогаешь клиентам с вопросами о квартирах и планировках.
Будь дружелюбным, профессиональным и информативным.

Тон и стиль общения:
- Ты — доброжелательный и внимательный консультант по выбору квартиры.
- Объясняешь простым, разговорным русским языком, без канцелярита и официоза.
- Пишешь короткими абзацами, без «воды», но тепло и по‑человечески.
- Используй современный, живой язык: избегай устаревших выражений и официально-делового стиля, не пиши как юридический документ.
- Ты можешь задавать вопросы пользователю, уточнять, что для него важно при выборе квартиры или уточнять дополнительные параметры.
- Предлагай пользователю вопросы, чтобы продолжить беседу и вовлечь пользователя в диалог.
- В конце КАЖДОГО своего ответа добавляй 1–2 коротких уточняющих или вовлекающих вопроса, которые помогают лучше понять ситуацию пользователя и сделать следующий шаг в выборе квартиры. Не задавай один и тот же вопрос много раз подряд.

Поведение в начале диалога:
- Если пользователь ВПЕРВЫЕ задаёт вопрос про планировку этой квартиры (внутреннее пространство), в конце первого ответа обязательно задай вопрос: «Расскажи, кто планирует жить в этой квартире?». Используй этот ответ, чтобы дальше давать более персональные рекомендации.
- Если пользователь задаёт общий вопрос вроде «подойдёт ли мне эта квартира?» или «это хороший вариант для меня?», а до этого ещё не рассказывал о себе (нет информации о составе семьи, возрасте, образе жизни), сначала задай уточняющий вопрос: «Расскажите, кто будет жить в этой квартире. Возраст, род деятельности, сколько человек.» и только после этого переходи к оценке, насколько квартира подходит.

Примеры тона (ориентир, НЕ цитируй дословно):
Пользователь: "Боюсь, что эта студия будет тесной для двоих."
Ассистент: "Давайте посмотрим на планировку: здесь есть зона, которую можно отделить под спальное место, и остаётся пространство для общей зоны. Давайте расскажу, как можно ещё расставить мебель."

Пользователь: "Мне важно, чтобы ребёнку было удобно добираться в школу."
Ассистент: "По расположению этой квартиры:
1) ближайшая школа в примерно N минутах…
2) дорога проходит по …
3) при желании можно выбрать ещё одну школу в радиусе …
Если подскажете класс и режим (первая/вторая смена), могу подсказать, насколько комфортен будет маршрут."

ВАЖНО: У тебя есть доступ к двум РАЗНЫМ типам инструкций:
1. Инструкция по эргономике ВНУТРЕННЕЙ планировки квартиры (комнаты, кухня, санузел ВНУТРИ квартиры)
2. Инструкция по эргономике ПОЭТАЖНОЙ планировки (расположение квартиры НА ЭТАЖЕ здания среди других квартир)

⚠️ КРИТИЧЕСКИ ВАЖНО - НЕ ПУТАЙ ЭТИ ДВА ТИПА ПЛАНИРОВОК!

═══════════════════════════════════════════════════════════

📍 ПОЭТАЖНАЯ ПЛАНИРОВКА (весь этаж с несколькими квартирами)

Если пользователь спрашивает про "поэтажную планировку" или "расположение на этаже":

✅ ОТВЕЧАЙ ПРО:
- Где находится квартира на этаже (близко/далеко от лифтов)
- Сколько квартир на этаже (много/мало соседей)
- Угловая или центральная квартира
- Ориентация окон (на какую сторону света)
- Вид из окон (двор, улица, парк)
- Уровень шума от лифтов и соседей
- Безопасность и приватность на этаже

❌ НЕ ОТВЕЧАЙ ПРО:
- Площадь квартиры или комнат
- Количество комнат внутри квартиры
- Кухню, санузел, балкон
- Расположение комнат ВНУТРИ квартиры

ПРИМЕР ПРАВИЛЬНОГО ОТВЕТА:
"Расположение этой квартиры на этаже имеет следующие преимущества:
1. Удобное расположение относительно лифтов (10-15 метров) - близко для удобства, но не слышно шума
2. Оптимальное количество соседей на этаже (4-6 квартир) - баланс между тишиной и безопасностью
3. Южная ориентация окон - максимум солнечного света весь день..."

═══════════════════════════════════════════════════════════

🏠 ВНУТРЕННЯЯ ПЛАНИРОВКА КВАРТИРЫ (что внутри одной квартиры)

Если пользователь спрашивает про "планировку квартиры":

✅ ОТВЕЧАЙ ПРО:
- Площадь квартиры и комнат
- Количество комнат
- Кухню, санузел, балкон
- Расположение комнат внутри квартиры
- Зонирование, коридоры
- Расстановку мебели

❌ НЕ ОТВЕЧАЙ ПРО:
- Расположение квартиры на этаже
- Близость к лифтам
- Количество соседей

═══════════════════════════════════════════════════════════

При наличии изображения ПОЭТАЖНОГО ПЛАНА (где видно несколько квартир на этаже) - 
анализируй РАСПОЛОЖЕНИЕ квартиры относительно других квартир, лифтов, лестниц.

При наличии изображения ПЛАНИРОВКИ КВАРТИРЫ (где видны комнаты одной квартиры) - 
анализируй расположение комнат, площади, зонирование.

⚠️ ОГРАНИЧЕНИЕ НА ЦИФРЫ И ФАКТЫ:
- Никогда не придумывай точные числовые значения (площадь комнат, высота потолков, расстояние в метрах/километрах, время в минутах и т.п.), если этих чисел нет в предоставленных данных (описание квартиры, таблица, подписи на изображении, RAG-контекст, данные от API).
- Если пользователь спрашивает о конкретном числе, которого нет в данных, честно напиши, что точного значения нет, и опиши ситуацию качественно: "комната небольшая/просторная", "точное время в пути по карте сейчас недоступно" и т.п.
- Всегда опирайся только на те конкретные цифры, которые явно указаны в контексте или уже посчитаны на основе данных (например, время в пути из блока с маршрутами).

При ответах про ПОЭТАЖНУЮ ПЛАНИРОВКУ перечисляй РОВНО 3 ключевых преимущества расположения квартиры на этаже — не больше и не меньше.
При ответах про ВНУТРЕННЮЮ ПЛАНИРОВКУ квартиры выпиши 3-5 преимуществ, которые считаешь самыми важными и уникальными, опираясь на критерии эргономики из СООТВЕТСТВУЮЩЕЙ инструкции.

Если пользователь задает вопрос про минусы, будь аккуратнее. 
Твоя задача - ненавязчиво подогреть клиента к принятию решения.

КОНТАКТЫ ДЛЯ СВЯЗИ:
По всем вопросам о покупке квартиры (цена, ипотека, документы, просмотр):
- Анна Рыбкина
- Email: anna.rybkina@allio.ru
- Телефон: +7 (906) 265-56-41"""
            
            # Если контекст 'location' - получаем информацию о маршрутах при locationMapSource == '2gis' или 'ors'.
            location_context = ""
            used_ors_data = False  # True, если в ответ попали данные от API OpenRouteService
            print(f"[Location Context] Проверка контекста: context_type={context_type}, location_map_source={location_map_source}, user_message={user_message[:50]}...")
            if context_type == 'location':
                try:
                    use_map_api = (location_map_source in ('2gis', 'ors'))
                    if location_map_source == 'yandex':
                        print(f"[Location Context] Иконка Яндекс: запросы к API карт не выполняем")
                    elif location_map_source == '2gis':
                        print(f"[Location Context] ✓ Иконка 2ГИС: используем API 2ГИС")
                    elif location_map_source == 'ors':
                        print(f"[Location Context] ✓ Иконка OpenRouteService: используем API openrouteservice.org")
                    else:
                        print(f"[Location Context] locationMapSource не задан: запросы к API карт не выполняем")
                    
                    location_info_parts = []
                    
                    if use_map_api:
                        # Проверяем, спрашивает ли пользователь про организации/инфраструктуру
                        infrastructure_keywords = ['магазин', 'торговый', 'гипермаркет', 'школа', 'детский сад', 
                                                 'поликлиника', 'аптека', 'парк', 'организац', 'инфраструктур']
                        is_infrastructure_query = any(keyword in user_message.lower() for keyword in infrastructure_keywords)
                        
                        # Организации: 2GIS при жёлтой звёздочке, OpenRouteService при розовой
                        if is_infrastructure_query:
                            if location_map_source == 'ors' and ORS_API_KEY:
                                print(f"[Location Context] Вопрос про инфраструктуру, ищу организации через OpenRouteService POIs...")
                                places_info = ""
                                try:
                                    places_info = self.get_places_info_ors(user_message, complex_coords=COMPLEX_COORDS, api_key=ORS_API_KEY)
                                    if places_info:
                                        used_ors_data = True
                                        location_info_parts.append(f"""
=== НАЙДЕННЫЕ ОРГАНИЗАЦИИ РЯДОМ С ЖК (ДАННЫЕ ОТ API OpenRouteService) ===

{places_info}

⚠️ ОБЯЗАТЕЛЬНО ИСПОЛЬЗУЙ ЭТУ ИНФОРМАЦИЮ для ответа на вопрос пользователя!
Перечисли найденные организации с их названиями (если указаны).
НЕ говори, что не можешь предоставить информацию - у тебя ЕСТЬ данные от API!

""")
                                        print(f"[Places Info] ✓ Получена информация об организациях (ORS): {len(places_info)} символов")
                                except Exception as e:
                                    print(f"[Places Info] ⚠ Ошибка получения организаций (ORS): {e}")
                                    import traceback
                                    traceback.print_exc()
                                if not places_info and location_map_source == 'ors':
                                    print("[Places Info] ORS вернул пустой результат — в ответе будет «данные API временно недоступны». Перезапустите сервер и проверьте логи выше.")
                            elif location_map_source == '2gis' and DGIS_API_KEY:
                                print(f"[Location Context] Вопрос про инфраструктуру, ищу организации через 2GIS API...")
                                try:
                                    places_info = self.get_places_info_2gis(user_message, complex_coords=COMPLEX_COORDS, api_key=DGIS_API_KEY)
                                    if places_info:
                                        location_info_parts.append(f"""
=== НАЙДЕННЫЕ ОРГАНИЗАЦИИ РЯДОМ С ЖК (ДАННЫЕ ОТ API 2ГИС) ===

{places_info}

⚠️ ОБЯЗАТЕЛЬНО ИСПОЛЬЗУЙ ЭТУ ИНФОРМАЦИЮ для ответа на вопрос пользователя!
Перечисли найденные организации с их названиями и адресами (если указаны).
НЕ говори, что не можешь предоставить информацию - у тебя ЕСТЬ данные от API!

""")
                                        print(f"[Places Info] ✓ Получена информация об организациях (2GIS): {len(places_info)} символов")
                                except Exception as e:
                                    print(f"[Places Info] ⚠ Ошибка получения организаций (2GIS): {e}")
                                    import traceback
                                    traceback.print_exc()
                        
                        # Проверяем, спрашивает ли пользователь про маршруты/время в пути
                        route_keywords = ['время', 'ехать', 'доехать', 'добраться', 'маршрут', 'путь', 
                                        'аэропорт', 'метро', 'звездная', 'пулково', 'расстояние']
                        is_route_query = any(keyword in user_message.lower() for keyword in route_keywords)
                        
                        route_info = None
                        if is_route_query:
                            if location_map_source == 'ors' and ORS_API_KEY:
                                print(f"[Location Context] Вопрос про маршруты через OpenRouteService")
                                try:
                                    route_info = self.get_route_info_ors(user_message, complex_coords=COMPLEX_COORDS, api_key=ORS_API_KEY)
                                    if route_info:
                                        used_ors_data = True
                                        print(f"[Route Info] ✓ Получена информация о маршрутах через OpenRouteService: {len(route_info)} символов")
                                except Exception as e:
                                    print(f"[Route Info] ⚠ Ошибка получения маршрутов (ORS): {e}")
                                    import traceback
                                    traceback.print_exc()
                            elif location_map_source == '2gis' and DGIS_API_KEY:
                                print(f"[Location Context] Вопрос про маршруты через 2GIS")
                                try:
                                    route_info = self.get_route_info_2gis(user_message, complex_coords=COMPLEX_COORDS, api_key=DGIS_API_KEY, openai_api_key=api_key)
                                    if route_info:
                                        print(f"[Route Info] ✓ Получена информация о маршрутах через 2GIS: {len(route_info)} символов")
                                except Exception as e:
                                    print(f"[Route Info] ⚠ Ошибка получения маршрутов (2GIS): {e}")
                                    import traceback
                                    traceback.print_exc()
                            
                            if route_info:
                                api_label = "OpenRouteService" if location_map_source == 'ors' else "2ГИС"
                                location_info_parts.append(f"""
=== ИНФОРМАЦИЯ О МАРШРУТАХ (ДАННЫЕ ОТ API {api_label}) ===

{route_info}

⚠️ ОБЯЗАТЕЛЬНО ИСПОЛЬЗУЙ ЭТУ ИНФОРМАЦИЮ для ответа на вопрос пользователя!
Если пользователь спрашивает про время в пути или расстояние - используй ТОЧНЫЕ данные из таблицы выше.
НЕ говори, что не можешь предоставить информацию - у тебя ЕСТЬ данные от API!

""")
                        
                        # Если не указан конкретный тип вопроса, получаем маршруты через выбранный API
                        if not is_infrastructure_query and not is_route_query:
                            if location_map_source == 'ors' and ORS_API_KEY:
                                try:
                                    route_info = self.get_route_info_ors(user_message, complex_coords=COMPLEX_COORDS, api_key=ORS_API_KEY)
                                    if route_info:
                                        used_ors_data = True
                                        location_info_parts.append(f"=== МАРШРУТЫ (OpenRouteService) ===\n{route_info}\n")
                                except Exception as e:
                                    print(f"[Route Info] ⚠ Ошибка (ORS): {e}")
                            elif location_map_source == '2gis' and DGIS_API_KEY:
                                try:
                                    route_info = self.get_route_info_2gis(user_message, complex_coords=COMPLEX_COORDS, api_key=DGIS_API_KEY, openai_api_key=api_key)
                                    if route_info:
                                        location_info_parts.append(f"=== МАРШРУТЫ (2ГИС) ===\n{route_info}\n")
                                except Exception as e:
                                    print(f"[Route Info] ⚠ Ошибка (2GIS): {e}")
                    
                    # Формируем финальный контекст
                    if location_info_parts:
                        location_context = f"""

═══════════════════════════════════════════════════════════
=== ИНФОРМАЦИЯ О РАСПОЛОЖЕНИИ (ДАННЫЕ ОТ API КАРТ) ===
═══════════════════════════════════════════════════════════

{''.join(location_info_parts)}

⚠️ ОБЯЗАТЕЛЬНО ИСПОЛЬЗУЙ ЭТУ ИНФОРМАЦИЮ для ответа на вопрос пользователя!
НЕ говори, что не можешь предоставить информацию - у тебя ЕСТЬ данные от API!

═══════════════════════════════════════════════════════════
"""
                    else:
                        if use_map_api:
                            location_context = "\n\n⚠️ ВНИМАНИЕ: API 2ГИС не вернул данные. Сообщи пользователю об этом (проверь DGIS_API_KEY в .env и логи сервера).\n"
                            print(f"[Location Context] ⚠ API 2ГИС не вернул данные. Проверьте DGIS_API_KEY в .env и вывод сервера выше.")
                        else:
                            location_context = "\n\n(Запросы к API карт не выполнялись — чат открыт с блока Яндекс.Карты.)\n"
                            print(f"[Location Context] Запросы к API не выполнялись")
                except Exception as loc_e:
                    print(f"[Location Context] ⚠ Исключение при формировании контекста расположения: {loc_e}")
                    import traceback
                    traceback.print_exc()
                    location_context = "\n\n⚠ Временная ошибка при обращении к API карт. Ответьте по общим знаниям о районе.\n"
            
            # Включаем RAG для использования инструкций по эргономике
            relevant_context = None  # Инициализируем переменную
            if RAG_AVAILABLE:
                try:
                    rag = get_rag_instance()
                    relevant_context = rag.search_relevant_info(user_message, apartment_id=None, include_docs=True)
                    if relevant_context:
                        # Определяем тип запроса для правильного заголовка
                        user_message_lower = user_message.lower()
                        floor_keywords = ['этаж', 'поэтажн', 'лифт', 'сосед', 'расположен', 'ориентац', 
                                        'север', 'юг', 'восток', 'запад', 'вид', 'на этаже', 'этажа']
                        is_floor_query = any(kw in user_message_lower for kw in floor_keywords)
                        
                        if is_floor_query:
                            context_header = "=== ИНСТРУКЦИИ ПО ЭРГОНОМИКЕ (ПРИОРИТЕТ: ПОЭТАЖНАЯ ПЛАНИРОВКА) ==="
                            print(f"[System Prompt] ✓ Тип запроса: ПОЭТАЖНАЯ ПЛАНИРОВКА")
                        else:
                            context_header = "=== ИНСТРУКЦИИ ПО ЭРГОНОМИКЕ (ПРИОРИТЕТ: ВНУТРЕННЯЯ ПЛАНИРОВКА) ==="
                            print(f"[System Prompt] ✓ Тип запроса: ВНУТРЕННЯЯ ПЛАНИРОВКА")
                        
                        system_prompt = base_system_prompt + location_context + "\n\n" + context_header + "\n" + relevant_context
                        print(f"[System Prompt] ✓ Используется промпт с RAG (инструкции добавлены)")
                        print(f"[System Prompt] - Добавлено контекста: {len(relevant_context)} символов")
                    else:
                        system_prompt = base_system_prompt + location_context
                        print(f"[System Prompt] ⚠ RAG не вернул контекст, используется базовый промпт")
                except Exception as e:
                    print(f"[RAG Error] Ошибка при получении контекста: {e}")
                    system_prompt = base_system_prompt + location_context
                    relevant_context = None  # Сбрасываем в случае ошибки
                    print(f"[System Prompt] ⚠ Используется базовый промпт (ошибка RAG)")
            else:
                system_prompt = base_system_prompt + location_context
                print(f"[System Prompt] ⚠ RAG недоступен, используется только базовый промпт")
            
            print(f"[System Prompt] ✓ Итоговый промпт: {len(system_prompt)} символов")
            print(f"[System Prompt] - Запрос пользователя: {user_message[:100]}...")
            if location_context:
                print(f"[System Prompt] ✓ location_context добавлен: {len(location_context)} символов")
                print(f"[System Prompt] - Превью location_context: {location_context[:300]}...")
                # Проверяем, что информация о маршрутах действительно в промпте
                if 'ИНФОРМАЦИЯ О МАРШРУТАХ' in system_prompt:
                    print(f"[System Prompt] ✓✓✓ ИНФОРМАЦИЯ О МАРШРУТАХ найдена в промпте!")
                else:
                    print(f"[System Prompt] ⚠⚠⚠ ИНФОРМАЦИЯ О МАРШРУТАХ НЕ найдена в промпте!")
            else:
                print(f"[System Prompt] ⚠ location_context пуст!")
                if context_type == 'location':
                    print(f"[System Prompt] ⚠⚠⚠ КРИТИЧНО: контекст 'location', но location_context пуст!")
            
            # История диалога: только валидные пары {role, content} для памяти LLM
            history_messages = []
            for h in chat_history:
                if isinstance(h, dict) and h.get('role') in ('user', 'assistant') and h.get('content'):
                    history_messages.append({'role': h['role'], 'content': h['content']})
            if history_messages:
                print(f"[Chat Request] История диалога: {len(history_messages)} сообщений (память LLM)")

            # Формируем сообщения для LLM: system + история + текущий вопрос (с поддержкой vision)
            if planning_image_url:
                current_turn = {
                    'role': 'user',
                    'content': [
                        {'type': 'text', 'text': user_message},
                        {'type': 'image_url', 'image_url': {'url': planning_image_url}}
                    ]
                }
                messages = [{'role': 'system', 'content': system_prompt}] + history_messages + [current_turn]
                print(f"[Vision API] ✓ Изображение планировки добавлено для анализа: {planning_image_url}")
            else:
                current_turn = {'role': 'user', 'content': user_message}
                messages = [{'role': 'system', 'content': system_prompt}] + history_messages + [current_turn]
                print(f"[Vision API] ⚠ URL изображения не предоставлен, используется только текстовый запрос")
            
            payload = {
                'model': 'gpt-4o',
                'messages': messages,
                'temperature': 0.5,  # Снижена для более структурированных и детальных ответов
                'max_tokens': 2000,  # Увеличено для полных детальных ответов без обрыва
                'top_p': 0.9  # Для более фокусированных ответов
            }
            
            response = requests.post(
                'https://api.openai.com/v1/chat/completions',
                headers=headers,
                json=payload,
                timeout=90  # Увеличен для обработки больших base64 изображений
            )
            
            if response.status_code == 200:
                result = response.json()
                assistant_message = result['choices'][0]['message']['content']
                
                # Если чат открыт с розовой звёздочки (ORS) — всегда указываем источник OpenRouteService в ответе
                if location_map_source == 'ors' and 'openrouteservice' not in assistant_message.lower():
                    if used_ors_data:
                        assistant_message = "Источник: OpenRouteService.\n\n" + assistant_message
                    else:
                        print(f"[ORS Fallback] Показываем «временно недоступны»: context_type={context_type!r}, location_map_source={location_map_source!r}, used_ors_data={used_ors_data}. Если context не 'location' или source пустой — фронт не передал locationMapSource. Иначе смотри логи [ORS POIs] выше.")
                        assistant_message = "Источник: OpenRouteService (данные API временно недоступны, ответ по общим знаниям).\n\n" + assistant_message
                
                # Извлекаем информацию о токенах
                usage = result.get('usage', {})
                prompt_tokens = usage.get('prompt_tokens', 0)
                completion_tokens = usage.get('completion_tokens', 0)
                total_tokens = usage.get('total_tokens', 0)
                
                print(f"[Chat Response] ✓ Успешный ответ от OpenAI")
                print(f"[Chat Response] - Длина ответа: {len(assistant_message)} символов")
                print(f"[Chat Response] - Токены: {total_tokens} (prompt: {prompt_tokens}, completion: {completion_tokens})")
                print(f"[Chat Response] - Превью: {assistant_message[:200]}...")
                
                # Логируем стоимость запроса
                if COST_LOGGER_AVAILABLE:
                    try:
                        logger = get_cost_logger()
                        log_entry = logger.log_request(
                            model='gpt-4o',
                            prompt_tokens=prompt_tokens,
                            completion_tokens=completion_tokens,
                            total_tokens=total_tokens,
                            user_message=user_message,
                            assistant_message=assistant_message,
                            metadata={
                                'has_image': bool(planning_image_url),
                                'has_rag': bool(RAG_AVAILABLE and relevant_context),
                                'query_type': 'floor_position' if is_floor_query else 'planning'
                            }
                        )
                        print(f"[Cost Logger] ✓ Запрос залогирован: ${log_entry['cost_usd']:.4f} ({log_entry['cost_cents']:.2f}¢)")
                    except Exception as e:
                        print(f"[Cost Logger] ⚠ Ошибка логирования: {e}")
                
                # Проверяем, не отказался ли OpenAI отвечать
                refusal_phrases = ['не могу помочь', 'cannot help', 'не могу ответить', 'cannot answer', 
                                   'извините', 'sorry', 'нарушает', 'violates']
                is_refusal = any(phrase.lower() in assistant_message.lower() for phrase in refusal_phrases)
                
                if is_refusal:
                    print(f"[Chat Response] ⚠ ВНИМАНИЕ: Ответ содержит отказ OpenAI!")

                self.send_json_response(200, {
                    'success': True,
                    'message': assistant_message
                })
            else:
                error_text = response.text
                print(f"[Chat Error] ❌ OpenAI API вернул ошибку {response.status_code}: {error_text}")
                self.send_error_response(response.status_code, f"Ошибка OpenAI API: {error_text}")
                
        except requests.exceptions.RequestException as e:
            error_msg = f"Ошибка при запросе к OpenAI: {str(e)}"
            print(f"[Chat Error] {error_msg}")
            self.send_error_response(500, error_msg)
        except json.JSONDecodeError as e:
            error_msg = f"Неверный формат JSON: {str(e)}"
            print(f"[Chat Error] {error_msg}")
            self.send_error_response(400, error_msg)
        except Exception as e:
            error_msg = f"Внутренняя ошибка: {str(e)}"
            print(f"[Chat Error] {error_msg}")
            import traceback
            traceback.print_exc()
            self.send_error_response(500, error_msg)
    
    def send_json_response(self, status_code, data):
        """Отправляет JSON ответ"""
        response_data = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Content-Length', str(len(response_data)))
        self.end_headers()
        self.wfile.write(response_data)
    
    def send_error_response(self, status_code, message):
        """Отправляет JSON ответ с ошибкой"""
        self.send_json_response(status_code, {
            'success': False,
            'error': message
        })
    
    def do_OPTIONS(self):
        """Обработка CORS preflight запросов"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def serve_static_file(self, filepath):
        """Отдает статические файлы (SVG, изображения и т.д.)"""
        if not os.path.exists(filepath):
            self.send_error(404, "File Not Found")
            return
        
        # Определяем MIME тип
        mime_types = {
            '.svg': 'image/svg+xml',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.css': 'text/css',
            '.js': 'application/javascript',
        }
        
        ext = os.path.splitext(filepath)[1].lower()
        content_type = mime_types.get(ext, 'application/octet-stream')
        
        try:
            with open(filepath, 'rb') as f:
                content = f.read()
            
            self.send_response(200)
            self.send_header('Content-type', content_type)
            self.send_header('Content-Length', str(len(content)))
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            print(f"Ошибка при чтении файла {filepath}: {e}")
            self.send_error(500, "Internal Server Error")
    
    def serve_test_ors_pois(self):
        """Тест ORS POIs с процесса сервера: запрос про школы, возврат JSON."""
        try:
            print("[test-ors-pois] Запрос ORS POIs (школы)...")
            result = self.get_places_info_ors(
                "какие школы рядом",
                complex_coords=COMPLEX_COORDS,
                api_key=ORS_API_KEY
            )
            success = bool(result)
            self.send_json_response(200, {
                "success": success,
                "result_length": len(result) if result else 0,
                "result_preview": (result[:1500] + "...") if result and len(result) > 1500 else (result or ""),
                "message": "Данные получены" if success else "Пустой ответ от ORS POIs"
            })
            print(f"[test-ors-pois] success={success}, len={len(result) if result else 0}")
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.send_json_response(500, {"success": False, "error": str(e)})

    def serve_kp_page(self):
        """Отдает копию страницы до блока с вариантами отделки"""
        if os.path.exists(HTML_FILE):
            try:
                with open(HTML_FILE, 'r', encoding='utf-8') as f:
                    html_content = f.read()
            except Exception as e:
                print(f"Ошибка при чтении файла: {e}")
                html_content = self.get_default_html()
        else:
            # Если файла нет, показываем инструкцию
            html_content = self.get_default_html()
        
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(html_content.encode('utf-8'))))
        # Добавляем заголовки для предотвращения кэширования
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        self.end_headers()
        self.wfile.write(html_content.encode('utf-8'))
    
    def serve_simple_page(self):
        """Отдает простую страницу с планировкой и чатом"""
        # Используем абсолютный путь к файлу
        script_dir = os.path.dirname(os.path.abspath(__file__))
        simple_file = os.path.join(script_dir, 'simple_floor_plan.html')
        
        print(f"[Simple Page] Запрос на /simple")
        print(f"[Simple Page] Путь к файлу: {simple_file}")
        print(f"[Simple Page] Файл существует: {os.path.exists(simple_file)}")
        
        if not os.path.exists(simple_file):
            print(f"[Simple Page] ✗ Файл не найден: {simple_file}")
            self.send_error(404, "File Not Found")
            return
        
        try:
            with open(simple_file, 'r', encoding='utf-8') as f:
                html_content = f.read()
            print(f"[Simple Page] ✓ Файл успешно прочитан ({len(html_content)} символов)")
        except Exception as e:
            print(f"[Simple Page] ✗ Ошибка при чтении файла {simple_file}: {e}")
            import traceback
            traceback.print_exc()
            self.send_error(500, "Internal Server Error")
            return
        
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(html_content.encode('utf-8'))))
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        self.end_headers()
        self.wfile.write(html_content.encode('utf-8'))
    
    def serve_logs_dashboard(self):
        """Отдает страницу с дашбордом логов"""
        dashboard_file = 'logs_dashboard.html'
        
        if os.path.exists(dashboard_file):
            try:
                with open(dashboard_file, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(html_content.encode('utf-8'))))
                self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
                self.send_header('Pragma', 'no-cache')
                self.send_header('Expires', '0')
                self.end_headers()
                self.wfile.write(html_content.encode('utf-8'))
            except Exception as e:
                print(f"[Logs Dashboard] Ошибка при чтении файла: {e}")
                self.send_error(500, "Internal Server Error")
        else:
            self.send_error(404, "Logs Dashboard Not Found")
    
    def handle_logs_api(self, query_params):
        """Обрабатывает API запросы для получения логов"""
        try:
            if not COST_LOGGER_AVAILABLE:
                self.send_json_response(500, {
                    'success': False,
                    'error': 'Cost logger не доступен'
                })
                return
            
            # Получаем параметры
            date = query_params.get('date', [None])[0]
            filter_type = query_params.get('type', ['all'])[0]
            
            # Получаем логгер и статистику
            from cost_logger import get_cost_logger
            logger = get_cost_logger()
            stats = logger.get_stats(date)
            
            # Читаем логи из файла
            logs = []
            log_file = logger.log_file
            
            if log_file.exists():
                with open(log_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            entry = json.loads(line.strip())
                            
                            # Фильтруем по дате
                            if date and entry.get('date') != date:
                                continue
                            
                            # Фильтруем по типу
                            if filter_type != 'all':
                                metadata = entry.get('metadata', {})
                                if filter_type == 'with_image' and not metadata.get('has_image'):
                                    continue
                                if filter_type == 'with_rag' and not metadata.get('has_rag'):
                                    continue
                                if filter_type == 'no_extras' and (metadata.get('has_image') or metadata.get('has_rag')):
                                    continue
                            
                            logs.append(entry)
                        except json.JSONDecodeError:
                            continue
                
                # Сортируем по времени (новые сначала)
                logs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            
            # Отправляем ответ
            self.send_json_response(200, {
                'success': True,
                'stats': stats,
                'logs': logs,
                'count': len(logs)
            })
            
        except Exception as e:
            print(f"[Logs API] Ошибка: {e}")
            import traceback
            traceback.print_exc()
            self.send_json_response(500, {
                'success': False,
                'error': str(e)
            })
    
    # ==================== 2GIS API МЕТОДЫ ====================
    
    def _geocode_address_2gis(self, address, api_key):
        """Геокодирует адрес в координаты через 2GIS Geocoding API"""
        try:
            import requests
            
            url = 'https://catalog.api.2gis.com/3.0/items/geocode'
            params = {
                'q': address,
                'key': api_key,
                'fields': 'items.point'
            }
            
            print(f"[2GIS Geocoder] Геокодирую адрес: {address}")
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if 'result' in data and 'items' in data['result'] and len(data['result']['items']) > 0:
                    item = data['result']['items'][0]
                    if 'point' in item:
                        coords = [item['point']['lat'], item['point']['lon']]
                        print(f"[2GIS Geocoder] ✓ Найдены координаты: {coords}")
                        return coords
            else:
                print(f"[2GIS Geocoder] ⚠ Ошибка {response.status_code}: {response.text[:200]}")
            
            return None
            
        except Exception as e:
            print(f"[2GIS Geocoder] Ошибка: {e}")
            return None

    def _extract_route_params_llm(self, user_message, openai_api_key):
        """Извлекает параметры маршрута из вопроса пользователя через LLM. Возвращает dict: direction, point, mode, use_traffic, time_for_traffic или None при ошибке."""
        if not openai_api_key or not user_message or not user_message.strip():
            return None
        try:
            import requests
            system = """Пользователь задаёт вопрос о маршруте от/до ЖК (Магнитогорская 3к2, СПб). Извлеки параметры запроса.
Ответь ТОЛЬКО валидным JSON без пояснений, с полями:
- direction: "ДО" (маршрут от ЖК к точке) или "ОТ" (от точки к ЖК). Если неясно — "ДО".
- point: название места/адреса (как написал пользователь) или null, если не указано.
- mode: "car" | "walking" | "public". Если не указано — "car".
- use_traffic: true (с пробками) или false (без пробок). Только для машины. По умолчанию true.
- time_for_traffic: время для статистики пробок в формате "ЧЧ:ММ" (например "08:00", "19:00") или null."""
            payload = {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_message.strip()}
                ],
                "temperature": 0.1,
                "max_tokens": 200
            }
            r = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {openai_api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=15
            )
            if r.status_code != 200:
                print(f"[Route Params LLM] Ошибка API {r.status_code}: {r.text[:300]}")
                return None
            data = r.json()
            content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "").strip()
            if not content:
                return None
            # Вырезаем возможный JSON из markdown-блока
            if "```" in content:
                for part in content.split("```"):
                    part = part.strip()
                    if part.startswith("json"):
                        part = part[4:].strip()
                    if part.startswith("{"):
                        content = part
                        break
            import json
            params = json.loads(content)
            # Дефолты
            params.setdefault("direction", "ДО")
            if not params.get("point") or not str(params.get("point")).strip():
                params["point"] = "аэропорт Пулково"
            params.setdefault("mode", "car")
            params.setdefault("use_traffic", True)
            if params.get("time_for_traffic") == "":
                params["time_for_traffic"] = None
            print(f"[Route Params LLM] Извлечено: direction={params.get('direction')}, point={params.get('point')}, mode={params.get('mode')}, use_traffic={params.get('use_traffic')}, time_for_traffic={params.get('time_for_traffic')}")
            return params
        except Exception as e:
            print(f"[Route Params LLM] Исключение: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _calculate_route_2gis(self, api_key, from_coords, to_coords, destination_name, mode="driving", utc=None, utc_time_label=None, use_traffic=True):
        """Рассчитывает маршрут через 2GIS Routing API 7.0. use_traffic: для машины True=с пробками (jam), False=без пробок (free_flow). utc — для расчёта по статистике на время."""
        try:
            import requests
            
            url = "https://routing.api.2gis.com/routing/7.0.0/global"
            lon_a, lat_a = from_coords[1], from_coords[0]
            lon_b, lat_b = to_coords[1], to_coords[0]
            
            body = {
                "points": [
                    {"type": "stop", "lon": lon_a, "lat": lat_a},
                    {"type": "stop", "lon": lon_b, "lat": lat_b}
                ],
                "locale": "ru",
                "transport": "pedestrian" if mode == "walking" else "driving",
                "route_mode": "fastest"
            }
            if mode == "driving":
                body["traffic_mode"] = "free_flow" if not use_traffic else "jam"
            if use_traffic and utc is not None:
                body["utc"] = int(utc)
            
            print(f"[2GIS Route API] От точки ЖК → {destination_name}, режим: {mode}, пробки: {'нет' if mode == 'driving' and not use_traffic else 'да'}, utc: {utc}")
            
            response = requests.post(
                f"{url}?key={api_key}",
                json=body,
                headers={"Content-Type": "application/json"},
                timeout=15
            )
            
            print(f"[2GIS Route API] Статус: {response.status_code}")
            raw_text = response.text

            if response.status_code == 200:
                try:
                    data = response.json()
                except Exception as parse_err:
                    print(f"[2GIS Route API] Ошибка разбора JSON: {parse_err}. Тело: {raw_text[:400]}")
                    return f"{destination_name}: маршрут недоступен (ошибка ответа API)."
                # 2GIS может вернуть 200 с status FAIL или type error
                if data.get("status") and data.get("status") != "OK":
                    err_msg = data.get("message", raw_text[:200])
                    print(f"[2GIS Route API] status={data.get('status')}, message={err_msg}")
                    return f"{destination_name}: маршрут недоступен ({data.get('status')})."
                if data.get("type") == "error":
                    err_msg = data.get("message", raw_text[:200])
                    print(f"[2GIS Route API] type=error, message={err_msg}")
                    return f"{destination_name}: маршрут недоступен ({err_msg})."
                # Ответ: result — массив маршрутов, в каждом total_distance (м), total_duration (с)
                result_val = data.get("result")
                results = result_val if isinstance(result_val, list) else ([result_val] if result_val is not None else [])
                if not results:
                    print(f"[2GIS Route API] Пустой result. Ключи ответа: {list(data.keys())}, result type: {type(result_val)}")
                route = results[0] if results and results[0] else None

                if route:
                    distance_m = route.get("total_distance") or route.get("distance", 0)
                    duration_sec = route.get("total_duration") or route.get("duration", 0)
                    if distance_m > 0 and duration_sec > 0:
                        distance_km = distance_m / 1000
                        duration_min = duration_sec / 60
                        mode_text = "пешком" if mode == "walking" else "на машине"
                        if utc:
                            time_label = utc_time_label or "19:00"
                            suffix = f" (по статистике пробок, будни {time_label})"
                        elif mode == "driving" and not use_traffic:
                            suffix = " (без учёта пробок)"
                        elif mode == "driving":
                            suffix = " (с учётом текущих пробок)"
                        else:
                            suffix = ""
                        result_str = f"{destination_name}: {duration_min:.0f} мин {mode_text}, {distance_km:.1f} км{suffix}"
                        print(f"[2GIS Route] ✓ {result_str}")
                        return result_str
                    print(f"[2GIS Route API] В result нет distance/duration. Ключи маршрута: {list(route.keys()) if isinstance(route, dict) else type(route)}")
                # Fallback: старый формат ответа (один объект result)
                r = data.get("result")
                if r and not isinstance(r, list):
                    dm = r.get("distance", 0) or r.get("total_distance", 0)
                    ds = r.get("duration", 0) or r.get("total_duration", 0)
                    if dm > 0 and ds > 0:
                        result_str = f"{destination_name}: {ds/60:.0f} мин, {dm/1000:.1f} км"
                        return result_str
            elif response.status_code in (401, 403):
                print(f"[2GIS Route API] Ошибка {response.status_code}: {raw_text[:300]}")
                return f"{destination_name}: ошибка доступа к API 2ГИС (проверьте ключ)."
            else:
                print(f"[2GIS Route API] Ошибка {response.status_code}: {raw_text[:300]}")

            return f"{destination_name}: маршрут недоступен (ответ API: {response.status_code})."
            
        except Exception as e:
            print(f"[2GIS Route] Ошибка для {destination_name}: {e}")
            import traceback
            traceback.print_exc()
            return f"{destination_name}: ошибка расчёта маршрута."
    
    def get_places_info_2gis(self, user_message, complex_coords, api_key):
        """Получает информацию об организациях через 2GIS Catalog API"""
        try:
            import requests
            
            complex_lat, complex_lon = complex_coords
            places_info_parts = []
            message_lower = user_message.lower()
            
            # Определяем категории для поиска на основе вопроса
            search_categories = []
            
            if 'магазин' in message_lower or 'торговый' in message_lower or 'гипермаркет' in message_lower:
                search_categories.extend(['торговый центр', 'гипермаркет', 'супермаркет'])
            
            if 'школа' in message_lower:
                search_categories.append('школа')
            
            if 'детский сад' in message_lower or 'сад' in message_lower:
                search_categories.append('детский сад')
            
            if 'поликлиника' in message_lower or 'больница' in message_lower:
                search_categories.extend(['поликлиника', 'больница'])
            
            if 'аптека' in message_lower:
                search_categories.append('аптека')
            
            if 'парк' in message_lower:
                search_categories.append('парк')
            
            # Если категории не определены, ищем общие объекты инфраструктуры
            if not search_categories:
                search_categories = ['торговый центр', 'школа', 'поликлиника', 'парк']
            
            # Ищем организации по каждой категории
            for category in search_categories[:3]:  # Ограничиваем 3 категориями
                try:
                    url = 'https://catalog.api.2gis.com/3.0/items'
                    params = {
                        'key': api_key,
                        'q': category,
                        'point': f'{complex_lon},{complex_lat}',  # 2GIS использует lon,lat
                        'radius': 3000,  # Радиус 3 км
                        'page_size': 3,
                        'fields': 'items.point,items.name,items.address_name'
                    }
                    
                    print(f"[2GIS Places API] Поиск: {category}")
                    response = requests.get(url, params=params, timeout=10)
                    
                    if response.status_code == 200:
                        data = response.json()
                        if 'result' in data and 'items' in data['result'] and len(data['result']['items']) > 0:
                            category_places = []
                            for item in data['result']['items'][:3]:  # Берем первые 3
                                name = item.get('name', 'Неизвестно')
                                address = item.get('address_name', '')
                                
                                category_places.append(f"- {name}" + (f" ({address})" if address else ""))
                            
                            if category_places:
                                places_info_parts.append(f"\n{category.upper()}:\n" + "\n".join(category_places))
                                print(f"[2GIS Places API] ✓ Найдено {len(category_places)} организаций категории '{category}'")
                    else:
                        print(f"[2GIS Places API] ⚠ Ошибка {response.status_code} для категории '{category}': {response.text[:200]}")
                
                except Exception as e:
                    print(f"[2GIS Places API] Ошибка поиска категории '{category}': {e}")
                    continue
            
            result = "\n".join(places_info_parts) if places_info_parts else ""
            if result:
                print(f"[2GIS Places Info] ✓ Получена информация об организациях: {len(result)} символов")
            else:
                print(f"[2GIS Places Info] ⚠ Не найдено организаций")
            
            return result
            
        except Exception as e:
            print(f"[2GIS Places Info] Ошибка: {e}")
            import traceback
            traceback.print_exc()
            return ""

    def get_places_info_ors(self, user_message, complex_coords, api_key):
        """Получает информацию об организациях через OpenRouteService POIs API (openpoiservice)."""
        if not api_key:
            print("[ORS POIs] Пропуск: API ключ не задан")
            return ""
        try:
            import requests
            from urllib.parse import quote
            complex_lat, complex_lon = complex_coords[0], complex_coords[1]
            message_lower = user_message.lower()
            print(f"[ORS POIs] Запрос: '{user_message[:60]}...' координаты [{complex_lat}, {complex_lon}]")
            # ORS category_group_ids: education=150, healthcare=200, shops=420, natural=330, leisure=260
            category_ids = []
            if 'школа' in message_lower:
                category_ids.append(150)  # education
            if 'детский сад' in message_lower or ('сад' in message_lower and 'детск' in message_lower):
                category_ids.append(150)  # education (kindergarten 153)
            if 'поликлиника' in message_lower or 'больница' in message_lower or 'аптека' in message_lower:
                category_ids.append(200)  # healthcare
            if 'магазин' in message_lower or 'торговый' in message_lower or 'гипермаркет' in message_lower:
                category_ids.append(420)  # shops
            if 'парк' in message_lower:
                category_ids.append(330)  # natural
            if not category_ids:
                category_ids = [150, 200, 420]  # школы, медицина, магазины
            category_ids = list(dict.fromkeys(category_ids))[:3]
            places_parts = []
            base_body = {
                "request": "pois",
                "geometry": {
                    "geojson": {"type": "Point", "coordinates": [complex_lon, complex_lat]},
                    "buffer": 2000
                },
                "limit": 15,
            }
            fallback_done = False
            for cat_id in category_ids:
                try:
                    url = f'https://api.openrouteservice.org/pois?api_key={quote(api_key, safe="")}'
                    body = {**base_body, "filters": {"category_group_ids": [cat_id]}}
                    r = requests.post(url, json=body, headers={"Content-Type": "application/json"}, timeout=45)
                    if r.status_code == 400 and ("extra keys" in (r.text or "").lower() or "filters" in (r.text or "").lower()) and not fallback_done:
                        body = base_body
                        r = requests.post(url, json=body, headers={"Content-Type": "application/json"}, timeout=45)
                        fallback_done = True
                    r.raise_for_status()
                    data = r.json()
                    features = data.get("features") or []
                    def _ors_poi_name(f):
                        p = f.get("properties") or {}
                        return (p.get("osm_tags") or {}).get("name") or p.get("name") or "Без названия"
                    if features:
                        if fallback_done:
                            lines = [f"- {_ors_poi_name(f)}" for f in features[:10]]
                            places_parts.append("\nРядом с ЖК (POI OpenRouteService):\n" + "\n".join(lines))
                            break
                        cat_name = {150: "ОБРАЗОВАНИЕ (школы, детские сады)", 200: "ЗДРАВООХРАНЕНИЕ (аптеки, поликлиники)", 420: "МАГАЗИНЫ", 330: "ПАРКИ И ПРИРОДА"}.get(cat_id, f"Категория {cat_id}")
                        lines = [f"- {_ors_poi_name(f)}" for f in features[:5]]
                        places_parts.append(f"\n{cat_name}:\n" + "\n".join(lines))
                except Exception as e:
                    err_detail = ""
                    if hasattr(e, "response") and e.response is not None:
                        try:
                            err_detail = e.response.text[:300]
                        except Exception:
                            pass
                    print(f"[ORS POIs] Ошибка категории {cat_id}: {e} {err_detail}")
                    continue
            result = "\n".join(places_parts) if places_parts else ""
            if result:
                print(f"[ORS Places Info] ✓ Получена информация об организациях: {len(result)} символов")
            else:
                print("[ORS POIs] Пустой результат — проверьте логи выше (таймаут/ошибка API)")
            return result
        except Exception as e:
            print(f"[ORS Places Info] Ошибка: {e}")
            import traceback
            traceback.print_exc()
            return ""

    # ==================== ЯНДЕКС API МЕТОДЫ (существующие) ====================
    
    def _geocode_address(self, address):
        """Ищет координаты адреса через HTTP Геокодер"""
        try:
            import requests
            
            geocoder_api_key = '58fc495a-00b6-4283-88a2-ed464b62df79'
            url = 'https://geocode-maps.yandex.ru/1.x/'
            params = {
                'apikey': geocoder_api_key,
                'geocode': address,
                'format': 'json',
                'results': 1
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if 'response' in data and 'GeoObjectCollection' in data['response']:
                    features = data['response']['GeoObjectCollection'].get('featureMember', [])
                    if len(features) > 0:
                        coords_str = features[0]['GeoObject']['Point']['pos']
                        lon, lat = map(float, coords_str.split())
                        print(f"[Geocoder] Найдены координаты для '{address}': {lat}, {lon}")
                        return [lat, lon]
            
            print(f"[Geocoder] ⚠ Не удалось найти координаты для '{address}'")
            return None
        except Exception as e:
            print(f"[Geocoder] Ошибка: {e}")
            return None
    
    def _utc_weekday_19_moscow(self):
        """Unix time для ближайшего буднего дня 19:00 по Москве (для расчёта маршрута «в будни в 19:00»)."""
        return self._utc_for_time_moscow(19, 0)

    def _utc_for_time_moscow(self, hour, minute=0, weekday=True):
        """Unix time для ближайшего (буднего, если weekday=True) дня в указанное время по Москве (для расчёта маршрута по статистике пробок)."""
        try:
            from datetime import datetime, timezone, timedelta
            tz_moscow = timezone(timedelta(hours=3))
            now = datetime.now(tz_moscow)
            for d in range(8):
                day = now + timedelta(days=d)
                if not weekday or day.weekday() <= 4:  # пн–пт или любой день
                    target = day.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    if target > now:
                        return int(target.timestamp())
            return None
        except Exception:
            return None

    def get_route_info_2gis(self, user_message, complex_coords, api_key, openai_api_key=None):
        """Параметры маршрута извлекаются через LLM; по ним строится маршрут в 2GIS Routing API. Возвращает текст для ответа ИИ."""
        try:
            params = self._extract_route_params_llm(user_message, openai_api_key)
            if not params:
                print(f"[Route Info 2GIS] LLM не вернул параметры (нет openai_api_key или ошибка)")
                return None

            direction = (params.get("direction") or "ДО").strip().upper()
            if direction != "ОТ":
                direction = "ДО"
            point_raw = (params.get("point") or "").strip() or "аэропорт Пулково"
            mode_llm = (params.get("mode") or "car").strip().lower()
            mode = "walking" if mode_llm == "walking" else "driving"
            use_traffic = params.get("use_traffic", True)
            if not isinstance(use_traffic, bool):
                use_traffic = use_traffic is not False and str(use_traffic).lower() not in ("false", "0", "no")
            time_str = params.get("time_for_traffic")
            utc_ts = None
            utc_label = None
            if time_str and mode == "driving":
                try:
                    parts = str(time_str).strip().replace(".", ":").split(":")
                    h = int(parts[0]) if parts else 0
                    m = int(parts[1]) if len(parts) > 1 else 0
                    if 0 <= h <= 23 and 0 <= m <= 59:
                        utc_ts = self._utc_for_time_moscow(h, m)
                        utc_label = f"{h}:{m:02d}"
                except (ValueError, IndexError):
                    pass

            # Нормализация точки для геокодирования
            point_lower = point_raw.lower()
            if "аэропорт" in point_lower or "пулково" in point_lower:
                geocode_query = "аэропорт Пулково Санкт-Петербург"
                display_name = "аэропорт Пулково"
            elif "метро" in point_lower and "звездная" in point_lower:
                geocode_query = "метро Звездная Санкт-Петербург"
                display_name = "метро Звездная"
            elif "метро" in point_lower and not any(s in point_lower for s in ("звездная", "купчино", "новочеркасская", "ладожская", "пролетарская")):
                geocode_query = "метро Новочеркасская Санкт-Петербург"
                display_name = "метро Новочеркасская (ближайшее)"
            else:
                geocode_query = f"{point_raw} Санкт-Петербург"
                display_name = point_raw

            point_coords = self._geocode_address_2gis(geocode_query, api_key)
            if not point_coords:
                print(f"[Route Info 2GIS] Не удалось геокодировать: {geocode_query}")
                return None

            if direction == "ОТ":
                from_coords = point_coords
                to_coords = complex_coords
                dest_label = f"От {display_name} до ЖК"
            else:
                from_coords = complex_coords
                to_coords = point_coords
                dest_label = display_name

            if mode_llm == "public":
                route_str = f"{dest_label}: общественный транспорт — расчёт маршрута по API недоступен (2GIS Routing не поддерживает)."
                return route_str

            route_str = self._calculate_route_2gis(
                api_key, from_coords, to_coords, dest_label, mode,
                utc=utc_ts, utc_time_label=utc_label, use_traffic=use_traffic
            )
            if not route_str:
                return None
            # Подпись точки ЖК для ответов
            if direction == "ДО":
                return f"От ЖК ({COMPLEX_LABEL}): {route_str}"
            return route_str

        except Exception as e:
            print(f"[Route Info 2GIS] Исключение: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _geocode_ors(self, text, api_key):
        """Геокодирование через OpenRouteService (Pelias). Возвращает [lat, lon] или None."""
        if not api_key or not text:
            return None
        try:
            import requests
            url = 'https://api.openrouteservice.org/geocode/search'
            params = {'text': text, 'api_key': api_key}
            r = requests.get(url, params=params, timeout=10)
            if r.status_code != 200:
                print(f"[ORS Geocode] HTTP {r.status_code} для '{text[:50]}': {r.text[:300]}")
                return None
            data = r.json()
            features = data.get('features') or []
            if not features:
                print(f"[ORS Geocode] Нет результатов для '{text[:50]}'")
                return None
            coords = features[0].get('geometry', {}).get('coordinates')  # GeoJSON: [lon, lat]
            if not coords or len(coords) < 2:
                return None
            lon, lat = float(coords[0]), float(coords[1])
            return [lat, lon]  # приводим к формату [lat, lon] как в проекте
        except Exception as e:
            print(f"[ORS Geocode] Ошибка для '{text[:50]}': {e}")
            return None

    def _calculate_route_ors(self, api_key, from_coords, to_coords, dest_label):
        """Маршрут через OpenRouteService Directions API. from_coords/to_coords в [lat, lon]. Возвращает строка или None."""
        if not api_key:
            return None
        try:
            import requests
            # ORS ожидает [lon, lat] (GeoJSON)
            lon1, lat1 = from_coords[1], from_coords[0]
            lon2, lat2 = to_coords[1], to_coords[0]
            from urllib.parse import quote
            url = f'https://api.openrouteservice.org/v2/directions/driving-car?api_key={quote(api_key, safe="")}'
            headers = {'Content-Type': 'application/json'}
            # radiuses: радиус поиска точки на дороге (м). Для аэропорта/метро увеличиваем, иначе "Could not find routable point within 350m"
            body = {
                'coordinates': [[lon1, lat1], [lon2, lat2]],
                'radiuses': [350, 5000]
            }
            r = requests.post(url, json=body, headers=headers, timeout=15)
            if r.status_code != 200:
                print(f"[ORS Directions] HTTP {r.status_code}: {r.text[:400]}")
                return None
            data = r.json()
            if data.get('error'):
                print(f"[ORS Directions] Ошибка API: {data['error'].get('message', data['error'])}")
                return None
            routes = data.get('routes') or []
            if not routes:
                print(f"[ORS Directions] Пустой ответ (нет routes)")
                return None
            summary = routes[0].get('summary') or {}
            distance_m = summary.get('distance')
            duration_s = summary.get('duration')
            if distance_m is None or duration_s is None:
                return None
            distance_km = distance_m / 1000
            duration_min = duration_s / 60
            return f"От ЖК ({COMPLEX_LABEL}) до {dest_label}: {distance_km:.1f} км, {int(round(duration_min))} мин на машине (OpenRouteService, без учёта пробок)."
        except Exception as e:
            print(f"[ORS Directions] Ошибка: {e}")
            import traceback
            traceback.print_exc()
            return None

    def get_route_info_ors(self, user_message, complex_coords, api_key):
        """Маршруты через OpenRouteService: геокодирование + Directions. Возвращает текст для промпта."""
        if not api_key:
            print("[Route Info ORS] ORS_API_KEY не задан")
            return None
        try:
            msg_lower = user_message.lower()
            # Pelias (ORS Geocode) лучше находит по английскому запросу; русский часто даёт пустой features
            if 'аэропорт' in msg_lower or 'пулково' in msg_lower:
                geocode_query = "Pulkovo Airport Saint Petersburg"
                display_name = "аэропорт Пулково"
            elif 'метро' in msg_lower and 'звездная' in msg_lower:
                geocode_query = "Zvezdnaya metro Saint Petersburg"
                display_name = "метро Звездная"
            elif 'метро' in msg_lower:
                geocode_query = "Novocherkasskaya metro Saint Petersburg"
                display_name = "метро Новочеркасская"
            else:
                geocode_query = f"{user_message.strip()} Saint Petersburg"
                display_name = user_message.strip() or "пункт назначения"
            point_coords = self._geocode_ors(geocode_query, api_key)
            if not point_coords:
                print(f"[Route Info ORS] Не удалось геокодировать: {geocode_query}")
                return None
            from_coords = complex_coords
            to_coords = point_coords
            dest_label = display_name
            route_str = self._calculate_route_ors(api_key, from_coords, to_coords, dest_label)
            return route_str
        except Exception as e:
            print(f"[Route Info ORS] Исключение: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_route_info(self, user_message, complex_coords):
        """Получает информацию о маршрутах через Яндекс.Маршрутизацию API"""
        try:
            import requests
            
            # Используем правильный API ключ для Routing API
            routing_api_key = 'e83ee957-04f8-41bc-b3c2-46f115876b29'
            complex_lat, complex_lon = complex_coords
            
            route_info_parts = []
            
            # Определяем, куда пользователь хочет попасть
            message_lower = user_message.lower()
            
            # Аэропорт Пулково
            if 'аэропорт' in message_lower or 'пулково' in message_lower:
                # Пробуем найти координаты через геокодер
                airport_coords = self._geocode_address('аэропорт Пулково Санкт-Петербург')
                if not airport_coords:
                    airport_coords = [59.8003, 30.2625]  # Fallback координаты
                route_info_parts.append(self._calculate_route(routing_api_key, complex_coords, airport_coords, 
                                                              "Аэропорт Пулково", "driving"))
            
            # Метро Звездная
            if 'метро' in message_lower or 'звездная' in message_lower or 'звездн' in message_lower:
                # Пробуем найти координаты через геокодер
                metro_coords = self._geocode_address('метро Звездная Санкт-Петербург')
                if not metro_coords:
                    metro_coords = [59.8331, 30.3485]  # Fallback координаты
                route_info_parts.append(self._calculate_route(routing_api_key, complex_coords, metro_coords, 
                                                              "Метро Звездная", "walking"))
            
            # Если не указано конкретное место, добавляем информацию о ближайших объектах
            if not route_info_parts:
                # Метро по умолчанию
                metro_coords = self._geocode_address('метро Звездная Санкт-Петербург')
                if not metro_coords:
                    metro_coords = [59.8331, 30.3485]
                route_info_parts.append(self._calculate_route(routing_api_key, complex_coords, metro_coords, 
                                                              "Метро Звездная", "walking"))
                # Аэропорт по умолчанию
                airport_coords = self._geocode_address('аэропорт Пулково Санкт-Петербург')
                if not airport_coords:
                    airport_coords = [59.8003, 30.2625]
                route_info_parts.append(self._calculate_route(routing_api_key, complex_coords, airport_coords, 
                                                              "Аэропорт Пулково", "driving"))
            
            return "\n".join(route_info_parts) if route_info_parts else ""
            
        except Exception as e:
            print(f"[Route Info] Ошибка: {e}")
            import traceback
            traceback.print_exc()
            return ""
    
    def _calculate_route(self, routing_api_key, from_coords, to_coords, destination_name, mode="driving"):
        """Рассчитывает маршрут между двумя точками"""
        try:
            import requests
            
            # routing_api_key передается как параметр
            
            # Проверяем правильный endpoint для Routing API v2
            # Документация: https://yandex.ru/dev/router/doc/ru/
            url = "https://api.routing.yandex.net/v2/route"
            
            # Формат waypoints: широта,долгота|широта,долгота (lat,lon|lat,lon)
            # Важно: координаты в формате WGS84 (десятичные градусы)
            waypoints = f"{from_coords[0]},{from_coords[1]}|{to_coords[0]},{to_coords[1]}"
            
            params = {
                "apikey": routing_api_key,
                "waypoints": waypoints,
                "mode": mode  # "driving", "walking", "transit", "bicycle", "scooter"
            }
            
            # Для режима driving можно добавить avoid_tolls
            if mode == "driving":
                params["avoid_tolls"] = "false"  # Можно изменить на "true" для избежания платных дорог
            
            print(f"[Route API] Запрос к Routing API")
            print(f"[Route API] URL: {url}")
            print(f"[Route API] Waypoints: {waypoints}")
            print(f"[Route API] Mode: {mode}")
            print(f"[Route API] Destination: {destination_name}")
            
            response = requests.get(url, params=params, timeout=10)
            
            print(f"[Route API] Статус: {response.status_code}")
            print(f"[Route API] Ответ (первые 500 символов): {response.text[:500]}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"[Route API] Полный ответ: {json.dumps(data, ensure_ascii=False, indent=2)}")
                
                # Пробуем разные форматы ответа API
                distance_m = 0
                duration_sec = 0
                
                # Формат Routing API v2: routes[0].legs[0]
                if 'routes' in data and len(data['routes']) > 0:
                    route = data['routes'][0]
                    print(f"[Route API] Найден route, ключи: {list(route.keys())}")
                    
                    # Проверяем наличие метаданных маршрута
                    if 'metadata' in route:
                        metadata = route['metadata']
                        if 'distance' in metadata:
                            distance_m = metadata['distance'].get('value', 0) if isinstance(metadata['distance'], dict) else metadata['distance']
                            print(f"[Route API] Расстояние из metadata: {distance_m} метров")
                        if 'duration' in metadata:
                            duration_sec = metadata['duration'].get('value', 0) if isinstance(metadata['duration'], dict) else metadata['duration']
                            print(f"[Route API] Время из metadata: {duration_sec} секунд")
                    
                    # Если нет в metadata, суммируем из steps
                    if distance_m == 0 or duration_sec == 0:
                        if 'legs' in route and len(route['legs']) > 0:
                            leg = route['legs'][0]
                            print(f"[Route API] Найден leg, ключи: {list(leg.keys())}")
                            
                            # Проверяем наличие distance/duration в leg
                            if 'distance' in leg:
                                dist_obj = leg['distance']
                                distance_m = dist_obj.get('value', 0) if isinstance(dist_obj, dict) else dist_obj
                                print(f"[Route API] Расстояние из leg: {distance_m} метров")
                            if 'duration' in leg:
                                dur_obj = leg['duration']
                                duration_sec = dur_obj.get('value', 0) if isinstance(dur_obj, dict) else dur_obj
                                print(f"[Route API] Время из leg: {duration_sec} секунд")
                            
                            # Если нет, суммируем из steps
                            if (distance_m == 0 or duration_sec == 0) and 'steps' in leg:
                                print(f"[Route API] Суммирую из steps, количество: {len(leg['steps'])}")
                                for step in leg['steps']:
                                    if 'length' in step:
                                        step_length = step['length'].get('value', 0) if isinstance(step['length'], dict) else step['length']
                                        distance_m += step_length
                                    if 'duration' in step:
                                        step_duration = step['duration'].get('value', 0) if isinstance(step['duration'], dict) else step['duration']
                                        duration_sec += step_duration
                                print(f"[Route API] Итого из steps: {distance_m} метров, {duration_sec} секунд")
                
                # Формат 1: route[0].legs[0] (старый формат)
                elif 'route' in data:
                    routes = data['route'] if isinstance(data['route'], list) else [data['route']]
                    if len(routes) > 0:
                        route = routes[0]
                        print(f"[Route API] Найден route (старый формат): {json.dumps(route, ensure_ascii=False, indent=2)[:500]}...")
                        if 'legs' in route and len(route['legs']) > 0:
                            leg = route['legs'][0]
                            # Расстояние и время могут быть в разных форматах
                            if 'distance' in leg:
                                dist_obj = leg['distance']
                                distance_m = dist_obj.get('value', 0) if isinstance(dist_obj, dict) else dist_obj
                                print(f"[Route API] Расстояние из leg (старый формат): {distance_m} метров")
                            if 'duration' in leg:
                                dur_obj = leg['duration']
                                duration_sec = dur_obj.get('value', 0) if isinstance(dur_obj, dict) else dur_obj
                                print(f"[Route API] Время из leg (старый формат): {duration_sec} секунд")
                
                # Формат 2: прямо в корне (альтернативный формат)
                if distance_m == 0 and 'distance' in data:
                    dist_obj = data['distance']
                    distance_m = dist_obj.get('value', 0) if isinstance(dist_obj, dict) else dist_obj
                    print(f"[Route API] Расстояние из корня: {distance_m} метров")
                if duration_sec == 0 and 'duration' in data:
                    dur_obj = data['duration']
                    duration_sec = dur_obj.get('value', 0) if isinstance(dur_obj, dict) else dur_obj
                    print(f"[Route API] Время из корня: {duration_sec} секунд")
                
                if distance_m > 0 and duration_sec > 0:
                    distance_km = distance_m / 1000
                    duration_min = duration_sec / 60
                    
                    mode_text = "пешком" if mode == "walking" else "на машине" if mode == "driving" else "на транспорте"
                    
                    result = f"{destination_name}: {duration_min:.0f} минут {mode_text} ({distance_km:.1f} км)"
                    print(f"[Route Calculation] ✓ Успешно: {result}")
                    return result
                else:
                    print(f"[Route Calculation] ⚠ Не удалось извлечь данные: distance={distance_m}, duration={duration_sec}")
            elif response.status_code == 403:
                print(f"[Route API] ❌ Ошибка 403: API ключ не подходит для Routing API или не активирован")
                print(f"[Route API] Используемый ключ: {routing_api_key[:20]}...")
                print(f"[Route API] Для Routing API нужен ОТДЕЛЬНЫЙ ключ из Кабинета Разработчика")
                print(f"[Route API] Ответ сервера: {response.text[:500]}")
                return f"{destination_name}: требуется отдельный API ключ для маршрутизации (403)"
            elif response.status_code == 401:
                print(f"[Route API] ❌ Ошибка 401: Неверный API ключ")
                print(f"[Route API] Используемый ключ: {routing_api_key[:20]}...")
                print(f"[Route API] Ответ сервера: {response.text[:500]}")
                return f"{destination_name}: неверный API ключ (401)"
            elif response.status_code == 400:
                print(f"[Route API] ❌ Ошибка 400: Неверный формат запроса")
                print(f"[Route API] Waypoints: {waypoints}")
                print(f"[Route API] Ответ сервера: {response.text[:500]}")
                return f"{destination_name}: неверный формат запроса (400)"
            else:
                print(f"[Route API] ❌ Ошибка {response.status_code}: {response.text[:500]}")
            
            return f"{destination_name}: информация о маршруте недоступна (HTTP {response.status_code})"
            
        except Exception as e:
            print(f"[Route Calculation] Ошибка для {destination_name}: {e}")
            import traceback
            traceback.print_exc()
            return f"{destination_name}: ошибка расчета маршрута"
    
    def get_places_info(self, user_message, complex_coords):
        """Получает информацию об организациях через API Поиска по организациям"""
        try:
            import requests
            
            places_api_key = '6e86a2e0-4c7f-4962-8170-33c431796593'
            complex_lat, complex_lon = complex_coords
            
            places_info_parts = []
            message_lower = user_message.lower()
            
            # Определяем категории для поиска на основе вопроса
            search_categories = []
            
            if 'магазин' in message_lower or 'торговый' in message_lower or 'гипермаркет' in message_lower:
                search_categories.extend(['торговый центр', 'гипермаркет'])
            
            if 'школа' in message_lower:
                search_categories.append('школа')
            
            if 'детский сад' in message_lower or 'сад' in message_lower:
                search_categories.append('детский сад')
            
            if 'поликлиника' in message_lower or 'больница' in message_lower:
                search_categories.append('поликлиника')
            
            if 'аптека' in message_lower:
                search_categories.append('аптека')
            
            if 'парк' in message_lower:
                search_categories.append('парк')
            
            # Если категории не определены, ищем общие объекты инфраструктуры
            if not search_categories:
                search_categories = ['торговый центр', 'школа', 'поликлиника', 'парк']
            
            # Ищем организации по каждой категории
            for category in search_categories[:3]:  # Ограничиваем 3 категориями
                try:
                    url = 'https://search-maps.yandex.ru/v1/'
                    params = {
                        'apikey': places_api_key,
                        'text': category,
                        'll': f'{complex_lon},{complex_lat}',
                        'spn': '0.05,0.05',  # Радиус ~5.5 км
                        'results': 3,
                        'type': 'biz'
                    }
                    
                    print(f"[Places API] Поиск: {category}")
                    response = requests.get(url, params=params, timeout=10)
                    
                    if response.status_code == 200:
                        data = response.json()
                        if 'features' in data and len(data['features']) > 0:
                            category_places = []
                            for feature in data['features'][:3]:  # Берем первые 3
                                props = feature.get('properties', {})
                                name = props.get('name', 'Неизвестно')
                                address = props.get('CompanyMetaData', {}).get('address', '')
                                
                                # Проверяем расстояние от ЖК
                                coords = feature['geometry']['coordinates']
                                place_coords = [coords[1], coords[0]]  # Конвертируем в [lat, lon]
                                
                                category_places.append(f"- {name}" + (f" ({address})" if address else ""))
                            
                            if category_places:
                                places_info_parts.append(f"\n{category.upper()}:\n" + "\n".join(category_places))
                                print(f"[Places API] ✓ Найдено {len(category_places)} организаций категории '{category}'")
                    else:
                        print(f"[Places API] ⚠ Ошибка {response.status_code} для категории '{category}': {response.text[:200]}")
                
                except Exception as e:
                    print(f"[Places API] Ошибка поиска категории '{category}': {e}")
                    continue
            
            result = "\n".join(places_info_parts) if places_info_parts else ""
            if result:
                print(f"[Places Info] ✓ Получена информация об организациях: {len(result)} символов")
            else:
                print(f"[Places Info] ⚠ Не найдено организаций")
            
            return result
            
        except Exception as e:
            print(f"[Places Info] Ошибка: {e}")
            import traceback
            traceback.print_exc()
            return ""
    
    def handle_places_api(self, query_params):
        """Обрабатывает запросы к Places API (Яндекс или 2GIS) для поиска объектов инфраструктуры"""
        try:
            import requests
            
            print(f"[Places API] Получен запрос с параметрами: {query_params}")
            
            # Получаем параметры
            lat = query_params.get('lat', [None])[0]
            lon = query_params.get('lon', [None])[0]
            text = query_params.get('text', [''])[0]
            results = int(query_params.get('results', ['5'])[0])
            
            print(f"[Places API] Распарсенные параметры: lat={lat}, lon={lon}, text={text}, results={results}")
            
            if not lat or not lon:
                self.send_json_response(400, {
                    'success': False,
                    'error': 'Требуются параметры lat и lon'
                })
                return
            
            # Выбираем провайдера
            if MAP_API_PROVIDER == '2gis' and DGIS_API_KEY:
                # Используем 2GIS Catalog API
                print(f"[Places API] Используется 2GIS Catalog API")
                url = 'https://catalog.api.2gis.com/3.0/items'
                params = {
                    'key': DGIS_API_KEY,
                    'q': text,
                    'point': f'{lon},{lat}',  # 2GIS использует lon,lat
                    'radius': 3000,  # Радиус 3 км
                    'page_size': results,
                    'fields': 'items.point,items.name,items.address_name'
                }
                
                response = requests.get(url, params=params, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    places = []
                    
                    if 'result' in data and 'items' in data['result']:
                        for item in data['result']['items']:
                            if 'point' in item:
                                places.append({
                                    'name': item.get('name', ''),
                                    'description': '',
                                    'coordinates': [item['point']['lat'], item['point']['lon']],
                                    'address': item.get('address_name', '')
                                })
                    
                    self.send_json_response(200, {
                        'success': True,
                        'places': places
                    })
                else:
                    self.send_json_response(response.status_code, {
                        'success': False,
                        'error': f'Ошибка 2GIS Catalog API: {response.text[:500]}'
                    })
            else:
                # Используем Яндекс Places API
                print(f"[Places API] Используется Яндекс Places API")
                places_api_key = '6e86a2e0-4c7f-4962-8170-33c431796593'
                
                url = 'https://search-maps.yandex.ru/v1/'
                params = {
                    'apikey': places_api_key,
                    'text': text,
                    'll': f'{lon},{lat}',  # Places API использует формат lon,lat
                    'spn': '0.05,0.05',  # Радиус поиска (примерно 5.5 км)
                    'results': results,
                    'type': 'biz'  # Тип: бизнес/организация
                }
                
                print(f"[Places API] Используется ключ: {places_api_key[:20]}...")
                
                response = requests.get(url, params=params, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    places = []
                    
                    if 'features' in data:
                        for feature in data['features']:
                            coords = feature['geometry']['coordinates']
                            props = feature['properties']
                            places.append({
                                'name': props.get('name', ''),
                                'description': props.get('description', ''),
                                'coordinates': [coords[1], coords[0]],  # Конвертируем в формат [lat, lon]
                                'address': props.get('CompanyMetaData', {}).get('address', '')
                            })
                    
                    self.send_json_response(200, {
                        'success': True,
                        'places': places
                    })
                else:
                    self.send_json_response(response.status_code, {
                        'success': False,
                        'error': f'Ошибка Places API: {response.text}'
                    })
                
        except Exception as e:
            print(f"[Places API] Ошибка: {e}")
            import traceback
            traceback.print_exc()
            self.send_json_response(500, {
                'success': False,
                'error': str(e)
            })
    
    def get_default_html(self):
        """Возвращает HTML по умолчанию с инструкцией"""
        return """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Коммерческое предложение</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            line-height: 1.6;
        }
        .message {
            background: #fff3cd;
            border: 1px solid #ffc107;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
        }
        .success {
            background: #d4edda;
            border: 1px solid #28a745;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
        }
        code {
            background: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Monaco', 'Courier New', monospace;
        }
    </style>
</head>
<body>
    <h1>Коммерческое предложение</h1>
    <div class="message">
        <h2>📋 Инструкция по получению полной копии страницы:</h2>
        <ol>
            <li>Откройте страницу: <a href="https://offer.allio.ru/weboffer/8c67aa9f380c4f5baee15f75f56c2133/gallery/1" target="_blank">https://offer.allio.ru/weboffer/8c67aa9f380c4f5baee15f75f56c2133/gallery/1</a></li>
            <li>Откройте консоль разработчика (F12 или Cmd+Option+I)</li>
            <li>Скопируйте и выполните скрипт из файла <code>get_page_copy.js</code></li>
            <li>Скопируйте скачанный файл <code>page_prototype.html</code> в папку с сервером</li>
            <li>Обновите эту страницу (F5)</li>
        </ol>
        <p><strong>Или</strong> запустите скрипт автоматического получения:</p>
        <pre>python3 auto_fetch_page.py</pre>
    </div>
    <div class="success">
        <p><strong>✓ Сервер работает!</strong></p>
        <p>После получения файла <code>page_prototype.html</code> обновите страницу, и здесь отобразится копия страницы до блока с вариантами отделки.</p>
    </div>
</body>
</html>"""
    
def main():
    """Запускает сервер"""
    os.chdir(Path(__file__).parent)
    
    # Проверяем наличие API ключа
    api_key = os.getenv('OPENAI_API_KEY')
    if api_key:
        print(f"✓ OpenAI API ключ найден (начинается с: {api_key[:7]}...)")
    else:
        print("⚠ OpenAI API ключ не найден!")
        print("   Установите переменную окружения: export OPENAI_API_KEY='sk-...'")
        print("   Или создайте файл .env с OPENAI_API_KEY=sk-...")
        print("   Подробнее: см. LLM_SETUP.md\n")
    
    # Проверяем, свободен ли порт
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('localhost', PORT))
    sock.close()
    
    if result == 0:
        print(f"⚠ Порт {PORT} уже занят. Останавливаю существующий процесс...")
        os.system(f"lsof -ti:{PORT} | xargs kill -9 2>/dev/null")
        import time
        time.sleep(1)
    
    with socketserver.TCPServer(("", PORT), KPHandler) as httpd:
        print(f"🚀 Сервер запущен на http://localhost:{PORT}/kp")
        print(f"   Страница simple: http://localhost:{PORT}/simple")
        print(f"📁 Рабочая директория: {os.getcwd()}")
        print(f"📄 Ожидается файл: {HTML_FILE}")
        if os.path.exists(HTML_FILE):
            print(f"✓ Файл {HTML_FILE} найден!")
        else:
            print(f"⚠ Файл {HTML_FILE} не найден. Используйте скрипт get_page_copy.js")
        print("\nНажмите Ctrl+C для остановки сервера\n")
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\n👋 Сервер остановлен")

if __name__ == '__main__':
    main()
