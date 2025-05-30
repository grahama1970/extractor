# Marker Ground Truth - PDF Annotation Companion Tool

## Executive Summary

A standalone companion tool for creating ground truth annotations for PDF documents, enabling users to label tables, equations, text, and other elements with expected extraction outputs.

## Architecture Decision: Separate Project

### Why Separate?

1. **Clean Separation of Concerns**
   - Marker: PDF extraction and processing
   - Ground Truth: Annotation and validation
   
2. **Independent Development**
   - Can evolve without affecting core marker functionality
   - Different dependencies (UI frameworks, annotation tools)
   
3. **Reusability**
   - Can be used with other PDF extraction tools
   - Exportable annotation format

4. **Deployment Flexibility**
   - Can be deployed as web app, desktop app, or both
   - No need to bundle UI dependencies with marker

## Project Structure

```
marker-ground-truth/
├── backend/
│   ├── api/
│   │   ├── __init__.py
│   │   ├── annotations.py      # CRUD for annotations
│   │   ├── documents.py        # PDF upload/management
│   │   ├── export.py           # Export to various formats
│   │   └── validation.py       # Compare extractions
│   ├── models/
│   │   ├── annotation.py       # Annotation data model
│   │   ├── document.py         # Document metadata
│   │   └── region.py           # Region types and schemas
│   ├── storage/
│   │   ├── database.py         # SQLite/PostgreSQL
│   │   └── files.py            # PDF and image storage
│   └── services/
│       ├── pdf_renderer.py     # Convert PDF to images
│       ├── marker_client.py    # Interface with marker
│       └── export_service.py   # Export annotations
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── PDFViewer.tsx         # PDF page display
│   │   │   ├── AnnotationCanvas.tsx   # Drawing interface
│   │   │   ├── RegionEditor.tsx       # Edit region properties
│   │   │   └── OutputEditor.tsx       # Expected output editor
│   │   ├── hooks/
│   │   │   ├── useAnnotations.ts
│   │   │   └── usePDFNavigation.ts
│   │   └── types/
│   │       └── annotations.ts
│   └── public/
├── shared/
│   └── schemas/
│       ├── annotation_format.json
│       └── region_types.json
└── integration/
    ├── marker_plugin.py        # Marker integration
    └── export_formats/
        ├── coco.py
        ├── yolo.py
        └── marker_native.py
```

## Core Features

### 1. PDF Viewer with Annotation

```typescript
interface PDFAnnotator {
  // Load PDF and render as images
  loadPDF(file: File): Promise<void>;
  
  // Navigation
  currentPage: number;
  totalPages: number;
  goToPage(page: number): void;
  
  // Annotation tools
  currentTool: 'select' | 'table' | 'text' | 'equation' | 'image';
  drawRegion(type: RegionType, bounds: Rectangle): Region;
  
  // Region management
  regions: Region[];
  selectedRegion: Region | null;
  updateRegion(id: string, updates: Partial<Region>): void;
  deleteRegion(id: string): void;
}
```

### 2. Region Types and Schemas

```python
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel

class RegionType(Enum):
    TABLE = "table"
    TEXT = "text"
    EQUATION = "equation"
    IMAGE = "image"
    CODE = "code"
    HEADING = "heading"
    LIST = "list"
    FOOTNOTE = "footnote"

class Rectangle(BaseModel):
    x: float
    y: float
    width: float
    height: float
    page: int

class Region(BaseModel):
    id: str
    type: RegionType
    bounds: Rectangle
    description: Optional[str]
    expected_output: Dict[str, Any]
    metadata: Dict[str, Any] = {}
    confidence_required: float = 0.9
    
class TableRegion(Region):
    type: RegionType = RegionType.TABLE
    expected_output: Dict[str, Any] = {
        "format": "pandas_json",
        "data": [],
        "columns": [],
        "index": []
    }
    metadata: Dict[str, Any] = {
        "has_headers": True,
        "merged_cells": [],
        "complex_structure": False
    }

class EquationRegion(Region):
    type: RegionType = RegionType.EQUATION
    expected_output: Dict[str, Any] = {
        "format": "latex",
        "content": "",
        "display_mode": False
    }
```

### 3. Annotation Interface

```python
class AnnotationInterface:
    """Core annotation functionality."""
    
    def create_annotation_session(self, pdf_path: str) -> str:
        """Start new annotation session."""
        # Convert PDF pages to images
        images = self.pdf_to_images(pdf_path)
        
        # Create session
        session = AnnotationSession(
            pdf_path=pdf_path,
            page_images=images,
            created_at=datetime.now()
        )
        
        return session.id
    
    def add_region(self, session_id: str, region: Region) -> Region:
        """Add annotated region."""
        # Validate region bounds
        self.validate_region_bounds(region)
        
        # Store region
        region.id = str(uuid.uuid4())
        self.storage.save_region(session_id, region)
        
        return region
    
    def update_expected_output(self, region_id: str, 
                             expected_output: Dict[str, Any]) -> None:
        """Update expected extraction output."""
        region = self.storage.get_region(region_id)
        
        # Validate output format
        self.validate_output_format(region.type, expected_output)
        
        region.expected_output = expected_output
        self.storage.update_region(region)
```

### 4. Quick Annotation Workflow

```python
class QuickAnnotator:
    """Streamlined annotation for common patterns."""
    
    def auto_detect_regions(self, page_image: np.ndarray) -> List[Region]:
        """Use marker to suggest regions."""
        # Run marker's layout detection
        layout = self.marker.detect_layout(page_image)
        
        # Convert to annotation regions
        suggestions = []
        for block in layout.blocks:
            region = self.block_to_region(block)
            suggestions.append(region)
            
        return suggestions
    
    def apply_template(self, region_type: RegionType) -> Dict[str, Any]:
        """Get template expected output."""
        templates = {
            RegionType.TABLE: {
                "format": "pandas_json",
                "data": [["cell1", "cell2"], ["cell3", "cell4"]],
                "columns": ["Column 1", "Column 2"],
                "index": [0, 1]
            },
            RegionType.EQUATION: {
                "format": "latex",
                "content": "E = mc^2",
                "display_mode": True
            },
            RegionType.TEXT: {
                "format": "plain_text",
                "content": "Sample text content"
            }
        }
        return templates.get(region_type, {})
```

### 5. Export and Validation

```python
class GroundTruthExporter:
    """Export annotations in various formats."""
    
    def export_marker_format(self, session: AnnotationSession) -> Dict:
        """Export in marker-native format."""
        return {
            "version": "1.0",
            "document": session.pdf_path,
            "pages": [
                {
                    "page_num": page_num,
                    "regions": [
                        region.dict() for region in regions
                    ]
                }
                for page_num, regions in session.regions_by_page.items()
            ],
            "metadata": {
                "created_at": session.created_at,
                "annotator": session.annotator_id,
                "total_regions": len(session.all_regions)
            }
        }
    
    def export_for_training(self, sessions: List[AnnotationSession]) -> None:
        """Export for model training."""
        training_data = []
        
        for session in sessions:
            for region in session.all_regions:
                training_data.append({
                    "image": self.crop_region(session, region),
                    "type": region.type,
                    "expected_output": region.expected_output,
                    "metadata": region.metadata
                })
        
        # Save in format suitable for fine-tuning
        self.save_training_data(training_data)

class ValidationService:
    """Compare marker output with ground truth."""
    
    def validate_extraction(self, 
                          ground_truth: Region,
                          extracted: Dict[str, Any]) -> ValidationResult:
        """Compare extracted output with expected."""
        if ground_truth.type == RegionType.TABLE:
            return self.validate_table(ground_truth, extracted)
        elif ground_truth.type == RegionType.EQUATION:
            return self.validate_equation(ground_truth, extracted)
        # ... other types
    
    def validate_table(self, truth: TableRegion, 
                      extracted: Dict) -> ValidationResult:
        """Detailed table validation."""
        expected_df = pd.DataFrame(truth.expected_output["data"],
                                 columns=truth.expected_output["columns"])
        
        try:
            extracted_df = pd.DataFrame(extracted["data"],
                                      columns=extracted["columns"])
            
            # Compare structure
            structure_match = (expected_df.shape == extracted_df.shape)
            
            # Compare content
            content_match = expected_df.equals(extracted_df)
            
            # Calculate similarity metrics
            if not content_match:
                similarity = self.calculate_table_similarity(
                    expected_df, extracted_df
                )
            else:
                similarity = 1.0
                
            return ValidationResult(
                matches=content_match,
                similarity=similarity,
                structure_correct=structure_match,
                details=self.get_differences(expected_df, extracted_df)
            )
            
        except Exception as e:
            return ValidationResult(
                matches=False,
                error=str(e)
            )
```

### 6. UI Components (React/TypeScript)

```typescript
// Main annotation component
const PDFAnnotator: React.FC = () => {
  const [currentPage, setCurrentPage] = useState(1);
  const [regions, setRegions] = useState<Region[]>([]);
  const [selectedRegion, setSelectedRegion] = useState<Region | null>(null);
  const [tool, setTool] = useState<ToolType>('select');
  
  const handleDrawRegion = (bounds: Rectangle) => {
    const newRegion: Region = {
      id: generateId(),
      type: tool as RegionType,
      bounds: { ...bounds, page: currentPage },
      description: '',
      expectedOutput: getTemplateForType(tool)
    };
    
    setRegions([...regions, newRegion]);
    setSelectedRegion(newRegion);
  };
  
  return (
    <div className="pdf-annotator">
      <Toolbar 
        currentTool={tool}
        onToolChange={setTool}
      />
      
      <div className="main-content">
        <PDFPageViewer
          page={currentPage}
          onDraw={handleDrawRegion}
          regions={regions.filter(r => r.bounds.page === currentPage)}
          selectedRegion={selectedRegion}
          onSelectRegion={setSelectedRegion}
        />
        
        <RegionEditor
          region={selectedRegion}
          onUpdate={(updates) => updateRegion(selectedRegion.id, updates)}
          onDelete={() => deleteRegion(selectedRegion.id)}
        />
      </div>
      
      <PageNavigation
        current={currentPage}
        total={totalPages}
        onChange={setCurrentPage}
      />
    </div>
  );
};

// Expected output editor with JSON validation
const ExpectedOutputEditor: React.FC<{
  region: Region;
  onChange: (output: any) => void;
}> = ({ region, onChange }) => {
  const [jsonError, setJsonError] = useState<string | null>(null);
  
  const handleJsonChange = (value: string) => {
    try {
      const parsed = JSON.parse(value);
      setJsonError(null);
      onChange(parsed);
    } catch (e) {
      setJsonError(e.message);
    }
  };
  
  if (region.type === RegionType.TABLE) {
    return (
      <TableOutputEditor
        data={region.expectedOutput}
        onChange={onChange}
      />
    );
  }
  
  return (
    <JsonEditor
      value={JSON.stringify(region.expectedOutput, null, 2)}
      onChange={handleJsonChange}
      error={jsonError}
      schema={getSchemaForType(region.type)}
    />
  );
};
```

### 7. Integration with Marker

```python
class MarkerIntegration:
    """Bridge between ground truth tool and marker."""
    
    def test_extraction(self, 
                       pdf_path: str,
                       ground_truth_path: str) -> TestReport:
        """Test marker extraction against ground truth."""
        # Load ground truth
        ground_truth = self.load_ground_truth(ground_truth_path)
        
        # Run marker extraction
        marker_output = self.run_marker(pdf_path)
        
        # Match regions
        matches = self.match_regions(ground_truth.regions, 
                                   marker_output.blocks)
        
        # Validate each match
        results = []
        for gt_region, extracted_block in matches:
            result = self.validator.validate_extraction(
                gt_region, 
                extracted_block
            )
            results.append(result)
        
        return TestReport(
            total_regions=len(ground_truth.regions),
            matched=len([r for r in results if r.matches]),
            accuracy=sum(r.similarity for r in results) / len(results),
            details=results
        )
    
    def generate_test_suite(self, 
                          annotations_dir: str) -> TestSuite:
        """Generate test cases from annotations."""
        test_cases = []
        
        for annotation_file in Path(annotations_dir).glob("*.json"):
            annotation = self.load_annotation(annotation_file)
            
            test_case = TestCase(
                pdf_path=annotation.document,
                expected_regions=annotation.regions,
                metadata=annotation.metadata
            )
            test_cases.append(test_case)
        
        return TestSuite(test_cases)
```

## Deployment Options

### 1. Desktop Application (Electron + React)
```json
{
  "name": "marker-ground-truth",
  "version": "1.0.0",
  "main": "electron/main.js",
  "scripts": {
    "start": "electron .",
    "build": "electron-builder"
  }
}
```

### 2. Web Application (FastAPI + React)
```python
# Backend API
app = FastAPI(title="Marker Ground Truth API")

@app.post("/documents/upload")
async def upload_document(file: UploadFile):
    """Upload PDF for annotation."""
    pass

@app.post("/annotations")
async def create_annotation(annotation: Region):
    """Create new annotation."""
    pass

@app.get("/export/{format}")
async def export_annotations(format: str):
    """Export in specified format."""
    pass
```

### 3. Jupyter Integration
```python
# For data scientists
from marker_ground_truth import NotebookAnnotator

annotator = NotebookAnnotator()
annotator.load_pdf("document.pdf")
annotator.show_page(1)

# Draw regions interactively
region = annotator.draw_region()
region.expected_output = {
    "data": [[1, 2], [3, 4]],
    "columns": ["A", "B"]
}

# Save annotations
annotator.save("ground_truth.json")
```

## Benefits of Separate Project

1. **Focused Development**: UI/UX improvements without touching marker core
2. **Community Contribution**: Easier for others to contribute annotations
3. **Dataset Building**: Can build public datasets for PDF extraction
4. **Flexible Deployment**: Desktop, web, or notebook based on needs
5. **Tool Agnostic**: Annotations can be used with any PDF extraction tool

## Next Steps

1. **Create Repository**: `marker-ground-truth` as separate project
2. **Define Annotation Format**: Standardize the JSON schema
3. **Build MVP**: Start with basic table annotation
4. **Integrate with Marker**: Add validation commands to marker CLI
5. **Community Datasets**: Enable sharing of annotated PDFs