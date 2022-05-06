#!/bin/bash

BASE_PATH=/home/house
. $BASE_PATH/venv/bin/activate
export DATABASE_URL="postgresql://house:<password>>@localhost/house"
export TG_BOT_TOKEN="<TOKEN>"
export GOOGLE_KEY="<KEY>"

trap "kill -- -$$" EXIT

# /usr/bin/pidproxy $BASE_PATH/logs/$1.pid 
cd $BASE_PATH/tgbot
export LC_ALL=en_US.UTF-8
# export BOT_ENV=PROD
python tg_bot.py