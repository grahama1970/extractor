')
        all_running = True
        
        for container_id in container_ids:
            if not container_id:
                continue
                
            status_result = subprocess.run(
                ["docker", "inspect", "--format", "{{.State.Status}}", container_id],
                capture_output=True,
                text=True,
                check=False
            )
            
            status = status_result.stdout.strip()
            if status != "running":
                logger.error(f"Container {container_id} status: {status}")
                all_running = False
        
        return all_running
    except Exception as e:
        logger.error(f"Error checking container status: {e}")
        return False

def check_label_studio_api() -> bool:
    """Check if Label Studio API is accessible."""
    url = os.getenv("LABEL_STUDIO_URL", "http://localhost:8080")
    
    try:
        response = requests.get(f"{url}/api/health")
        if response.status_code == 200:
            logger.info("Label Studio API is accessible")
            return True
        else:
            logger.error(f"Label Studio API health check failed: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Error accessing Label Studio API: {e}")
        return False

def check_ml_backend() -> bool:
    """Check if ML backend is accessible."""
    ml_backend_url = os.getenv("ML_BACKEND_URL", "http://localhost:9090")
    
    try:
        response = requests.get(f"{ml_backend_url}/health")
        if response.status_code == 200:
            logger.info("ML backend is accessible")
            return True
        else:
            logger.error(f"ML backend health check failed: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Error accessing ML backend: {e}")
        return False

def test_api_client() -> bool:
    """Test the Label Studio API client."""
    try:
        client = LabelStudioClient()
        if client.test_connection():
            logger.info("Label Studio API client connection successful")
            
            # Test additional API operations
            projects = client.get_projects()
            logger.info(f"Found {len(projects)} projects")
            
            return True
        else:
            logger.error("Label Studio API client connection failed")
            return False
    except Exception as e:
        logger.error(f"Error testing Label Studio API client: {e}")
        return False

def measure_api_performance() -> dict:
    """Measure API response time for common operations."""
    try:
        client = LabelStudioClient()
        metrics = {}
        
        # Measure projects endpoint
        start_time = time.time()
        client.get_projects()
        metrics["projects_ms"] = int((time.time() - start_time) * 1000)
        
        # If there are projects, measure tasks endpoint
        projects = client.get_projects()
        if projects:
            project_id = projects[0]["id"]
            
            start_time = time.time()
            client.get_tasks(project_id, limit=10)
            metrics["tasks_ms"] = int((time.time() - start_time) * 1000)
        
        logger.info(f"API performance metrics: {metrics}")
        return metrics
    except Exception as e:
        logger.error(f"Error measuring API performance: {e}")
        return {}

def main():
    """Run all tests."""
    logger.info("Starting Label Studio Docker setup tests")
    
    # Check Docker
    if not check_docker_running():
        logger.error("Docker is not running. Please start Docker and try again.")
        return
    
    # Check containers
    if not check_containers_running():
        logger.error("Label Studio containers are not running. Please start them with docker-compose up -d")
        return
    
    # Check Label Studio API
    if not check_label_studio_api():
        logger.error("Label Studio API is not accessible. Check container logs for errors.")
        logger.info("You can check logs with: docker-compose logs marker-label-studio")
        return
    
    # Check ML backend
    ml_backend_status = check_ml_backend()
    if not ml_backend_status:
        logger.warning("ML backend is not accessible. Pre-annotation may not work.")
        logger.info("You can check logs with: docker-compose logs marker-ocr-ml-backend")
    
    # Test API client
    if not test_api_client():
        logger.error("Label Studio API client tests failed.")
        return
    
    # Measure API performance
    measure_api_performance()
    
    # Overall status
    logger.info("==== Test Summary ====")
    logger.info("Docker: Running")
    logger.info("Containers: Running")
    logger.info("Label Studio API: Accessible")
    logger.info(f"ML Backend: {'Accessible' if ml_backend_status else 'Not accessible'}")
    logger.info("API Client: Working")
    logger.info("====================")
    logger.info("Label Studio Docker setup is working correctly.")
    logger.info(f"You can access Label Studio at: {os.getenv('LABEL_STUDIO_URL', 'http://localhost:8080')}")

if __name__ == "__main__":
    main()