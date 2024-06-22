import logging
from datetime import datetime, timedelta
import json
from concurrent.futures import ThreadPoolExecutor
from flask import request, Response, current_app as app

from app.config import IGNORED_MODEL_NAMES, IMAGE_MODEL_NAMES, AUTH_TOKEN, HISTORY_MSG_LIMIT
from app.config import configure_logging, get_env_value
from app.utils import send_chat_message, fetch_channel_id, map_model_name, process_content, get_user_contents, \
    generate_hash, get_next_auth_token, handle_error, get_request_parameters, get_topic_from_headers

configure_logging()


# 从文件初始化 storage_map
def load_storage_map():
    try:
        with open('storage_map.json', 'r') as file:
            return json.load(file, object_hook=json_datetime_parser)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

# 辅助函数，将 JSON 对象转换为 datetime
def json_datetime_parser(dct):
    new_dct = {}
    for key, value in dct.items():
        if isinstance(value, list) and len(value) == 2:
            channel_id, expiry_str = value
            try:
                expiry_time = datetime.strptime(expiry_str, '%Y-%m-%dT%H:%M:%S.%f')
                new_dct[key] = (channel_id, expiry_time)
            except ValueError as e:
                logging.error(f"Error parsing date: {expiry_str} with error {e}")
    return new_dct

# 辅助函数，将 datetime 转换为 JSON 可序列化格式
def json_datetime_converter(obj):
    if isinstance(obj, datetime):
        return obj.strftime('%Y-%m-%dT%H:%M:%S.%f')
    raise TypeError("Type %s not serializable" % type(obj))

# Function to perform the blocking file write operation
def blocking_file_write(file_path, data):
    try:
        with open(file_path, 'w') as file:
            json.dump(data, file, default=json_datetime_converter)
    except Exception as e:
        print(f"Failed to write to file: {e}")

# ThreadPoolExecutor as a context manager to handle the thread pool
executor = ThreadPoolExecutor(max_workers=2)  # You can adjust max_workers based on your needs

# Function to save the storage map using the thread pool
def save_storage_map(storage_map):
    executor.submit(blocking_file_write, 'storage_map.json', storage_map)

# 程序启动时加载 storage_map
storage_map = load_storage_map()

@app.route("/v1/chat/completions", methods=["GET", "POST", "OPTIONS"])
def onRequest():
    try:
        return fetch(request)
    except Exception as e:
        logging.error("An error occurred with chat : %s", e)
        return handle_error(e)


@app.route('/v1/models')
def list_models():
    return {
        "object": "list",
        "data": [{
            "id": m,
            "object": "model",
            "created": int(datetime.now().timestamp()),
            "owned_by": "popai"
        } for m in IGNORED_MODEL_NAMES]
    }


@app.route('/v1/images/generations', methods= ["post"])
def image():
    try:
        request.get_json()["model"] = IMAGE_MODEL_NAMES[0]
        return fetch(request)
    except Exception as e:
        logging.error("An error occurred with image : %s", e)
        return handle_error(e)


def get_channel_id(hash_value, token, model_name, content, template_id):
    if hash_value in storage_map:
        channel_id, expiry_time = storage_map[hash_value]
        if expiry_time > datetime.now() and channel_id:
            logging.info("Returning channel id from cache")
            return channel_id
    channel_id = fetch_channel_id(token, model_name, content, template_id)
    expiry_time = datetime.now() + timedelta(days=int(get_env_value('EXPIRED_DAYS', '1')))
    storage_map[hash_value] = (channel_id, expiry_time)
    save_storage_map(storage_map)  # 保存更新到文件
    return channel_id


def fetch(req):
    if req.method == "OPTIONS":
        return handle_options_request()
    token = get_next_auth_token(AUTH_TOKEN)
    messages, model_name, prompt, user_stream = get_request_parameters(req.get_json())
    model_to_use = map_model_name(model_name)
    template_id = 2000000 if model_name in IMAGE_MODEL_NAMES else ''

    if not messages and prompt:
        final_user_content = prompt
        first_argument = final_user_content
        image_url = None
    elif messages:
        last_message = messages[-1]
        first_user_message, end_user_message, concatenated_messages, user_messages_list = get_user_contents(messages, HISTORY_MSG_LIMIT)
        final_user_content = user_messages_list[-1]
        user_text, image_url = process_content(last_message.get('content'))
        final_user_content = concatenated_messages + '\n' + final_user_content if concatenated_messages else final_user_content

        topic = get_topic_from_headers(req.headers)
        if topic is not None and len(topic) > 0:
            first_argument = topic
        else:
            first_argument = first_user_message
        # hash_value = generate_hash(first_argument, model_to_use, token)

    hash_value = generate_hash(first_argument, model_to_use, token)
    channel_id = get_channel_id(hash_value, token, model_to_use, final_user_content, template_id)

    if final_user_content is None:
        return Response("No user message found", status=400)

    return send_chat_message(req, token, channel_id, final_user_content, model_to_use, user_stream, image_url, model_name)


def handle_options_request():
    return Response(status=204, headers={'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*'})
