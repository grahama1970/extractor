import { useState } from "react";
import { 
  Upload, Search, Archive, Copy, Trash2, Plus, Minus,
  ChevronLeft, ChevronRight, Edit, Sparkles, ArrowLeft,
  File, Tag, MessageSquare, Settings
} from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const TabbedLayout = () => {
  const [currentPage, setCurrentPage] = useState(345);
  const [leftSidebarOpen, setLeftSidebarOpen] = useState(true);
  const [rightSidebarOpen, setRightSidebarOpen] = useState(true);
  const [selectedAnnotation, setSelectedAnnotation] = useState("section");

  const pdfFiles = [
    { name: "Research Paper 2024", pages: 45, status: "complete" },
    { name: "Technical Specification", pages: 89, status: "pending" },
    { name: "User Manual Draft", pages: 120, status: "complete" }
  ];

  return (
    <div className="h-screen bg-background overflow-hidden">
      {/* Header */}
      <header className="h-16 border-b bg-card flex items-center px-6">
        <Link to="/" className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors">
          <ArrowLeft className="h-4 w-4" />
          Back to Prototypes
        </Link>
        <div className="flex-1 text-center">
          <h1 className="text-lg font-semibold">Tabbed Interface with Floating Tools</h1>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setLeftSidebarOpen(!leftSidebarOpen)}
          >
            {leftSidebarOpen ? <Minus className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
            Files
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setRightSidebarOpen(!rightSidebarOpen)}
          >
            Properties
            {rightSidebarOpen ? <Minus className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
          </Button>
        </div>
      </header>

      <div className="flex h-[calc(100vh-4rem)]">
        {/* Left Sidebar */}
        {leftSidebarOpen && (
          <div className="w-72 border-r bg-card">
            <Tabs defaultValue="files" className="h-full flex flex-col">
              <TabsList className="grid w-full grid-cols-2 m-4 mb-0">
                <TabsTrigger value="files" className="flex items-center gap-2">
                  <File className="h-4 w-4" />
                  Files
                </TabsTrigger>
                <TabsTrigger value="search" className="flex items-center gap-2">
                  <Search className="h-4 w-4" />
                  Search
                </TabsTrigger>
              </TabsList>
              
              <TabsContent value="files" className="flex-1 p-4 pt-6 space-y-4">
                <Button className="w-full">
                  <Upload className="mr-2 h-4 w-4" />
                  Load PDF
                </Button>
                
                <div className="space-y-2">
                  {pdfFiles.map((file, index) => (
                    <Card
                      key={index}
                      className="group h-12 px-3 rounded-xl flex items-center justify-between text-left transition-colors hover:bg-muted cursor-pointer"
                      role="button"
                      aria-label={`Open ${file.name}`}
                    >
                      <div className="min-w-0">
                        <div className="font-medium text-sm truncate">{file.name}</div>
                        <div className="text-xs text-muted-foreground truncate">
                          {file.pages} pages | <span className={`text-status-${file.status}`}>{file.status}</span>
                        </div>
                      </div>
                      <Button variant="ghost" size="icon" className="opacity-0 group-hover:opacity-100 transition-opacity" aria-label="Archive">
                        <Archive className="h-4 w-4" />
                      </Button>
                    </Card>
                  ))}
                </div>
              </TabsContent>
              
              <TabsContent value="search" className="flex-1 p-4 pt-6 space-y-4">
                <Input placeholder="Search in documents..." />
                <div className="text-sm text-muted-foreground">
                  Advanced search functionality would be implemented here.
                </div>
              </TabsContent>
            </Tabs>
          </div>
        )}

        {/* Main Content Area */}
        <div className="flex-1 relative">
          {/* Floating Annotation Toolbar */}
          <div className="absolute top-4 left-4 z-10 bg-card rounded-lg shadow-lg p-2 flex gap-2">
            <Button size="sm" variant="outline" title="Section Annotation">
              <Tag className="h-4 w-4 text-annotation-section" />
            </Button>
            <Button size="sm" variant="outline" title="Table Annotation">
              <Tag className="h-4 w-4 text-annotation-table" />
            </Button>
            <Button size="sm" variant="outline" title="Figure Annotation">
              <Tag className="h-4 w-4 text-annotation-figure" />
            </Button>
            <div className="border-l mx-1" />
            <Button size="sm" variant="outline" title="Copy">
              <Copy className="h-4 w-4" />
            </Button>
            <Button size="sm" variant="outline" title="Delete">
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>

          {/* PDF Viewer */}
          <div className="h-full bg-muted flex items-center justify-center relative">
            <div className="text-muted-foreground font-medium">
              Rendered PDF Page {currentPage}
            </div>
            
            {/* Annotation overlays */}
            <div className="absolute top-[15%] left-[10%] w-[60%] h-[15%] border-2 border-dashed border-annotation-section cursor-pointer hover:bg-annotation-section/10 transition-colors">
              <div className="absolute -top-6 left-0 px-2 py-1 text-xs font-medium text-white bg-annotation-section rounded">
                Section
              </div>
            </div>
            
            <div className="absolute top-[40%] left-[15%] w-[50%] h-[35%] border-2 border-dashed border-annotation-table cursor-pointer hover:bg-annotation-table/10 transition-colors">
              <div className="absolute -top-6 left-0 px-2 py-1 text-xs font-medium text-white bg-annotation-table rounded">
                Table
              </div>
            </div>
          </div>

          {/* Bottom Navigation Bar */}
          <div className="absolute bottom-0 left-0 right-0 bg-card border-t p-4">
            <div className="flex items-center justify-center gap-4">
              <Button size="sm" variant="outline">
                <ChevronLeft className="h-4 w-4" />
              </Button>
              
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">Page</span>
                <Input
                  type="number"
                  value={currentPage}
                  onChange={(e) => setCurrentPage(Number(e.target.value))}
                  className="w-20 text-center"
                />
                <span className="text-sm text-muted-foreground">of 1000</span>
              </div>
              
              <input
                type="range"
                min="1"
                max="1000"
                value={currentPage}
                onChange={(e) => setCurrentPage(Number(e.target.value))}
                className="flex-1 max-w-xs"
              />
              
              <Button size="sm" variant="outline">
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>

        {/* Right Sidebar */}
        {rightSidebarOpen && (
          <div className="w-80 border-l bg-card">
            <Tabs defaultValue="properties" className="h-full flex flex-col">
              <TabsList className="grid w-full grid-cols-3 m-4 mb-0">
                <TabsTrigger value="properties" className="flex items-center gap-1">
                  <Settings className="h-3 w-3" />
                  Props
                </TabsTrigger>
                <TabsTrigger value="annotations" className="flex items-center gap-1">
                  <Tag className="h-3 w-3" />
                  Tags
                </TabsTrigger>
                <TabsTrigger value="notes" className="flex items-center gap-1">
                  <MessageSquare className="h-3 w-3" />
                  Notes
                </TabsTrigger>
              </TabsList>
              
              <TabsContent value="properties" className="flex-1 p-4 pt-6 space-y-4">
                <div>
                  <label className="text-sm font-medium mb-2 block">Label Type</label>
                  <Input defaultValue="Section" />
                </div>
                
                <div>
                  <label className="text-sm font-medium mb-2 block">Instance ID</label>
                  <Input defaultValue="sec-001" />
                </div>
                
                <div>
                  <label className="text-sm font-medium mb-2 block">Confidence</label>
                  <Input type="number" defaultValue="95" min="0" max="100" />
                </div>
                
                <Button variant="outline" className="w-full">
                  <Sparkles className="mr-2 h-4 w-4" />
                  Generate JSON
                </Button>
              </TabsContent>
              
              <TabsContent value="annotations" className="flex-1 p-4 pt-6 space-y-4">
                <div className="space-y-2">
                  <div className="flex items-center gap-2 p-2 rounded border">
                    <div className="w-3 h-3 bg-annotation-section rounded-full"></div>
                    <span className="text-sm">Section Header</span>
                  </div>
                  <div className="flex items-center gap-2 p-2 rounded border">
                    <div className="w-3 h-3 bg-annotation-table rounded-full"></div>
                    <span className="text-sm">Data Table</span>
                  </div>
                </div>
              </TabsContent>
              
              <TabsContent value="notes" className="flex-1 p-4 pt-6">
                <Textarea
                  className="h-full min-h-[200px] resize-none"
                  placeholder="Add your notes here..."
                />
              </TabsContent>
            </Tabs>
          </div>
        )}
      </div>
    </div>
  );
};

export default TabbedLayout;
