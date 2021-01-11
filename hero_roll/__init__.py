
import yaml

data: dict


def get_settings():
    with open('hero_roll/data.yaml') as f:
        return yaml.load(f, Loader=yaml.FullLoader)
