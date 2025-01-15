
#!/bin/bash
docker kill cc-registry; docker rm cc-registry
echo "Clean docker"
## Docker cleanup
docker rmi $(docker images --filter "dangling=true" -q --no-trunc)
docker rmi $(docker images -q) -f
docker rmi $(docker images | awk '{print $3}')
docker volume rm $(docker volume ls | awk '{print $2}')
echo "rebuild image" 
docker build -t cc-registry:test -f Dockerfile .
echo "Running cc-registry container"
docker run --name cc-registry -p 8081:8081 -d cc-registry:test

