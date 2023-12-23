docker build -f .dockerfile -t straders_ui .
docker network create spacetraders-network
docker stop straders_ui_instance
docker rm straders_ui_instance
docker run --name straders_ui_instance  --network spacetraders-network -p 80:3000 -e ST_DB_HOST=localhost -e ST_DB_PASS=mysecretpassword -e ST_DB_PORT=6432  -d straders_ui
