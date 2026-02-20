#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль для логирования стоимости запросов к OpenAI
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

class CostLogger:
    """Логирует стоимость и метрики запросов к OpenAI"""
    
    # Цены GPT-4o (на январь 2026)
    PRICES = {
        'gpt-4o': {
            'input': 2.50 / 1_000_000,   # $2.50 за 1M токенов
            'output': 10.00 / 1_000_000  # $10.00 за 1M токенов
        },
        'gpt-4o-mini': {
            'input': 0.15 / 1_000_000,   # $0.15 за 1M токенов
            'output': 0.60 / 1_000_000   # $0.60 за 1M токенов
        }
    }
    
    def __init__(self, log_dir='logs', log_file='api_costs.jsonl'):
        """
        Инициализация логгера
        
        Args:
            log_dir: Папка для логов
            log_file: Имя файла лога (JSONL формат - JSON Lines)
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.log_file = self.log_dir / log_file
        
    def calculate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """
        Рассчитывает стоимость запроса
        
        Args:
            model: Название модели (gpt-4o, gpt-4o-mini)
            prompt_tokens: Количество входных токенов
            completion_tokens: Количество выходных токенов
            
        Returns:
            Стоимость запроса в долларах
        """
        if model not in self.PRICES:
            model = 'gpt-4o'  # По умолчанию
        
        prices = self.PRICES[model]
        input_cost = prompt_tokens * prices['input']
        output_cost = completion_tokens * prices['output']
        
        return input_cost + output_cost
    
    def log_request(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        user_message: str = '',
        assistant_message: str = '',
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Логирует запрос в файл
        
        Args:
            model: Модель OpenAI
            prompt_tokens: Входные токены
            completion_tokens: Выходные токены
            total_tokens: Всего токенов
            user_message: Вопрос пользователя (опционально)
            assistant_message: Ответ ассистента (опционально)
            metadata: Дополнительные данные (user_id, session_id и т.д.)
            
        Returns:
            Словарь с информацией о запросе
        """
        cost = self.calculate_cost(model, prompt_tokens, completion_tokens)
        
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'date': datetime.now().strftime('%Y-%m-%d'),
            'time': datetime.now().strftime('%H:%M:%S'),
            'model': model,
            'tokens': {
                'prompt': prompt_tokens,
                'completion': completion_tokens,
                'total': total_tokens
            },
            'cost_usd': round(cost, 6),
            'cost_cents': round(cost * 100, 4),
            'user_message_length': len(user_message),
            'assistant_message_length': len(assistant_message)
        }
        
        # Добавляем метаданные, если есть
        if metadata:
            log_entry['metadata'] = metadata
        
        # Опционально сохраняем тексты сообщений (для отладки)
        # ВНИМАНИЕ: В продакшн может быть много данных!
        if os.getenv('LOG_MESSAGES', 'false').lower() == 'true':
            log_entry['messages'] = {
                'user': user_message[:200] if user_message else '',  # Первые 200 символов
                'assistant': assistant_message[:200] if assistant_message else ''
            }
        
        # Записываем в файл (JSONL формат - каждая строка - отдельный JSON)
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        
        return log_entry
    
    def get_stats(self, date: Optional[str] = None) -> Dict[str, Any]:
        """
        Получает статистику за день
        
        Args:
            date: Дата в формате YYYY-MM-DD (None = сегодня)
            
        Returns:
            Словарь со статистикой
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        if not self.log_file.exists():
            return {
                'date': date,
                'total_requests': 0,
                'total_tokens': 0,
                'total_cost_usd': 0.0,
                'total_cost_cents': 0.0
            }
        
        stats = {
            'date': date,
            'total_requests': 0,
            'total_tokens': 0,
            'prompt_tokens': 0,
            'completion_tokens': 0,
            'total_cost_usd': 0.0,
            'requests_by_hour': {}
        }
        
        with open(self.log_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    
                    # Фильтруем по дате
                    if entry.get('date') != date:
                        continue
                    
                    stats['total_requests'] += 1
                    stats['total_tokens'] += entry['tokens']['total']
                    stats['prompt_tokens'] += entry['tokens']['prompt']
                    stats['completion_tokens'] += entry['tokens']['completion']
                    stats['total_cost_usd'] += entry['cost_usd']
                    
                    # Группируем по часам
                    hour = entry['time'][:2]  # Первые 2 символа = час
                    if hour not in stats['requests_by_hour']:
                        stats['requests_by_hour'][hour] = {'count': 0, 'cost': 0.0}
                    stats['requests_by_hour'][hour]['count'] += 1
                    stats['requests_by_hour'][hour]['cost'] += entry['cost_usd']
                    
                except json.JSONDecodeError:
                    continue
        
        stats['total_cost_cents'] = round(stats['total_cost_usd'] * 100, 2)
        stats['avg_cost_per_request'] = round(
            stats['total_cost_usd'] / stats['total_requests'], 4
        ) if stats['total_requests'] > 0 else 0.0
        
        return stats
    
    def get_monthly_stats(self, year: int, month: int) -> Dict[str, Any]:
        """
        Получает статистику за месяц
        
        Args:
            year: Год (YYYY)
            month: Месяц (1-12)
            
        Returns:
            Словарь со статистикой за месяц
        """
        if not self.log_file.exists():
            return {
                'period': f'{year}-{month:02d}',
                'total_requests': 0,
                'total_cost_usd': 0.0
            }
        
        month_prefix = f'{year}-{month:02d}'
        
        stats = {
            'period': month_prefix,
            'total_requests': 0,
            'total_tokens': 0,
            'prompt_tokens': 0,
            'completion_tokens': 0,
            'total_cost_usd': 0.0,
            'daily_stats': {}
        }
        
        with open(self.log_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    
                    # Фильтруем по месяцу
                    if not entry.get('date', '').startswith(month_prefix):
                        continue
                    
                    date = entry['date']
                    
                    stats['total_requests'] += 1
                    stats['total_tokens'] += entry['tokens']['total']
                    stats['prompt_tokens'] += entry['tokens']['prompt']
                    stats['completion_tokens'] += entry['tokens']['completion']
                    stats['total_cost_usd'] += entry['cost_usd']
                    
                    # Группируем по дням
                    if date not in stats['daily_stats']:
                        stats['daily_stats'][date] = {'count': 0, 'cost': 0.0}
                    stats['daily_stats'][date]['count'] += 1
                    stats['daily_stats'][date]['cost'] += entry['cost_usd']
                    
                except json.JSONDecodeError:
                    continue
        
        stats['total_cost_cents'] = round(stats['total_cost_usd'] * 100, 2)
        stats['avg_cost_per_request'] = round(
            stats['total_cost_usd'] / stats['total_requests'], 4
        ) if stats['total_requests'] > 0 else 0.0
        
        return stats


# Глобальный экземпляр логгера
_logger_instance = None

def get_cost_logger() -> CostLogger:
    """Получает глобальный экземпляр логгера"""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = CostLogger()
    return _logger_instance
