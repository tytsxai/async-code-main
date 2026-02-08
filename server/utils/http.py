from flask import jsonify


def error_response(message: str, status_code: int):
    return jsonify({'status': 'error', 'error': message}), status_code
