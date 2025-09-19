import { useEffect, useState } from "react";
import { 
  Upload, Copy, Trash2, Plus, ArrowLeft, FileText, Tag, 
  ChevronLeft, ChevronRight, Play, Pause, RotateCcw, 
  Check, X, Zap, Target, Archive, Download
} from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const DashboardLayout = () => {
  const [activeDocuments, setActiveDocuments] = useState([
    { id: 1, name: "Research Paper 2024", currentPage: 5, totalPages: 45, annotations: 12, isActive: true },
    { id: 2, name: "Tech Specification", currentPage: 23, totalPages: 89, annotations: 34, isActive: true },
    { id: 3, name: "User Manual Draft", currentPage: 67, totalPages: 120, annotations: 45, isActive: false }
  ]);
  const [selectedTool, setSelectedTool] = useState("section");
  const [batchMode, setBatchMode] = useState(false);
  const [rapidMode, setRapidMode] = useState(false);

  const annotationTools = [
    { id: "section", name: "Section", color: "annotation-section", shortcut: "S" },
    { id: "table", name: "Table", color: "annotation-table", shortcut: "T" },
    { id: "figure", name: "Figure", color: "annotation-figure", shortcut: "F" },
    { id: "text", name: "Text", color: "annotation-text", shortcut: "P" }
  ];

  const toggleDocumentActive = (docId: number) => {
    setActiveDocuments(docs => docs.map(doc => 
      doc.id === docId ? { ...doc, isActive: !doc.isActive } : doc
    ));
  };

  const navigatePage = (docId: number, direction: 'prev' | 'next') => {
    setActiveDocuments(docs => docs.map(doc => {
      if (doc.id === docId) {
        const newPage = direction === 'next' 
          ? Math.min(doc.currentPage + 1, doc.totalPages)
          : Math.max(doc.currentPage - 1, 1);
        return { ...doc, currentPage: newPage };
      }
      return doc;
    }));
  };

  const [appReady, setAppReady] = useState(false);
  useEffect(() => { setAppReady(true); }, []);

  return (
    <div className="h-screen bg-background overflow-hidden">
      {/* Header */}
      <header className="h-16 border-b bg-card flex items-center px-6" data-testid="top-toolbar">
        <Link to="/" className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors">
          <ArrowLeft className="h-4 w-4" />
          Back to Prototypes
        </Link>
        <div className="flex-1 text-center">
          <h1 className="text-lg font-semibold">Multi-Document Rapid Annotation</h1>
        </div>
        <div className="flex gap-2" data-testid="pipeline-actions">
          <Button
            variant={rapidMode ? "default" : "outline"}
            size="sm"
            onClick={() => setRapidMode(!rapidMode)}
          >
            <Zap className="mr-2 h-4 w-4" />
            Rapid Mode
          </Button>
          <Button
            variant={batchMode ? "default" : "outline"}
            size="sm"
            onClick={() => setBatchMode(!batchMode)}
          >
            <Target className="mr-2 h-4 w-4" />
            Batch Mode
          </Button>
          {/* Unified selectors for Happy Path; no-ops here */}
          <Button size="sm" variant="outline" title="Load pipeline annotations" data-testid="btn-load-pipeline-annos" disabled>
            <Download className="h-4 w-4" />
          </Button>
          <Button size="sm" variant="outline" title="Save annotations" data-testid="btn-save-annotations" disabled>
            <Archive className="h-4 w-4" />
          </Button>
          <Button size="sm" variant="outline" title="Upsert to Arango" data-testid="btn-upsert-pipeline" disabled>
            <Upload className="h-4 w-4" />
          </Button>
        </div>
      </header>

      <div className="flex h-[calc(100vh-4rem)]">
        {appReady && <div data-testid="app-ready" className="hidden" aria-hidden />}
        {/* Quick Tools Sidebar */}
        <div className="w-64 border-r bg-card p-4 flex flex-col">
          <div className="mb-6">
            <h3 className="font-semibold mb-4">Annotation Tools</h3>
            <div className="space-y-2">
              {annotationTools.map((tool) => (
                <Button
                  key={tool.id}
                  variant={selectedTool === tool.id ? "default" : "outline"}
                  className="w-full justify-start"
                  onClick={() => setSelectedTool(tool.id)}
                >
                  <Tag className={`mr-2 h-4 w-4 text-${tool.color}`} />
                  {tool.name}
                  <Badge variant="secondary" className="ml-auto text-xs">
                    {tool.shortcut}
                  </Badge>
                </Button>
              ))}
            </div>
          </div>

          <div className="mb-6">
            <h3 className="font-semibold mb-4">Quick Actions</h3>
            <div className="space-y-2">
              <Button variant="outline" className="w-full justify-start" size="sm">
                <Copy className="mr-2 h-4 w-4" />
                Copy Last
              </Button>
              <Button variant="outline" className="w-full justify-start" size="sm">
                <RotateCcw className="mr-2 h-4 w-4" />
                Undo
              </Button>
              <Button variant="outline" className="w-full justify-start" size="sm">
                <Trash2 className="mr-2 h-4 w-4" />
                Delete
              </Button>
            </div>
          </div>

          <div className="mt-auto">
            <Button className="w-full" variant="outline">
              <Upload className="mr-2 h-4 w-4" />
              Load More PDFs
            </Button>
          </div>
        </div>

        {/* Multi-Document Workspace */}
        <div className="flex-1 p-4 overflow-y-auto">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold">Active Documents</h2>
            <div className="text-sm text-muted-foreground">
              {activeDocuments.filter(doc => doc.isActive).length} documents active
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
            {activeDocuments.map((doc) => (
              <Card 
                key={doc.id} 
                className={`transition-all ${
                  doc.isActive 
                    ? "ring-2 ring-primary shadow-lg" 
                    : "opacity-60 hover:opacity-80"
                }`}
              >
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-sm font-medium truncate">
                      {doc.name}
                    </CardTitle>
                    <div className="flex gap-1">
                      <Button
                        size="sm"
                        variant={doc.isActive ? "default" : "outline"}
                        onClick={() => toggleDocumentActive(doc.id)}
                      >
                        {doc.isActive ? <Pause className="h-3 w-3" /> : <Play className="h-3 w-3" />}
                      </Button>
                    </div>
                  </div>
                  <div className="text-xs text-muted-foreground">
                    Page {doc.currentPage} of {doc.totalPages} • {doc.annotations} annotations
                  </div>
                </CardHeader>

                <CardContent className="space-y-4">
                  {/* PDF Preview Area */}
                  <div className="aspect-[3/4] bg-muted rounded border-2 border-dashed border-muted-foreground/20 relative overflow-hidden">
                    <div className="absolute inset-0 flex items-center justify-center text-xs text-muted-foreground">
                      PDF Page {doc.currentPage}
                    </div>
                    
                    {/* Sample annotation overlays for active documents */}
                    {doc.isActive && (
                      <>
                        <div className="absolute top-[15%] left-[10%] w-[80%] h-[12%] border-2 border-dashed border-annotation-section cursor-crosshair hover:bg-annotation-section/10 transition-colors">
                          <div className="absolute -top-5 left-0 px-1 py-0.5 text-xs font-medium text-white bg-annotation-section rounded text-[10px]">
                            Section
                          </div>
                        </div>
                        
                        <div className="absolute top-[35%] left-[15%] w-[70%] h-[30%] border-2 border-dashed border-annotation-table cursor-crosshair hover:bg-annotation-table/10 transition-colors">
                          <div className="absolute -top-5 left-0 px-1 py-0.5 text-xs font-medium text-white bg-annotation-table rounded text-[10px]">
                            Table
                          </div>
                        </div>
                      </>
                    )}
                  </div>

                  {/* Quick Navigation */}
                  <div className="flex items-center justify-between">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => navigatePage(doc.id, 'prev')}
                      disabled={doc.currentPage === 1}
                    >
                      <ChevronLeft className="h-3 w-3" />
                    </Button>
                    
                    <div className="flex-1 mx-3">
                      <Input
                        type="number"
                        value={doc.currentPage}
                        min={1}
                        max={doc.totalPages}
                        className="text-center h-8 text-sm"
                        onChange={(e) => {
                          const page = Math.max(1, Math.min(Number(e.target.value), doc.totalPages));
                          setActiveDocuments(docs => docs.map(d => 
                            d.id === doc.id ? { ...d, currentPage: page } : d
                          ));
                        }}
                      />
                    </div>
                    
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => navigatePage(doc.id, 'next')}
                      disabled={doc.currentPage === doc.totalPages}
                    >
                      <ChevronRight className="h-3 w-3" />
                    </Button>
                  </div>

                  {/* Quick Annotation Buttons */}
                  {doc.isActive && (
                    <div className="grid grid-cols-2 gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        className="text-xs"
                        onClick={() => {/* Add section annotation */}}
                      >
                        <Check className="mr-1 h-3 w-3 text-annotation-section" />
                        Section
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        className="text-xs"
                        onClick={() => {/* Add table annotation */}}
                      >
                        <Check className="mr-1 h-3 w-3 text-annotation-table" />
                        Table
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>
            ))}

            {/* Add New Document Card */}
            <Card className="border-dashed border-2 border-muted-foreground/30 hover:border-primary/50 transition-colors cursor-pointer">
              <CardContent className="flex items-center justify-center h-full min-h-[300px]">
                <div className="text-center">
                  <Plus className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
                  <p className="text-sm text-muted-foreground">Add PDF Document</p>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Batch Processing Tools */}
          {batchMode && (
            <Card className="mt-6 border-primary/20">
              <CardHeader>
                <CardTitle className="text-base">Batch Processing</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-4">
                  <Button>Apply to All Active</Button>
                  <Button variant="outline">Next Unannnotated</Button>
                  <Button variant="outline">Auto-detect Tables</Button>
                  <div className="ml-auto text-sm text-muted-foreground">
                    Processing {activeDocuments.filter(doc => doc.isActive).length} documents
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
};

export default DashboardLayout;
