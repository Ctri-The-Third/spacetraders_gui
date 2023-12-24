FROM python:3-slim-bookworm
copy ./requirements.txt ./requirements.txt
run python -m pip install -r requirements.txt
Copy ./spacetraders_sdk/ ./spacetraders_sdk 
run python -m pip install -r spacetraders_sdk/requirements.txt

workdir spacetraders_sdk
run chmod +x ./setup.sh
run /spacetraders_sdk/setup.sh

workdir ..
copy . . 

ENV ST_DB_USER=spacetraders 


CMD python main.py
