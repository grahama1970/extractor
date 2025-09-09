import { Link } from "react-router-dom";
import { FileText, Layout, Grid3X3, Layers } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const Index = () => {
  const prototypes = [
    {
      id: 1,
      title: "Classic Three-Panel",
      description: "Traditional layout with dedicated panels for exploration, annotation, and inspection. Perfect for detailed document analysis workflows.",
      icon: Layout,
      route: "/classic",
      features: ["Three-panel layout", "Contextual toolbars", "Advanced navigation", "Detailed inspector"]
    },
    {
      id: 2,
      title: "Tabbed Interface",
      description: "Modern tabbed design with floating annotation tools and collapsible sidebars for maximum document viewing space.",
      icon: Layers,
      route: "/tabbed",
      features: ["Floating toolbars", "Tabbed sidebars", "Compact design", "Focus mode"]
    },
    {
      id: 3,
      title: "Dashboard Cards",
      description: "Card-based modular interface with drag-and-drop functionality and visual project management approach.",
      icon: Grid3X3,
      route: "/dashboard",
      features: ["Modular cards", "Drag & drop", "Visual workflow", "Project-focused"]
    }
  ];

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b bg-card">
        <div className="container mx-auto px-6 py-8">
          <div className="flex items-center gap-3 mb-4">
            <FileText className="h-8 w-8 text-primary" />
            <h1 className="text-3xl font-bold text-foreground">PDF Annotation System</h1>
          </div>
          <p className="text-lg text-muted-foreground max-w-2xl">
            Explore three different prototype variations for document annotation workflows. Each design offers unique approaches to PDF annotation and document management.
          </p>
        </div>
      </header>

      <main className="container mx-auto px-6 py-12">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {prototypes.map((prototype) => {
            const IconComponent = prototype.icon;
            return (
              <Card key={prototype.id} className="group hover:shadow-lg transition-all duration-300 border-2 hover:border-primary/20">
                <CardHeader className="text-center pb-4">
                  <div className="mx-auto mb-4 p-3 bg-primary/10 rounded-full w-fit group-hover:bg-primary/20 transition-colors">
                    <IconComponent className="h-8 w-8 text-primary" />
                  </div>
                  <CardTitle className="text-xl">{prototype.title}</CardTitle>
                  <CardDescription className="text-sm leading-relaxed">
                    {prototype.description}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                    <h4 className="font-medium text-sm text-muted-foreground">Key Features:</h4>
                    <ul className="space-y-1">
                      {prototype.features.map((feature, index) => (
                        <li key={index} className="text-sm flex items-center gap-2">
                          <div className="w-1.5 h-1.5 bg-primary rounded-full" />
                          {feature}
                        </li>
                      ))}
                    </ul>
                  </div>
                  <Link to={prototype.route} className="block pt-4">
                    <Button className="w-full group-hover:shadow-md transition-all">
                      View Prototype
                    </Button>
                  </Link>
                </CardContent>
              </Card>
            );
          })}
        </div>

        <div className="mt-16 text-center">
          <h2 className="text-2xl font-bold mb-4">About These Prototypes</h2>
          <p className="text-muted-foreground max-w-3xl mx-auto leading-relaxed">
            Each prototype demonstrates different approaches to PDF annotation interfaces, from traditional three-panel layouts to modern card-based designs. 
            They maintain core functionality while exploring various UX patterns and workflows suitable for different user preferences and use cases.
          </p>
        </div>
      </main>
    </div>
  );
};

export default Index;