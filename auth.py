USERS = {
    "amodh": "amodh2006",
    "coach": "coach2006",
    "tch": "tch2006",
    "username": "password"
}

ROLES = {
    "amodh": "admin",
    "coach": "admin",
    "tch": "admin",
    "username": "viewer"
}

def verify_user(username, password):
    if username in USERS and USERS[username] == password:
        return True
    return False

def get_role(username):
    return ROLES.get(username, "viewer")