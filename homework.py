
""".

Исполняемый файл по управлению ботом для отслеживания
статуса по проверке домашнего задания.
"""

import logging
import os
import requests
from pprint import pprint
import time
from constants import RETRY_PERIOD, ENDPOINT, HOMEWORK_VERDICTS, DAYS_30
from http import HTTPStatus
import sys


from dotenv import load_dotenv
from telebot import TeleBot

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

file_handler = logging.FileHandler(filename='app.log', encoding='utf-8')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s - %(funcName)s - %(lineno)s'))
 
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s - %(funcName)s - %(lineno)s'))
 
logger.addHandler(file_handler)
logger.addHandler(console_handler)



def check_tokens():
    """.

    Функция проверки наличия переменных окружения
    необходимых для работы программы.
    """
    tokens = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    if all(tokens):
        return True
    else:
        return False


def send_message(bot, message):
    """.

    Функция для отправки сообщений в Telegram. В качестве параметров в неё
    передаётся экземпляр бота и сообщение. Внутри выполняются проверка на сбой
    при отправке сообщения в Telegram.
    """
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug('Сообщение успешно отправлено в Telegram')
    except Exception as error:
        logger.error(f'сбой при отправке сообщения в Telegram: {error}')


def get_api_answer(timestamp):
    """.

    Функция делает запрос к единственному эндпоинту API-сервиса. В качестве 
    параметра в функцию передаётся временная метка. В случае успешного запроса 
    должна вернуть ответ API, приведя его из формата JSON к типам данных 
    Python. Внутри функции делается проверка на ошибку запроса к основному API 
    и проверка на ошибку кода ответа НТТP отличного от 200.
    """
    try:
        homework_statuses = requests.get(ENDPOINT, headers=HEADERS, params={'from_date': timestamp - DAYS_30})
    except Exception as error:
        logger.error(f'Ошибка запроса к основному API адресу: {error}')
    if homework_statuses.status_code != HTTPStatus.OK:
        logger.error(f'API возвращяет код отличный от 200: {homework_statuses.status_code}')
        raise Exception(f'API возвращяет код отличный от 200: {homework_statuses.status_code}')
    return homework_statuses.json()

def check_response(response):
    try:
        homeworks_list = response['homeworks']
    except KeyError:
        logger.error('отсутствие ожидаемых ключей в ответе API')

    if type(homeworks_list) is not list:
        logger.error('Структура данных под ключом homeworks не соответствует ожиданиям')
        raise TypeError('Структура данных под ключом homeworks не соответствует ожиданиям')
    
    homework_new = homeworks_list[0]


    if type(response) is not dict:
        logger.error('Структура данных ответа от API не соответствует ожиданиям')
        raise TypeError('Структура данных ответа от API не соответствует ожиданиям')

    return homework_new



def parse_status(homework):
    if 'homework_name' not in homework:
        logger.error('В ответе API нет ключа homework_name')
        raise KeyError('В ответе API нет ключа homework_name')

    homework_name = homework.get('homework_name')
    status_homework = homework.get('status')

    if status_homework not in HOMEWORK_VERDICTS:
        logger.debug(
            f'Появился новый недокументированный статус домашней работы: {status_homework}'
        )
        raise KeyError(f'Появился новый недокументированный статус домашней работы: {status_homework}')
    verdict = HOMEWORK_VERDICTS[status_homework]

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    availability_tokens = check_tokens()
    if not availability_tokens:
        logger.critical('Отсутствие обязательных переменных окружения во время запуска бота')
        sys.exit()
    
    # response = get_api_answer(timestamp)
    # homework = check_response(response)
    # message = parse_status(homework)
    # send_message(bot, message)
    
    # pprint(get_api_answer(timestamp))
    # print(check_tokens())
    

    # Создаем объект класса бота
    # bot = TeleBot(token=TELEGRAM_TOKEN)
    # timestamp = int(time.time())
    

    ...

    while True:
        try:
            response = get_api_answer(timestamp)
            pprint(response)
            homework = check_response(response)
            message = parse_status(homework)
            send_message(bot, message)
            time.sleep(RETRY_PERIOD)

        except Exception as error:
            logger.error(f'Сбой в работе программы: {error}')
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            time.sleep(RETRY_PERIOD)
        


if __name__ == '__main__':
    main()
