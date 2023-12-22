docker build -f .dockerfile -t straders_UI .
docker network create spacetraders-network
docker stop straders_UI_instance
docker rm straders_UI_instance
docker run --name straders_UI_instance  --network spacetraders-network -e ST_DB_HOST=localhost -e ST_DB_PASS=mysecretpassword -e ST_DB_PORT=6432  -d straders_UI 