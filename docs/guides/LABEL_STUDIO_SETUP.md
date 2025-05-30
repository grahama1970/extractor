# Label Studio Integration Guide for OCR Fine-Tuning

This guide explains how to set up Label Studio for OCR annotation and integrate it with Marker's OCR fine-tuning pipeline.

## Overview

Label Studio is an open-source data labeling tool that we use for creating high-quality OCR training data. This guide covers:

1. Setting up Label Studio with Docker
2. Configuring the OCR annotation interface
3. Connecting Marker's OCR models for pre-annotation
4. Exporting annotations for fine-tuning
5. Creating a human-in-the-loop workflow

## Prerequisites

- Docker and docker-compose installed
- Python 3.8+ with pip
- Marker repository cloned
- (Optional) GPU with CUDA support for faster OCR processing

## Installation

### Using Docker Compose (Recommended)

1. Navigate to the Docker configuration directory:

```bash
cd marker/docker/label-studio
```

2. Create an environment file from the template:

```bash
cp .env.example .env
```

3. Edit the `.env` file to configure your installation:

```bash
# Generate a secure password
nano .env
```

4. Start the Label Studio containers:

```bash
docker-compose up -d
```

5. Verify the installation:

```bash
docker-compose ps
```

The output should show the containers running:
- `marker-label-studio` - The main Label Studio application
- `marker-label-studio-postgres` - PostgreSQL database
- `marker-label-studio-redis` - Redis cache (optional)
- `marker-ocr-ml-backend` - Marker OCR pre-annotation service

### Manual Installation (Alternative)

If you prefer not to use Docker, you can install Label Studio directly:

```bash
pip install label-studio
label-studio start
```

However, this method requires manual setup of the ML backend for pre-annotation.

## Accessing Label Studio

Once installed, access Label Studio at:

```
http://localhost:8080
```

Default credentials (if you didn't change them in `.env`):
- Email: `admin@example.com`
- Password: `admin`

## Setting Up OCR Projects

### Creating a New OCR Project

1. Log in to Label Studio
2. Click "Create Project"
3. Name your project (e.g., "OCR Fine-Tuning")
4. Select "Computer Vision" under Template
5. Click "Optical Character Recognition" template
6. (Optional) Customize labels - default includes "Text", "Handwriting", and "Signature"

### Custom Labeling Configuration

For better OCR annotation, use this enhanced configuration:

```xml
<View>
  <Image name="image" value="$image"/>
  <RectangleLabels name="label" toName="image">
    <Label value="Text" background="green"/>
    <Label value="Handwriting" background="blue"/>
    <Label value="Signature" background="red"/>
    <Label value="Table" background="orange"/>
    <Label value="Diagram" background="purple"/>
  </RectangleLabels>
  <TextArea name="transcription" toName="image" editable="true" perRegion="true" 
            displayMode="region-list" required="true"/>
</View>
```

This configuration allows:
- Drawing bounding boxes around text
- Assigning text type labels
- Transcribing text content for each region

## Connecting Marker OCR Models

### Automatic Setup with Docker

If you used the provided Docker setup, the Marker OCR ML backend should be automatically configured. To verify:

1. Go to your project settings
2. Click on "Machine Learning" tab
3. You should see "Marker OCR" in the connected models

If not, manually add the ML backend:
1. Click "Add Model"
2. Enter title: "Marker OCR"
3. Enter URL: "http://marker-ocr-ml-backend:9090" (when using Docker)
4. Toggle "Use for interactive preannotations" on
5. Click "Validate and Save"

### Using Fine-Tuned Models

To use your custom fine-tuned OCR models:

1. Place your model files in `marker/docker/label-studio/models/recognition/`
2. Restart the ML backend container:

```bash
docker-compose restart marker-ocr-ml-backend
```

## Annotating OCR Tasks

### Importing Images

1. Go to your project
2. Click "Import" button
3. Choose "Upload Files" and select images
4. Click "Import"

### Using Pre-annotations

1. Select tasks you want to annotate
2. Click "Label" button
3. Toggle "Auto-Annotation" on
4. Make sure "Auto accept annotation suggestions" is checked

### Annotation Workflow

1. When you open a task, Marker OCR will automatically detect text regions and transcribe them
2. Review the bounding boxes and adjust if needed
3. Check and correct the transcribed text
4. Use shortcut keys (press "?" to see available shortcuts) to speed up annotation
5. Submit when complete

## Exporting Annotations for Fine-Tuning

### Manual Export

1. Go to your project
2. Click "Export" button
3. Select "JSON" format
4. Download the file

### Using Python SDK

For automated export, use our Python utility:

```python
from marker.finetuning.utils.label_studio import export_annotations_for_finetuning

# Export annotations to fine-tuning format
export_annotations_for_finetuning(
    project_id=123,  # Your project ID
    output_dir="data/ocr_finetuning"
)
```

## Human-in-the-Loop Workflow

For continuous model improvement:

1. **Annotate**: Create initial OCR annotations
2. **Export**: Export annotations to fine-tuning format
3. **Fine-tune**: Train OCR model on annotations
4. **Improve**: Use fine-tuned model for pre-annotations
5. **Iterate**: Continue annotating, focusing on uncertain predictions

Use our automation script for this workflow:

```bash
python marker/finetuning/utils/humanloop_ocr.py \
  --images_dir data/ocr_images \
  --output_dir models/ocr_finetuned \
  --project_name "OCR-Project" \
  --wait_for_annotations \
  --iterations 3
```

## Interactive Dashboard

For a visual interface to the entire workflow:

```bash
cd marker/finetuning/utils
streamlit run dashboard.py
```

The dashboard allows you to:
- Create and manage Label Studio projects
- Import images for annotation
- Monitor annotation progress
- Run fine-tuning with visualizations
- View model improvement metrics

## Troubleshooting

### Common Issues

1. **Connection Error to ML Backend**
   - Ensure the ML backend container is running
   - Check network connectivity between containers
   - Verify the URL is correct in ML settings

2. **Pre-annotations Not Working**
   - Check ML backend logs: `docker-compose logs marker-ocr-ml-backend`
   - Verify image format is supported (JPG, PNG, TIFF)
   - Ensure the labeling configuration matches expectation

3. **Postgres Database Connection Issues**
   - Check database logs: `docker-compose logs marker-label-studio-postgres`
   - Verify environment variables in .env file
   - Check that volumes are properly mounted

4. **Model Loading Errors**
   - Verify model path is correct
   - Check CUDA availability (if using GPU)
   - Look for model version compatibility issues

## Advanced Configuration

### Scaling for Large Projects

For larger annotation projects, consider:

1. Increase database resources:
```yaml
postgres:
  deploy:
    resources:
      limits:
        memory: 2G
```

2. Add read replicas or caching for high-throughput deployments

3. Configure Redis for improved performance:
```yaml
environment:
  - USE_REDIS_CACHE=true
```

### Security Considerations

For production environments:

1. Use HTTPS with proper certificates
2. Set up authentication with SSO or LDAP
3. Configure proper network isolation
4. Use non-root users in containers
5. Regularly backup your annotation data

## Resources

- [Label Studio Documentation](https://labelstud.io/guide/)
- [Label Studio ML Backend](https://github.com/HumanSignal/label-studio-ml-backend)
- [Marker Documentation](https://github.com/VikParuchuri/marker)
- [Annotation Best Practices](https://labelstud.io/guide/best_practices)