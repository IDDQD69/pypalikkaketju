
import yaml

data: dict


def get_settings():
    global data

    if not data:
        with open('data.yaml') as f:
            data = yaml.load(f, Loader=yaml.FullLoader)

    return data