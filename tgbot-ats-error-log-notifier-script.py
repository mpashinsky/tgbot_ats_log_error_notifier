import json
import sys
import re
from datetime import datetime, timedelta
import requests
import time

BOT_TOKEN = ''
POTOK_TOKEN = ''
chat_ids = ['450092386', '348438868', '1606360814', '2054961458', '2077591122', '2135127961', '1015753135', '1430112443']
THRESHOLD_IN_MINUTES = 3


def get_responsible_user_name(applicant_id, stage_type):

    responsible_user_id = get_responsible_user_id(applicant_id, stage_type)
    if responsible_user_id is not None:
        command = ('https://app.potok.io/api/v3/users/' + str(responsible_user_id) + '.json?token=' + str(POTOK_TOKEN))

        try:
            response = requests.get(command)
        except Exception:
            return "-"

        if response is None or response == '':
            return "-"

        response_text = getattr(response, 'text', '')
        if response_text == '':
            return "-н"

        response_json = json.loads(response_text)
        if 'name' not in response_json:
            return "-"

        return response_json['name']

    return "-"


def get_responsible_user_id(applicant_id, stage_type):

    if applicant_id is None or len(applicant_id) == 0:
        return None

    command = ('https://app.potok.io/api/v3/applicants/' + applicant_id + '.json?token=' + str(POTOK_TOKEN))

    try:
        response = requests.get(command)
    except Exception:
        return ""

    if response is None or response == '':
        return None

    response_text = getattr(response, 'text', '')
    if response_text == '':
        return None

    response_json = json.loads(response_text)
    if 'ajs_joins' not in response_json:
        return None

    ajs_joins = response_json['ajs_joins']

    for ajs_join in ajs_joins:
        if ajs_join['stage']['stage_type'] == stage_type:
            return ajs_join['responsible_user_id']


def get_all_chat_ids():
    command = ('https://api.telegram.org/bot' + BOT_TOKEN + '/getUpdates')

    try:
        response = requests.get(command)
    except Exception:
        return
    
    if response is None or response == '':
        return

    response_text = getattr(response, 'text', '')
    if response_text == '':
        return

    final = json.loads(response_text)
    if 'result' in final:
        chat_id_dict = final['result']

        for item in chat_id_dict:
            if 'message' in item:
                chat_id = str(item['message']['chat']['id'])
                chat_ids.append(chat_id) if chat_id not in chat_ids else chat_ids


# Send message to telegram bot
def telegram_bot_send_message(bot_message):

    if len(BOT_TOKEN) > 2:
        for chat_id in chat_ids:
            send_text = ('https://api.telegram.org/bot' + BOT_TOKEN + '/sendMessage?chat_id=' + chat_id
                         + '&parse_mode=Markdown&text=' + bot_message)
            try:
                requests.get(send_text)
            except Exception:
                pass


def find_last_timestamp(file_lines):
    last_timestamp = None

    for line in reversed(file_lines):
        match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d{3}', line)
        if match:
            last_timestamp = datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S')
            break

    return last_timestamp


def translate_error(error_message):
    if re.search(r"Applicant firstname is empty.", error_message):
        return "Имя не задано."

    if re.search(r"Applicant lastname is empty.", error_message):
        return "Фамилия не задана."

    if re.search(r"Ajs join with stage type ID", error_message):
        return ("Связь с вакансией на нужном этапе не найдена у кандидата. "
                "Для проверки СБ - Проверка СБ, для финалсита - Оформление. "
                "Этап был изменён вручную или вакансия заархивирована.")

    if re.search(r"ATS security form not present for applicant", error_message):
        return "Нет анкеты или она заполнена на другой вакансии."

    if re.search(r"Logins", error_message):
        return "Пользователь с такими логинами уже существует."

    if re.search(r"client.exceptions.PotokAtsClientException", error_message):
        return "Ошибка на стороне Потока."

    if re.search(r"Passport series and number is not a valid Russian passport series and number", error_message):
        return "Номер или серия паспорта заданы некорректно."

    if re.search(r"Passport date of issue is empty", error_message):
        return "Дата выдачи паспорта не задана."

    if re.search(r"Passport date of issue is later than current date", error_message):
        return "Дата выдачи паспорта позже текущей даты."

    if re.search(r"Passport date of issue is before than birthdate", error_message):
        return "Дата выдачи паспорта раньше даты рождения."

    if re.search(r"Applicant phone and email are empty.", error_message):
        return "Не заданы ни номер телефона ни e-mail."

    if re.search(r"Phone is empty.", error_message):
        return "Не задан номер телефона."

    if re.search(r"is not a valid mobile phone number", error_message):
        return "Номер телефона задан некорректно."

    if re.search(r"Applicant person name is not correct", error_message):
        return "Некорректные символы в ФИО кандидата."

    if re.search(r"Birthdate is empty", error_message):
        return "Не задана дата рождения."

    if re.search(r"Birthdate is later than current date", error_message):
        return "Дата рождения позже текущей даты."

    if re.search(r"is not a valid email", error_message):
        return "Некорректный email"

    return error_message


def find_error_begin(line):
    pattern = (r"java.lang.IllegalStateException: Process type: '(\w+)'. Error occurred while "
               r"trying to import applicant with external ID '(\d+)'")
    match = re.search(pattern, line)
    if match:
        return match.group(2)


def find_error_cause(line):
    cause_pattern = r"Caused by: (.+)"
    cause_match = re.search(cause_pattern, line)
    if cause_match:
        return ": " + translate_error(cause_match.group(1)) + "\n"


def get_timestamp_threshold(last_timestamp, threshold_in_minutes):
    return last_timestamp - timedelta(minutes=threshold_in_minutes)


def get_responsible_recruiter_name(applicant_id):
    pass


def get_all_errors_after_timestamp(timestamp_threshold, file_lines, stage_type):
    error_message = ""
    line_with_timestamp_found = False
    index = 1

    for line in file_lines:
        if line_with_timestamp_found:
            applicant_id = find_error_begin(line)
            if applicant_id is not None:
                responsible_recruiter_name = get_responsible_user_name(applicant_id, stage_type)
                error_message = error_message + str(index) + ". Ответственный: " + responsible_recruiter_name + ". " + applicant_id
                index = index + 1
            else:
                error_cause = find_error_cause(line)
                if error_cause is not None:
                    error_message = error_message + error_cause
        else:
            match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d{3}', line)
            if match:
                timestamp = datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S')
                if timestamp >= timestamp_threshold:
                    line_with_timestamp_found = True
    return error_message


def notify_about_errors_in_log(file_path, title, stage_type):
    with open(file_path, 'r') as file:
        file_lines = file.readlines()

        last_timestamp = find_last_timestamp(file_lines)

        if last_timestamp:

            timestamp_threshold = get_timestamp_threshold(last_timestamp, THRESHOLD_IN_MINUTES)
            result_message = get_all_errors_after_timestamp(timestamp_threshold, file_lines, stage_type)
            if result_message:
                print(title + result_message)
                telegram_bot_send_message(title + result_message)
        else:
            print("No valid timestamp found in the file.")


if __name__ == "__main__":
    if len(sys.argv) != 6:
        print("Usage: ats-error-notifier-script.py <telegram-bot-token> <potok-token> <sb_file_path> <finalist_log_file_path> "
              "<interval_in_minutes>")
        sys.exit(1)

    BOT_TOKEN = sys.argv[1]
    POTOK_TOKEN = sys.argv[2]
    sb_file_path = sys.argv[3]
    finalist_log_file_path = sys.argv[4]
    send_notification_interval_in_minutes = sys.argv[5]

    while True:
        get_all_chat_ids()
        telegram_bot_send_message("============================")
        time.sleep(1)
        notify_about_errors_in_log(sb_file_path, "*Проблемные кандидаты, ожидающие проверки СБ*:\n\n", "sb")
        notify_about_errors_in_log(finalist_log_file_path, "*Проблемные кандидаты, ожидающие передачи финалиста*:\n\n", "push_to_external_system")
        time.sleep(float(send_notification_interval_in_minutes) * 60)
