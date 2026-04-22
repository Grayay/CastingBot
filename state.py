import time


STATE_TTL_SECONDS = 20 * 60
user_states = {}


def get_user_state(user_id):
    state = user_states.get(user_id)
    if not state:
        return {}

    created_at = state.get("created_at")
    if created_at is None:
        user_states.pop(user_id, None)
        return {}

    if time.time() - created_at > STATE_TTL_SECONDS:
        user_states.pop(user_id, None)
        return {}

    return state


def set_user_state(user_id, state):
    next_state = dict(state)
    next_state["created_at"] = time.time()
    user_states[user_id] = next_state


def update_user_state(user_id, **kwargs):
    state = user_states.get(user_id, {}).copy()
    if not state:
        return
    state.update(kwargs)
    state["created_at"] = time.time()
    user_states[user_id] = state


def clear_user_state(user_id):
    user_states.pop(user_id, None)


def clear_expired_user_state(user_id):
    state = user_states.get(user_id)
    if not state:
        return False

    created_at = state.get("created_at")
    if created_at is None or time.time() - created_at > STATE_TTL_SECONDS:
        user_states.pop(user_id, None)
        return True

    return False