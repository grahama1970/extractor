import * as React from "react";
import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Archive, Download, Play, Sparkles, Upload } from "lucide-react";

type Props = {
  onLoadPipeline?: () => void;
  onSave?: () => void;
  onUpsert?: () => void;
  onExportCoco?: () => void;
  onSuggestTables?: () => void;
  onRunPipeline?: () => void;
};

export function ActionsMenu({
  onLoadPipeline,
  onSave,
  onUpsert,
  onExportCoco,
  onSuggestTables,
  onRunPipeline,
}: Props) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button size="sm" variant="outline" aria-label="Actions">Actions</Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-52">
        <DropdownMenuItem onClick={onSave}><Archive className="h-4 w-4 mr-2" />Save annotations</DropdownMenuItem>
        <DropdownMenuItem onClick={onLoadPipeline}><Download className="h-4 w-4 mr-2" />Load pipeline annotations</DropdownMenuItem>
        <DropdownMenuItem onClick={onUpsert}><Upload className="h-4 w-4 mr-2" />Upsert to Arango</DropdownMenuItem>
        <DropdownMenuItem onClick={onExportCoco}><Download className="h-4 w-4 mr-2" />Export COCO</DropdownMenuItem>
        <DropdownMenuItem onClick={onSuggestTables}><Sparkles className="h-4 w-4 mr-2" />Suggest Tables</DropdownMenuItem>
        <DropdownMenuItem onClick={onRunPipeline}><Play className="h-4 w-4 mr-2" />Run Pipeline</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
