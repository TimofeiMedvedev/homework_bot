
""".

Исполняемый файл по управлению ботом для отслеживания
статуса по проверке домашнего задания.
"""

import logging
import os
import sys
import time
from http import HTTPStatus

import requests
from dotenv import load_dotenv
from telebot import TeleBot, telebot

from constants import DAYS_30, ENDPOINT, HOMEWORK_VERDICTS, RETRY_PERIOD

load_dotenv()


class ConnectionError(Exception):
    """Ошибка запроса к API."""


class SendMessageTelegram(Exception):
    """Ошибка запроса в телеграмм."""


class SendTelegram(Exception):
    """Ошибка при отправке сообщений в Telegram."""


TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
FAILURE_TO_SEND_MESSAGE = '{error}, {message}'

HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

file_handler = logging.FileHandler(filename='app.log', encoding='utf-8')
file_handler.setFormatter(
    logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s - %(funcName)s - %(lineno)s'
    )
)

console_handler = logging.StreamHandler(stream=sys.stdout)
console_handler.setFormatter(
    logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s - %(funcName)s - %(lineno)s'
    )
)

logger.addHandler(file_handler)
logger.addHandler(console_handler)


def check_tokens():
    """.

    Функция проверки наличия переменных окружения
    необходимых для работы программы.
    """
    tokens = {
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }
    return [key for key in tokens if tokens[key] is None]


def send_message(bot, message):
    """.

    Функция для отправки сообщений в Telegram. В качестве параметров в неё
    передаётся экземпляр бота и сообщение. Внутри выполняются проверка на сбой
    при отправке сообщения в Telegram.
    """
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)

    except telebot.apihelper.ApiException:
        raise SendMessageTelegram('Ошибка со стороны Telegram')

    except Exception as error:
        raise SendTelegram(
            f'сбой при отправке сообщения в Telegram: {error}'
        )
    else:
        logger.debug('Сообщение успешно отправлено в Telegram')


def get_api_answer(now_timestamp):
    """.

    Функция делает запрос к единственному эндпоинту API-сервиса. В качестве
    параметра в функцию передаётся временная метка. В случае успешного запроса
    должна вернуть ответ API, приведя его из формата JSON к типам данных
    Python. Внутри функции делается проверка на ошибку запроса к основному API
    и проверка на ошибку кода ответа НТТP отличного от 200.
    """
    timestamp = now_timestamp
    dict_api = dict(
        url=ENDPOINT,
        headers=HEADERS,
        params={'from_date': timestamp}
    )
    try:
        homework_statuses = requests.get(**dict_api)
    except Exception as error:
        raise ConnectionError(
            f'Ошибка запроса к основному API адресу: {error}',
            **dict_api
        )
    if homework_statuses.status_code != HTTPStatus.OK:
        raise requests.exceptions.HTTPError(
            f'API возвращяет код отличный от 200: '
            f'{homework_statuses.status_code}',
            **dict_api
        )
    return homework_statuses.json()


def check_response(response):
    """.

    Функция проверяет корректность данных от API адреса. В качестве параметров
    она принимает данные API от практикума. Внутри функции по ключу homeworks
    берётся список с проверенными домашними работами и из него достаётся
    последняя работа даже если список пустой. Также внутри выполняется
    проверка на соответствие ключу homeworks.
    """
    try:
        homeworks_list = response['homeworks']
    except KeyError:
        raise KeyError('отсутствие ожидаемых ключей в ответе API')
    if not homeworks_list:
        raise IndexError('Пустой список')

    if not isinstance(homeworks_list, list):
        raise TypeError(
            f'{type(homeworks_list)} type(homeworks_list) must be list'
        )

    if not isinstance(response, dict):
        raise TypeError(
            f'{type(response)} type(responce) must be dict',
        )
    homework_new = homeworks_list[0]

    return homework_new


def parse_status(homework):
    """.

    Функция принимает в качестве параметра последнюю проверенную домашнюю
    работу и возвращает статус этой работы. Внутри выполняется проверка на
    ошибку несоответствия ключа 'homework_name' и на несоответствие статуса
    работы.'
    """
    if 'homework_name' not in homework:
        raise KeyError('В ответе API нет ключа homework_name')

    homework_name = homework.get('homework_name')
    status_homework = homework.get('status')

    if status_homework not in HOMEWORK_VERDICTS:
        raise KeyError(
            f'Появился новый недокументированный статус домашней работы: '
            f'{status_homework}'
        )
    verdict = HOMEWORK_VERDICTS[status_homework]

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """.

    Основная логика работы бота. Внутри функции создаётся экземпляр бота в
    Telegram, временная метка. Выполняется проверка на ошибку наличия токенов
    из виртуального окружения. Внутри цикла делаем запрос к вспомогательным
    функциям, а также проверяем наличие ошибок уровня логирования ERROR и
    отправляем их сообщением в телеграмм.
    """
    tokens_not = check_tokens()
    if tokens_not:
        logger.critical(
            f'Отсутствие переменных окружения во время запуска бота: '
            f'{tokens_not}'
        )
        sys.exit()

    bot = TeleBot(token=TELEGRAM_TOKEN)
    now_timestamp = int(time.time()) - DAYS_30
    previous_str = ''

    while True:
        try:
            response = get_api_answer(now_timestamp)
            homework = check_response(response)
            message = parse_status(homework)
            send_message(bot, message)

        except IndexError:
            logger.debug('Список пуст')

        except SendMessageTelegram:
            logger.error('Сбой отправки сообщения в Telegram')

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if message != previous_str:
                send_message(bot, message)
                previous_str = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
