"""Editable state_script example: a 10% risk of accidental death each time the date changes.

process receives copies of the new state, the previous state and the requested history,
and returns the state to save. Raise an exception to fail the state update with its message.
Assumes the Schema has 角色.是否存活 (bool).
"""

import random


def process(state, previous, history):
    alive = state["角色"]["是否存活"]
    # Death is permanent, whatever the model patched.
    if not previous["角色"]["是否存活"]:
        alive = False
    elif state["世界"]["日期"] != previous["世界"]["日期"] and random.random() < 0.10:
        alive = False
    state["角色"]["是否存活"] = alive
    return state
