from dataclasses import dataclass, field


@dataclass
class HardCoded:
    ADMINS: list[str] = field(default_factory=lambda: ['adam.schubert@sg1-game.net'])


@dataclass
class Config(HardCoded):
    DEBUG: bool = True
    TARGETS: list[str] = field(default_factory=lambda: ['google.com', '8.8.8.8', 'cloudflare.com'])
    TARGETS_FAIL_THRESHOLD: int = 50  # More than 50% must fail to restart the modem.
    MODEM_URL: str = 'http://admin:admin@192.168.8.1/'
    RESTART_SERVICES: list[str] = field(default_factory=lambda: ['openvpn@client'])
    CHECK_INTERVAL: int = 60  # seconds

    def validate(self) -> None:
        for name in ('ADMINS', 'TARGETS', 'RESTART_SERVICES'):
            value = getattr(self, name)
            if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
                message = f'{name} must be a list of nonempty strings'
                raise ValueError(message)
        if not self.TARGETS:
            message = 'TARGETS must contain at least one target'
            raise ValueError(message)
        if not isinstance(self.MODEM_URL, str) or not self.MODEM_URL:
            message = 'MODEM_URL must be a nonempty string'
            raise ValueError(message)
        if type(self.TARGETS_FAIL_THRESHOLD) is not int or not 0 <= self.TARGETS_FAIL_THRESHOLD <= 100:
            message = 'TARGETS_FAIL_THRESHOLD must be an integer between 0 and 100'
            raise ValueError(message)
        if type(self.CHECK_INTERVAL) is not int or self.CHECK_INTERVAL <= 0:
            message = 'CHECK_INTERVAL must be a positive integer'
            raise ValueError(message)
        if not isinstance(self.DEBUG, bool):
            message = 'DEBUG must be a boolean'
            raise TypeError(message)


@dataclass
class Testing(Config):
    TESTING: bool = True


@dataclass
class Production(Config):
    DEBUG: bool = False
    TARGETS: list[str] = field(default_factory=list)
    MODEM_URL: str = ''
