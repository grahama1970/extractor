#!/bin/bash
# Management script for Label Studio Docker containers
# Usage: ./manage.sh [start|stop|restart|status|logs]

set -e

# Configuration
COMPOSE_FILE="docker-compose.yml"
ENV_FILE=".env"

# Check for .env file
if [ ! -f "$ENV_FILE" ]; then
    echo "No .env file found. Creating from template..."
    cp .env.example "$ENV_FILE"
    echo "Please edit $ENV_FILE with your configuration"
fi

# Function to check Docker status
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        echo "Error: Docker is not running or not accessible"
        exit 1
    fi
}

# Function to check if containers are running
check_running() {
    if [ -z "$(docker-compose ps -q)" ]; then
        echo "Label Studio containers are not running"
        return 1
    else
        echo "Label Studio containers are running"
        return 0
    fi
}

# Start containers
start() {
    echo "Starting Label Studio containers..."
    docker-compose up -d
    echo "Waiting for containers to initialize..."
    sleep 5
    docker-compose ps
    
    # Check if Label Studio is accessible
    echo "Checking if Label Studio is accessible..."
    MAX_RETRIES=10
    RETRY_COUNT=0
    
    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        if curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/api/health | grep -q "200"; then
            echo "Label Studio is accessible!"
            break
        else
            RETRY_COUNT=$((RETRY_COUNT+1))
            if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
                echo "Label Studio not yet accessible, retrying in 5 seconds..."
                sleep 5
            else
                echo "Label Studio not accessible after $MAX_RETRIES attempts."
                echo "Check logs with: ./manage.sh logs"
            fi
        fi
    done
    
    echo "Label Studio URL: http://localhost:8080"
}

# Stop containers
stop() {
    echo "Stopping Label Studio containers..."
    docker-compose down
}

# Restart containers
restart() {
    echo "Restarting Label Studio containers..."
    docker-compose restart
}

# Check status
status() {
    echo "Label Studio container status:"
    docker-compose ps
}

# Show logs
logs() {
    if [ -z "$2" ]; then
        echo "Showing logs for all containers:"
        docker-compose logs --tail=50
    else
        echo "Showing logs for $2:"
        docker-compose logs --tail=50 "$2"
    fi
}

# Initialize Label Studio
init() {
    echo "Initializing Label Studio..."
    
    # Wait for Label Studio to be ready
    MAX_RETRIES=10
    RETRY_COUNT=0
    
    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        if curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/api/health | grep -q "200"; then
            echo "Label Studio is accessible, proceeding with initialization..."
            break
        else
            RETRY_COUNT=$((RETRY_COUNT+1))
            if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
                echo "Label Studio not yet accessible, retrying in 5 seconds..."
                sleep 5
            else
                echo "Label Studio not accessible after $MAX_RETRIES attempts."
                echo "Check logs with: ./manage.sh logs"
                exit 1
            fi
        fi
    done
    
    # Run the test setup script
    echo "Running test setup script..."
    python test_setup.py
}

# Clean up all data (destructive!)
clean() {
    echo "WARNING: This will remove all Label Studio data and containers."
    read -p "Are you sure you want to continue? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Stopping and removing containers..."
        docker-compose down
        
        echo "Removing volumes..."
        docker volume rm $(docker volume ls -q | grep "label-studio") 2>/dev/null || true
        docker volume rm $(docker volume ls -q | grep "pgdata") 2>/dev/null || true
        docker volume rm $(docker volume ls -q | grep "redisdata") 2>/dev/null || true
        
        echo "Cleanup complete."
    else
        echo "Cleanup aborted."
    fi
}

# Check Docker is running
check_docker

# Execute based on command
case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    status)
        status
        ;;
    logs)
        logs "$@"
        ;;
    init)
        init
        ;;
    clean)
        clean
        ;;
    *)
        echo "Usage: $0 [start|stop|restart|status|logs|init|clean]"
        echo "  start  - Start Label Studio containers"
        echo "  stop   - Stop Label Studio containers"
        echo "  restart - Restart Label Studio containers"
        echo "  status - Show container status"
        echo "  logs [container] - Show logs (optionally for a specific container)"
        echo "  init   - Initialize Label Studio (runs test script)"
        echo "  clean  - Remove all containers and data (destructive!)"
        exit 1
esac

exit 0