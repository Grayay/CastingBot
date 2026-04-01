user_states = {}


def get_user_state(user_id):
    return user_states.get(user_id, {})


def set_user_state(user_id, state):
    user_states[user_id] = state


def update_user_state(user_id, **kwargs):
    state = user_states.get(user_id, {}).copy()
    state.update(kwargs)
    user_states[user_id] = state


def clear_user_state(user_id):
    user_states.pop(user_id, None)