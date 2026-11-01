"""Generate a scrypt password hash for the dashboard environment."""
from getpass import getpass
from .auth import hash_password
def main():
    password=getpass('New dashboard password: ')
    confirm=getpass('Confirm password: ')
    if len(password)<12:raise SystemExit('Password must be at least 12 characters')
    if password != confirm:raise SystemExit('Passwords did not match')
    print('DASHBOARD_PASSWORD_HASH='+hash_password(password))
if __name__=='__main__':main()
