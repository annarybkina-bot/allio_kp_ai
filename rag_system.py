#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG система для хранения и поиска информации о квартирах
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional
import re

class ApartmentRAG:
    """Система RAG для работы с информацией о квартирах и документами"""
    
    def __init__(self, storage_file='apartments_db.json', docs_storage_file='docs_db.json'):
        self.storage_file = storage_file
        self.docs_storage_file = docs_storage_file
        self.apartments = {}
        self.docs = {}  # Хранилище документов/инструкций
        self.load_from_storage()
        self.load_docs_from_storage()
    
    def load_from_storage(self):
        """Загружает данные из файла"""
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, 'r', encoding='utf-8') as f:
                    self.apartments = json.load(f)
                print(f"[RAG] Загружено {len(self.apartments)} квартир из хранилища")
            except Exception as e:
                print(f"[RAG] Ошибка загрузки: {e}")
                self.apartments = {}
        else:
            self.apartments = {}
    
    def load_docs_from_storage(self):
        """Загружает документы из файла"""
        if os.path.exists(self.docs_storage_file):
            try:
                with open(self.docs_storage_file, 'r', encoding='utf-8') as f:
                    self.docs = json.load(f)
                print(f"[RAG Docs] Загружено {len(self.docs)} документов из хранилища")
            except Exception as e:
                print(f"[RAG Docs] Ошибка загрузки: {e}")
                self.docs = {}
        else:
            self.docs = {}
    
    def save_docs_to_storage(self):
        """Сохраняет документы в файл"""
        try:
            with open(self.docs_storage_file, 'w', encoding='utf-8') as f:
                json.dump(self.docs, f, ensure_ascii=False, indent=2)
            print(f"[RAG Docs] Сохранено {len(self.docs)} документов в хранилище")
        except Exception as e:
            print(f"[RAG Docs] Ошибка сохранения: {e}")
    
    def add_document(self, doc_id: str, doc_path: str, doc_type: str = 'markdown'):
        """Добавляет документ в RAG систему"""
        try:
            if not os.path.exists(doc_path):
                print(f"[RAG Docs] ⚠ Файл не найден: {doc_path}")
                return False
            
            with open(doc_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Разбиваем документ на секции для лучшего поиска
            sections = self._parse_markdown_sections(content)
            
            doc_info = {
                'id': doc_id,
                'path': doc_path,
                'type': doc_type,
                'content': content,
                'sections': sections,
                'fullText': self._create_doc_full_text(content, sections)
            }
            
            self.docs[doc_id] = doc_info
            self.save_docs_to_storage()
            print(f"[RAG Docs] ✓ Документ {doc_id} добавлен ({len(sections)} секций)")
            return True
        except Exception as e:
            print(f"[RAG Docs] Ошибка добавления документа: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _parse_markdown_sections(self, content: str) -> List[Dict]:
        """Парсит markdown документ на секции"""
        sections = []
        lines = content.split('\n')
        current_section = None
        current_content = []
        
        for line in lines:
            # Определяем заголовки (##, ###)
            if line.startswith('##'):
                # Сохраняем предыдущую секцию
                if current_section:
                    current_section['content'] = '\n'.join(current_content).strip()
                    sections.append(current_section)
                
                # Начинаем новую секцию
                level = len(line) - len(line.lstrip('#'))
                title = line.lstrip('#').strip()
                current_section = {
                    'level': level,
                    'title': title,
                    'content': ''
                }
                current_content = []
            else:
                if current_section:
                    current_content.append(line)
        
        # Сохраняем последнюю секцию
        if current_section:
            current_section['content'] = '\n'.join(current_content).strip()
            sections.append(current_section)
        
        return sections
    
    def _create_doc_full_text(self, content: str, sections: List[Dict]) -> str:
        """Создает полный текстовый индекс для поиска по документу"""
        parts = [content]  # Весь контент
        # Добавляем заголовки и содержимое секций
        for section in sections:
            parts.append(f"{section['title']}: {section['content']}")
        return ' '.join(parts)
    
    def save_to_storage(self):
        """Сохраняет данные в файл"""
        try:
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(self.apartments, f, ensure_ascii=False, indent=2)
            print(f"[RAG] Сохранено {len(self.apartments)} квартир в хранилище")
        except Exception as e:
            print(f"[RAG] Ошибка сохранения: {e}")
    
    def add_apartment(self, apartment_id: str, context_data: Dict):
        """Добавляет или обновляет информацию о квартире"""
        # Нормализуем данные
        apartment_info = {
            'id': apartment_id,
            'type': context_data.get('type', ''),
            'area': context_data.get('area', ''),
            'project': context_data.get('project', ''),
            'price': context_data.get('price', {}),
            'characteristics': context_data.get('characteristics', {}),
            'features': context_data.get('features', []),
            'roomDetails': context_data.get('roomDetails', []),
            'apartmentNumber': context_data.get('apartmentNumber', ''),
            'fullText': self._create_full_text(context_data),
            'updated_at': None  # Можно добавить timestamp
        }
        
        self.apartments[apartment_id] = apartment_info
        self.save_to_storage()
        print(f"[RAG] Квартира {apartment_id} добавлена/обновлена")
    
    def _create_full_text(self, context_data: Dict) -> str:
        """Создает полный текстовый индекс для поиска"""
        parts = []
        
        if context_data.get('type'):
            parts.append(f"Тип: {context_data['type']}")
        if context_data.get('project'):
            parts.append(f"Проект: {context_data['project']}")
        if context_data.get('price', {}).get('current'):
            parts.append(f"Цена: {context_data['price']['current']}")
        if context_data.get('characteristics'):
            for key, value in context_data['characteristics'].items():
                parts.append(f"{key}: {value}")
        if context_data.get('features'):
            parts.append(f"Преимущества: {', '.join(context_data['features'])}")
        if context_data.get('roomDetails'):
            for detail in context_data['roomDetails']:
                category = detail.get('category', '')
                total_area = detail.get('totalArea', '')
                rooms = ', '.join(detail.get('rooms', []))
                parts.append(f"{category} {total_area}: {rooms}")
        
        return ' '.join(parts)
    
    def search_relevant_info(self, query: str, apartment_id: Optional[str] = None, include_docs: bool = True) -> str:
        """Ищет релевантную информацию для запроса используя семантический поиск"""
        query_lower = query.lower()
        query_words = set(re.findall(r'\b\w+\b', query_lower))
        
        print(f"[RAG Search] Запрос: '{query[:50]}...', apartment_id: {apartment_id}")
        print(f"[RAG Search] Всего квартир в базе: {len(self.apartments)}")
        
        # Если указан конкретный apartment_id, ищем только в нем
        apartments_to_search = {}
        if apartment_id and apartment_id in self.apartments:
            apartments_to_search[apartment_id] = self.apartments[apartment_id]
            print(f"[RAG Search] Используется конкретная квартира: {apartment_id}")
        else:
            apartments_to_search = self.apartments
            if apartment_id:
                print(f"[RAG Search] ⚠ Квартира {apartment_id} не найдена в базе, поиск по всем")
            else:
                print(f"[RAG Search] Поиск по всем квартирам ({len(apartments_to_search)} шт.)")
        
        if not apartments_to_search:
            print("[RAG Search] ⚠ База данных пуста")
            return ""
        
        # Определяем тему запроса для правильного форматирования
        query_theme = self._detect_query_theme(query_lower)
        
        # Если указан конкретный apartment_id и он найден, получаем информацию о квартире
        apartment_context = ""
        if apartment_id and apartment_id in self.apartments:
            print(f"[RAG Search] Получена информация о квартире {apartment_id}")
            apartment_context = self.format_apartment_info(self.apartments[apartment_id], query_theme)
        
        # Определяем тему запроса заранее (если еще не определили)
        if 'query_theme' not in locals():
            query_theme = self._detect_query_theme(query_lower)
        
        # Поиск по релевантности для нескольких квартир
        results = []
        for apt_id, apt_info in apartments_to_search.items():
            score = 0
            full_text_lower = apt_info.get('fullText', '').lower()
            
            # Подсчитываем совпадения ключевых слов
            for word in query_words:
                if len(word) > 2:  # Игнорируем короткие слова
                    count = full_text_lower.count(word)
                    score += count * 2  # Увеличиваем вес совпадений
            
            # Специальные проверки для важных запросов (семантический поиск)
            query_theme = self._detect_query_theme(query_lower)
            
            if query_theme == 'planning':
                if apt_info.get('roomDetails'):
                    score += 20
                if any(word in full_text_lower for word in ['комнат', 'площад', 'планировк']):
                    score += 15
            
            if query_theme == 'price':
                if apt_info.get('price'):
                    score += 20
                if any(word in full_text_lower for word in ['цена', 'стоимость', 'р./м']):
                    score += 15
            
            if query_theme == 'characteristics':
                if apt_info.get('characteristics'):
                    score += 15
                if any(word in full_text_lower for word in ['этаж', 'номер', 'окон', 'спален']):
                    score += 10
            
            if query_theme == 'features':
                if apt_info.get('features'):
                    score += 15
                if any(word in full_text_lower for word in ['преимуществ', 'балкон', 'солнечн']):
                    score += 10
            
            if score > 0:
                results.append((score, apt_info))
        
        # Сортируем по релевантности
        results.sort(key=lambda x: x[0], reverse=True)
        
        # Формируем контекст квартиры (берем лучший результат)
        if not apartment_context:  # Если еще не получили из apartment_id
            if results:
                best_match = results[0][1]
                best_score = results[0][0]
                print(f"[RAG Search] ✓ Найден лучший результат с score={best_score}")
                apartment_context = self.format_apartment_info(best_match, query_theme)
            elif apartments_to_search:
                first_apt = list(apartments_to_search.values())[0]
                print(f"[RAG Search] ⚠ Релевантность не найдена, используется первая квартира из базы")
                apartment_context = self.format_apartment_info(first_apt, query_theme)
        
        # Ищем в документах, если запрос касается планировки/эргономики
        doc_context = ""
        if include_docs and self.docs:
            query_theme = self._detect_query_theme(query_lower)
            # Всегда ищем в документах для запросов о планировке/эргономике/преимуществах
            # Расширяем список триггеров для более надежного поиска
            planning_keywords = ['планировк', 'эргономик', 'площад', 'комнат', 'преимуществ', 'достоинств', 'плюс', 
                               'оценк', 'качеств', 'функциональн', 'удобств', 'комфорт', 'зонирован',
                               'этаж', 'лифт', 'расположен', 'сосед', 'ориентац', 'вид', 'окон']
            if query_theme in ['planning', 'general', 'features', 'floor_position'] or any(word in query_lower for word in planning_keywords):
                doc_context = self._search_in_documents(query, query_lower, query_words)
                if doc_context:
                    print(f"[RAG Docs] ✓ Найдена релевантная информация в документах ({len(doc_context)} символов)")
        
        # Объединяем контекст квартиры и документов
        if apartment_context and doc_context:
            # Определяем заголовок в зависимости от типа запроса
            query_theme = self._detect_query_theme(query_lower)
            if query_theme == 'floor_position':
                header = "\n\n---\n\nРЕЛЕВАНТНЫЕ РАЗДЕЛЫ ИНСТРУКЦИЙ (ПОЭТАЖНАЯ + ВНУТРЕННЯЯ ПЛАНИРОВКА):\n\n"
            else:
                header = "\n\n---\n\nРЕЛЕВАНТНЫЕ РАЗДЕЛЫ ИНСТРУКЦИЙ (ВНУТРЕННЯЯ + ПОЭТАЖНАЯ ПЛАНИРОВКА):\n\n"
            return apartment_context + header + doc_context
        elif apartment_context:
            return apartment_context
        elif doc_context:
            return doc_context
        
        print("[RAG Search] ⚠ Нет результатов")
        return ""
    
    def _search_in_documents(self, query: str, query_lower: str, query_words: set) -> str:
        """Ищет релевантную информацию в документах"""
        if not self.docs:
            return ""
        
        # Определяем тип запроса
        query_theme = self._detect_query_theme(query_lower)
        
        # Выбираем приоритетные документы в зависимости от типа запроса
        priority_docs = []
        if query_theme == 'floor_position':
            # Для запросов про поэтажную планировку приоритет - floor_position_guide
            priority_docs = ['floor_position_guide', 'ergonomics_guide']
            print(f"[RAG Search] Тип запроса: ПОЭТАЖНАЯ ПЛАНИРОВКА")
        elif query_theme in ['planning', 'features', 'general']:
            # Для запросов про внутреннюю планировку приоритет - ergonomics_guide
            priority_docs = ['ergonomics_guide', 'floor_position_guide']
            print(f"[RAG Search] Тип запроса: ВНУТРЕННЯЯ ПЛАНИРОВКА / ОБЩИЙ")
        else:
            # Для остальных запросов используем оба документа
            priority_docs = list(self.docs.keys())
        
        best_sections = []
        
        # Ищем сначала в приоритетных документах
        for doc_id in priority_docs:
            if doc_id not in self.docs:
                continue
                
            doc_info = self.docs[doc_id]
            full_text_lower = doc_info.get('fullText', '').lower()
            sections = doc_info.get('sections', [])
            
            # Подсчитываем релевантность документа
            doc_score = 0
            for word in query_words:
                if len(word) > 2:
                    doc_score += full_text_lower.count(word)
            
            # Бонус для приоритетного документа
            if priority_docs.index(doc_id) == 0:
                doc_score += 20
            
            # Если документ релевантен, ищем конкретные секции
            if doc_score > 0:
                for section in sections:
                    section_text = (section.get('title', '') + ' ' + section.get('content', '')).lower()
                    section_score = 0
                    
                    for word in query_words:
                        if len(word) > 2:
                            section_score += section_text.count(word)
                    
                    # Специальные проверки для ключевых слов ВНУТРЕННЕЙ планировки
                    if query_theme == 'planning':
                        if any(kw in section_text for kw in ['площад', 'соотношен', 'жил', 'нежил', 'комнат', 'кухн', 'санузел']):
                            section_score += 15
                    
                    # Специальные проверки для ключевых слов ПОЭТАЖНОЙ планировки
                    if query_theme == 'floor_position':
                        if any(kw in section_text for kw in ['этаж', 'лифт', 'расположен', 'сосед', 'ориентац', 'вид', 'окон']):
                            section_score += 15
                    
                    # Общие проверки
                    if any(word in query_lower for word in ['преимуществ', 'достоинств', 'плюс']):
                        if any(kw in section_text for kw in ['преимуществ', 'достоинств', 'плюс', 'хорош']):
                            section_score += 10
                    
                    if section_score > 0:
                        best_sections.append((section_score, section, doc_id))
        
        # Сортируем и берем лучшие секции
        best_sections.sort(key=lambda x: x[0], reverse=True)
        
        if best_sections:
            # Берем топ-5 секций (больше, чтобы охватить оба типа инструкций)
            result_parts = []
            for score, section, doc_id in best_sections[:5]:
                # Указываем из какой инструкции секция
                doc_label = "ВНУТРЕННЯЯ ПЛАНИРОВКА" if doc_id == 'ergonomics_guide' else "ПОЭТАЖНАЯ ПЛАНИРОВКА"
                result_parts.append(f"### [{doc_label}] {section.get('title', '')}\n{section.get('content', '')[:600]}...")
            
            return '\n\n'.join(result_parts)
        
        return ""
    
    def _detect_query_theme(self, query_lower: str) -> str:
        """Определяет тему запроса для улучшения поиска"""
        # Ключевые слова для поэтажной планировки (расположение на этаже)
        floor_position_keywords = ['этаж', 'поэтажн', 'лифт', 'лестниц', 'сосед', 'коридор', 'расположен', 
                                   'ориентац', 'сторон света', 'север', 'юг', 'восток', 'запад',
                                   'вид из окон', 'двор', 'улиц', 'шум', 'тиш', 'угловая', 'центральная',
                                   'на этаже', 'этажа']
        
        # Ключевые слова для внутренней планировки
        planning_keywords = ['планировк', 'комнат', 'площад', 'метраж', 'размер', 'план', 'схем',
                            'кухн', 'санузел', 'ванн', 'балкон', 'лоджи', 'коридор внутр', 
                            'прихож', 'зонирован', 'мебел', 'гардероб', 'кладов']
        
        price_keywords = ['цена', 'стоимость', 'стоит', 'оплат', 'ипотек', 'р./м']
        characteristics_keywords = ['номер', 'спален', 'потолок', 'сдача', 'отделк']
        features_keywords = ['преимуществ', 'достоинств', 'плюс', 'солнечн']
        
        # Сначала проверяем поэтажную планировку (более специфичные запросы)
        if any(kw in query_lower for kw in floor_position_keywords):
            return 'floor_position'
        elif any(kw in query_lower for kw in planning_keywords):
            return 'planning'
        elif any(kw in query_lower for kw in price_keywords):
            return 'price'
        elif any(kw in query_lower for kw in characteristics_keywords):
            return 'characteristics'
        elif any(kw in query_lower for kw in features_keywords):
            return 'features'
        
        return 'general'
    
    def format_apartment_info(self, apt_info: Dict, query_theme: str = 'general') -> str:
        """Форматирует информацию о квартире для LLM в зависимости от типа запроса"""
        
        # Для запросов про ПОЭТАЖНУЮ планировку - минимум деталей о внутренней планировке
        if query_theme == 'floor_position':
            context_text = "Информация о расположении квартиры:\n\n"
            
            if apt_info.get('type'):
                context_text += f"Тип: {apt_info['type']}\n"
            
            if apt_info.get('apartmentNumber'):
                context_text += f"Номер квартиры: {apt_info['apartmentNumber']}\n"
            
            # Только информация релевантная для поэтажной планировки
            if apt_info.get('characteristics'):
                # Извлекаем только этаж и ориентацию
                for key, value in apt_info['characteristics'].items():
                    if 'этаж' in key.lower() or 'ориентац' in key.lower() or 'окон' in key.lower():
                        context_text += f"- {key}: {value}\n"
            
            if apt_info.get('features'):
                # Извлекаем только фичи релевантные для поэтажной планировки
                relevant_features = []
                for feature in apt_info['features']:
                    feature_lower = feature.lower()
                    if any(kw in feature_lower for kw in ['сторон', 'вид', 'окон', 'тих', 'шум', 'солнечн']):
                        relevant_features.append(feature)
                
                if relevant_features:
                    context_text += "\nПреимущества расположения:\n"
                    for feature in relevant_features:
                        context_text += f"- {feature}\n"
            
            context_text += "\n⚠️ ВАЖНО: Пользователь спрашивает про ПОЭТАЖНУЮ планировку (расположение на этаже), а НЕ про внутреннюю планировку квартиры!\n"
            
            return context_text
        
        # Для всех остальных запросов - полная информация
        context_text = "Информация о квартире:\n\n"
        
        if apt_info.get('type'):
            context_text += f"Тип квартиры: {apt_info['type']}\n"
        
        if apt_info.get('project'):
            context_text += f"Проект: {apt_info['project']}\n"
        
        if apt_info.get('apartmentNumber'):
            context_text += f"Номер квартиры: {apt_info['apartmentNumber']}\n"
        
        if apt_info.get('price', {}).get('current'):
            price_text = f"Цена при 100% оплате или в ипотеку: {apt_info['price']['current']}"
            if apt_info.get('price', {}).get('perM2Current'):
                price_text += f" ({apt_info['price']['perM2Current']})"
            context_text += price_text + "\n"
        
        if apt_info.get('price', {}).get('base'):
            price_text = f"Цена базовая: {apt_info['price']['base']}"
            if apt_info.get('price', {}).get('perM2Base'):
                price_text += f" ({apt_info['price']['perM2Base']})"
            context_text += price_text + "\n"
        
        if apt_info.get('characteristics'):
            context_text += "\nХарактеристики:\n"
            for key, value in apt_info['characteristics'].items():
                context_text += f"- {key}: {value}\n"
        
        if apt_info.get('features'):
            context_text += "\nПреимущества:\n"
            for feature in apt_info['features']:
                context_text += f"- {feature}\n"
        
        if apt_info.get('roomDetails'):
            context_text += "\nПланировка и площади помещений:\n"
            for detail in apt_info['roomDetails']:
                context_text += f"{detail.get('category', '')} ({detail.get('totalArea', '')}):\n"
                for room in detail.get('rooms', []):
                    context_text += f"  - {room}\n"
        
        return context_text
    
    def get_apartment_by_id(self, apartment_id: str) -> Optional[Dict]:
        """Получает информацию о квартире по ID"""
        return self.apartments.get(apartment_id)
    
    def get_all_apartments(self) -> Dict:
        """Возвращает все квартиры"""
        return self.apartments

# Глобальный экземпляр RAG системы
_rag_instance = None

def get_rag_instance():
    """Получает глобальный экземпляр RAG системы"""
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = ApartmentRAG()
    return _rag_instance
