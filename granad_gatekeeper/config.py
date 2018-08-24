
class HardCoded(object):
    ADMINS = ['adam.schubert@sg1-game.net']


class Config(HardCoded):
    DEBUG = True
    TARGETS = ['google.com', '8.8.8.8', 'salamek.cz']
    TARGETS_FAIL_THRESHOLD = 50  # <= 50% must fail to restart modem
    MODEM_URL = 'http://admin:admin@192.168.8.1/'
    RESTART_SERVICES = ['granad-rs232', 'openvpn@client']
    CHECK_ITERVAL = 60  # seconds


class Testing(Config):
    TESTING = True


class Production(Config):
    DEBUG = False
    TARGETS = None  # To be overwritten by a YAML file.
    MODEM_URL = None  # To be overwritten by a YAML file.
