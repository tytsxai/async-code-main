def get_latest_user_prompt(task: dict) -> str:
    messages = task.get('chat_messages') or []
    for msg in reversed(messages):
        if msg.get('role') == 'user':
            return msg.get('content', '')
    return ""
