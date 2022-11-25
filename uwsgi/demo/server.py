# -*- coding: utf8 -*-

import time
from flask import Flask

app = Flask(__name__)


@app.route('/')
def index():
    return 'Hello World'


@app.route('/long_request')
def long_request():
    delayed_seconds = 8
    for i in range(delayed_seconds, 0, -1):
        print('Please waiting for {} seconds.'.format(i))
        time.sleep(1)

    return f'This data delayed {delayed_seconds} seconds.'
