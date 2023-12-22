docker build -f .dockerfile -t straders_UI .
docker network create spacetraders-network
docker stop straders_UI_instance
docker rm straders_UI_instance
docker run --name straders_UI_instance --network="spacetraders-network" --env-file=scripts\.env -d straders_dispatcher 